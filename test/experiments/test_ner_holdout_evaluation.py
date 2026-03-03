from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.experiments.ner_holdout_evaluation.backends import run_backend_inference
from aymurai.experiments.ner_holdout_evaluation.config import (
    NERHoldoutEvaluationConfig,
)
from aymurai.experiments.ner_holdout_evaluation.loaders import load_samples
from aymurai.experiments.ner_holdout_evaluation.metrics import evaluate_predictions
from aymurai.experiments.ner_holdout_evaluation.mlflow_logging import (
    build_feedback_records,
)
from aymurai.experiments.ner_holdout_evaluation.runner import run_experiment
from aymurai.experiments.ner_holdout_evaluation.types import (
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
) -> NERHoldoutEvaluationConfig:
    payload = {
        "experiment": {
            "name": "ner-holdout-evaluation",
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
                "experiment_name": "ner-holdout-evaluation",
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
            "examples_yaml_path": "resources/langextract/ner_alignment_examples.yml",
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

    return NERHoldoutEvaluationConfig.model_validate(payload)


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
                "aymurai.experiments.ner_holdout_evaluation.backends.call_anonymizer_predict",
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

    def test_run_ner_api_backend_emits_per_sample_trace_with_active_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "test.conll"
            input_path.write_text("Juan B-PER\n\n", encoding="utf-8")

            config = build_config(
                input_path=str(input_path),
                data_format="conll_bio",
                outputs_base=str(Path(tmp_dir) / "out"),
            )
            samples = [
                CanonicalSample(
                    sample_id="s1", text="Juan Perez", tokens=["Juan", "Perez"]
                )
            ]

            class _FakeSpan:
                def __init__(self, trace_id):
                    self.request_id = trace_id
                    self.trace_id = trace_id
                    self.inputs = None
                    self.outputs = None
                    self.attributes = {}
                    self.exceptions = []

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def set_inputs(self, inputs):
                    self.inputs = inputs

                def set_outputs(self, outputs):
                    self.outputs = outputs

                def set_attributes(self, attributes):
                    self.attributes.update(attributes)

                def record_exception(self, exc):
                    self.exceptions.append(str(exc))

            outer_span = _FakeSpan("tr-sample")
            inner_span = _FakeSpan("tr-sample")

            with (
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.mlflow.active_run",
                    return_value=object(),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.mlflow.start_span",
                    side_effect=[outer_span, inner_span],
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.call_anonymizer_predict",
                    return_value=(
                        {
                            "labels": [
                                {
                                    "text": "Juan Perez",
                                    "start_char": 0,
                                    "end_char": 10,
                                    "attrs": {
                                        "aymurai_label": "PER",
                                        "aymurai_method": "ner/flair",
                                    },
                                }
                            ]
                        },
                        12.0,
                    ),
                ),
            ):
                predictions, traces, sample_trace_ids = run_backend_inference(
                    samples, config
                )

            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0].trace_ids, ["tr-sample"])
            self.assertEqual(sample_trace_ids, {"s1": "tr-sample"})
            self.assertEqual(len(traces), 1)
            self.assertEqual(traces[0].trace_id, "tr-sample")
            self.assertEqual(traces[0].provider, "aymurai")
            self.assertEqual(traces[0].model, "ner/flair")
            self.assertEqual(traces[0].parsed_output["labels"][0]["text"], "Juan Perez")
            self.assertEqual(
                outer_span.inputs, {"sample_id": "s1", "text": "Juan Perez"}
            )
            self.assertEqual(
                outer_span.outputs["spans"][0],
                {
                    "label": "PER",
                    "start": 0,
                    "end": 10,
                    "text": "Juan Perez",
                },
            )
            self.assertEqual(outer_span.attributes["backend_mode"], "ner_api")
            self.assertNotIn("sample_id", outer_span.outputs)
            self.assertNotIn("backend_mode", outer_span.outputs)
            self.assertEqual(inner_span.inputs["path"], "/anonymizer/predict")
            self.assertEqual(inner_span.inputs["use_cache"], False)
            self.assertEqual(inner_span.outputs["labels"][0]["text"], "Juan Perez")
            self.assertEqual(inner_span.attributes["entity_count"], 1)

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
                    "aymurai.experiments.ner_holdout_evaluation.backends.load_examples_from_yaml",
                    return_value=[object()],
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.build_tracing_model",
                    return_value=object(),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.run_langextract",
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

    def test_run_langextract_backend_uses_canonical_sample_inputs_with_active_run(self):
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
                trace_id="tr-sample",
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

            class _FakeSpan:
                def __init__(self, trace_id):
                    self.request_id = trace_id
                    self.trace_id = trace_id
                    self.inputs = None
                    self.outputs = None
                    self.attributes = {}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def set_inputs(self, inputs):
                    self.inputs = inputs

                def set_outputs(self, outputs):
                    self.outputs = outputs

                def set_attributes(self, attributes):
                    self.attributes.update(attributes)

                def set_status(self, _status):
                    return None

            outer_span = _FakeSpan("tr-sample")

            with (
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.mlflow.active_run",
                    return_value=object(),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.mlflow.start_span",
                    return_value=outer_span,
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.load_examples_from_yaml",
                    return_value=[object()],
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.build_tracing_model",
                    return_value=object(),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.backends.run_langextract",
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

            self.assertEqual(predictions[0].trace_ids, ["tr-sample"])
            self.assertEqual(sample_trace_ids["s1"], "tr-sample")
            self.assertEqual(len(traces), 1)
            self.assertEqual(
                outer_span.inputs, {"sample_id": "s1", "text": "Juan Perez"}
            )
            self.assertEqual(outer_span.attributes["backend_mode"], "langextract")
            self.assertEqual(outer_span.attributes["model_id"], "qwen3:8b")
            self.assertNotIn("sample_id", outer_span.outputs)
            self.assertNotIn("backend_mode", outer_span.outputs)
            self.assertEqual(outer_span.outputs["spans"][0]["label"], "PER")


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
        self.assertTrue(all(score.entity_match_rate == 1.0 for score in sample_scores))
        self.assertEqual(summary.metrics["strict_f1"], 1.0)
        self.assertEqual(summary.metrics["perfect_span_set_rate"], 1.0)
        self.assertGreaterEqual(summary.metrics["token_relaxed_micro_f1"], 0.0)
        self.assertTrue(isinstance(confusion, list))

    def test_metrics_empty_gold_and_prediction_score_as_perfect(self):
        samples = [
            CanonicalSample(
                sample_id="s1",
                text="Sin entidades",
                tokens=["Sin", "entidades"],
                gold_spans=[],
                gold_bio=["O", "O"],
            )
        ]
        predictions = [
            BackendPrediction(sample_id="s1", backend_mode="ner_api", spans=[])
        ]

        sample_scores, summary, _ = evaluate_predictions(
            samples,
            predictions,
            include_token_relaxed=False,
        )

        self.assertEqual(len(sample_scores), 1)
        self.assertTrue(sample_scores[0].perfect_span_set)
        self.assertEqual(sample_scores[0].entity_match_rate, 1.0)
        self.assertEqual(sample_scores[0].precision, 1.0)
        self.assertEqual(sample_scores[0].recall, 1.0)
        self.assertEqual(sample_scores[0].f1, 1.0)
        self.assertEqual(summary.metrics["strict_f1"], 0.0)
        self.assertEqual(summary.metrics["perfect_span_set_rate"], 1.0)

    def test_metrics_tolerate_boundary_punctuation_differences(self):
        samples = [
            CanonicalSample(
                sample_id="s1",
                text="28 de octubre de 2021.",
                tokens=["28", "de", "octubre", "de", "2021."],
                gold_spans=[
                    CanonicalSpan(
                        label="FECHA",
                        start=0,
                        end=21,
                        text="28 de octubre de 2021.",
                        normalized_text="28 de octubre de 2021",
                        alt_start_char=0,
                        alt_end_char=20,
                    )
                ],
                gold_bio=["B-FECHA", "I-FECHA", "I-FECHA", "I-FECHA", "I-FECHA"],
            )
        ]
        predictions = [
            BackendPrediction(
                sample_id="s1",
                backend_mode="langextract",
                spans=[
                    CanonicalSpan(
                        label="FECHA",
                        start=0,
                        end=20,
                        text="28 de octubre de 2021",
                        normalized_text="28 de octubre de 2021",
                        alt_start_char=0,
                        alt_end_char=20,
                    )
                ],
            )
        ]

        sample_scores, summary, _ = evaluate_predictions(
            samples,
            predictions,
            include_token_relaxed=False,
        )

        self.assertEqual(len(sample_scores), 1)
        self.assertTrue(sample_scores[0].perfect_span_set)
        self.assertEqual(sample_scores[0].entity_match_rate, 1.0)
        self.assertEqual(summary.metrics["strict_f1"], 1.0)

    def test_feedback_records_use_yes_no(self):
        sample_scores = [
            MagicMock(
                sample_id="s1",
                perfect_span_set=True,
                entity_match_rate=1.0,
                precision=1.0,
                recall=1.0,
                f1=1.0,
                tp=2,
                fp=0,
                fn=0,
                token_relaxed_accuracy=1.0,
            ),
            MagicMock(
                sample_id="s2",
                perfect_span_set=False,
                entity_match_rate=0.5,
                precision=1.0,
                recall=0.5,
                f1=2.0 / 3.0,
                tp=1,
                fp=0,
                fn=1,
                token_relaxed_accuracy=0.75,
            ),
        ]
        records, entities = build_feedback_records(
            sample_scores,
            sample_trace_ids={"s1": "trace-1"},
            backend_mode="ner_api",
        )

        self.assertEqual(len(records), 12)
        by_sample_and_name = {(r.sample_id, r.name): r for r in records}
        self.assertEqual(by_sample_and_name[("s1", "perfect_prediction")].value, "yes")
        self.assertEqual(by_sample_and_name[("s2", "perfect_prediction")].value, "no")
        self.assertEqual(
            by_sample_and_name[("s1", "entity_match_rate")].value,
            1.0,
        )
        self.assertEqual(
            by_sample_and_name[("s2", "entity_match_rate")].value,
            0.5,
        )
        self.assertEqual(
            by_sample_and_name[("s2", "strict_recall")].value,
            0.5,
        )
        self.assertEqual(len(entities), 12)


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
                        "  name: 'ner-holdout-evaluation'",
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
                    "aymurai.experiments.ner_holdout_evaluation.runner.load_samples",
                    return_value=fake_samples,
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.iter_backend_inference",
                    return_value=iter([(fake_samples[0], fake_predictions[0], [])]),
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

    def test_runner_starts_mlflow_before_backend_inference(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_path = root / "test.conll"
            input_path.write_text("Juan B-PER\nPerez I-PER\n\n", encoding="utf-8")
            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "experiment:",
                        "  name: 'ner-holdout-evaluation'",
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
                        "    enabled: true",
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
            events: list[str] = []

            class _NoopContext:
                def __enter__(self):
                    events.append("start_run_enter")
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _load_samples(_config):
                events.append("load_samples")
                return fake_samples

            def _iter_backend_inference(_samples, _config):
                events.append("iter_backend_inference")
                yield fake_samples[0], fake_predictions[0], []

            with (
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.configure_mlflow",
                    return_value=(True, "exp-1"),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.mlflow.start_run",
                    return_value=_NoopContext(),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.mlflow.set_tags"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.mlflow.log_param"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.log_run_metadata"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.log_feedback_to_mlflow"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.safe_log_artifact"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.safe_log_artifacts"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.load_samples",
                    side_effect=_load_samples,
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.iter_backend_inference",
                    side_effect=_iter_backend_inference,
                ),
            ):
                run_experiment(str(config_path))

            self.assertEqual(
                events,
                ["start_run_enter", "load_samples", "iter_backend_inference"],
            )

    def test_runner_logs_feedback_incrementally(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_path = root / "test.conll"
            input_path.write_text("Juan B-PER\nPerez I-PER\n\n", encoding="utf-8")
            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "experiment:",
                        "  name: 'ner-holdout-evaluation'",
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
                        "    enabled: true",
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

            fake_samples = [
                CanonicalSample(
                    sample_id="sample-1",
                    text="Juan Perez",
                    tokens=["Juan", "Perez"],
                    gold_spans=[
                        CanonicalSpan(label="PER", start=0, end=10, text="Juan Perez")
                    ],
                    gold_bio=["B-PER", "I-PER"],
                ),
                CanonicalSample(
                    sample_id="sample-2",
                    text="Sin entidades",
                    tokens=["Sin", "entidades"],
                    gold_spans=[],
                    gold_bio=["O", "O"],
                ),
            ]
            fake_predictions = [
                BackendPrediction(
                    sample_id="sample-1",
                    backend_mode="ner_api",
                    spans=[
                        CanonicalSpan(label="PER", start=0, end=10, text="Juan Perez")
                    ],
                    latency_ms=10.0,
                    raw_payload={"labels": []},
                    trace_ids=["trace-1"],
                ),
                BackendPrediction(
                    sample_id="sample-2",
                    backend_mode="ner_api",
                    spans=[],
                    latency_ms=5.0,
                    raw_payload={"labels": []},
                    trace_ids=["trace-2"],
                ),
            ]

            class _NoopContext:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _iter_backend_inference(_samples, _config):
                yield fake_samples[0], fake_predictions[0], []
                yield fake_samples[1], fake_predictions[1], []

            with (
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.configure_mlflow",
                    return_value=(True, "exp-1"),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.mlflow.start_run",
                    return_value=_NoopContext(),
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.mlflow.set_tags"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.mlflow.log_param"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.log_run_metadata"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.safe_log_artifact"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.safe_log_artifacts"
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.load_samples",
                    return_value=fake_samples,
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.iter_backend_inference",
                    side_effect=_iter_backend_inference,
                ),
                patch(
                    "aymurai.experiments.ner_holdout_evaluation.runner.log_feedback_to_mlflow"
                ) as mock_log_feedback,
            ):
                run_experiment(str(config_path))

            self.assertEqual(mock_log_feedback.call_count, 2)


if __name__ == "__main__":
    unittest.main()
