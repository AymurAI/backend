include .env
export $(shell sed 's/=.*//' .env)
include .env.common
export $(shell sed 's/=.*//' .env.common)

# Select which API service to control (override with API_SERVICE=aymurai-api-gpu)
API_SERVICE ?= aymurai-api
# Select which full API service to control (override with API_FULL_SERVICE=aymurai-api-full-gpu)
API_FULL_SERVICE ?= aymurai-api-full


api-build:
	docker compose build $(API_SERVICE)
api-run:
	docker compose run --service-ports $(API_SERVICE)
api-up:
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
	docker compose run --service-ports $(API_FULL_SERVICE)
api-full-up:
	docker compose up -d $(API_FULL_SERVICE)
api-full-stop:
	docker compose stop $(API_FULL_SERVICE)
api-full-logs:
	docker compose logs -f $(API_FULL_SERVICE)
api-full-pull:
	docker compose pull $(API_FULL_SERVICE)

stress-test:
	locust -f locustfile.py --host http://localhost:8899

alembic-regenerate:
	rm -rvf resources/cache/sqlite/* && \
	rm -rvf aymurai/database/versions/* && \
	cd aymurai && \
	uv run alembic revision --autogenerate -m "Create database" && \
	uv run alembic upgrade head

# --- Frontend build ---
FRONTEND_DIR=frontend
FRONTEND_DIST_DIR=frontend-dist

frontend-install:
	cd $(FRONTEND_DIR) && pnpm install

frontend-build: frontend-install
	cd $(FRONTEND_DIR) && pnpm run build:web
	# Copy build output to frontend-dist
	rm -rf $(FRONTEND_DIST_DIR)
	cp -r $(FRONTEND_DIR)/out/renderer $(FRONTEND_DIST_DIR)

frontend-clean:
	rm -rf $(FRONTEND_DIST_DIR)
