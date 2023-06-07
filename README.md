# google-cloud-functions

This repository contains the source code for the Observe Google Cloud Function(s).
The code fetches data from various GCP REST APIs and forwards it to Pub/Sub.
The semi-structured data in Pub/Sub is eventually parsed in Observe.

See https://www.notion.so/observeinc/GCP-collection-4af5eaa49951466fad879acfbc2c6cd9#107096e7e8794d5babc8ceec653a63ab
for info on contributing to this repo.

# Running locally

export PARENT=projects/YOUR_PROJECT_ID
export TOPIC_ID=projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME

python3 -m venv .venv

source .venv/bin/activate

pip3 install -r requirements.txt

python3 -c 'from main import main; main("")'

python3 -c 'from main import project_main; project_main("")'