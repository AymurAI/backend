from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import mimetypes
import os
import re
import time
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
from pydantic import BaseModel
from tqdm.auto import tqdm

from aymurai.experiments.data_augmentation.config import (
    DataAugmentationRunConfig,
    load_data_augmentation_config,
    render_run_dir_name,
)
from aymurai.experiments.mlflow_utils import (
    configure_mlflow,
    safe_end_run,
    safe_generation_trace_context,
    safe_log_artifacts,
    safe_log_generation_trace,
    safe_log_metrics,
    safe_log_params,
    safe_set_generation_trace_data,
    safe_set_tags,
    safe_start_run,
)

LABEL_PATTERN = re.compile(r"<([^<>\s]+)>")

DEFAULT_LABEL_NORMALIZATION_MAP: dict[str, str] = {
    "CUIJ": "CUIJ",
    "CUIT": "CUIT_CUIL",
    "CUIL": "CUIT_CUIL",
    "CVU": "CBU",
    "EMAIL": "CORREO_ELECTRONICO",
    "MAIL": "CORREO_ELECTRONICO",
    "FECHA_HECHO": "FECHA",
    "NUM_TEL": "TELEFONO",
    "CAUSA": "NUM_EXPEDIENTE",
    "NUM_CUIT": "CUIT_CUIL",
    "NUMERO_TELEFONO": "TELEFONO",
    "PERIODO": "FECHA",
    "PERÍODO": "FECHA",
    "ACSUADO/A": "PER",
    "ACSUSDO/A": "PER",
    "EMPRESA": "TEXTO_ANONIMIZAR",
    "FECHA_DEL_HECHO": "FECHA",
    "CTA": "NUM_CAJA_AHORRO",
    "NUM_CAUSA": "NUM_EXPEDIENTE",
    "NUM:CAUSA": "NUM_EXPEDIENTE",
    "NUM_IPP": "NUM_EXPEDIENTE",
    "NUM_IP": "NUM_EXPEDIENTE",
    "INTITUCION": "LOC",
    "INSTITUCIÓN": "LOC",
    "IMEI": "TEXTO_ANONIMIZAR",
    "ALIAS": "TEXTO_ANONIMIZAR",
    "DIR": "DIRECCION",
    "DOMINIO": "PATENTE_DOMINIO",
    "DOMINIO_PATENTE": "PATENTE_DOMINIO",
    "NUM_ANONIMIZAR": "TEXTO_ANONIMIZAR",
    "FECHA_NUMERICA": "FECHA",
    "FECHA_NUMÉRICA": "FECHA",
    "NOM": "PER",
    "LUGAR_DE_DETENCIÓN": "LOC",
    "LUGAR_DE_DETENCION": "LOC",
    "PASPORTE": "DNI",
    "PASAPORTE": "DNI",
    "QUERY": "TEXTO_ANONIMIZAR",
    "query": "TEXTO_ANONIMIZAR",
    "LOCS": "LOC",
    "LOCs": "LOC",
}

LABEL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^LOCS?$"), "LOC"),
    (re.compile(r"^TEL(?:EFONO)?(?:_|$)|NUM_TEL|NUMERO_TELEFONO"), "TELEFONO"),
    (re.compile(r"EDAD"), "EDAD"),
    (re.compile(r"A+C?S?U?S?AD(?:O|A|X|O_A|A_O)?"), "PER"),
    (re.compile(r"DENUNCIANTE"), "PER"),
    (re.compile(r"DEFENSOR(?:A|X)?"), "PER"),
    (re.compile(r"TESTIG[OA]"), "PER"),
    (re.compile(r"^NOM(?:_|$)"), "PER"),
    (re.compile(r"CLUB"), "LOC"),
    (re.compile(r"INSTITUCION|INTITUCION"), "LOC"),
    (re.compile(r"LOCALIDAD"), "LOC"),
    (re.compile(r"LUGAR_DE_DETENCION"), "LOC"),
    (re.compile(r"LUGAR_HECHO"), "LOC"),
    (re.compile(r"FECHA_NUMERICA|FECHA_HECHO|FECHA_DEL_HECHO|PERIODO"), "FECHA"),
    (re.compile(r"NUM_CAUSA|^CAUSA$"), "NUM_EXPEDIENTE"),
    (re.compile(r"NUM_CUIT"), "CUIT_CUIL"),
    (re.compile(r"NUM_IPP|NUM_IP"), "NUM_EXPEDIENTE"),
    (re.compile(r"^CTA(?:_|$)"), "NUM_CAJA_AHORRO"),
    (re.compile(r"^DIR(?:_|$)"), "DIRECCION"),
    (re.compile(r"DOMINIO(?:_PATENTE)?"), "PATENTE_DOMINIO"),
    (re.compile(r"MAIL"), "CORREO_ELECTRONICO"),
    (re.compile(r"QUERY"), "TEXTO_ANONIMIZAR"),
    (re.compile(r"NUM_ANONIMIZAR|ANONIMIZAR"), "TEXTO_ANONIMIZAR"),
    (re.compile(r"ALIAS|IMEI|EMPRESA"), "TEXTO_ANONIMIZAR"),
    (re.compile(r"PASPORTE|PASAPORTE"), "DNI"),
]

LLM_ONLY_LABELS = {"TEXTO_ANONIMIZAR"}


@dataclass(frozen=True)
class TagOccurrence:
    occurrence_id: int
    label: str
    start: int
    end: int
    placeholder: str


class ReplacementSelection(BaseModel):
    occurrence_id: int
    label: str
    chosen_value: str


class ReplacementSelectionBatch(BaseModel):
    resolved_paragraph: str
    replacements: list[ReplacementSelection]


OLLAMA_SYSTEM_PROMPT = """You are helping build a Spanish legal NER training set.
Choose exactly one candidate value for each anonymization tag occurrence.
Resolve the full paragraph by replacing the anonymization tags with the chosen values.
Do not paraphrase the paragraph.
Do not invent new values unless the label is explicitly listed as missing and handled by the LLM.
Return only the JSON object required by the schema.
"""

OLLAMA_USER_PROMPT_TEMPLATE = """
Analyze the anonymized paragraph, choose exactly one candidate value for each tag occurrence, and return the final resolved paragraph.

Paragraph:
{paragraph}

Occurrences:
{occurrences_json}

Candidate values by label:
{candidate_values_json}

Missing labels without Faker candidates:
{missing_labels_json}

Rules:
- Use exactly one replacement per occurrence_id.
- If a label exists in candidate_values_by_label, the chosen_value should come from that candidate list.
- If a label is listed in missing_labels, you are allowed to generate a coherent replacement directly.
- The field resolved_paragraph must contain the full paragraph with the chosen values inserted in place of the anonymization tags.
- Keep grammatical and legal coherence whenever possible.
- Do not add explanations.
""".strip()


def get_llm_provider_name(config: DataAugmentationRunConfig) -> str:
    return config.ollama.provider


def log_step(message: str) -> None:
    print(f"[data-augmentation] {message}")


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "aymurai").exists():
            return candidate
    raise RuntimeError(
        "Could not locate the project root from the current working directory."
    )


