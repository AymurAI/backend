include .env
export $(shell sed 's/=.*//' .env)
include .env.common
export $(shell sed 's/=.*//' .env.common)


api-build:
	docker compose build aymurai-api
api-run:
	docker compose run --service-ports aymurai-api
api-pull:
	docker compose pull aymurai-api

api-full-build:
	docker compose build aymurai-api-full
api-full-run:
	docker compose run --service-ports aymurai-api-full
api-full-pull:
	docker compose pull aymurai-api-full

ollama-up:
	docker compose up -d --no-recreate ollama

ollama-stop:
	docker compose stop ollama

ollama-restart:
	docker compose restart ollama

ollama-pull:
ifndef MODEL
	$(error MODEL variable is required, e.g. make ollama-pull MODEL=llama3)
endif
	docker compose up -d --no-recreate ollama
	docker compose exec ollama ollama pull $(MODEL)

ollama-run:
ifndef MODEL
	$(error MODEL variable is required, e.g. make ollama-run MODEL=llama3)
endif
	docker compose up -d --no-recreate ollama
	docker compose exec -it ollama ollama run $(MODEL)

ollama-list:
	docker compose up -d --no-recreate ollama
	docker compose exec ollama ollama list

ollama-rm:
ifndef MODEL
	$(error MODEL variable is required, e.g. make ollama-rm MODEL=llama3)
endif
	docker compose up -d --no-recreate ollama
	docker compose exec ollama ollama rm $(MODEL)

stress-test:
	locust -f locustfile.py --host http://localhost:8899

alembic-regenerate:
	rm -rvf resources/cache/sqlite/* && \
	rm -rvf aymurai/database/versions/* && \
	cd aymurai && \
	uv run alembic revision --autogenerate -m "Create database" && \
	uv run alembic upgrade head
