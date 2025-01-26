# syntax=docker/dockerfile:1.3
ARG UV_VERSION=0.5.10
ARG CORE_IMAGE=ubuntu:noble

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS astral-uv-source
FROM ${CORE_IMAGE} as devcontainer


ENV EDITOR=vim

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND noninteractive
ENV PATH=/usr/local/cuda/bin/:$PATH
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/:$LD_LIBRARY_PATH

ARG PYTHON_VERSION=3.10
ENV PYTHON_VERSION=${PYTHON_VERSION}
ENV UV_VERSION=${UV_VERSION}
ENV UV_PYTHON_PREFERENCE=system

# add es_AR locale but en_US is default
RUN apt update && apt install -y locales \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && sed -i -e 's/# es_AR.UTF-8 UTF-8/es_AR.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# Install basic tools
RUN apt update \
    && apt install software-properties-common -y \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    # utils
    ssh \
    rsync \
    acl \
    zsh \
    htop \
    make \
    vim \
    curl \
    sudo \
    git-core \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python3-setuptools \
    ca-certificates \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*

RUN rm -f /usr/lib/python${PYTHON_VERSION}/EXTERNALLY-MANAGED
RUN update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

ARG DEVCONTAINER_USER=ubuntu
RUN usermod -aG sudo $DEVCONTAINER_USER \
    && passwd -d $DEVCONTAINER_USER

ENV SHELL=/usr/bin/zsh
RUN chsh $DEVCONTAINER_USER -s $SHELL

# Install docker
RUN curl -fsSL https://get.docker.com | sh && \
    usermod -aG docker $DEVCONTAINER_USER

# Install dev dependences & tools
RUN apt update && apt install -y \
    apt-transport-https \
    lsb-release \
    gnupg \
    kmod \
    # antiword \
    # LibreOffice deps
    libreoffice-writer \
    libreoffice-common \
    default-jre \
    # Libmagic
    libmagic1 \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*



WORKDIR /tmp

# Install UV & python
COPY --from=astral-uv-source /uv /uvx /bin/

# Install dependencies
USER $DEVCONTAINER_USER
# COPY --from=builder --chown=$USER_NAME:$USER_NAME /tmp/venv /home/$USER_NAME/.venv
# ENV PYTHONPATH=/home/$USER_NAME/.venv/lib/python${PYTHON_VERSION}/site-packages:$PYTHONPATH

RUN sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"


# Custom Zsh configurations
RUN echo "autoload bashcompinit && bashcompinit" >> ~/.zshrc && \
    echo "autoload -Uz compinit && compinit" >> ~/.zshrc && \
    echo "sudo setfacl -m u:ubuntu:rw /var/run/docker.sock" >> ~/.zshrc


WORKDIR /workspace
COPY .devcontainer/entrypoint.sh /home/$DEVCONTAINER_USER/

ENV UV_CACHE_DIR=/resources/cache/uv