def load_less_frequent_labels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    df.columns = [str(col).strip() for col in df.columns]
    if "label" not in df.columns:
        raise ValueError(
            f"Expected a 'label' column in {path}, found columns={df.columns.tolist()}"
        )
    df["label"] = df["label"].astype(str).str.strip()
    if "relative_frequency_pct" in df.columns:
        df["relative_frequency_pct"] = pd.to_numeric(
            df["relative_frequency_pct"], errors="coerce"
        )
    return df[df["label"].astype(bool)].reset_index(drop=True)


def select_target_label_rows(
    less_frequent_labels_df: pd.DataFrame,
    *,
    target_label_count: int | None,
) -> pd.DataFrame:
    if target_label_count is None:
        return less_frequent_labels_df.copy().reset_index(drop=True)
    if target_label_count <= 0:
        raise ValueError("generation.target_label_count must be positive or null.")
    return (
        less_frequent_labels_df.head(target_label_count).copy().reset_index(drop=True)
    )


def load_unique_labels(path: Path) -> pd.DataFrame:
    labels = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not labels:
        raise ValueError(f"No labels found in {path}")
    return pd.DataFrame({"label": labels})


def canonicalize_label_for_matching(label: str) -> str:
    label = str(label).strip().upper()
    label = (
        label.replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )
    label = re.sub(r"[^A-Z0-9]+", "_", label)
    return re.sub(r"_+", "_", label).strip("_")


def normalize_label_name(label: str, label_map: dict[str, str] | None = None) -> str:
    label = str(label).strip()
    label_map = label_map or {}
    if label in label_map:
        return label_map[label]

    canonical_label = canonicalize_label_for_matching(label)
    if canonical_label.startswith("NUM_"):
        suffix_label = canonical_label[4:]
        if suffix_label in {"CAJA_AHORRO", "MATRICULA", "EXPEDIENTE", "ACTUACION"}:
            return f"NUM_{suffix_label}"
        if suffix_label in {
            "PER",
            "BANCO",
            "FECHA",
            "DIRECCION",
            "LOC",
            "DNI",
            "TELEFONO",
            "CBU",
            "CUIJ",
            "CUIT_CUIL",
            "IP",
            "LINK",
            "USUARIX",
            "NOMBRE_ARCHIVO",
            "ESTUDIOS",
            "NACIONALIDAD",
            "MARCA_AUTOMOVIL",
            "PATENTE_DOMINIO",
            "TEXTO_ANONIMIZAR",
            "EDAD",
        }:
            return suffix_label

    for pattern, target_label in LABEL_RULES:
        if pattern.search(canonical_label):
            return target_label
    return label


def standardize_paragraph_labels(
    text: str, label_map: dict[str, str] | None = None
) -> str:
    label_map = label_map or {}

    def _replace(match: re.Match[str]) -> str:
        original_label = match.group(1)
        normalized_label = normalize_label_name(original_label, label_map)
        return f"<{normalized_label}>"

    return LABEL_PATTERN.sub(_replace, text)


def find_labels_in_text(text: str, allowed_labels: set[str] | None = None) -> list[str]:
    labels = [match.group(1) for match in LABEL_PATTERN.finditer(text)]
    if allowed_labels is None:
        return sorted(set(labels))
    return sorted({label for label in labels if label in allowed_labels})


def extract_tag_occurrences(text: str) -> list[TagOccurrence]:
    return [
        TagOccurrence(
            occurrence_id=idx,
            label=match.group(1),
            start=match.start(),
            end=match.end(),
            placeholder=match.group(0),
        )
        for idx, match in enumerate(LABEL_PATTERN.finditer(text))
    ]


def build_unique_label_inventory(
    paragraphs_df: pd.DataFrame, label_column: str
) -> pd.DataFrame:
    return (
        paragraphs_df[label_column]
        .explode()
        .dropna()
        .astype(str)
        .value_counts()
        .rename_axis("label")
        .reset_index(name="paragraph_count")
        .sort_values(["paragraph_count", "label"], ascending=[False, True])
        .reset_index(drop=True)
    )


def collect_distinct_labels(
    paragraphs_df: pd.DataFrame, label_column: str
) -> list[str]:
    if label_column not in paragraphs_df.columns:
        return []
    return sorted(
        {
            str(label).strip()
            for label in paragraphs_df[label_column].explode().dropna().tolist()
            if str(label).strip()
        }
    )


def build_fuzzy_label_groups(
    train_labels: Iterable[str],
    odt_labels: Iterable[str],
    *,
    min_similarity: float = 0.72,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str], pd.DataFrame]:
    train_labels = sorted(
        {str(label).strip() for label in train_labels if str(label).strip()}
    )
    odt_labels = sorted(
        {str(label).strip() for label in odt_labels if str(label).strip()}
    )
    canonical_train_lookup = {
        canonicalize_label_for_matching(train_label): train_label
        for train_label in train_labels
    }

    grouped_matches: dict[str, list[dict[str, Any]]] = {
        label: [] for label in train_labels
    }
    odt_to_train_map: dict[str, str] = {}
    review_rows: list[dict[str, Any]] = []

    for odt_label in odt_labels:
        odt_key = canonicalize_label_for_matching(odt_label)
        if odt_key in canonical_train_lookup:
            exact_train_label = canonical_train_lookup[odt_key]
            grouped_matches[exact_train_label].append(
                {"odt_label": odt_label, "score": 1.0}
            )
            odt_to_train_map[odt_label] = exact_train_label
            review_rows.append(
                {
                    "odt_label": odt_label,
                    "best_train_label": exact_train_label,
                    "best_score": 1.0,
                    "accepted": True,
                    "top_3_candidates": [
                        f"{exact_train_label} (1.000)",
                        "exact_canonical_match",
                    ],
                }
            )
            continue

        scored_candidates = []
        for train_label in train_labels:
            train_key = canonicalize_label_for_matching(train_label)
            score = SequenceMatcher(None, odt_key, train_key).ratio()
            scored_candidates.append(
                {"odt_label": odt_label, "train_label": train_label, "score": score}
            )

        scored_candidates = sorted(
            scored_candidates, key=lambda item: (-item["score"], item["train_label"])
        )
        best_match = scored_candidates[0]
        accepted = best_match["score"] >= min_similarity
        review_rows.append(
            {
                "odt_label": odt_label,
                "best_train_label": best_match["train_label"],
                "best_score": best_match["score"],
                "accepted": accepted,
                "top_3_candidates": [
                    f"{item['train_label']} ({item['score']:.3f})"
                    for item in scored_candidates[:3]
                ],
            }
        )
        if accepted:
            grouped_matches[best_match["train_label"]].append(
                {"odt_label": odt_label, "score": best_match["score"]}
            )
            odt_to_train_map[odt_label] = best_match["train_label"]

    grouped_matches = {
        train_label: sorted(
            matches, key=lambda item: (-item["score"], item["odt_label"])
        )
        for train_label, matches in grouped_matches.items()
    }
    review_df = (
        pd.DataFrame(review_rows)
        .sort_values(
            ["accepted", "best_score", "odt_label"], ascending=[False, False, True]
        )
        .reset_index(drop=True)
    )
    return grouped_matches, odt_to_train_map, review_df


