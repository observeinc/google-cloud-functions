# google-cloud-functions

This is a Python-based project that uses the Google Cloud Platform (GCP) Asset API
to ingest GCP resources. The assets are then sent to a GCP bucket and subsequently
to a pub/sub service. On the receiving end, we poll the pub/sub for these resources.

## Architecture and Design

- Use the GCP Asset API to export assets to a GCP Bucket.
- Process the GCS directory and check for the presence of the lock file.
- Parse each blob (file) in the GCS directory:
    - Skip if the blob is a directory, empty, or is the lock file.
    - Parse the blob content into a list of JSON objects.
- Extract the asset type and content type from each blob's path.
- Publish the JSON objects to a pub/sub service with relevant headers.
- Once processed, each blob is deleted from the GCS directory.
- After all blobs are processed, the lock file is deleted.

## Installation

The [`observeinc/collection/google`](https://registry.terraform.io/modules/observeinc/collection/google/latest) module installs this application as a Google Cloud function along with other required resources.

## Development

### Setting up the Docker Environment

To prepare your local development environment with Docker:

```sh
PROJECT_ID=foobar make docker/dev
```

Replace `foobar` with your actual project ID.

### Setting Up the Environment for Local Development

After initializing your Docker environment, set up the necessary environment variables:

```sh
export PARENT="your_value_here"
export PROJECT="your_value_here"
export OUTPUT_BUCKET="your_value_here"
export PUBSUB_TOPIC="your_value_here"
export TASK_QUEUE="your_value_here"
export GCP_REGION="your_value_here"
export SERVICE_ACCOUNT_EMAIL="your_value_here"
export GCS_TO_PUBSUB_CLOUD_FUNCTION_URI="your_value_here"
```

Replace `your_value_here` with the actual values for your environment.

### Manual Testing

The following code snippets facilitate local development and testing:

```python
# Manual call for testing
# mock_request = Mock()
# mock_request.get_json.return_value = {
#     "asset_types": ["storage.googleapis.com.*"],
#     "content_types": ["RESOURCE"],
# }
# export_assets(mock_request)


# blob_path = "dev-content-eng-colin-bucket/asset_export_v2_20230809141905/RESOURCE/operation_name.txt"
# create_cloud_task(blob_path)

# data = 'asset_export_v2_20230809141905/RESOURCE/operation_name.txt'
# response = gcs_to_pubsub(data)


# bucket_name = "dev-content-eng-colin-bucket"
# resource_prefix = "asset_export_v2_20230808210346/IAM_POLICY/"
# process_gcs_directory(bucket_name, resource_prefix)
```

### Docker and Makefile Usage

Utilize Docker and the Makefile to manage build and test processes:

- Build the Docker image:

```sh
make docker/build
```

- Run the Docker container for development:

```sh
PROJECT_ID=foobar make docker/dev
```

- Execute tests inside the Docker container:

```sh
make docker/test
```

- Clean up Docker images:

```sh
make docker/clean
```

## Testing

Use Python's `unittest` framework for testing. Run the entire test suite:

```sh
make test
```

For specific tests, use the following commands:

- Run all tests in a specific file:

```sh
python -m pytest tests/main_test.py
```

- Run all tests in a specific class of a test file:

```sh
python -m pytest tests/main_test.py::TestExportAssets
```

- Execute a particular test within a class:

```sh
python -m pytest tests/main_test.py::TestExportAssets::test_export_assets
```

## Contributing

1. Fork the repository ([https://github.com/observeinc/google-cloud-functions/fork](https://github.com/observeinc/google-cloud-functions/fork))
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request
