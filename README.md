# google-cloud-functions

This is a Python-based project that uses the Google Cloud Platform (GCP) Asset API
to ingest GCP resources. The assets are then sent to a GCP bucket and subsequently
to a pub/sub service. On the receiving end, we poll the pub/sub for these resources

## Architecture and Design

- Use the GCP Asset API to export assets to a GCP Bucket
- Publish resources from the GCP bucket to a pub/sub service

## Installation

[Terraform Installation Module](https://github.com/observeinc/terraform-google-collection/tree/main)


## Development

Requires having a GCP account and docker installed

```
PROJECT_ID=foobar make dev
```

## Contributing

- Fork it (https://github.com/observeinc/google-cloud-functions/fork)
- Create your feature branch (git checkout -b feature/fooBar)
- Commit your changes (git commit -am 'Add some fooBar')
- Push to the branch (git push origin feature/fooBar)
- Create a new Pull Request

See https://www.notion.so/observeinc/GCP-collection-4af5eaa49951466fad879acfbc2c6cd9#107096e7e8794d5babc8ceec653a63ab
for info on contributing to this repo.
