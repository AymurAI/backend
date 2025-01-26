#!/bin/sh

# Ensure the .gitconfig file is included in the global git configuration
cp /tmp/.gitconfig ~/.gitconfig
git config --global commit.template ~/.gitmessage

uv sync --frozen --all-extras

# configure precommit
uv run pre-commit install
chown $USER_NAME .git/hooks/pre-commit


# Run the CMD, as the main container process
# exec "$@"
$@