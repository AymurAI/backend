# Experiments Setup

This guide walks through running the entity-disambiguation experiments with MLflow
tracking and MinIO artifacts.

## 1) Update the devcontainer

The devcontainer installs base dependencies via `uv`. The MLflow client lives in the
`mlops` dependency group, so install it after rebuilding the container:

```bash
uv sync --frozen --all-extras --group mlops
```

If you use VS Code, run "Dev Containers: Rebuild and Reopen in Container" first.

## 2) Configure environment

- Set MinIO credentials in `.env`:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
- Verify MLflow settings in `.env.common`:
  - `MLFLOW_TRACKING_URI`
  - `MLFLOW_S3_ENDPOINT_URL`
  - `MLFLOW_ARTIFACT_ROOT`

The experiment runner also uses:
- `API_BASE_URL` (defaults to `http://localhost:8899`)
- `REQUEST_TIMEOUT` (defaults to `300`)

## 3) Start services

```bash
make mlops-up
make ollama-up
make api-up
```

If you need the GPU services, set:
```bash
make ollama-up OLLAMA_SERVICE=ollama-gpu
make api-up API_SERVICE=aymurai-api-gpu
```

## 4) Pull the model

```bash
make ollama-pull MODEL=gemma3:270m
```

## 5) Run the experiment

```bash
make exp-run CONFIG=resources/experiments/entity-disambiguation/exp-gemma3-pv1.yaml
```

## Predictions vs. ground truth filenames

Ground-truth files are expected to end with `-test.json`, while predictions use
the same base name without the suffix.

Example:
- `document-1-test.json` (ground truth)
- `document-1.json` (prediction)

Predictions are written to disk (not logged as artifacts). MLflow logs:
- Run params (model, prompt IDs, dataset hash, etc.)
- Aggregate metrics and per-document scores (as an artifact)
- Prompt text (if enabled in config)

## 6) Access MLflow UI

If running remotely, forward the MLflow port:
```bash
ssh -L 5000:127.0.0.1:5000 user@remote-host
```

Then open `http://localhost:5000`.

## Config location

Experiment configs live under:
- `resources/experiments/entity-disambiguation/`

Use the template at `docs/experiments/base.yaml` when creating new experiment
configs. Copy it into `resources/experiments/entity-disambiguation/` and adjust
the model, prompts, and data paths as needed.

The main runner is:
- `aymurai/experiments/entity_disambiguation/runner.py`

## NER + LangExtract alignment experiment

Config template:
- `resources/experiments/ner-langextract-alignment/exp-template.yaml`

Run:

```bash
uv run --group mlops -- python -m aymurai.experiments.ner_langextract_alignment.runner \
  --config resources/experiments/ner-langextract-alignment/exp-template.yaml
```

Key outputs (under `outputs.base_dir`):
- `samples.jsonl`
- `llm_traces/traces.jsonl`
- `llm_traces/traces_summary.csv`
- `train_candidates.jsonl`
- `review_required.jsonl`
- `labelstudio/discrepancies.json`
- `labelstudio/agreements_qa_sample.json`

## NER/LangExtract holdout evaluation experiment

Config template:
- `resources/experiments/ner-holdout-evaluation/exp_template.yml`

Run:

```bash
uv run --group mlops -- python -m aymurai.experiments.ner_holdout_evaluation.runner \
  --config resources/experiments/ner-holdout-evaluation/exp_template.yml
```

Notes:
- `backend.mode` runs one backend per execution: `ner_api` or `langextract`.
- Dataset formats supported in `data.format`:
  - `conll_bio`
  - `hf_token_classification`
  - `span_jsonl`
- The experiment logs hybrid MLflow tracking:
  - classic params/metrics/artifacts
  - per-sample categorical feedback (`perfect_prediction`) as YES/NO

Key outputs (under `outputs.base_dir`):
- `samples_gold.jsonl`
- `predictions.jsonl`
- `per_sample_scores.jsonl`
- `metrics_summary.json`
- `reports/label_metrics.csv`
- `reports/token_relaxed_confusion.csv`
- `feedback/perfect_prediction.jsonl`
- `llm_traces/traces.jsonl` (only for `backend.mode=langextract`)
- `llm_traces/traces_summary.csv` (only for `backend.mode=langextract`)
- `manifest.json`
