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
- `DOCUMENT_API_BASE_URL` (defaults to `http://localhost:8899`)
- `DOCUMENT_REQUEST_TIMEOUT` (defaults to `30`)

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

The main runner is:
- `aymurai/experiments/entity_disambiguation/runner.py`
