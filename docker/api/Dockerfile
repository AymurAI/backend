# -------------------
# Build Stage
# -------------------
FROM python:3.10-slim AS builder

# Install Git
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Setup working directory
WORKDIR /app

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --extra runtime

# Copy application code
COPY aymurai /app/aymurai

# Finalize package installation
RUN --mount=type=bind,source=.git,target=.git \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-editable


# -------------------
# Base API Stage
# -------------------
FROM python:3.10-slim AS aymurai-api

# Set environment variables
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

# Configure locales
RUN apt update && \
    apt install -y locales && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# es_AR.UTF-8 UTF-8/es_AR.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8

# Set locale environment
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Install LibreOffice for document processing
RUN apt update && \
    apt-get install -y --no-install-recommends \
        libreoffice-writer \
        libreoffice-common \
        default-jre \
        libmagic1 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /tmp/* /var/tmp/* && \
    rm -rf /var/lib/apt/lists/*

# Copy UV tool and virtual environment
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy static resources
COPY resources/api/static /resources/api/static
COPY resources/pipelines /resources/pipelines

# Set working directory
WORKDIR /app

# Define start command
CMD uv run fastapi run --port 8899 .venv/lib/python3.10/site-packages/aymurai/api/main.py


# -----------------------------
# Full API Stage (with models)
# -----------------------------
FROM aymurai-api AS aymurai-api-full

# Configure TensorFlow and resources
ENV TF_CPP_MIN_LOG_LEVEL=3 \
    TFHUB_CACHE_DIR=resources/cache/tfhub_modules \
    RESOURCES_BASEPATH=resources

# Copy additional resources
COPY ./resources/api resources/api
COPY ./resources/pipelines/production resources/pipelines/production

# Initialize application to download models
RUN uv run python /app/.venv/lib/python3.10/site-packages/aymurai/api/main.py
