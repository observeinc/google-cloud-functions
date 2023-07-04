# -*- coding: utf-8 -*-
import gzip
import logging
import traceback
from unittest.mock import Mock
from google.cloud import asset_v1, storage, pubsub_v1
from cloudevents.http import CloudEvent
import functions_framework
from typing import List, Dict
import os
import json

# Set necessary environment variables
PARENT = os.environ["PARENT"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"].strip()
PUBSUB_TOPIC = os.environ["TOPIC_ID"].strip()
DEFAULT_ASSET_TYPES = [
    "aiplatform.googleapis.com.*",
    "anthos.googleapis.com.*",
    "apigateway.googleapis.com.*",
    "apikeys.googleapis.com.*",
    "appengine.googleapis.com.*",
    "apps.k8s.io.*",
    "artifactregistry.googleapis.com.*",
    "assuredworkloads.googleapis.com.*",
    "batch.k8s.io.*",
    "beyondcorp.googleapis.com.*",
    "bigquery.googleapis.com.*",
    "bigquerymigration.googleapis.com.*",
    "bigtableadmin.googleapis.com.*",
    "cloudbilling.googleapis.com.*",
    "clouddeploy.googleapis.com.*",
    "cloudfunctions.googleapis.com.*",
    "cloudkms.googleapis.com.*",
    "cloudresourcemanager.googleapis.com.*",
    "composer.googleapis.com.*",
    "compute.googleapis.com.*",
    "connectors.googleapis.com.*",
    "container.googleapis.com.*",
    "containerregistry.googleapis.com.*",
    "dataflow.googleapis.com.*",
    "dataform.googleapis.com.*",
    "datafusion.googleapis.com.*",
    "datamigration.googleapis.com.*",
    "dataplex.googleapis.com.*",
    "dataproc.googleapis.com.*",
    "datastream.googleapis.com.*",
    "dialogflow.googleapis.com.*",
    "dlp.googleapis.com.*",
    "dns.googleapis.com.*",
    "documentai.googleapis.com.*",
    "domains.googleapis.com.*",
    "eventarc.googleapis.com.*",
    "extensions.k8s.io.*",
    "file.googleapis.com.*",
    "firestore.googleapis.com.*",
    "gameservices.googleapis.com.*",
    "gkebackup.googleapis.com.*",
    "gkehub.googleapis.com.*",
    "healthcare.googleapis.com.*",
    "iam.googleapis.com.*",
    "ids.googleapis.com.*",
    "k8s.io.*",
    "logging.googleapis.com.*",
    "managedidentities.googleapis.com.*",
    "memcache.googleapis.com.*",
    "metastore.googleapis.com.*",
    "monitoring.googleapis.com.*",
    "networkconnectivity.googleapis.com.*",
    "networking.k8s.io.*",
    "networkmanagement.googleapis.com.*",
    "networkservices.googleapis.com.*",
    "orgpolicy.googleapis.com.*",
    "osconfig.googleapis.com.*",
    "privateca.googleapis.com.*",
    "pubsub.googleapis.com.*",
    "rbac.authorization.k8s.io.*",
    "redis.googleapis.com.*",
    "run.googleapis.com.*",
    "secretmanager.googleapis.com.*",
    "servicedirectory.googleapis.com.*",
    "servicemanagement.googleapis.com.*",
    "serviceusage.googleapis.com.*",
    "spanner.googleapis.com.*",
    "speech.googleapis.com.*",
    "sqladmin.googleapis.com.*",
    "storage.googleapis.com.*",
    "tpu.googleapis.com.*",
    "transcoder.googleapis.com.*",
    "vpcaccess.googleapis.com.*",
    "workflows.googleapis.com.*",
]
DEFAULT_CONTENT_TYPES = ["RESOURCE", "IAM_POLICY"]


def export_assets(request):
    """
    Export assets from Google Cloud to a specified storage bucket.

    Args:
        request: HTTP request object with JSON data. The JSON should contain
                 'asset_types' and/or 'content_type' fields to specify assets.

    Returns:
        A tuple containing a success message and HTTP status code.
    """
    logging.info("Received export assets request")
    try:
        data = request.get_json()
    except Exception as e:
        logging.error(f"Failed decode json from request {request}. Error: {e}")
        logging.error(traceback.format_exc())
        return

    if not data:
        logging.warning(
            "Request data is empty, using default asset types and content types"
        )

    asset_types = (
        data.get("asset_types", DEFAULT_ASSET_TYPES) if data else DEFAULT_ASSET_TYPES
    )
    content_types = (
        data.get("content_type", DEFAULT_CONTENT_TYPES)
        if data
        else DEFAULT_CONTENT_TYPES
    )

    content_type_map = {
        "RESOURCE": asset_v1.ContentType.RESOURCE,
        "IAM_POLICY": asset_v1.ContentType.IAM_POLICY,
        "ORG_POLICY": asset_v1.ContentType.ORG_POLICY,
        "ACCESS_POLICY": asset_v1.ContentType.ACCESS_POLICY,
    }

    client = asset_v1.AssetServiceClient()

    for content_type in content_types:
        logging.info(f"Processing content type: {content_type}")
        if content_type not in content_type_map:
            logging.error(f"Invalid CONTENT_TYPE: {content_type}")
            raise ValueError(f"Invalid CONTENT_TYPE: {content_type}")

        try:
            output_config = asset_v1.OutputConfig()
            output_config.gcs_destination.uri_prefix = (
                f"{OUTPUT_BUCKET}/asset_export_v1/{content_type}"
            )

            request = asset_v1.ExportAssetsRequest(
                parent=PARENT,
                content_type=content_type_map[content_type],
                asset_types=asset_types,
                output_config=output_config,
            )

            client.export_assets(request=request)
            logging.info(f"Asset export triggered for content type: {content_type}")

        except Exception as e:
            logging.error(f"Failed to export content type {content_type}. Error: {e}")
            logging.error(traceback.format_exc())
            return f"Failed to export content type {content_type}. Error: {e}", 500

    return "Asset export triggered", 200


# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def gcs_to_pubsub(cloud_event: CloudEvent):
    """
    Function triggered by a change in a storage bucket. When a change is detected,
    it fetches the blob from the bucket, and if it passes checks, sends its contents
    to a Pub/Sub topic.

    Args:
        cloud_event: The CloudEvent triggered by a change in the bucket.

    Returns:
        None
    """
    logging.info("Cloud event triggered")

    data = cloud_event.data
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(data["bucket"])

    blob = bucket.get_blob(data["name"])

    # Check if blob is None
    if blob is None:
        logging.warning("Blob is None, returning without further action")
        return

    # Skip processing if filename starts with "temp"
    if blob.name.startswith("temp"):
        logging.info("Blob name starts with 'temp', skipping processing")
        return

    content = blob.download_as_bytes()

    # exit early if content is empty
    if not content:
        logging.warning("Content is empty, returning without further action")
        return

    # parse the content as a list of JSON objects
    try:
        json_objects = [json.loads(line) for line in content.splitlines() if line]
    except json.JSONDecodeError as e:
        return

    # Extract content_type and asset_type from the GCS bucket path
    gcs_prefix = f"{bucket.name}/"
    path = data["name"][len(gcs_prefix) :]
    folders = path.split("/")
    if len(folders) < 4:
        logging.warning("Path structure unexpected, returning without further action")
        return

    content_type = folders[2]
    asset_type = folders[3]

    # publish to Pub/Sub
    publisher = pubsub_v1.PublisherClient()
    for json_object in json_objects:
        message = json.dumps(json_object)
        publisher.publish(
            PUBSUB_TOPIC,
            data=gzip.compress(message.encode()),
            observe_content_encoding="gzip",
            observe_original_length=str(len(message)),
            observe_gcp_kind="https://cloud.google.com/asset-inventory/docs/reference/rest/v1/TopLevel/exportAssets",
            observe_gcp_asset_type=asset_type,
            observe_gcp_content_type=content_type,
        )

    # delete the file from the bucket
    if blob.exists():
        blob.delete()
        logging.info("Blob successfully deleted")
    else:
        logging.warning("Blob not found, could not delete")


# Manual call for testing
# mock_request = Mock()
# mock_request.get_json.return_value = {
#     "asset_types": ["storage.googleapis.com.*"],
#     "content_types": ["RESOURCE"]
# }
# export_assets(mock_request)
