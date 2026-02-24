from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.experiments.ner_testset_evaluation.backends import run_backend_inference
from aymurai.experiments.ner_testset_evaluation.config import (
    NERTestsetEvaluationConfig,
)
from aymurai.experiments.ner_testset_evaluation.loaders import load_samples
from aymurai.experiments.ner_testset_evaluation.metrics import evaluate_predictions
from aymurai.experiments.ner_testset_evaluation.mlflow_logging import (
    build_feedback_records,
)
from aymurai.experiments.ner_testset_evaluation.runner import run_experiment
from aymurai.experiments.ner_testset_evaluation.types import (
    BackendPrediction,
    CanonicalSample,
    CanonicalSpan,
)


def build_config(
    *,
    input_path: str,
    data_format: str,
    backend_mode: str = "ner_api",
    outputs_base: str,
    mapping_path: str | None = None,
) -> NERTestsetEvaluationConfig:
    payload = {
        "experiment": {
            "name": "ner-testset-evaluation",
            "run_name": "{backend}-{model}-{timestamp}",
        },
        "data": {
            "format": data_format,
            "input_path": input_path,
            "sample_id_field": "sample_id",
            "text_field": "text",
            "tokens_field": "tokens",
            "tags_field": "tags",
            "spans_field": "spans",
            "label_field": "label",
            "start_field": "start",
            "end_field": "end",
            "deduplicate_by_text": False,
        },
        "backend": {"mode": backend_mode},
        "api": {
            "base_url": "http://localhost:8899",
            "anonymizer_predict_path": "/anonymizer/predict",
            "timeout_s": 10,
            "retries": 0,
            "retry_backoff_s": 0.1,
            "use_cache": False,
        },
        "mapping": {"labels_yaml_path": mapping_path},
        "comparison": {
            "normalize_case": True,
            "normalize_accents": True,
            "normalize_punctuation": True,
        },
        "metrics": {
            "include_token_relaxed": True,
            "perfect_definition": "span_set_exact",
        },
        "logging": {
            "mlflow": {
                "enabled": False,
                "tracking_uri": "http://localhost:5000",
                "experiment_name": "ner-testset-evaluation",
                "enable_openai_autolog": False,
                "request_timeout_s": 15,
                "request_max_retries": 1,
            },
            "privacy": {
                "log_prompt_text": True,
                "log_llm_outputs": True,
                "log_raw_predictions": True,
                "redact_sensitive_fields": False,
            },
        },
        "outputs": {"base_dir": outputs_base},
    }

    if backend_mode == "langextract":
        payload["langextract"] = {
            "provider": "ollama",
            "model_id": "qwen3:8b",
            "base_url": "http://localhost:11434/v1",
            "api_key_env": "OLLAMA_API_KEY",
            "api_key_fallback": "ollama",
            "prompt_description": "Extract entities",
            "examples_yaml_path": "resources/langextract/ner_alignment_examples.yaml",
            "temperature": 0.0,
            "max_tokens": 128,
            "think": False,
            "request_timeout_s": 10,
            "retries": 0,
            "retry_backoff_s": 0.1,
            "max_workers": 1,
            "extraction_passes": 1,
            "batch_length": 1,
        }

    return NERTestsetEvaluationConfig.model_validate(payload)


