#!/bin/sh

uv venv --python $PYTHON_VERSION .venv
uv sync --frozen

# configure precommit
uv run pre-commit install
chown $USER_NAME .git/hooks/pre-commit


# Run the CMD, as the main container process
# exec "$@"
$@