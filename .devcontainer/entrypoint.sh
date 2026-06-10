#!/bin/sh

# install dependencies
uv sync --frozen --all-extras --all-groups

# configure precommit
uv run pre-commit install

# Run the CMD, as the main container process
# exec "$@"
$@
