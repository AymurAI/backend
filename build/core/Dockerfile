FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND noninteractive
ENV PATH=/usr/local/cuda/bin/:$PATH
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/:$LD_LIBRARY_PATH

ENV PIP_VERSION=22.2.2
ENV PYTHON_VERSION=3.10

ENV PYTORCH_VERSION=1.12.1
ENV TORCH_PIP_INDEX=https://download.pytorch.org/whl/cu113
ENV APEX_VERSION=22.03
ENV TESSERACT_VERSION=5.2.0

# OS packages
RUN apt update \
    && apt install software-properties-common -y \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    zsh \
    git-lfs \
    git \
    curl \
    wget \
    unzip \
    cmake \
    python3-setuptools \
    apt-transport-https \
    gnupg \
    antiword \
    poppler-utils \
    automake \
    # ca-certificates \
    # g++ \
    libtool \
    libleptonica-dev \
    pkg-config \
    # tesseract-ocr \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-distutils \
    build-essential \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*


# set default python version
RUN update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

WORKDIR /tmp

# install pip
RUN wget https://github.com/pypa/pip/archive/refs/tags/${PIP_VERSION}.zip \
    && unzip ${PIP_VERSION}.zip \
    && cd pip-${PIP_VERSION} \
    && python setup.py install

# install pytorch
# RUN --mount=type=cache,target=/root/.cache,id=pip \
    # pip install torch==${PYTORCH_VERSION} --extra-index-url ${TORCH_PIP_INDEX}

# install apex
# RUN git clone https://github.com/NVIDIA/apex \
#     && cd apex && git checkout ${APEX_VERSION} \
#     && pip install -v --disable-pip-version-check --no-cache-dir --global-option="--cpp_ext" --global-option="--cuda_ext" ./

# Build and install tesseract
# RUN wget https://github.com/tesseract-ocr/tesseract/archive/${TESSERACT_VERSION}.tar.gz \
#     && tar -xzf ${TESSERACT_VERSION}.tar.gz && cd tesseract-${TESSERACT_VERSION} \
#     && ./autogen.sh && ./configure \
#     && make -j && make install && ldconfig

# # Download tesseract models
# RUN cd /usr/local/share/tessdata \
#     # && wget https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata \
#     && wget https://github.com/tesseract-ocr/tessdata/raw/main/spa.traineddata


# copy devs scripts
COPY build/core/parse-deps.py /bin/
RUN chmod +x /bin/parse-deps.py

# install aymurai requirements
RUN --mount=type=bind,source=src/aymurai/setup.py,target=/root/aymurai/setup.py \
    --mount=type=cache,target=/root/.cache,id=pip \
    pip install Cython wheel \
    && python /root/aymurai/setup.py egg_info \
    && pip install $(parse-deps.py aymurai.egg-info/requires.txt) \
    && rm -rf *.egg-info

# # install spacy models
RUN --mount=type=cache,target=/root/.cache,id=pip \
    python -m spacy download es_core_news_sm

# FIXME: force install gdown 4.6.0 even when flair dependence is gdown==4.4.0
RUN  --mount=type=cache,target=/root/.cache,id=pip \
    pip install -U gdown==4.6.0
# RUN --mount=type=cache,target=/root/.cache,id=pip \
#     python -m spacy download es_dep_news_trf


# add es_AR locale but en_US is default
RUN apt update && apt install -y locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && sed -i -e 's/# es_AR.UTF-8 UTF-8/es_AR.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8


WORKDIR /root
CMD ["/bin/bash"]