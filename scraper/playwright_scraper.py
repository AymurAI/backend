#!/usr/bin/env python3
"""
Playwright scraper para la sección “Gestión Documental” del Poder Judicial de la Nación.

Este script usa Playwright para capturar las cabeceras y cookies que el frontend genera
y después reproduce las llamadas al API para descargar en lote los PDFs que se enumeran
en la interfaz. Se detecta de forma dinámica el endpoint y los parámetros de paginación,
pero también puede recibir una firma manual si así se prefiere.
"""

import argparse
import asyncio
import copy
import json
import logging
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from playwright.async_api import APIRequestContext, Page, async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


PAGE_KEYWORDS = (
    "pagina",
    "page",
    "pageindex",
    "pagenumber",
    "paginaactual",
    "numeropagina",
    "offset",
)
SIZE_KEYWORDS = (
    "size",
    "pagesize",
    "tamanio",
    "cantidad",
    "limit",
    "perpage",
    "per_page",
)

MORE_BUTTON_SELECTOR = "text=/Mostrar\\s+m[aá]s/i"


def safe_filename(value: str) -> str:
    clean = unicodedata.normalize("NFC", value.strip())
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"[^\w\-\.]", "", clean)
    return clean[:120]


def detect_numeric_fields(
    container: Dict[str, Any], keywords: Iterable[str]
) -> Dict[str, int]:
    matches: Dict[str, int] = {}
    for key, value in container.items():
        lowered = key.lower()
        if any(keyword in lowered for keyword in keywords):
            try:
                matches[key] = int(value)
            except (TypeError, ValueError):
                continue
    return matches


def update_values(
    container: Dict[str, Any], keys: Iterable[str], new_value: int
) -> None:
    for key in keys:
        if key in container:
            container[key] = new_value


def strip_sensitive_headers(headers: Dict[str, str]) -> Dict[str, str]:
    blocked = {
        "content-length",
        "origin",
        "connection",
        "accept-encoding",
    }
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


def load_signature_from_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def extract_attachment_id(record: Dict[str, Any]) -> Optional[str]:
    candidates = (
        "idAdjunto",
        "adjunto",
        "idDocumento",
        "documentoAdjunto",
        "id",
        "adjuntoId",
    )
    for key in candidates:
        value = record.get(key)
        if isinstance(value, dict):
            nested = value.get("id") or value.get("codigo")
            if nested:
                return str(nested)
        elif value:
            return str(value)
    return None


def record_field(record: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        if key in record and record[key]:
            return str(record[key])
    return None


def find_listing_path(
    payload: Any, path: Tuple[str, ...] = ()
) -> Optional[Tuple[Tuple[str, ...], List[Dict[str, Any]]]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, dict) for item in value)
            ):
                if any(
                    any(
                        "id" in field.lower() or "adjunto" in field.lower()
                        for field in item.keys()
                    )
                    for item in value
                ):
                    return path + (key,), value
            child = find_listing_path(value, path + (key,))
            if child:
                return child
    elif isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            if any(
                any(
                    "id" in field.lower() or "adjunto" in field.lower()
                    for field in item.keys()
                )
                for item in payload
            ):
                return path, payload
    return None


def extract_records_by_path(
    payload: Dict[str, Any], path: Tuple[str, ...]
) -> List[Dict[str, Any]]:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return []
        current = current.get(key)
        if current is None:
            return []
    if isinstance(current, list):
        return [item for item in current if isinstance(item, dict)]
    return []


def derive_pdf_url(template: str, attachment_id: str) -> str:
    if "{id}" in template:
        return template.format(id=attachment_id)
    return template.rstrip("/") + "/" + attachment_id


@dataclass
class SearchSignature:
    method: str
    base_url: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    json_body: Optional[Dict[str, Any]]
    listing_path: Tuple[str, ...]
    example_record: Dict[str, Any]
    page_keys: Dict[str, int]
    size_keys: Dict[str, int]
    body_type: str


