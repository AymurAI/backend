include .env
export $(shell sed 's/=.*//' .env)
include .env.common
export $(shell sed 's/=.*//' .env.common)


core-build:
	docker compose build aymurai-core
	docker tag ${CORE_IMAGE_CUDA}:latest aymurai-core-gpu:latest
core-run:
	docker compose run aymurai-core

redis-run:
	docker compose -f .devcontainer/docker-compose.yml run redis

dev-build: core-build redis-run
	docker compose -f .devcontainer/docker-compose.yml build devcontainer-gpu
dev-build-cpu: core-build redis-run
	docker compose -f .devcontainer/docker-compose.yml build devcontainer


jupyter-run: dev-build redis-run
	docker compose -f .devcontainer/docker-compose.yml run devcontainer-gpu \
		jupyter-lab /workspace --no-browser
jupyter-run-cpu: dev-build-cpu redis-run
	docker compose -f .devcontainer/docker-compose.yml run devcontainer \
		jupyter-lab /workspace --no-browser

core-cpu-build:
	docker compose build aymurai-core-cpu
core-cpu-run:
	docker compose run aymurai-core-cpu


api-build: core-cpu-build
	docker compose build aymurai-api-dev
api-run:
	docker compose run --service-ports aymurai-api-dev
api-test:
	docker compose run \
			-e TEST_MODE=1 \
			-e LOG_LEVEL=error \
		aymurai-api-dev

api-prod-build: api-build
	docker compose build aymurai-api-prod
api-prod-run:
	docker run -p 8899:8899 --hostname=aymurai-api-prod ${API_IMAGE}-prod
api-prod-push:
	docker tag ${API_IMAGE}-prod ${API_IMAGE}-prod:$(shell date +%F)
	docker push ${API_IMAGE}-prod
	docker push ${API_IMAGE}-prod:${shell date +%F}
api-prod-pull:
	docker pull ${API_IMAGE}-prod