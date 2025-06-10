include .env
export $(shell sed 's/=.*//' .env)
include .env.common
export $(shell sed 's/=.*//' .env.common)



api-build:
	docker compose build aymurai-api-dev
api-run:
	docker compose run --service-ports aymurai-api-dev
api-pull:
	docker compose pull aymurai-api

api-full-build:
	docker compose build aymurai-api-full
api-full-run:
	docker compose run aymurai-api-full
api-full-pull:
	docker compose pull aymurai-api-full

stress-test:
	locust -f locustfile.py --host http://localhost:8899

alembic-regenerate:
	rm -rvf resources/cache/sqlite/* && \
	rm -rvf aymurai/database/versions/* && \
	cd aymurai && \
	uv run alembic revision --autogenerate -m "Create database" && \
	uv run alembic upgrade head