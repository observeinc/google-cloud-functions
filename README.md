# google-cloud-functions

This repository contains the source code for the Observe Google Cloud Function(s).
The code fetches data from various GCP REST APIs and forwards it to Pub/Sub.
The semi-structured data in Pub/Sub is eventually parsed in Observe.

See https://www.notion.so/observeinc/GCP-collection-4af5eaa49951466fad879acfbc2c6cd9#107096e7e8794d5babc8ceec653a63ab
for info on contributing to this repo.

# Development

```
make dev
```