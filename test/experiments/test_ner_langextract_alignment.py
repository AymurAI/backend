import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aymurai.experiments.ner_langextract_alignment.compare import compare_entities
from aymurai.experiments.ner_langextract_alignment.labelstudio_export import (
    sample_agreements_stratified,
)
from aymurai.experiments.ner_langextract_alignment.labelstudio_import import (
    consolidate_datasets,
)
from aymurai.experiments.ner_langextract_alignment.normalize import (
    parse_langextract_predictions,
)
from aymurai.experiments.ner_langextract_alignment.runner import run_experiment
from aymurai.experiments.ner_langextract_alignment.types import (
    LLMTrace,
    NormalizedEntity,
)


class CompareTests(unittest.TestCase):
    def test_status_exact_match(self):
        ner = [
            NormalizedEntity(
                label="PER", start_char=0, end_char=4, text="Juan", source="ner"
            )
        ]
        lx = [
            NormalizedEntity(
                label="PER",
                start_char=0,
                end_char=4,
                text="Juan",
                source="langextract",
            )
        ]
        result = compare_entities(ner, lx)
        self.assertEqual(result.status, "exact_match")

    def test_status_partial_match(self):
        ner = [
            NormalizedEntity(
                label="PER", start_char=0, end_char=4, text="Juan.", source="ner"
            )
        ]
        lx = [
            NormalizedEntity(
                label="PER",
                start_char=0,
                end_char=4,
                text="Juan",
                source="langextract",
            )
        ]
        result = compare_entities(ner, lx)
        self.assertEqual(result.status, "partial_match")

    def test_status_ner_only(self):
        ner = [
            NormalizedEntity(
                label="PER", start_char=0, end_char=4, text="Juan", source="ner"
            )
        ]
        result = compare_entities(ner, [])
        self.assertEqual(result.status, "ner_only")

    def test_status_langextract_only(self):
        lx = [
            NormalizedEntity(
                label="PER",
                start_char=0,
                end_char=4,
                text="Juan",
                source="langextract",
            )
        ]
        result = compare_entities([], lx)
        self.assertEqual(result.status, "langextract_only")

    def test_status_mixed(self):
        ner = [
            NormalizedEntity(
                label="PER", start_char=0, end_char=4, text="Juan", source="ner"
            )
        ]
        lx = [
            NormalizedEntity(
                label="DNI",
                start_char=6,
                end_char=14,
                text="12345678",
                source="langextract",
            )
        ]
        result = compare_entities(ner, lx)
        self.assertEqual(result.status, "mixed")


class NormalizeTests(unittest.TestCase):
    def test_unmapped_langextract_class_flagged(self):
        entities, flags = parse_langextract_predictions(
            text="Juan Perez",
            extractions=[
                {
                    "extraction_class": "UNKNOWN",
                    "extraction_text": "Juan",
                    "char_interval": {"start_pos": 0, "end_pos": 4},
                }
            ],
            label_mapping={"PER": "PER"},
            normalize_case=True,
            normalize_accents=True,
            normalize_punctuation=True,
        )
        self.assertEqual(entities, [])
        self.assertTrue(
            any(flag.startswith("langextract_unmapped_class") for flag in flags)
        )


class LabelStudioTests(unittest.TestCase):
    def test_agreement_sampling_is_deterministic(self):
        sample = {
            "comparison": {
                "matched": [
                    {
                        "label": "PER",
                    }
                ]
            }
        }
        data = [sample.copy() for _ in range(20)]
        a = sample_agreements_stratified(data, qa_rate=0.10, seed=42)
        b = sample_agreements_stratified(data, qa_rate=0.10, seed=42)
        self.assertEqual(len(a), len(b))
        self.assertEqual(a, b)

    def test_consolidate_decisions(self):
        samples = [
            {
                "sample_id": "a",
                "comparison": {"status": "exact_match"},
                "ner_predictions": [{"label": "PER"}],
                "langextract_predictions": [{"label": "PER"}],
            },
            {
                "sample_id": "b",
                "comparison": {"status": "mixed"},
                "ner_predictions": [{"label": "PER"}],
                "langextract_predictions": [{"label": "DNI"}],
            },
        ]
        decisions = {"b": {"decision": "accept_ner", "manual_entities": []}}
        train, review = consolidate_datasets(samples, decisions)
        self.assertEqual(len(train), 2)
        self.assertEqual(len(review), 0)


