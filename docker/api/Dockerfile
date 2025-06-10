FROM python:3.10-slim AS builder

# install git
RUN apt-get update && apt-get install -y --no-install-recommends git && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --extra runtime

# Copy the package into the image
COPY aymurai /app/aymurai

# Sync the package
RUN --mount=type=bind,source=.git,target=.git \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-editable


# Stage - aymurai-api
# -------------------
FROM python:3.10-slim AS aymurai-api

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

# add es_AR locale but en_US is default
RUN apt update && apt install -y locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && sed -i -e 's/# es_AR.UTF-8 UTF-8/es_AR.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# install libreoffice
RUN apt update \
    && apt-get install -y --no-install-recommends \
    # antiword \
    libreoffice-writer \
    libreoffice-common \
    default-jre \
    libmagic1 \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder --chown=app:app /app/.venv /app/.venv

COPY resources/api/static /resources/api/static
COPY resources/pipelines /resources/pipelines

WORKDIR /app
CMD uv run fastapi run --port 8899 .venv/lib/python3.10/site-packages/aymurai/api/main.py




FROM aymurai-api AS aymurai-api-full

ENV TF_CPP_MIN_LOG_LEVEL=3
ENV TFHUB_CACHE_DIR=resources/cache/tfhub_modules
ENV RESOURCES_BASEPATH=resources

# copy api resources
COPY ./resources/api resources/api

# copy pipelines & run app startup to download models
COPY ./resources/pipelines/production resources/pipelines/production
RUN uv run python /app/.venv/lib/python3.10/site-packages/aymurai/api/main.py
