include .env
export $(shell sed 's/=.*//' .env)
include .env.common
export $(shell sed 's/=.*//' .env.common)

# Select which Ollama service to control (ollama or ollama-gpu)
OLLAMA_SERVICE ?= ollama
OLLAMA_CONTAINER := $(shell docker ps -q -f name=^$(OLLAMA_SERVICE)$$)

# Select which API service to control (override with API_SERVICE=aymurai-api-gpu)
API_SERVICE ?= aymurai-api
# Select which full API service to control (override with API_FULL_SERVICE=aymurai-api-full-gpu)
API_FULL_SERVICE ?= aymurai-api-full

api-build:
	docker compose build $(API_SERVICE)
api-run:
	@if [ "$(API_SERVICE)" = "aymurai-api-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose run --service-ports $(API_SERVICE)
api-up:
	@if [ "$(API_SERVICE)" = "aymurai-api-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose up -d $(API_SERVICE)
api-stop:
	docker compose stop $(API_SERVICE)
api-logs:
	docker compose logs -f $(API_SERVICE)
api-pull:
	docker compose pull $(API_SERVICE)

api-full-build:
	docker compose build $(API_FULL_SERVICE)
api-full-run:
	@if [ "$(API_FULL_SERVICE)" = "aymurai-api-full-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose run --service-ports $(API_FULL_SERVICE)
api-full-up:
	@if [ "$(API_FULL_SERVICE)" = "aymurai-api-full-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose up -d $(API_FULL_SERVICE)
api-full-stop:
	docker compose stop $(API_FULL_SERVICE)
api-full-logs:
	docker compose logs -f $(API_FULL_SERVICE)
api-full-pull:
	docker compose pull $(API_FULL_SERVICE)

ollama-up:
	@if [ "$(OLLAMA_SERVICE)" = "ollama-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose up -d --no-recreate $(OLLAMA_SERVICE)

ollama-stop:
	docker compose stop $(OLLAMA_SERVICE)

ollama-restart:
	docker compose restart $(OLLAMA_SERVICE)

ollama-pull:
ifndef MODEL
	$(error MODEL variable is required, e.g. make ollama-pull MODEL=llama3)
endif
ifndef OLLAMA_CONTAINER
	$(error Ollama container '$(OLLAMA_SERVICE)' is not running. Start it first with 'make ollama-up OLLAMA_SERVICE=$(OLLAMA_SERVICE)')
endif
	docker exec $(OLLAMA_SERVICE) ollama pull $(MODEL)

ollama-run:
ifndef MODEL
	$(error MODEL variable is required, e.g. make ollama-run MODEL=llama3)
endif
	@if [ "$(OLLAMA_SERVICE)" = "ollama-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose up -d --no-recreate $(OLLAMA_SERVICE)
	docker compose exec -it $(OLLAMA_SERVICE) ollama run $(MODEL)

ollama-list:
	@if [ "$(OLLAMA_SERVICE)" = "ollama-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose up -d --no-recreate $(OLLAMA_SERVICE)
	docker compose exec $(OLLAMA_SERVICE) ollama list

ollama-rm:
ifndef MODEL
	$(error MODEL variable is required, e.g. make ollama-rm MODEL=llama3)
endif
	@if [ "$(OLLAMA_SERVICE)" = "ollama-gpu" ]; then \
		docker compose stop ollama || true; \
	else \
		docker compose stop ollama-gpu || true; \
	fi
	docker compose up -d --no-recreate $(OLLAMA_SERVICE)
	docker compose exec $(OLLAMA_SERVICE) ollama rm $(MODEL)

mlops-up:
	docker compose up -d postgres minio minio-mc mlflow

mlops-stop:
	docker compose stop mlflow minio minio-mc postgres

mlops-logs:
	docker compose logs -f mlflow

exp-run:
ifndef CONFIG
	$(error CONFIG variable is required, e.g. make exp-run CONFIG=resources/experiments/entity-disambiguation/exp-gemma3-pv1.yaml)
endif
	uv run --group mlops -- python -m aymurai.experiments.entity_disambiguation.runner --config $(CONFIG)

export MLFLOW_TRACKING_URI=http://localhost:5005
exp-run-ner-holdout:
ifndef CONFIG
	$(error CONFIG variable is required, e.g. make exp-run-ner-holdout CONFIG=resources/experiments/ner-holdout-evaluation/ner_baseline.yml)
endif
	uv run --group mlops -- python -m aymurai.experiments.ner_holdout_evaluation.runner --config $(CONFIG)

export MLFLOW_TRACKING_URI=http://localhost:5005
exp-run-ner-langextract-alignment:
ifndef CONFIG
	$(error CONFIG variable is required, e.g. make exp-run-ner-langextract-alignment CONFIG=resources/experiments/ner-langextract-alignment/exp-template.yml)
endif
	uv run --group mlops -- python -m aymurai.experiments.ner_langextract_alignment.runner --config $(CONFIG)

stress-test:
	locust -f locustfile.py --host http://localhost:8899

alembic-regenerate:
	rm -rvf resources/cache/sqlite/* && \
	rm -rvf aymurai/database/versions/* && \
	cd aymurai && \
	uv run alembic revision --autogenerate -m "Create database" && \
	uv run alembic upgrade head