class LoaderTests(unittest.TestCase):
    def test_load_conll_bio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "test.conll"
            path.write_text(
                "Juan B-PER\nPerez I-PER\n\nDNI O\n123 B-DNI\n",
                encoding="utf-8",
            )
            config = build_config(
                input_path=str(path),
                data_format="conll_bio",
                outputs_base=str(Path(tmp_dir) / "out"),
            )

            samples = load_samples(config)
            self.assertEqual(len(samples), 2)
            self.assertEqual(samples[0].tokens, ["Juan", "Perez"])
            self.assertEqual(samples[0].gold_spans[0].label, "PER")
            self.assertEqual(samples[1].gold_spans[0].label, "DNI")

    def test_load_hf_token_classification_with_id2label(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "hf.jsonl"
            rows = [
                {
                    "sample_id": "s1",
                    "tokens": ["Juan", "Perez"],
                    "tags": [1, 2],
                    "text": "Juan Perez",
                }
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

            config = build_config(
                input_path=str(path),
                data_format="hf_token_classification",
                outputs_base=str(Path(tmp_dir) / "out"),
            )
            config.data.id2label = {"1": "B-PER", "2": "I-PER"}

            samples = load_samples(config)
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0].gold_bio, ["B-PER", "I-PER"])
            self.assertEqual(samples[0].gold_spans[0].label, "PER")

    def test_load_span_jsonl_ignores_invalid_spans(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "spans.jsonl"
            rows = [
                {
                    "sample_id": "s1",
                    "text": "Juan Perez DNI 123",
                    "tokens": ["Juan", "Perez", "DNI", "123"],
                    "spans": [
                        {"label": "PER", "start": 0, "end": 10},
                        {"label": "DNI", "start": -1, "end": 3},
                        {"label": "DNI", "start": 100, "end": 110},
                    ],
                }
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

            config = build_config(
                input_path=str(path),
                data_format="span_jsonl",
                outputs_base=str(Path(tmp_dir) / "out"),
            )

            samples = load_samples(config)
            self.assertEqual(len(samples), 1)
            self.assertEqual(len(samples[0].gold_spans), 1)
            self.assertEqual(samples[0].gold_spans[0].label, "PER")


class BackendTests(unittest.TestCase):
    def test_run_ner_api_backend_parses_labels(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "test.conll"
            input_path.write_text("Juan B-PER\n\n", encoding="utf-8")
            mapping_path = Path(tmp_dir) / "mapping.yaml"
            mapping_path.write_text("labels:\n  PER: PER\n", encoding="utf-8")

            config = build_config(
                input_path=str(input_path),
                data_format="conll_bio",
                outputs_base=str(Path(tmp_dir) / "out"),
                mapping_path=str(mapping_path),
            )
            samples = [
                CanonicalSample(
                    sample_id="s1", text="Juan Perez", tokens=["Juan", "Perez"]
                )
            ]

            with patch(
                "aymurai.experiments.ner_testset_evaluation.backends.call_anonymizer_predict",
                return_value=(
                    {
                        "labels": [
                            {
                                "text": "Juan Perez",
                                "start_char": 0,
                                "end_char": 10,
                                "attrs": {"aymurai_label": "PER"},
                            }
                        ]
                    },
                    12.0,
                ),
            ):
                predictions, traces, sample_trace_ids = run_backend_inference(
                    samples, config
                )

            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0].spans[0].label, "PER")
            self.assertEqual(predictions[0].latency_ms, 12.0)
            self.assertEqual(traces, [])
            self.assertEqual(sample_trace_ids, {})

    def test_run_langextract_backend_parses_spans_and_traces(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "test.jsonl"
            input_path.write_text(
                json.dumps({"sample_id": "s1", "text": "Juan Perez", "spans": []})
                + "\n",
                encoding="utf-8",
            )
            mapping_path = Path(tmp_dir) / "mapping.yaml"
            mapping_path.write_text("labels:\n  PER: PER\n", encoding="utf-8")

            config = build_config(
                input_path=str(input_path),
                data_format="span_jsonl",
                backend_mode="langextract",
                outputs_base=str(Path(tmp_dir) / "out"),
                mapping_path=str(mapping_path),
            )
            samples = [CanonicalSample(sample_id="s1", text="Juan Perez")]
            fake_trace = LLMTrace(
                trace_id="trace-1",
                sample_id="s1",
                provider="ollama",
                model="qwen3:8b",
                prompt="prompt",
                input_text="Juan Perez",
                raw_output="{}",
                parsed_output={"extractions": []},
                duration_ms=10.0,
                error=None,
            )

            with (
                patch(
                    "aymurai.experiments.ner_testset_evaluation.backends.load_examples_from_yaml",
                    return_value=[object()],
                ),
                patch(
                    "aymurai.experiments.ner_testset_evaluation.backends.build_tracing_model",
                    return_value=object(),
                ),
                patch(
                    "aymurai.experiments.ner_testset_evaluation.backends.run_langextract",
                    return_value=(
                        {
                            "document_id": "s1",
                            "text": "Juan Perez",
                            "extractions": [
                                {
                                    "extraction_class": "PER",
                                    "extraction_text": "Juan Perez",
                                    "char_interval": {"start_pos": 0, "end_pos": 10},
                                }
                            ],
                        },
                        [fake_trace],
                        15.0,
                    ),
                ),
            ):
                predictions, traces, sample_trace_ids = run_backend_inference(
                    samples, config
                )

            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0].spans[0].label, "PER")
            self.assertEqual(predictions[0].trace_ids, ["trace-1"])
            self.assertEqual(len(traces), 1)
            self.assertEqual(sample_trace_ids["s1"], "trace-1")


