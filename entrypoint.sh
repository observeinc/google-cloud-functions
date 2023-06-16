#!/bin/bash
set -eo pipefail

if [ -n "${DEBUG:-}" ]; then
    set -x
fi

echo "Setting project"
gcloud config set project $PROJECT_ID

echo "Running gcloud auth application-default login"
gcloud auth application-default login

exec "$@"
