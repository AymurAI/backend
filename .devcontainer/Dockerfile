# syntax=docker/dockerfile:1.3

ARG CORE_IMAGE
FROM ${CORE_IMAGE}

ENV EDITOR=vim

ARG USER_NAME=vscode
ENV USER_NAME=${USER_NAME}

ARG USER_UID
ARG USER_GID

RUN apt-get update && apt-get install -y sudo && \
    apt-get autoremove -y && apt-get clean && rm -rf /tmp/* /var/tmp/* && rm -rf /var/lib/apt/lists/* && \
    groupadd --gid $USER_GID $USER_NAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USER_NAME && \
    usermod -aG sudo $USER_NAME && \
    echo $USER_NAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USER_NAME && \
    chmod 0440 /etc/sudoers.d/$USER_NAME

ENV SHELL=/usr/bin/zsh
RUN chsh $USER_NAME -s $SHELL

# Install docker
RUN curl -fsSL https://get.docker.com -o get-docker.sh \
    && sh ./get-docker.sh \
    && usermod -aG docker $USER_NAME



# Install dev dependences & tools
RUN apt update && apt install -y \
    htop \
    vim \
    git-lfs \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ssh \
    rsync \
    kmod \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*


# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
# COPY .devcontainer/requirements.txt .devcontainer/entrypoint.sh /home/$USER_NAME/


# coding dev packages
RUN --mount=type=cache,target=/root/.cache,id=pip \
    --mount=type=bind,source=.devcontainer/requirements.txt,target=/root/dev-requirements.txt \
    pip install -r /root/dev-requirements.txt \
    && rm -rf /home/$USER_NAME/requirements.txt

# Add /packages to the python path
ENV PYTHONPATH=/packages/core:$PYTHONPATH

# # install aymurai requirements
# ARG AYMURAI_EXTRA_PACKAGE=dev
# RUN --mount=type=bind,source=src/aymurai/setup.py,target=/root/aymurai/setup.py \
#     --mount=type=cache,target=/root/.cache,id=pip \
#     pip install Cython wheel \
#     && python /root/aymurai/setup.py egg_info \
#     && pip install $(parse-deps.py aymurai.egg-info/requires.txt -s $AYMURAI_EXTRA_PACKAGE) \
#     && rm -rf *.egg-info

COPY .devcontainer/entrypoint.sh /
RUN chmod +x /entrypoint.sh


USER $USER_NAME
WORKDIR /tmp
RUN sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"


# ENTRYPOINT ["/entrypoint.sh"]