def build_rule_based_label_map(
    odt_labels: Iterable[str],
) -> tuple[dict[str, str], pd.DataFrame]:
    rule_map: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    for odt_label in sorted(
        {str(label).strip() for label in odt_labels if str(label).strip()}
    ):
        normalized = normalize_label_name(odt_label, DEFAULT_LABEL_NORMALIZATION_MAP)
        if normalized != odt_label:
            rule_map[odt_label] = normalized
            rows.append(
                {
                    "odt_label": odt_label,
                    "normalized_label": normalized,
                    "match_type": "manual_or_rule",
                }
            )
    return rule_map, pd.DataFrame(rows)


def build_label_mapping_coverage(
    raw_label_inventory_df: pd.DataFrame,
    effective_label_normalization_map: dict[str, str],
    known_train_labels: set[str],
) -> pd.DataFrame:
    coverage_df = raw_label_inventory_df.copy()
    coverage_df["mapped_label"] = coverage_df["label"].map(
        lambda value: normalize_label_name(value, effective_label_normalization_map)
    )
    coverage_df["is_mapped"] = coverage_df["mapped_label"].isin(known_train_labels)
    coverage_df["mapping_changed"] = coverage_df["mapped_label"] != coverage_df["label"]
    return coverage_df.sort_values(
        ["is_mapped", "paragraph_count", "label"], ascending=[True, False, True]
    ).reset_index(drop=True)


def sort_label_mapping_by_normalized_label(label_map: dict[str, str]) -> dict[str, str]:
    return dict(sorted(label_map.items(), key=lambda item: (item[1], item[0])))


