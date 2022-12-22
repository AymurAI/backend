ARG CORE_IMAGE


# ENV API_HOST=0.0.0.0
# ENV API_PORT=8000

FROM ${CORE_IMAGE} AS api-base

WORKDIR /tmp

# Install python packages
COPY ./build/api/requirements.txt .
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt

# Clean
RUN rm -rf /tmp/*

WORKDIR /root

COPY ./api/main.py /usr/bin/main.py
COPY ./test /test

# Install aymurai
COPY ./src/aymurai /root/aymurai
RUN --mount=type=cache,target=/root/.cache \
    pip install ./aymurai
# FIXME: force install gdown 4.6.0 even when flair dependence is gdown==4.4.0
RUN  --mount=type=cache,target=/root/.cache,id=pip \
    pip install -U gdown==4.6.0


CMD if [ "$TEST_MODE" = "1" ]; \
    then pytest --log-cli-level=ERROR --disable-warnings /usr/bin/main.py; \
    else \
        uvicorn --app-dir=/usr/bin main:api --reload --host=${API_HOST:-0.0.0.0} --port=${API_PORT:-8000}; \
    fi

ENV CUDA_VISIBLE_DEVICES=-1


FROM api-base as api-prod

COPY ./resources/pipelines/examples/flair-simple/pipeline.json /resources/pipelines/examples/pipelines/flair-simple/pipeline.json
COPY ./resources/cache/aymurai /resources/cache/aymurai
COPY ./resources/cache/tfhub_modules /resources/cache/tfhub_modules
# RUN pytest --log-cli-level=ERROR --disable-warnings /usr/bin/main.py