def build_signature_from_request(
    request,
    listing_path: Tuple[str, ...],
    example_record: Dict[str, Any],
    response_payload: Dict[str, Any],
) -> SearchSignature:
    parsed = urllib.parse.urlparse(request.url)
    base_url = urllib.parse.urlunparse(parsed._replace(query=""))
    query_params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    method = request.method
    headers = strip_sensitive_headers(dict(request.headers))
    json_body: Optional[Dict[str, Any]] = None
    post_data = request.post_data
    content_type = request.headers.get("content-type", "")
    if post_data:
        if "x-www-form-urlencoded" in content_type:
            json_body = dict(urllib.parse.parse_qsl(post_data))
        else:
            try:
                json_body = json.loads(post_data)
            except json.JSONDecodeError:
                logger.debug("No se pudo parsear cuerpo JSON de la petición inicial.")
    initial_container = {}
    initial_container.update(query_params)
    if isinstance(json_body, dict):
        initial_container.update(json_body)
    page_keys = detect_numeric_fields(initial_container, PAGE_KEYWORDS)
    size_keys = detect_numeric_fields(initial_container, SIZE_KEYWORDS)
    if not listing_path:
        found = find_listing_path(response_payload)
        if not found:
            raise RuntimeError(
                "No se pudo determinar la ruta de listado de documentos."
            )
        listing_path = found[0]
    if post_data:
        if "x-www-form-urlencoded" in content_type:
            body_type = "form"
        else:
            body_type = "json"
    else:
        body_type = "none"
    return SearchSignature(
        method=method.upper(),
        base_url=base_url,
        headers=headers,
        query_params=query_params,
        json_body=json_body,
        listing_path=listing_path,
        example_record=example_record,
        page_keys=page_keys,
        size_keys=size_keys,
        body_type=body_type,
    )


async def capture_signature(
    page: Page, args: argparse.Namespace, timeout: float = 20.0
) -> SearchSignature:
    future = asyncio.get_running_loop().create_future()

    async def inspect_response(response):
        if future.done():
            return
        if response.status != 200:
            return
        if response.request.resource_type != "xhr":
            return
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        found = find_listing_path(payload)
        if not found:
            return
        records = found[1]
        if not records:
            return
        future.set_result((response.request, found[0], records[0], payload))

    page.on(
        "response",
        lambda response: asyncio.create_task(inspect_response(response)),
    )
    await page.goto(
        "https://www.pjn.gov.ar/gestion-documental", wait_until="networkidle"
    )
    if args.simulate_ui:
        try:
            await apply_ui_filters(page, args)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Error al aplicar filtros UI: %s", exc)
    try:
        await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(
            "No se detectó automáticamente la llamada al API. Asegúrate de navegar en la página."
        )
        raise

    request, listing_path, sample_record, payload = future.result()
    signature = build_signature_from_request(
        request, listing_path, sample_record, payload
    )
    logger.info("Firma detectada: %s %s", signature.method, signature.base_url)
    logger.debug("Campos página: %s", signature.page_keys)
    logger.debug("Campos tamaño: %s", signature.size_keys)
    return signature


def load_signature(source: Dict[str, Any]) -> SearchSignature:
    signature = SearchSignature(
        method=source["method"].upper(),
        base_url=source["base_url"],
        headers=source.get("headers", {}),
        query_params=source.get("query_params", {}),
        json_body=source.get("json_body"),
        listing_path=tuple(source["listing_path"]),
        example_record=source.get("example_record", {}),
        page_keys={k: int(v) for k, v in source.get("page_keys", {}).items()},
        size_keys={k: int(v) for k, v in source.get("size_keys", {}).items()},
        body_type=source.get("body_type", "json"),
    )
    return signature