def group_raw_labels_by_normalized_label(
    label_map: dict[str, str],
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for raw_label, normalized_label in sorted(
        label_map.items(), key=lambda item: (item[1], item[0])
    ):
        grouped.setdefault(normalized_label, []).append(raw_label)
    return grouped


def write_unmapped_label_report(
    output_dir: Path,
    coverage_df: pd.DataFrame,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "unmapped_raw_labels.txt"
    unmapped_df = coverage_df.loc[
        ~coverage_df["is_mapped"], ["label", "mapped_label", "paragraph_count"]
    ]

    lines = [
        "# Raw labels without a valid mapping to a canonical train label",
        "# Add an exact mapping or rule, then run the pipeline again.",
        "# Format: raw_label -> current_mapped_label (paragraph_count)",
        "",
    ]
    for row in unmapped_df.to_dict("records"):
        lines.append(
            f"{row['label']} -> {row['mapped_label']} ({row['paragraph_count']})"
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def write_unsupported_label_report(
    output_dir: Path,
    *,
    unsupported_labels: list[str],
    llm_only_without_ollama: list[str],
    faker_supported_labels: set[str],
    llm_only_labels: set[str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "unsupported_normalized_labels.txt"
    lines = [
        "# Normalized labels that cannot be augmented with current settings",
        "# Add normalization mappings/rules or enable/adjust LLM handling.",
        "",
    ]
    if unsupported_labels:
        lines.append("# Missing Faker generators and not declared as LLM-only:")
        for label in unsupported_labels:
            lines.append(f"- {label}")
        lines.append("")

    if llm_only_without_ollama:
        lines.append(
            "# Declared LLM-only labels found while Ollama fallback is disabled:"
        )
        for label in llm_only_without_ollama:
            lines.append(f"- {label}")
        lines.append("")

    lines.append("# Faker-supported labels snapshot:")
    lines.append(", ".join(sorted(faker_supported_labels)))
    lines.append("")
    lines.append("# LLM-only labels snapshot:")
    lines.append(", ".join(sorted(llm_only_labels)) or "(none)")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def build_missing_label_inventory(
    candidate_paragraphs_df: pd.DataFrame,
    *,
    faker_supported_labels: set[str],
    llm_only_labels: set[str],
) -> pd.DataFrame:
    labels = (
        candidate_paragraphs_df["labels"].explode().dropna().astype(str).str.strip()
    )
    labels = labels[labels.astype(bool)]
    if labels.empty:
        return pd.DataFrame(
            columns=[
                "label",
                "paragraph_count",
                "resolution_mode",
                "has_faker_generator",
                "is_llm_only",
            ]
        )

    inventory_df = (
        labels.value_counts()
        .rename_axis("label")
        .reset_index(name="paragraph_count")
        .sort_values(["paragraph_count", "label"], ascending=[False, True])
        .reset_index(drop=True)
    )
    inventory_df["has_faker_generator"] = inventory_df["label"].isin(
        faker_supported_labels
    )
    inventory_df["is_llm_only"] = inventory_df["label"].isin(llm_only_labels)
    inventory_df["resolution_mode"] = "llm_missing_label"
    inventory_df.loc[
        inventory_df["is_llm_only"], "resolution_mode"
    ] = "llm_only_declared"
    inventory_df.loc[
        ~inventory_df["is_llm_only"] & inventory_df["has_faker_generator"],
        "resolution_mode",
    ] = "faker_supported"

    return inventory_df.loc[
        inventory_df["resolution_mode"] != "faker_supported"
    ].reset_index(drop=True)


def api_extract_document(
    document_path: Path,
    *,
    endpoint: str,
    timeout_s: float,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    session = session or requests.Session()
    response = call_extraction_api(
        session=session,
        endpoint=endpoint,
        file_path=document_path,
        timeout_s=timeout_s,
    )
    if response.get("status") != "success":
        raise RuntimeError(
            f"Failed to extract {document_path}: {response.get('detail')}"
        )
    detail = response.get("detail") or {}
    return {
        "document_id": detail.get("document_id"),
        "paragraphs": detail.get("document") or [],
    }


def call_extraction_api(
    session: requests.Session, endpoint: str, file_path: Path, timeout_s: float
) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": str(file_path),
        "status": "failure",
        "status_code": None,
        "elapsed_s": None,
        "detail": None,
    }

    if not file_path.exists():
        payload["detail"] = "File does not exist"
        return payload

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    files = {
        "file": (file_path.name, file_path.open("rb"), mime_type),
    }

    try:
        start = time.perf_counter()
        response = session.post(
            endpoint,
            files=files,
            timeout=timeout_s,
        )
        elapsed = time.perf_counter() - start
    except requests.RequestException as exc:
        payload["detail"] = f"Request failed: {exc}"
        return payload
    finally:
        files["file"][1].close()

    payload["status_code"] = response.status_code
    payload["elapsed_s"] = elapsed

    try:
        response_body = response.json()
    except ValueError:
        response_body = {"raw": response.text[:500]}

    if response.ok:
        payload["status"] = "success"
        payload["detail"] = {
            "document_id": response_body.get("document_id"),
            "document": response_body.get("document", []),
        }
    else:
        payload["detail"] = response_body

    return payload


def collect_paragraphs(
    document_paths: Iterable[Path],
    *,
    endpoint: str,
    timeout_s: float,
    label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    label_map = label_map or {}
    records: list[dict[str, Any]] = []
    with requests.Session() as session:
        for document_path in document_paths:
            extracted = api_extract_document(
                document_path, endpoint=endpoint, timeout_s=timeout_s, session=session
            )
            for paragraph_id, text in enumerate(extracted["paragraphs"]):
                raw_labels = find_labels_in_text(text)
                standardized_text = standardize_paragraph_labels(text, label_map)
                labels = find_labels_in_text(standardized_text)
                records.append(
                    {
                        "source_path": str(document_path),
                        "document_id": extracted["document_id"],
                        "paragraph_id": paragraph_id,
                        "raw_text": text,
                        "text": standardized_text,
                        "raw_labels": raw_labels,
                        "labels": labels,
                    }
                )
    return pd.DataFrame(records)


def load_augmentation_registry(project_root: Path) -> tuple[dict[str, Any], Any]:
    notebook_like_cwd = project_root / "notebooks" / "experiments" / "data-augmentation"
    original_cwd = Path.cwd()
    try:
        os.chdir(notebook_like_cwd)
        module = importlib.import_module(
            "aymurai.experiments.data_augmentation.anonymizer_entities"
        )
    finally:
        os.chdir(original_cwd)
    return module.augmentation_functions, module.faker


def generate_label_candidates(
    distinct_labels: Iterable[str],
    *,
    augmentation_functions: dict[str, Any],
    augmentation_faker: Any,
    n_options: int,
    max_attempts_per_label: int,
    seed: int | None = None,
    llm_only_labels: Iterable[str] | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    if seed is not None:
        augmentation_faker.seed_instance(seed)
    else:
        augmentation_faker.seed_instance(0)

    allowed_llm_only_labels = {
        str(label).strip()
        for label in (llm_only_labels or LLM_ONLY_LABELS)
        if str(label).strip()
    }

    candidate_map: dict[str, list[str]] = {}
    missing_labels: list[str] = []
    for label in sorted(set(distinct_labels)):
        if label in allowed_llm_only_labels:
            missing_labels.append(label)
            continue

        generator = augmentation_functions.get(label)
        if generator is None:
            missing_labels.append(label)
            continue

        values: list[str] = []
        seen: set[str] = set()
        attempts = 0
        while len(values) < n_options and attempts < max_attempts_per_label:
            attempts += 1
            candidate = str(generator()).strip()
            if not candidate or candidate in seen:
                continue
            values.append(candidate)
            seen.add(candidate)

        if len(values) < n_options:
            raise RuntimeError(
                f"Could not generate {n_options} unique values for label '{label}'. Generated only {len(values)} values."
            )

        candidate_map[label] = values

    # Keep unknown labels in missing_labels so the LLM can still resolve them.
    # This avoids hard failures when ODT sources introduce new/unmapped tags.
    return candidate_map, sorted(missing_labels)


def derive_paragraph_seed(row: pd.Series, *, base_seed: int) -> int:
    key = "|".join(
        [
            str(base_seed),
            str(row.get("source_path", "")),
            str(row.get("document_id", "")),
            str(row.get("paragraph_id", "")),
        ]
    )
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def build_ollama_user_prompt(
    paragraph: str,
    occurrences: list[TagOccurrence],
    candidate_map: dict[str, list[str]],
    missing_labels: list[str],
) -> str:
    occurrences_payload = [
        {
            "occurrence_id": occurrence.occurrence_id,
            "label": occurrence.label,
            "placeholder": occurrence.placeholder,
        }
        for occurrence in occurrences
    ]
    return OLLAMA_USER_PROMPT_TEMPLATE.format(
        paragraph=paragraph,
        occurrences_json=json.dumps(occurrences_payload, ensure_ascii=False, indent=2),
        candidate_values_json=json.dumps(candidate_map, ensure_ascii=False, indent=2),
        missing_labels_json=json.dumps(missing_labels, ensure_ascii=False, indent=2),
    )


def normalize_candidate_text(value: str) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[\s_\-\.]+", "", value)
    return re.sub(r"[^0-9a-záéíóúüñ]", "", value)


def fallback_missing_label_value(label: str) -> str:
    canonical = canonicalize_label_for_matching(label).replace("_", " ").strip().lower()
    descriptor = canonical if canonical else "dato"
    return f"dato reservado ({descriptor})"


def resolve_candidate_choice(
    label: str,
    chosen_value: str,
    candidate_map: dict[str, list[str]],
    *,
    allow_non_faker_values: bool = False,
) -> tuple[str, bool]:
    candidates = candidate_map.get(label, [])
    if chosen_value in candidates:
        return chosen_value, False

    normalized_choice = normalize_candidate_text(chosen_value)
    normalized_candidates: dict[str, list[str]] = {}
    for candidate in candidates:
        normalized_candidates.setdefault(
            normalize_candidate_text(candidate), []
        ).append(candidate)

    matches = normalized_candidates.get(normalized_choice, [])
    if len(matches) == 1:
        return matches[0], False
    if allow_non_faker_values and str(chosen_value).strip():
        return str(chosen_value).strip(), True
    raise ValueError(
        f"Chosen value '{chosen_value}' is not part of the candidates for label '{label}'"
    )


def apply_replacements(
    paragraph: str,
    occurrences: list[TagOccurrence],
    replacements: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    replacement_by_id = {item["occurrence_id"]: item for item in replacements}
    resolved_parts: list[str] = []
    entities: list[dict[str, Any]] = []
    cursor = 0
    resolved_cursor = 0

    for occurrence in occurrences:
        replacement = replacement_by_id[occurrence.occurrence_id]
        chosen_value = replacement["chosen_value"]

        prefix = paragraph[cursor : occurrence.start]
        resolved_parts.append(prefix)
        resolved_cursor += len(prefix)

        entity_start = resolved_cursor
        resolved_parts.append(chosen_value)
        resolved_cursor += len(chosen_value)
        entity_end = resolved_cursor

        entities.append(
            {
                "label": occurrence.label,
                "start_char": entity_start,
                "end_char": entity_end,
                "text": chosen_value,
                "occurrence_id": occurrence.occurrence_id,
                "source_placeholder": occurrence.placeholder,
            }
        )
        cursor = occurrence.end

    suffix = paragraph[cursor:]
    resolved_parts.append(suffix)
    return "".join(resolved_parts), entities


def build_token_offsets(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        start = text.find(token, cursor)
        if start == -1:
            raise ValueError(
                f"Could not align token '{token}' around '{text[cursor : cursor + 80]}'"
            )
        end = start + len(token)
        offsets.append((start, end))
        cursor = end
    return offsets


def entities_to_bio_lines(text: str, entities: list[dict[str, Any]]) -> list[str]:
    tokens = text.split()
    offsets = build_token_offsets(text, tokens)
    bio_tags = ["O"] * len(tokens)
    for entity in sorted(
        entities, key=lambda item: (item["start_char"], item["end_char"])
    ):
        first = True
        for idx, (tok_start, tok_end) in enumerate(offsets):
            if entity["end_char"] <= tok_start or entity["start_char"] >= tok_end:
                continue
            bio_tags[idx] = f"{'B' if first else 'I'}-{entity['label']}"
            first = False
    return [f"{token} {label}" for token, label in zip(tokens, bio_tags)]


def alignment_to_bio_lines(mapping: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for row in mapping.fillna("").to_dict("records"):
        source_chunk = str(row["source"]).strip()
        target_tokens = [token for token in str(row["target"]).split() if token]
        if not target_tokens:
            continue
        match = LABEL_PATTERN.search(source_chunk)
        if not match:
            lines.extend([f"{token} O" for token in target_tokens])
            continue
        label = match.group(1)
        for idx, token in enumerate(target_tokens):
            lines.append(f"{token} {'B' if idx == 0 else 'I'}-{label}")
    return lines


def build_alignment_records(
    source_text: str, target_text: str
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    from aymurai.utils.alignment.core import align_text

    alignment_df = align_text(source_text, target_text, columns=("source", "target"))
    alignment_records = alignment_df.fillna("").astype(str).to_dict("records")
    return alignment_df, alignment_records


def choose_replacements_with_ollama(
    paragraph: str,
    occurrences: list[TagOccurrence],
    candidate_map: dict[str, list[str]],
    missing_labels: list[str],
    *,
    config: DataAugmentationRunConfig,
) -> dict[str, Any]:
    if not config.generation.run_with_ollama:
        replacements = [
            {
                "occurrence_id": occurrence.occurrence_id,
                "label": occurrence.label,
                "chosen_value": candidate_map[occurrence.label][0],
                "selection_mode": "fallback_first_candidate",
                "used_non_faker_value": False,
            }
            for occurrence in occurrences
            if occurrence.label in candidate_map
        ]
        resolved_paragraph, _ = apply_replacements(paragraph, occurrences, replacements)
        return {
            "resolved_paragraph": resolved_paragraph,
            "replacements": replacements,
            "selection_mode": "fallback_first_candidate",
            "contains_non_faker_values": False,
            "user_prompt": None,
            "raw_response_text": None,
        }

    user_prompt = build_ollama_user_prompt(
        paragraph=paragraph,
        occurrences=occurrences,
        candidate_map=candidate_map,
        missing_labels=missing_labels if config.ollama.allow_missing_labels else [],
    )
    provider_name = get_llm_provider_name(config)
    provider_model_name: str
    raw_response_text: str

    if provider_name == "ollama":
        from aymurai.llm_providers import OllamaLLMProvider

        provider = OllamaLLMProvider(
            model=config.ollama.model,
            keep_alive=config.ollama.keep_alive,
        )
        response = provider.generate(
            messages=[
                {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={
                "temperature": config.ollama.temperature,
                "num_ctx": config.ollama.num_ctx,
            },
            format=ReplacementSelectionBatch.model_json_schema(),
        )
        raw_response_text = response.text
        provider_model_name = provider.model_name
    elif provider_name == "openai":
        from openai import OpenAI

        from aymurai.settings import load_env
        from aymurai.utils.openai_httpx_compat import apply_openai_httpx_compat

        load_env()
        apply_openai_httpx_compat()
        api_key = os.getenv(config.openai.api_key_env_var)
        if not api_key:
            raise ValueError(
                f"Missing OpenAI API key. Set {config.openai.api_key_env_var} in .env."
            )

        client = OpenAI(
            api_key=api_key,
            base_url=config.openai.base_url,
        )
        response = client.chat.completions.create(
            model=config.openai.model,
            messages=[
                {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.openai.temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "replacement_selection_batch",
                    "schema": ReplacementSelectionBatch.model_json_schema(),
                    "strict": True,
                },
            },
        )
        raw_response_text = (
            response.choices[0].message.content
            if response.choices and response.choices[0].message.content
            else ""
        )
        if not raw_response_text:
            raise ValueError("OpenAI returned an empty response.")
        provider_model_name = config.openai.model
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")

    payload = json.loads(raw_response_text)
    replacements = payload.get("replacements")
    resolved_paragraph = str(payload.get("resolved_paragraph", "")).strip()
    if not isinstance(replacements, list):
        raise ValueError(f"Invalid LLM response payload: {payload}")
    if not resolved_paragraph:
        raise ValueError(f"Missing resolved_paragraph in LLM response: {payload}")

    validated: list[dict[str, Any]] = []
    expected_ids = {occurrence.occurrence_id for occurrence in occurrences}
    seen_ids: set[int] = set()
    for item in replacements:
        occurrence_id = int(item["occurrence_id"])
        label = str(item["label"])
        chosen_value = str(item["chosen_value"])
        used_non_faker_value = False

        if occurrence_id not in expected_ids:
            raise ValueError(f"Unexpected occurrence_id={occurrence_id}")
        if occurrence_id in seen_ids:
            raise ValueError(f"Duplicate occurrence_id={occurrence_id}")

        if label in candidate_map:
            chosen_value, used_non_faker_value = resolve_candidate_choice(
                label,
                chosen_value,
                candidate_map,
                allow_non_faker_values=config.ollama.allow_non_faker_values,
            )
        elif not (config.ollama.allow_missing_labels and label in missing_labels):
            raise ValueError(
                f"Label '{label}' has no Faker candidates and Ollama-generated replacements are disabled or empty."
            )
        else:
            if not chosen_value.strip():
                chosen_value = fallback_missing_label_value(label)
            used_non_faker_value = True

        seen_ids.add(occurrence_id)
        validated.append(
            {
                "occurrence_id": occurrence_id,
                "label": label,
                "chosen_value": chosen_value,
                "used_non_faker_value": used_non_faker_value,
                "selection_mode": provider_name,
                "model": provider_model_name,
            }
        )

    if seen_ids != expected_ids:
        occurrence_by_id = {
            occurrence.occurrence_id: occurrence for occurrence in occurrences
        }
        missing = sorted(expected_ids - seen_ids)
        for occurrence_id in missing:
            occurrence = occurrence_by_id[occurrence_id]
            label = occurrence.label
            used_non_faker_value = False

            if label in candidate_map and candidate_map[label]:
                chosen_value = candidate_map[label][0]
            elif config.ollama.allow_missing_labels and label in missing_labels:
                chosen_value = fallback_missing_label_value(label)
                used_non_faker_value = True
            else:
                raise ValueError(
                    f"Missing replacements for occurrence_id values: {missing}. "
                    f"Could not auto-fill occurrence_id={occurrence_id} for label '{label}'."
                )

            validated.append(
                {
                    "occurrence_id": occurrence_id,
                    "label": label,
                    "chosen_value": chosen_value,
                    "used_non_faker_value": used_non_faker_value,
                    "selection_mode": f"{provider_name}_autofill_missing_occurrence",
                    "model": provider_model_name,
                }
            )

    return {
        "resolved_paragraph": resolved_paragraph,
        "replacements": sorted(validated, key=lambda item: item["occurrence_id"]),
        "selection_mode": "ollama",
        "provider": provider_name,
        "contains_non_faker_values": any(
            item["used_non_faker_value"] for item in validated
        ),
        "user_prompt": user_prompt,
        "raw_response_text": raw_response_text,
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_bio_txt(
    path: Path, records: list[dict[str, Any]], *, bio_key: str = "bio_lines"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            if record.get("status") != "ok":
                continue
            for line in record[bio_key]:
                handle.write(line + "\n")
            handle.write("\n")


def log_augmentation_generation_trace(
    record: dict[str, Any],
    *,
    enabled: bool,
    span: Any | None = None,
) -> None:
    sample_id = str(record.get("sample_id") or "")
    if not sample_id:
        return

    tags = {
        "experiment": "data-augmentation",
        "sample_id": sample_id,
        "status": str(record.get("status") or ""),
    }
    inputs = {
        "sample_id": sample_id,
        "document_id": record.get("document_id"),
        "paragraph_id": record.get("paragraph_id"),
        "source_path": record.get("source_path"),
        "source_text": record.get("source_text"),
        "labels": record.get("labels"),
        "target_labels": record.get("target_labels"),
        "candidate_values": record.get("candidate_values"),
        "missing_labels": record.get("missing_labels"),
        "prompt": record.get("ollama_user_prompt"),
    }
    outputs = {
        "status": record.get("status"),
        "resolved_text": record.get("resolved_text"),
        "local_resolved_text": record.get("local_resolved_text"),
        "resolved_text_matches_local": record.get("resolved_text_matches_local"),
        "replacements": record.get("replacements"),
        "entities": record.get("entities"),
        "bio_lines": record.get("bio_lines"),
        "alignment_path": record.get("alignment_path"),
        "alignment_records": record.get("alignment_records"),
        "raw_llm_output": record.get("ollama_raw_response_text"),
    }
    attributes = {
        "document_id": str(record.get("document_id") or ""),
        "paragraph_id": int(record.get("paragraph_id") or 0),
        "status": str(record.get("status") or ""),
        "label_count": len(record.get("labels") or []),
        "target_label_count": len(record.get("target_labels") or []),
        "entity_count": len(record.get("entities") or []),
        "replacement_count": len(record.get("replacements") or []),
        "alignment_record_count": len(record.get("alignment_records") or []),
        "contains_non_faker_values": bool(
            record.get("contains_non_faker_values", False)
        ),
        "resolved_text_matches_local": bool(
            record.get("resolved_text_matches_local", False)
        ),
    }

    if span is None:
        safe_log_generation_trace(
            enabled=enabled,
            name="data_augmentation.generate_sample",
            sample_id=sample_id,
            tags=tags,
            inputs=inputs,
            outputs=outputs,
            attributes=attributes,
        )
        return

    if enabled:
        safe_set_generation_trace_data(
            span,
            sample_id=sample_id,
            tags=tags,
            inputs=inputs,
            outputs=outputs,
            attributes=attributes,
        )


def augment_paragraph(
    row: pd.Series,
    *,
    config: DataAugmentationRunConfig,
    augmentation_functions: dict[str, Any],
    augmentation_faker: Any,
    alignments_dir: Path,
) -> dict[str, Any]:
    source_text = str(row["text"])
    sample_id = uuid.uuid4().hex
    paragraph_seed = derive_paragraph_seed(
        row,
        base_seed=int(config.generation.random_seed),
    )
    occurrences = extract_tag_occurrences(source_text)
    if not occurrences:
        raise ValueError("The paragraph does not contain anonymization tags.")

    distinct_labels = sorted({occurrence.label for occurrence in occurrences})
    candidate_map, missing_labels = generate_label_candidates(
        distinct_labels,
        augmentation_functions=augmentation_functions,
        augmentation_faker=augmentation_faker,
        n_options=config.generation.candidates_per_label,
        max_attempts_per_label=config.generation.max_attempts_per_label,
        seed=paragraph_seed,
        llm_only_labels=config.ollama.llm_only_labels,
    )

    if missing_labels and not (
        config.generation.run_with_ollama and config.ollama.allow_missing_labels
    ):
        return {
            "sample_id": sample_id,
            "document_id": row["document_id"],
            "paragraph_id": int(row["paragraph_id"]),
            "source_path": row["source_path"],
            "source_text": source_text,
            "resolved_text": None,
            "labels": distinct_labels,
            "target_labels": list(row["target_labels"]),
            "candidate_values": candidate_map,
            "candidate_seed": paragraph_seed,
            "missing_labels": missing_labels,
            "status": "skipped_missing_candidate_generators",
            "replacements": [],
            "entities": [],
            "bio_lines": [],
            "alignment_bio_lines": [],
            "alignment_path": None,
            "alignment_records": [],
        }

    llm_max_attempts = max(1, int(config.ollama.llm_call_retries) + 1)
    llm_attempt_errors: list[str] = []
    llm_resolution: dict[str, Any] | None = None
    for attempt in range(1, llm_max_attempts + 1):
        try:
            llm_resolution = choose_replacements_with_ollama(
                paragraph=source_text,
                occurrences=occurrences,
                candidate_map=candidate_map,
                missing_labels=missing_labels,
                config=config,
            )
            break
        except Exception as exc:
            llm_attempt_errors.append(str(exc))
            if attempt < llm_max_attempts:
                log_step(
                    f"LLM replacement attempt {attempt}/{llm_max_attempts} failed "
                    f"for document_id={row['document_id']}, paragraph_id={int(row['paragraph_id'])}; retrying"
                )

    if llm_resolution is None:
        return {
            "sample_id": sample_id,
            "document_id": row["document_id"],
            "paragraph_id": int(row["paragraph_id"]),
            "source_path": row["source_path"],
            "source_text": source_text,
            "resolved_text": None,
            "labels": distinct_labels,
            "target_labels": list(row["target_labels"]),
            "candidate_values": candidate_map,
            "candidate_seed": paragraph_seed,
            "missing_labels": missing_labels,
            "status": "skipped_llm_resolution_failed",
            "llm_attempt_count": llm_max_attempts,
            "llm_error": llm_attempt_errors[-1] if llm_attempt_errors else None,
            "llm_error_history": llm_attempt_errors,
            "replacements": [],
            "entities": [],
            "bio_lines": [],
            "alignment_bio_lines": [],
            "alignment_path": None,
            "alignment_records": [],
        }

    local_resolved_text, entities = apply_replacements(
        paragraph=source_text,
        occurrences=occurrences,
        replacements=llm_resolution["replacements"],
    )
    resolved_text = llm_resolution["resolved_paragraph"]
    alignment_df, alignment_records = build_alignment_records(
        source_text=source_text, target_text=resolved_text
    )
    bio_lines = entities_to_bio_lines(resolved_text, entities)
    alignment_bio_lines = alignment_to_bio_lines(alignment_df)

    alignments_dir.mkdir(parents=True, exist_ok=True)
    alignment_path = alignments_dir / f"{sample_id}.csv"
    alignment_df.to_csv(alignment_path, index=False)

    return {
        "sample_id": sample_id,
        "document_id": row["document_id"],
        "paragraph_id": int(row["paragraph_id"]),
        "source_path": row["source_path"],
        "source_text": source_text,
        "resolved_text": resolved_text,
        "labels": distinct_labels,
        "target_labels": list(row["target_labels"]),
        "candidate_values": candidate_map,
        "candidate_seed": paragraph_seed,
        "missing_labels": missing_labels,
        "status": "ok",
        "replacements": llm_resolution["replacements"],
        "llm_selection_mode": llm_resolution["selection_mode"],
        "contains_non_faker_values": llm_resolution.get(
            "contains_non_faker_values", False
        ),
        "ollama_user_prompt": llm_resolution.get("user_prompt"),
        "ollama_raw_response_text": llm_resolution.get("raw_response_text"),
        "local_resolved_text": local_resolved_text,
        "resolved_text_matches_local": resolved_text == local_resolved_text,
        "entities": entities,
        "bio_lines": bio_lines,
        "alignment_bio_lines": alignment_bio_lines,
        "alignment_path": str(alignment_path),
        "alignment_records": alignment_records,
    }


def run_pipeline(
    config: DataAugmentationRunConfig, *, run_dir_name: str | None = None
) -> list[dict[str, Any]]:
    run_dir_name = run_dir_name or render_run_dir_name(
        config.paths.run_dir_name_template
    )
    output_dir = Path(config.paths.output_dir) / run_dir_name
    alignments_dir = output_dir / config.paths.alignments_dirname
    endpoint = f"{config.api.base_url}{config.api.document_extract_path}"
    llm_provider = get_llm_provider_name(config)
    mlflow_enabled, mlflow_experiment_id = configure_mlflow(config.logging.mlflow)
    if mlflow_enabled:
        mlflow_enabled = safe_start_run(
            run_name=run_dir_name, experiment_id=mlflow_experiment_id
        )
    if mlflow_enabled:
        safe_set_tags(
            {
                "experiment": "data-augmentation",
                "run_dir": str(output_dir),
                "model": config.ollama.model,
            }
        )
        safe_log_params(
            {
                "run_dir_name": run_dir_name,
                "odt_count": len(config.paths.odt_paths),
                "generation_random_seed": config.generation.random_seed,
                "target_label_count": config.generation.target_label_count,
                "max_paragraphs": config.generation.max_paragraphs,
                "deduplicate_candidate_paragraphs": (
                    config.generation.deduplicate_candidate_paragraphs
                ),
                "candidates_per_label": config.generation.candidates_per_label,
                "run_with_ollama": config.generation.run_with_ollama,
                "ollama_model": config.ollama.model,
                "llm_call_retries": config.ollama.llm_call_retries,
                "normalization_fuzzy_threshold": config.normalization.fuzzy_threshold,
            }
        )

    log_step(f"Starting run in {output_dir}")
    log_step(f"Using document extract endpoint: {endpoint}")
    log_step(f"Using LLM provider: {llm_provider}")

    log_step("Loading canonical train labels and least-frequent label list")
    original_train_unique_labels_df = load_unique_labels(
        Path(config.paths.original_train_unique_labels_path)
    )
    original_train_unique_labels = set(original_train_unique_labels_df["label"])
    less_frequent_labels_df = load_less_frequent_labels(
        Path(config.paths.less_frequent_labels_path)
    )
    target_labels_df = select_target_label_rows(
        less_frequent_labels_df,
        target_label_count=config.generation.target_label_count,
    )
    log_step(
        f"Loaded {len(original_train_unique_labels)} canonical labels and selected "
        f"{len(target_labels_df)} target labels"
    )

    log_step(f"Extracting raw paragraphs from {len(config.paths.odt_paths)} ODT files")
    raw_paragraphs_df = collect_paragraphs(
        [Path(path) for path in config.paths.odt_paths],
        endpoint=endpoint,
        timeout_s=config.api.timeout_s,
        label_map={},
    )
    raw_label_inventory_df = build_unique_label_inventory(
        raw_paragraphs_df, "raw_labels"
    )
    log_step(
        f"Collected {len(raw_paragraphs_df)} paragraphs and found "
        f"{len(raw_label_inventory_df)} unique raw labels"
    )

    log_step("Building normalization map from manual rules and fuzzy matching")
    rule_based_label_map, _ = build_rule_based_label_map(
        raw_label_inventory_df["label"]
    )
    unresolved_odt_labels = [
        label
        for label in raw_label_inventory_df["label"]
        if label not in rule_based_label_map
    ]
    (
        fuzzy_label_groups,
        fuzzy_label_map,
        fuzzy_label_review_df,
    ) = build_fuzzy_label_groups(
        train_labels=original_train_unique_labels,
        odt_labels=unresolved_odt_labels,
        min_similarity=config.normalization.fuzzy_threshold,
    )

    effective_label_normalization_map = {
        **fuzzy_label_map,
        **rule_based_label_map,
        **DEFAULT_LABEL_NORMALIZATION_MAP,
        **config.normalization.exact_map,
    }
    effective_label_normalization_map = sort_label_mapping_by_normalized_label(
        effective_label_normalization_map
    )
    label_mapping_coverage_df = build_label_mapping_coverage(
        raw_label_inventory_df=raw_label_inventory_df,
        effective_label_normalization_map=effective_label_normalization_map,
        known_train_labels=original_train_unique_labels,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_label_inventory_df.to_csv(output_dir / "raw_label_inventory.csv", index=False)
    label_mapping_coverage_df.to_csv(
        output_dir / "label_mapping_coverage.csv", index=False
    )

    unmapped_raw_labels = label_mapping_coverage_df.loc[
        ~label_mapping_coverage_df["is_mapped"], "label"
    ].tolist()
    if (
        config.normalization.strict_require_all_raw_labels_mapped
        and unmapped_raw_labels
    ):
        log_step(
            f"Found {len(unmapped_raw_labels)} unmapped raw labels; stopping before augmentation"
        )
        report_path = write_unmapped_label_report(output_dir, label_mapping_coverage_df)
        unmapped_preview = label_mapping_coverage_df.loc[
            ~label_mapping_coverage_df["is_mapped"],
            ["label", "mapped_label", "paragraph_count"],
        ].to_dict("records")
        raise ValueError(
            "Some raw ODT labels are still unresolved before replacement.\n"
            f"Review {report_path} and add exact mappings or rules, then run the pipeline again.\n"
            f"Unmapped labels: {json.dumps(unmapped_preview, ensure_ascii=False)}"
        )
    log_step("All raw labels are mapped to canonical train labels")

    log_step("Normalizing target labels and recollecting standardized paragraphs")
    target_labels_df["normalized_label"] = target_labels_df["label"].map(
        lambda value: normalize_label_name(value, effective_label_normalization_map)
    )
    target_labels = set(target_labels_df["normalized_label"])

    paragraphs_df = collect_paragraphs(
        [Path(path) for path in config.paths.odt_paths],
        endpoint=endpoint,
        timeout_s=config.api.timeout_s,
        label_map=effective_label_normalization_map,
    )
    normalized_doc_labels = collect_distinct_labels(paragraphs_df, "labels")
    unmapped_normalized_labels = [
        label
        for label in normalized_doc_labels
        if label not in original_train_unique_labels
    ]
    if (
        config.normalization.strict_require_all_raw_labels_mapped
        and unmapped_normalized_labels
    ):
        raise ValueError(
            "Some normalized labels extracted from ODT documents are not part of the canonical train labels.\n"
            "Review label mappings/rules before augmentation.\n"
            f"Unmapped normalized labels: {json.dumps(unmapped_normalized_labels, ensure_ascii=False)}"
        )
    normalized_label_inventory_df = build_unique_label_inventory(
        paragraphs_df, "labels"
    )
    paragraphs_df["target_labels"] = paragraphs_df["labels"].map(
        lambda labels: [label for label in labels if label in target_labels]
    )
    paragraphs_df["has_target_label"] = paragraphs_df["target_labels"].map(bool)
    candidate_paragraphs_df = (
        paragraphs_df[paragraphs_df["has_target_label"]]
        .copy()
        .sort_values(["source_path", "paragraph_id"])
        .reset_index(drop=True)
    )
    duplicate_candidate_count = 0
    if config.generation.deduplicate_candidate_paragraphs:
        before_dedup_count = len(candidate_paragraphs_df)
        candidate_paragraphs_df = (
            candidate_paragraphs_df.drop_duplicates(subset=["text"])
            .copy()
            .reset_index(drop=True)
        )
        duplicate_candidate_count = before_dedup_count - len(candidate_paragraphs_df)
        if duplicate_candidate_count:
            log_step(
                f"Removed {duplicate_candidate_count} duplicate candidate paragraphs by normalized text"
            )
    if config.generation.max_paragraphs is not None:
        candidate_paragraphs_df = candidate_paragraphs_df.head(
            config.generation.max_paragraphs
        ).copy()
    log_step(
        f"Selected {len(candidate_paragraphs_df)} candidate paragraphs matching "
        f"{len(target_labels)} normalized target labels"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_label_inventory_df.to_csv(
        output_dir / "normalized_label_inventory.csv", index=False
    )
    target_labels_df.to_csv(output_dir / "target_labels.csv", index=False)
    fuzzy_label_review_df.to_csv(output_dir / "fuzzy_label_review.csv", index=False)
    (output_dir / "effective_label_normalization_map.json").write_text(
        json.dumps(effective_label_normalization_map, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "grouped_raw_labels_by_normalized_label.json").write_text(
        json.dumps(
            group_raw_labels_by_normalized_label(effective_label_normalization_map),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    project_root = find_project_root()
    log_step("Loading Faker augmentation registry")
    augmentation_functions, augmentation_faker = load_augmentation_registry(
        project_root
    )
    candidate_labels = collect_distinct_labels(candidate_paragraphs_df, "labels")
    llm_only_labels = {
        str(label).strip()
        for label in config.ollama.llm_only_labels
        if str(label).strip()
    }
    faker_supported_labels = set(augmentation_functions.keys())
    llm_missing_resolution_enabled = (
        config.generation.run_with_ollama and config.ollama.allow_missing_labels
    )
    missing_label_inventory_df = build_missing_label_inventory(
        candidate_paragraphs_df,
        faker_supported_labels=faker_supported_labels,
        llm_only_labels=llm_only_labels,
    )
    if not missing_label_inventory_df.empty:
        missing_inventory_path = output_dir / "missing_label_inventory.csv"
        missing_label_inventory_df.to_csv(missing_inventory_path, index=False)
        log_step(
            f"Collected {len(missing_label_inventory_df)} labels requiring LLM/missing-label handling at {missing_inventory_path}"
        )

    blocked_missing_labels = (
        []
        if llm_missing_resolution_enabled
        else sorted(
            label
            for label in candidate_labels
            if label in llm_only_labels or label not in faker_supported_labels
        )
    )
    llm_only_without_ollama = (
        []
        if llm_missing_resolution_enabled
        else sorted(label for label in candidate_labels if label in llm_only_labels)
    )
    if blocked_missing_labels:
        report_path = write_unsupported_label_report(
            output_dir,
            unsupported_labels=blocked_missing_labels,
            llm_only_without_ollama=llm_only_without_ollama,
            faker_supported_labels=faker_supported_labels,
            llm_only_labels=llm_only_labels,
        )
        if config.generation.dry_run_preflight_only:
            log_step(
                "Dry-run mode: detected labels that would block generation with current LLM settings; reports were saved."
            )
        else:
            raise ValueError(
                "Found normalized labels that cannot be augmented with the current pipeline configuration.\n"
                f"Review {report_path} and adjust mappings/rules/config before rerunning.\n"
                f"Blocked labels: {json.dumps(blocked_missing_labels, ensure_ascii=False)}; "
                f"LLM-only blocked labels: {json.dumps(llm_only_without_ollama, ensure_ascii=False)}"
            )

    if config.generation.dry_run_preflight_only:
        log_step(
            "Dry-run mode enabled: preflight checks passed; skipping augmentation generation"
        )
        if mlflow_enabled:
            safe_log_metrics(
                {
                    "raw_paragraph_count": float(len(raw_paragraphs_df)),
                    "raw_label_count": float(len(raw_label_inventory_df)),
                    "normalized_label_count": float(len(normalized_label_inventory_df)),
                    "candidate_paragraph_count": float(len(candidate_paragraphs_df)),
                    "duplicate_candidate_paragraph_count": float(
                        duplicate_candidate_count
                    ),
                    "missing_label_inventory_count": float(
                        len(missing_label_inventory_df)
                    ),
                    "dry_run_preflight_only": 1.0,
                }
            )
            safe_log_artifacts(output_dir, artifact_path="outputs")
            safe_end_run()
        return []

    records: list[dict[str, Any]] = []
    log_step(
        f"Generating {len(candidate_paragraphs_df)} augmented paragraphs "
        f"with {config.generation.candidates_per_label} Faker candidates per label"
    )
    progress = tqdm(total=len(candidate_paragraphs_df), desc="Augmenting paragraphs")
    for _, row in candidate_paragraphs_df.iterrows():
        trace_enabled = (
            mlflow_enabled and config.logging.mlflow.enable_generation_traces
        )
        with safe_generation_trace_context(
            enabled=trace_enabled,
            name="data_augmentation.generate_sample",
        ) as generation_span:
            record = augment_paragraph(
                row=row,
                config=config,
                augmentation_functions=augmentation_functions,
                augmentation_faker=augmentation_faker,
                alignments_dir=alignments_dir,
            )
            log_augmentation_generation_trace(
                record,
                enabled=trace_enabled,
                span=generation_span,
            )
        records.append(record)
        progress.update(1)
    progress.close()

    log_step("Writing JSONL, BIO, and alignment outputs")
    write_jsonl(output_dir / config.paths.jsonl_filename, records)
    write_bio_txt(output_dir / config.paths.bio_filename, records, bio_key="bio_lines")
    ok_count = sum(record.get("status") == "ok" for record in records)
    skipped_count = len(records) - ok_count
    if mlflow_enabled:
        safe_log_metrics(
            {
                "raw_paragraph_count": float(len(raw_paragraphs_df)),
                "raw_label_count": float(len(raw_label_inventory_df)),
                "normalized_label_count": float(len(normalized_label_inventory_df)),
                "candidate_paragraph_count": float(len(candidate_paragraphs_df)),
                "duplicate_candidate_paragraph_count": float(duplicate_candidate_count),
                "augmented_ok_count": float(ok_count),
                "augmented_skipped_count": float(skipped_count),
            }
        )
        safe_log_artifacts(output_dir, artifact_path="outputs")
        safe_end_run()
    log_step(f"Run finished: {ok_count} ok, {skipped_count} skipped")
    return records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the data augmentation pipeline from a YAML config."
    )
    parser.add_argument(
        "--config", required=True, help="Path to the YAML configuration file."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Run extraction, label mapping, normalization and augmentation preflight checks, "
            "then exit before generating augmented samples."
        ),
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = load_data_augmentation_config(args.config)
    if args.dry_run:
        config.generation.dry_run_preflight_only = True
    run_dir_name = render_run_dir_name(config.paths.run_dir_name_template)
    records = run_pipeline(config, run_dir_name=run_dir_name)
    output_dir = Path(config.paths.output_dir) / run_dir_name
    if config.generation.dry_run_preflight_only:
        print(f"Dry run completed. Preflight artifacts saved under {output_dir}")
        return
    print(
        f"Saved {len(records)} augmented samples to {output_dir / config.paths.jsonl_filename}"
    )
    print(f"Saved BIO output to {output_dir / config.paths.bio_filename}")


if __name__ == "__main__":
    main()
