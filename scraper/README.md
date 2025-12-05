# Scraper Playwright - Gestión Documental PJN

Este repositorio contiene un script en Python que usa **Playwright** para automatizar la recolección
de documentos PDF publicados en la sección de gestión documental del Poder Judicial de la Nación
(https://www.pjn.gov.ar/gestion-documental). El scraper reproduce las llamadas AJAX que genera el front-end,
mantiene las cookies que requiere el API y descarga los adjuntos desde el servicio oficial.

## Requisitos

1. Python 3.8+
2. Playwright y el navegador Chromium.

```bash
python -m pip install --upgrade pip
pip install playwright
playwright install chromium
```

## Uso básico

```bash
python playwright_scraper.py --output-dir datos --max-pages 5 --per-page 50 --pdf-template "https://pjn-documento-api.pjn.gov.ar/api/documento/adjunto/{id}"
```

El script hará:

- Abrirá una sesión de Playwright y visitará la página oficial.
- Detectará automáticamente qué llamada REST obtiene los documentos.
- Iterará páginas y descargará los PDFs dentro del directorio `datos`.

## Aplicar filtros desde la línea de comandos

La interfaz web permite limitar por dependencia, categorías y rango de fechas. El scraper replica ese comportamiento con los argumentos:

- `--dependencia "Fueros Federales"` aplica ese texto tanto a `dependencia` como a `dependenciaTexto`.
- `--category` se puede repetir para simular clics en categorías/subcategorías anidadas (por ejemplo `--category Reglamentos --category Normativa`).
- `--desde` y `--hasta` definen los campos `fechaDesde`/`fechaHasta` (o `desde`/`hasta`) que el backend espera.
- `--filter clave=valor` te deja añadir cualquier parámetro extra (por ejemplo `--filter orden=desc`, `--filter tipoDocumento=Resolución`).
- `--simulate-ui` simula los clicks sobre filtros, expande los botones “Mostrar más” y rellena las fechas como lo hace la UI antes de capturar la llamada AJAX. Úsalo si necesitás replicar exactamente la interacción de navegación para los filtros que ves en pantalla.
- `--debug-ui` habilita registros detallados sobre cada intento de clic/expansión para que puedas ver en consola qué filtros se están tocando en tiempo real.

Los filtros se mezclan automáticamente en la query y en el cuerpo de la petición, así que puedes combinar varios `-f` en el mismo comando.

## Estructura de almacenamiento guiada por filtros

Los documentos descargados se organizan siguiendo los filtros aplicados y la metadata del registro:

- Cada PDF se guarda en `ruta-de-salida/<dependencia>/<categoría>/<año>`, usando la dependencia que especifiques o la que entrega el API.
- La categoría se extrae de campos como `rubro`, `categoria` o `tipo` cuando están presentes.
- Si pasás `--category` el scraper usa esa secuencia de categorías/subcategorías como niveles adicionales (en lugar de los valores devueltos por el API), lo que refleja la navegación que aplicaste en los filtros.
- Si falta dependencia o año, se usan nombres como `sin-dependencia` o `sin-anio` para evitar colisiones.
- Los nombres de archivo ahora conservan acentos y caracteres especiales porque la normalización usa Unicode completo (`NFC`) antes de reemplazar espacios; así el título original permanece íntegro para tu pipeline de metadata.

Esto facilita tener directorios alineados con las dependencias del Poder Judicial y continuar el pipeline de anonimización con una estructura consistente.

Puedes ajustar el número de páginas, el retraso entre peticiones o el límite de documentos con
`--delay`, `--max-documents`, `--max-pages`.

## Firma manual del API

Si lo prefieres, puedes evitar la detección automática y proporcionar un JSON con la firma de las peticiones.
Esto es útil cuando ya sabes qué endpoint se usa o necesitas definir filtros específicos.

```json
{
  "method": "POST",
  "base_url": "https://www.pjn.gov.ar/api/documento/paginado",
  "headers": {
    "Accept": "application/json",
    "Referer": "https://www.pjn.gov.ar/gestion-documental"
  },
  "query_params": {
    "orden": "desc"
  },
  "json_body": {
    "pagina": 0,
    "size": 25,
    "dependencia": "Fueros Federales"
  },
  "listing_path": ["data", "registros"],
  "page_keys": {
    "pagina": 0
  },
  "size_keys": {
    "size": 25
  },
  "body_type": "json"
}
```

Guarda ese JSON y pásalo al script con `--signature-file firma.json`.

## Siguientes pasos

1. Define reglas de nombrado y almacenamiento según tu pipeline de anonimización.
2. Agrega paralelismo/control de errores si necesitas escalar la descarga.
3. Encadena el dump resultante con los módulos de extracción y validación de Aymurai.