def prepare_page_payload(
    signature: SearchSignature,
    page_value: int,
    page_size: int,
) -> Tuple[Dict[str, str], Optional[Dict[str, Any]]]:
    query_params = signature.query_params.copy()
    if signature.json_body is not None:
        body_payload = copy.deepcopy(signature.json_body)
    else:
        body_payload = None
    if signature.page_keys:
        update_values(query_params, signature.page_keys.keys(), page_value)
        if body_payload is not None:
            update_values(body_payload, signature.page_keys.keys(), page_value)
    if signature.size_keys:
        update_values(query_params, signature.size_keys.keys(), page_size)
        if body_payload is not None:
            update_values(body_payload, signature.size_keys.keys(), page_size)
    return query_params, body_payload


def apply_filter_overrides(
    query_params: Dict[str, str],
    body_payload: Optional[Dict[str, Any]],
    overrides: Dict[str, str],
) -> None:
    if not overrides:
        return
    for key, value in overrides.items():
        query_params[key] = value
        if body_payload is not None:
            body_payload[key] = value


def build_filter_overrides(
    raw_filters: Iterable[str],
    dependencia: Optional[str],
    desde: Optional[str],
    hasta: Optional[str],
) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    for option in raw_filters:
        if "=" not in option:
            raise ValueError(f"Filtro inválido: {option!r}. Use clave=valor.")
        key, value = option.split("=", 1)
        overrides[key] = value
    if dependencia:
        overrides.setdefault("dependencia", dependencia)
        overrides.setdefault("dependenciaTexto", dependencia)
    if desde:
        overrides.setdefault("fechaDesde", desde)
        overrides.setdefault("desde", desde)
    if hasta:
        overrides.setdefault("fechaHasta", hasta)
        overrides.setdefault("hasta", hasta)
    return overrides


def ui_debug(args: argparse.Namespace, message: str) -> None:
    if getattr(args, "debug_ui", False):
        logger.info("[UI] %s", message)


async def expand_more_filters(page: Page, args: argparse.Namespace) -> None:
    while True:
        locator = page.locator(MORE_BUTTON_SELECTOR)
        if not await locator.count():
            break
        ui_debug(args, "Expandiendo filtros con 'Mostrar más'")
        await locator.first.click()
        await page.wait_for_timeout(250)