class RunnerIntegrationTests(unittest.TestCase):
    def test_runner_with_mocked_backends(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paragraphs_path = root / "paragraphs.jsonl"
            paragraphs = [
                {
                    "sample_id": "s1",
                    "document_id": "d1",
                    "paragraph_id": "0",
                    "source_path": "doc1",
                    "text": "Acusado Juan Perez DNI 12345678",
                },
                {
                    "sample_id": "s2",
                    "document_id": "d1",
                    "paragraph_id": "1",
                    "source_path": "doc1",
                    "text": "Sin entidades",
                },
            ]
            with paragraphs_path.open("w", encoding="utf-8") as fh:
                for row in paragraphs:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

            mapping_path = root / "mapping.yaml"
            mapping_path.write_text(
                "labels:\n  PER: PER\n  DNI: DNI\n", encoding="utf-8"
            )

            examples_path = root / "examples.yaml"
            examples_path.write_text(
                "examples:\n  - text: 'foo'\n    extractions:\n      - extraction_class: 'PER'\n        extraction_text: 'foo'\n",
                encoding="utf-8",
            )

            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "experiment:",
                        "  name: 'ner-langextract-alignment'",
                        "  run_name: '{model}-{timestamp}'",
                        "data:",
                        f"  input_paragraphs_jsonl: '{paragraphs_path}'",
                        "  max_paragraphs: 20",
                        "api:",
                        "  base_url: 'http://localhost:8899'",
                        "  use_cache: false",
                        "langextract:",
                        "  provider: 'ollama'",
                        "  model_id: 'qwen2.5:7b'",
                        "  base_url: 'http://localhost:11434/v1'",
                        "  api_key_env: 'OLLAMA_API_KEY'",
                        "  api_key_fallback: 'ollama'",
                        "  prompt_description: 'Extract entities'",
                        f"  examples_yaml_path: '{examples_path}'",
                        "mapping:",
                        f"  labels_yaml_path: '{mapping_path}'",
                        "labelstudio:",
                        f"  export_dir: '{root / 'labelstudio'}'",
                        "  qa_sample_rate: 0.1",
                        "  qa_seed: 42",
                        "logging:",
                        "  mlflow:",
                        "    tracking_uri: 'http://localhost:5000'",
                        "    experiment_name: 'test'",
                        "outputs:",
                        f"  base_dir: '{root / 'outputs'}'",
                    ]
                ),
                encoding="utf-8",
            )

            def fake_ner(*args, **kwargs):
                text = kwargs["text"]
                if "DNI" in text:
                    return (
                        {
                            "document": text,
                            "labels": [
                                {
                                    "text": "Juan Perez",
                                    "start_char": 8,
                                    "end_char": 18,
                                    "attrs": {"aymurai_label": "PER"},
                                },
                                {
                                    "text": "12345678",
                                    "start_char": 23,
                                    "end_char": 31,
                                    "attrs": {"aymurai_label": "DNI"},
                                },
                            ],
                        },
                        12.0,
                    )
                return ({"document": text, "labels": []}, 7.0)

            def fake_lx(*args, **kwargs):
                sample_id = kwargs["sample_id"]
                text = kwargs["text"]
                if sample_id == "s1":
                    payload = {
                        "document_id": sample_id,
                        "text": text,
                        "extractions": [
                            {
                                "extraction_class": "PER",
                                "extraction_text": "Juan Perez",
                                "char_interval": {"start_pos": 8, "end_pos": 18},
                            },
                            {
                                "extraction_class": "DNI",
                                "extraction_text": "12345678",
                                "char_interval": {"start_pos": 23, "end_pos": 31},
                            },
                        ],
                    }
                else:
                    payload = {
                        "document_id": sample_id,
                        "text": text,
                        "extractions": [],
                    }

                traces = [
                    LLMTrace(
                        trace_id=f"trace-{sample_id}",
                        sample_id=sample_id,
                        provider="ollama",
                        model="qwen2.5:7b",
                        prompt="prompt",
                        input_text=text,
                        raw_output="{}",
                        parsed_output=payload,
                        duration_ms=10.0,
                        error=None,
                    )
                ]
                return payload, traces, 15.0

            noop_ctx = MagicMock()
            noop_ctx.__enter__ = lambda self: self
            noop_ctx.__exit__ = lambda self, exc_type, exc, tb: False

            with (
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.call_anonymizer_predict",
                    side_effect=fake_ner,
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.run_langextract",
                    side_effect=fake_lx,
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.build_tracing_model",
                    return_value=object(),
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.configure_mlflow"
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.log_run_metadata"
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.mlflow.start_run",
                    return_value=noop_ctx,
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.mlflow.log_artifact"
                ),
                patch(
                    "aymurai.experiments.ner_langextract_alignment.runner.mlflow.log_artifacts"
                ),
            ):
                run_experiment(str(config_path))

            self.assertTrue((root / "outputs" / "samples.jsonl").exists())
            self.assertTrue((root / "outputs" / "train_candidates.jsonl").exists())
            self.assertTrue((root / "labelstudio" / "discrepancies.json").exists())

    def test_runner_deduplicates_same_text(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paragraphs_path = root / "paragraphs.jsonl"
            duplicated_text = "Acusado Juan Perez DNI 12345678"
            paragraphs = [
                {
                    "sample_id": "s1",
                    "document_id": "d1",
                    "paragraph_id": "0",
                    "source_path": "doc1",
                    "text": duplicated_text,
                },
                {
                    "sample_id": "s2",
                    "document_id": "d2",
                    "paragraph_id": "0",
                    "source_path": "doc2",
                    "text": duplicated_text,
                },
            ]
            with paragraphs_path.open("w", encoding="utf-8") as fh:
                for row in paragraphs:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

            mapping_path = root / "mapping.yaml"
            mapping_path.write_text(
                "labels:\n  PER: PER\n  DNI: DNI\n", encoding="utf-8"
            )
            examples_path = root / "examples.yaml"
            examples_path.write_text(
                "examples:\n  - text: 'foo'\n    extractions:\n      - extraction_class: 'PER'\n        extraction_text: 'foo'\n",
                encoding="utf-8",
            )

            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "experiment:",
                        "  name: 'ner-langextract-alignment'",
                        "  run_name: '{model}-{timestamp}'",
                        "data:",
                        f"  input_paragraphs_jsonl: '{paragraphs_path}'",
                        "  deduplicate_by_text: true",
                        "api:",
                        "  base_url: 'http://localhost:8899'",
                        "  use_cache: false",
                        "langextract:",
                        "  provider: 'ollama'",
                        "  model_id: 'qwen2.5:7b'",
                        "  base_url: 'http://localhost:11434/v1'",
                        "  api_key_env: 'OLLAMA_API_KEY'",
                        "  api_key_fallback: 'ollama'",
                        "  prompt_description: 'Extract entities'",
                        f"  examples_yaml_path: '{examples_path}'",
                        "mapping:",
                        f"  labels_yaml_path: '{mapping_path}'",
                        "labelstudio:",
                        f"  export_dir: '{root / 'labelstudio'}'",
                        "  qa_sample_rate: 0.1",
                        "  qa_seed: 42",
                        "logging:",
                        "  mlflow:",
                        "    tracking_uri: 'http://localhost:5000'",
                        "    experiment_name: 'test'",
                        "outputs:",
                        f"  base_dir: '{root / 'outputs'}'",
                    ]
                ),
                encoding="utf-8",
            )

            ner_calls = {"count": 0}
            lx_calls = {"count": 0}

            def fake_ner(*args, **kwargs):
                ner_calls["count"] += 1
                text = kwargs["text"]
                return (
                    {
                        "document": text,
                        "labels": [
                            {
                                "text": "Juan Perez",
                                "start_char": 8,
                                "end_char": 18,
                                "attrs": {"aymurai_label": "PER"},
                            }
                        ],
                    },
                    10.0,
                )

            def fake_lx(*args, **kwargs):
                lx_calls["count"] += 1
                sample_id = kwargs["sample_id"]
                text = kwargs["text"]
                payload = {
                    "document_id": sample_id,
                    "text": text,
                    "extractions": [
                        {
                            "extraction_class": "PER",
                            "extraction_text": "Juan Perez",
                            "char_interval": {"start_pos": 8, "end_pos": 18},
                        }
                    ],
                }
                traces = [
                    LLMTrace(
                        trace_id=f"trace-{sample_id}",
                        sample_id=sample_id,
                        provider="ollama",
                        model="qwen2.5:7b",
                        prompt="prompt",
                        input_text=text,
                        raw_output="{}",
                        parsed_output=payload,
                        duration_ms=10.0,
                        error=None,
                    )
                ]
                return payload, traces, 15.0

            noop_ctx = MagicMock()
            noop_ctx.__enter__ = lambda self: self
            noop_ctx.__exit__ = lambda self, exc_type, exc, tb: False

            with patch(
                "aymurai.experiments.ner_langextract_alignment.runner.call_anonymizer_predict",
                side_effect=fake_ner,
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.run_langextract",
                side_effect=fake_lx,
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.build_tracing_model",
                return_value=object(),
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.configure_mlflow"
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.log_run_metadata"
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.mlflow.start_run",
                return_value=noop_ctx,
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.mlflow.log_artifact"
            ), patch(
                "aymurai.experiments.ner_langextract_alignment.runner.mlflow.log_artifacts"
            ):
                run_experiment(str(config_path))

            self.assertEqual(ner_calls["count"], 1)
            self.assertEqual(lx_calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
