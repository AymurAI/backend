include .env
export $(shell sed 's/=.*//' .env)
include .env.common
export $(shell sed 's/=.*//' .env.common)



api-build:
	uv build
	docker compose build aymurai-api-dev
api-run:
	docker compose run --service-ports aymurai-api-dev

api-prod-build: api-build
	uv build
	docker compose build aymurai-api-prod
api-prod-run:
	docker compose run aymurai-api-prod
api-prod-push:
	docker tag ${API_IMAGE}-prod ${API_IMAGE}-prod:$(shell date +%F)
	docker push ${API_IMAGE}-prod
	docker push ${API_IMAGE}-prod:${shell date +%F}
api-prod-pull:
	docker pull ${API_IMAGE}-prod


stress-test:
	locust -f locustfile.py --host http://localhost:8899

alembic-regenerate:
	rm -rvf resources/cache/sqlite/* && \
	rm -rvf aymurai/database/versions/* && \
	cd aymurai && \
	uv run alembic revision --autogenerate -m "Create database" && \
	uv run alembic upgrade head