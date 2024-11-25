FROM python:3.10-slim AS aymurai-api
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

ENV CUDA_VISIBLE_DEVICES=-1
ENV API_PORT=8899

WORKDIR /tmp

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
    antiword \
    libreoffice-writer \
    libreoffice-common \
    default-jre \
    libmagic1 \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*

# Add /packages to the python path
ENV PYTHONPATH=/packages:$PYTHONPATH
COPY --from=aymurai-core-cpu /packages/core /packages

# install spacy models
RUN --mount=type=cache,target=/root/.cache,id=pip \
    python -m spacy download es_core_news_sm

# install aymurai
COPY ./aymurai /tmp/aymurai
COPY ./requirements.txt ./pyproject.toml /tmp/
RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,source=.git,target=/tmp/.git \
    ls -lha .git && \
    pip install --no-cache-dir setuptools-scm && \
    pip install /tmp --no-deps --target=/packages
COPY ./aymurai /packages/aymurai/

# install fastapi-cli
RUN pip install --no-cache-dir uvicorn fastapi-cli

WORKDIR /packages
COPY ./test /test


# Run api
# FIXME: remove test from here
CMD if [ "$TEST_MODE" = "1" ]; \
    then pytest --log-cli-level=ERROR --disable-warnings /usr/bin/main.py; \
    else \
        # uvicorn --app-dir=/usr/bin main:api --reload --host=${API_HOST:-0.0.0.0} --port=${API_PORT:-8000}; \
        fastapi run aymurai/api/main.py --port=${API_PORT:-8000}; \
    fi



FROM aymurai-api AS aymurai-prod

ENV TF_CPP_MIN_LOG_LEVEL=3
ENV TFHUB_CACHE_DIR=resources/cache/tfhub_modules

# copy api resources
COPY ./resources/api resources/api

# copy pipelines & run app startup to download models
COPY ./resources/pipelines/production resources/pipelines/production
RUN python /packages/aymurai/api/main.py