async def click_filter_option(page: Page, args: argparse.Namespace, text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    strategies = [
        ("role=button", page.get_by_role("button", name=text, exact=False)),
        ("role=link", page.get_by_role("link", name=text, exact=False)),
        ("text-match", page.get_by_text(text, exact=False)),
        ("button:has-text", page.locator(f'button:has-text("{text}")')),
        ("div:has-text", page.locator(f'div:has-text("{text}")')),
    ]
    ui_debug(
        args,
        f"Intentando seleccionar filtro '{text}' usando {len(strategies)} estrategias",
    )
    for description, locator in strategies:
        ui_debug(args, f"Probando estrategia '{description}' para '{text}'")
        if await locator.count():
            ui_debug(args, f"Clic en '{text}' usando '{description}'")
            await locator.first.click()
            await page.wait_for_timeout(400)
            return True
        ui_debug(args, f"No se encontró '{text}' con '{description}'")
    return False


def normalize_ui_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return value


async def apply_ui_filters(page: Page, args: argparse.Namespace) -> None:
    await expand_more_filters(page, args)
    if args.dependencia:
        clicked = await click_filter_option(page, args, args.dependencia)
        if not clicked:
            logger.warning(
                "No se encontró la dependencia %s en el filtro UI.", args.dependencia
            )
        await expand_more_filters(page, args)
    for category in getattr(args, "category_path", []):
        await expand_more_filters(page, args)
        clicked = await click_filter_option(page, args, category)
        if not clicked:
            logger.warning("No se encontró la categoría %s en el filtro UI.", category)
        await expand_more_filters(page, args)
    if args.desde:
        desde_input = page.locator("input[placeholder='Desde']")
        if await desde_input.count():
            await desde_input.fill(normalize_ui_date(args.desde))
    if args.hasta:
        hasta_input = page.locator("input[placeholder='Hasta']")
        if await hasta_input.count():
            await hasta_input.fill(normalize_ui_date(args.hasta))
    apply_button = page.locator("button:has-text('Aplicar')")
    if not await apply_button.count():
        apply_button = page.locator("button:has-text('Buscar')")
    if await apply_button.count():
        ui_debug(args, "Aplicando filtros (botón 'Aplicar'/'Buscar')")
        await apply_button.first.click()
    else:
        await page.keyboard.press("Enter")
    await page.wait_for_timeout(1500)


def extract_year(value: Optional[str]) -> str:
    if not value:
        return "sin-anio"
    match = re.search(r"(19|20)\d{2}", value)
    return match.group(0) if match else "sin-anio"


def determine_document_path(
    args: argparse.Namespace, record: Dict[str, Any], document: Dict[str, str]
) -> Path:
    dependency = (
        args.dependencia
        or document.get("dependency")
        or record_field(record, ("dependencia", "origen", "tribunal"))
        or "sin-dependencia"
    )
    category = record_field(
        record, ("rubro", "categoria", "tipo", "clasificacion", "subcategoria")
    )
    year = extract_year(document.get("date"))
    segments = [args.output_dir, safe_filename(dependency)]
    if getattr(args, "category_path", None):
        segments.extend(
            safe_filename(part) for part in args.category_path if part and part.strip()
        )
    elif category:
        segments.append(safe_filename(category))
    segments.append(year)
    return Path(*segments) / document["file_name"]


def build_document(
    record: Dict[str, Any], pdf_template: str
) -> Optional[Dict[str, str]]:
    attachment_id = extract_attachment_id(record)
    if not attachment_id:
        return None
    pdf_url = derive_pdf_url(pdf_template, attachment_id)
    document_date = record_field(record, ("fecha", "fechaDocumento", "fechaResolucion"))
    title = record_field(record, ("titulo", "descripcion", "tituloDocumento", "nombre"))
    dependency = record_field(
        record, ("dependencia", "dependenciaTexto", "origen", "tribunal")
    )
    parts = [
        document_date or "fecha-desconocida",
        title or "sin-titulo",
        dependency or "dependencia",
        attachment_id,
    ]
    name = safe_filename("_".join(part for part in parts if part))
    return {
        "attachment_id": attachment_id,
        "pdf_url": pdf_url,
        "file_name": f"{name}.pdf",
        "title": title or "",
        "date": document_date or "",
        "dependency": dependency or "",
    }


async def download_document(
    context: APIRequestContext, destination: Path, document: Dict[str, str]
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        logger.info("Salteando %s, ya existe", destination.name)
        return
    response = await context.get(
        document["pdf_url"], headers={"Referer": "https://www.pjn.gov.ar/"}
    )
    response_ok = response.ok
    if not response_ok:
        logger.warning(
            "Error al obtener %s (%s)",
            document["attachment_id"],
            response.status,
        )
        return
    content = await response.body()
    destination.write_bytes(content)
    logger.info("Descargado %s (%s)", destination.name, len(content))


async def run_scraping(
    args: argparse.Namespace,
    signature: SearchSignature,
    context_request: APIRequestContext,
) -> None:
    documents_downloaded = 0
    page_start = (
        args.page_start
        if args.page_start is not None
        else next(iter(signature.page_keys.values()), 0)
    )
    page_size = (
        args.page_size
        if args.page_size is not None
        else next(iter(signature.size_keys.values()), args.per_page)
    )
    for page_index in range(args.max_pages):
        if args.max_documents and documents_downloaded >= args.max_documents:
            logger.info("Se alcanzó el límite de documentos solicitado.")
            break
        page_value = page_start + page_index
        query_params, body_payload = prepare_page_payload(
            signature, page_value, page_size
        )
        apply_filter_overrides(query_params, body_payload, args.filter_overrides)
        if signature.method == "GET":
            response = await context_request.get(
                signature.base_url,
                params=query_params,
                headers=signature.headers,
            )
        else:
            if body_payload is not None:
                if signature.body_type == "form":
                    response = await context_request.post(
                        signature.base_url,
                        params=query_params,
                        data=body_payload,
                        headers=signature.headers,
                    )
                else:
                    response = await context_request.post(
                        signature.base_url,
                        params=query_params,
                        json=body_payload,
                        headers=signature.headers,
                    )
            else:
                response = await context_request.post(
                    signature.base_url,
                    params=query_params,
                    headers=signature.headers,
                )
        if not response.ok:
            logger.warning("Respuesta %s en página %s", response.status, page_value)
            break
        payload = await response.json()
        records = extract_records_by_path(payload, signature.listing_path)
        if not records:
            logger.info("No hay registros en la página %s", page_value)
            break
        logger.info("Procesando página %s (%d registros)", page_value, len(records))
        for record in records:
            if args.max_documents and documents_downloaded >= args.max_documents:
                break
            doc = build_document(record, args.pdf_template)
            if not doc:
                continue
            destination = determine_document_path(args, record, doc)
            await download_document(context_request, destination, doc)
            documents_downloaded += 1
        await asyncio.sleep(args.delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scraper de gestión documental usando Playwright"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("descargas"),
        help="Carpeta donde se guardan los PDFs",
    )
    parser.add_argument(
        "--pdf-template",
        default="https://pjn-documento-api.pjn.gov.ar/api/documento/adjunto/{id}",
    )
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--per-page", type=int, default=25)
    parser.add_argument(
        "-f",
        "--filter",
        action="append",
        default=[],
        help="Filtros adicionales como clave=valor (aplica a query y/o cuerpo).",
    )
    parser.add_argument(
        "--dependencia",
        help="Filtra por dependencia (ej. 'Fueros Federales' o 'Consejo de la Magistratura').",
    )
    parser.add_argument(
        "--desde",
        help="Fecha mínima de publicación en formato ISO o compatible con el backend.",
    )
    parser.add_argument(
        "--hasta",
        help="Fecha máxima de publicación en formato ISO o compatible con el backend.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Secuencia de categorías/subcategorías a seleccionar tras la dependencia.",
    )
    parser.add_argument(
        "--simulate-ui",
        action="store_true",
        help="Simula clicks/fechas en la UI antes de detectar la llamada REST.",
    )
    parser.add_argument(
        "--debug-ui",
        action="store_true",
        help="Imprime en consola cada intento de interacción con los filtros.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Retraso entre páginas para respetar al servidor",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=0,
        help="Máximo de PDFs a guardar (0 = infinito)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecutar Playwright en modo headless",
    )
    parser.add_argument(
        "--signature-file",
        type=Path,
        help="Ruta a un JSON con la firma del API",
    )
    parser.add_argument(
        "--page-start",
        type=int,
        help="Valor base para el primer número de página",
    )
    parser.add_argument(
        "--page-size", type=int, help="Cantidad de registros por página"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_documents < 0:
        raise ValueError("max-documents debe ser positivo o cero.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.category_path = args.category or []
    args.filter_overrides = build_filter_overrides(
        args.filter, args.dependencia, args.desde, args.hasta
    )

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=args.headless)
            context = await browser.new_context(viewport={"width": 1400, "height": 900})
            page = await context.new_page()
            signature: SearchSignature
            if args.signature_file:
                signature_data = load_signature_from_file(args.signature_file)
                signature = load_signature(signature_data)
                await page.goto(
                    "https://www.pjn.gov.ar/gestion-documental",
                    wait_until="networkidle",
                )
            else:
                signature = await capture_signature(page, args)
            await run_scraping(args, signature, context.request)
            await browser.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
