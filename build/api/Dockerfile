ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS api-base

ENV API_PORT=8899

WORKDIR /tmp

# Install python packages
COPY ./build/api/requirements.txt .
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt

# Clean
RUN rm -rf /tmp/*

WORKDIR /root

COPY ./src/aymurai/aymurai/api/main.py /usr/bin/main.py
COPY ./test /test

# Install aymurai
COPY ./src/aymurai /root/aymurai
RUN --mount=type=cache,target=/root/.cache \
    pip install ./aymurai
# FIXME: force install gdown 4.6.0 even when flair dependence is gdown==4.4.0
RUN  --mount=type=cache,target=/root/.cache,id=pip \
    pip install -U gdown==4.6.0


# COPY build/api/entrypoint.sh /entrypoint.sh
# CMD redis-server /etc/redis/redis.conf &\
#     if [ "$TEST_MODE" = "1" ]; \
#     then pytest --log-cli-level=ERROR --disable-warnings /usr/bin/main.py; \
#     else \
#         uvicorn --app-dir=/usr/bin main:api --reload --host=${API_HOST:-0.0.0.0} --port=${API_PORT:-8000}; \
#     fi
CMD if [ "$TEST_MODE" = "1" ]; \
    then pytest --log-cli-level=ERROR --disable-warnings /usr/bin/main.py; \
    else \
        uvicorn --app-dir=/usr/bin main:api --reload --host=${API_HOST:-0.0.0.0} --port=${API_PORT:-8000}; \
    fi

ENV CUDA_VISIBLE_DEVICES=-1


FROM api-base as api-prod

ENV TF_CPP_MIN_LOG_LEVEL=3
ENV TFHUB_CACHE_DIR=/resources/cache/tfhub_modules

# copy api resources
COPY ./resources/api /resources/api

# copy pipelines & run app startup to download models
COPY ./resources/pipelines/production /resources/pipelines/production
RUN python /usr/bin/main.py
