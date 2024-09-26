#!/bin/sh

# configure precommit
pre-commit install
chown $USER_NAME .git/hooks/pre-commit


# install src packages
sudo pip install --no-deps -e .
# Run the CMD, as the main container process
# exec "$@"
$@