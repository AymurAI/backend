ARG BASE_IMAGE
FROM $BASE_IMAGE AS core

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND noninteractive
ENV PATH=/usr/local/cuda/bin/:$PATH
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/:$LD_LIBRARY_PATH

ENV PIP_VERSION=23.2.1
ENV PYTHON_VERSION=3.10


# OS packages
RUN apt update \
    && apt install software-properties-common -y \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    zsh \
    git \
    curl \
    wget \
    unzip \
    cmake \
    apt-transport-https \
    gnupg \
    antiword \
    poppler-utils \
    automake \
    libtool \
    libleptonica-dev \
    pkg-config \
    libreoffice-writer \
    libreoffice-common \
    default-jre \
    python3-setuptools \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-distutils \
    # python3-pip \
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
# RUN wget https://bootstrap.pypa.io/get-pip.py \
#     && python get-pip.py


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


# add es_AR locale but en_US is default
RUN apt update && apt install -y locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && sed -i -e 's/# es_AR.UTF-8 UTF-8/es_AR.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8


# # Install Redis.
# RUN \
#   cd /tmp && \
#   wget http://download.redis.io/redis-stable.tar.gz && \
#   tar xvzf redis-stable.tar.gz && \
#   cd redis-stable && \
#   make && \
#   make install && \
#   cp -f src/redis-sentinel /usr/local/bin && \
#   mkdir -p /etc/redis && \
#   cp -f *.conf /etc/redis && \
#   rm -rf /tmp/redis-stable* && \
#   sed -i 's/^\(bind .*\)$/# \1/' /etc/redis/redis.conf && \
#   sed -i 's/^\(daemonize .*\)$/# \1/' /etc/redis/redis.conf && \
#   sed -i 's/^\(dir .*\)$/# \1\ndir \/data/' /etc/redis/redis.conf && \
#   sed -i 's/^\(logfile .*\)$/# \1/' /etc/redis/redis.conf && \
#   sed -i 's/^\(# maxmemory .*\)$/maxmemory 30000000/' /etc/redis/redis.conf && \
#   sed -i 's/^\(# maxmemory-policy .*\)$/maxmemory-policy volatile-lru/' /etc/redis/redis.conf


# # Define mountable directories.
VOLUME ["/data"]

WORKDIR /root
CMD ["/bin/bash"]