class MetricsAndFeedbackTests(unittest.TestCase):
    def test_metrics_strict_relaxed_and_perfect(self):
        samples = [
            CanonicalSample(
                sample_id="s1",
                text="Juan Perez",
                tokens=["Juan", "Perez"],
                gold_spans=[
                    CanonicalSpan(label="PER", start=0, end=10, text="Juan Perez")
                ],
                gold_bio=["B-PER", "I-PER"],
            ),
            CanonicalSample(
                sample_id="s2",
                text="Sin entidades",
                tokens=["Sin", "entidades"],
                gold_spans=[],
                gold_bio=["O", "O"],
            ),
        ]
        predictions = [
            BackendPrediction(
                sample_id="s1",
                backend_mode="ner_api",
                spans=[CanonicalSpan(label="PER", start=0, end=10, text="Juan Perez")],
            ),
            BackendPrediction(sample_id="s2", backend_mode="ner_api", spans=[]),
        ]

        sample_scores, summary, confusion = evaluate_predictions(
            samples,
            predictions,
            include_token_relaxed=True,
        )

        self.assertEqual(len(sample_scores), 2)
        self.assertTrue(all(score.perfect_span_set for score in sample_scores))
        self.assertEqual(summary.metrics["strict_f1"], 1.0)
        self.assertEqual(summary.metrics["perfect_span_set_rate"], 1.0)
        self.assertGreaterEqual(summary.metrics["token_relaxed_micro_f1"], 0.0)
        self.assertTrue(isinstance(confusion, list))

    def test_feedback_records_use_yes_no(self):
        sample_scores = [
            MagicMock(sample_id="s1", perfect_span_set=True),
            MagicMock(sample_id="s2", perfect_span_set=False),
        ]
        records, entities = build_feedback_records(
            sample_scores,
            sample_trace_ids={"s1": "trace-1"},
            backend_mode="ner_api",
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].value, "yes")
        self.assertEqual(records[1].value, "no")
        self.assertEqual(len(entities), 2)


class RunnerIntegrationTests(unittest.TestCase):
    def test_runner_writes_expected_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_path = root / "test.conll"
            input_path.write_text("Juan B-PER\nPerez I-PER\n\n", encoding="utf-8")
            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "experiment:",
                        "  name: 'ner-testset-evaluation'",
                        "  run_name: '{backend}-{model}-{timestamp}'",
                        "data:",
                        "  format: 'conll_bio'",
                        f"  input_path: '{input_path}'",
                        "  deduplicate_by_text: false",
                        "backend:",
                        "  mode: 'ner_api'",
                        "mapping:",
                        "  labels_yaml_path: null",
                        "logging:",
                        "  mlflow:",
                        "    enabled: false",
                        "    tracking_uri: 'http://localhost:5000'",
                        "    experiment_name: 'test'",
                        "  privacy:",
                        "    log_prompt_text: true",
                        "    log_llm_outputs: true",
                        "    log_raw_predictions: true",
                        "    redact_sensitive_fields: false",
                        "outputs:",
                        f"  base_dir: '{root / 'outputs'}'",
                    ]
                ),
                encoding="utf-8",
            )

            fake_predictions = [
                BackendPrediction(
                    sample_id="sample-1",
                    backend_mode="ner_api",
                    spans=[
                        CanonicalSpan(label="PER", start=0, end=10, text="Juan Perez")
                    ],
                    latency_ms=10.0,
                    raw_payload={"labels": []},
                )
            ]
            fake_samples = [
                CanonicalSample(
                    sample_id="sample-1",
                    text="Juan Perez",
                    tokens=["Juan", "Perez"],
                    gold_spans=[
                        CanonicalSpan(label="PER", start=0, end=10, text="Juan Perez")
                    ],
                    gold_bio=["B-PER", "I-PER"],
                )
            ]

            with (
                patch(
                    "aymurai.experiments.ner_testset_evaluation.runner.load_samples",
                    return_value=fake_samples,
                ),
                patch(
                    "aymurai.experiments.ner_testset_evaluation.runner.run_backend_inference",
                    return_value=(fake_predictions, [], {}),
                ),
            ):
                run_experiment(str(config_path))

            out = root / "outputs"
            self.assertTrue((out / "samples_gold.jsonl").exists())
            self.assertTrue((out / "predictions.jsonl").exists())
            self.assertTrue((out / "per_sample_scores.jsonl").exists())
            self.assertTrue((out / "metrics_summary.json").exists())
            self.assertTrue((out / "reports" / "label_metrics.csv").exists())
            self.assertTrue((out / "reports" / "token_relaxed_confusion.csv").exists())
            self.assertTrue((out / "feedback" / "perfect_prediction.jsonl").exists())
            self.assertTrue((out / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
