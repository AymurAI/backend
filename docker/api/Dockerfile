ARG UV_VERSION=0.5.10
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS astral-uv-source
FROM python:3.10-slim AS builder


COPY --from=astral-uv-sourcw /uv /uvx /bin/

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

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable

# install spacy models
RUN --mount=type=cache,target=/root/.cache,id=pip \
    python -m spacy download es_core_news_sm

# Copy the project into the intermediate image
ADD pyproject.toml uv.lock aymurai /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable




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

COPY --from=builder --chown=app:app /app/.venv /app/.venv

CMD fastapi run aymurai/api/main.py




FROM aymurai-api AS aymurai-api-full

ENV TF_CPP_MIN_LOG_LEVEL=3
ENV TFHUB_CACHE_DIR=resources/cache/tfhub_modules
ENV RESOURCES_BASEPATH=resources

# copy api resources
COPY ./resources/api resources/api

# copy pipelines & run app startup to download models
COPY ./resources/pipelines/production resources/pipelines/production
RUN python /packages/aymurai/api/main.py
