# -*- coding: utf-8 -*-
import functions_framework
import gzip
import json
import logging
import os
import traceback
import time

from google.cloud import asset_v1, compute_v1, pubsub_v1, storage
from google.cloud.pubsub_v1.publisher import exceptions
from google.cloud import logging as gcloud_logging
from google.api_core import exceptions as google_exceptions
from googleapiclient import discovery
from cloudevents.http import CloudEvent
from typing import Any, Callable, Dict, Iterable, List
from unittest.mock import Mock
from datetime import datetime

# Instantiates a client
logging_client = gcloud_logging.Client()

# Connects the logger to the root logging handler; by default, the severity level will be INFO.
logging_client.setup_logging()

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


def publish(records: List[dict], observe_gcp_kind: str):
    """
    Publish records to pub/sub

    Args:
        records: List of JSON data to publish to pub/sub.
        observe_gcp_kind: String with the type of data we are seeing, i.e.
            "https://cloud.google.com/asset-inventory/docs/supported-asset-types#INSTANCE_TO_INSTANCEGROUP",
    """
    for r in records:
        data = json.dumps(r).encode("utf-8")
        original_length = len(data)
        compressed_data = gzip.compress(data)

        publisher = pubsub_v1.PublisherClient()
        publisher.publish(
            PUBSUB_TOPIC,
            data=compressed_data,
            observe_gcp_kind=observe_gcp_kind,
            observe_original_length=str(len(data)),
            observe_content_encoding="gzip",
        )


def safe_list(
    resource: discovery.Resource, list_kwargs: dict, key: str, max_depth=1000
) -> Iterable[Any]:
    """safe_list returns an iterable of all elements in the Resource."""

    for i in range(max_depth):
        result: dict = resource.list(**list_kwargs).execute()
        for r in result.get(key, []):
            yield r

        if result.get("nextPageToken", "") == "":
            return
        list_kwargs["pageToken"] = result["nextPageToken"]

    raise Exception("max_depth exceeded")


def list_service_accounts(project_id: str) -> List[dict]:
    """
    List service accounts.

    Args:
        project_id: String container the project id we want to return service
            accounts for
    Returns:
        A list of dicts with service accounts and corresponding projectId
    """
    res = []
    with discovery.build("iam", "v1") as service:
        accounts = safe_list(
            service.projects().serviceAccounts(),
            {"name": "projects/" + project_id},
            "accounts",
        )
        for account in accounts:
            res.append(
                {
                    "projectId": project_id,
                    "account": account,
                }
            )
    return res


def list_instance_to_instance_groups(project_id: str) -> List[dict]:
    """
    List instances and their corresponding instance groups in a project

    Args:
        project_id: String containing the projectId we want instances from
            from
    Returns:
        A list of dicts with instances and corresponding instance groups for project.
    """
    res = []
    with compute_v1.ZonesClient() as zones_client:
        with compute_v1.InstanceGroupsClient() as instance_group_client:

            zones = zones_client.list(project=project_id)

            for zone in zones:
                instance_groups = instance_group_client.list(
                    project=project_id, zone=zone.name
                )

                for instance_group in instance_groups:
                    instances = instance_group_client.list_instances(
                        project=project_id,
                        instance_group=instance_group.name,
                        zone=zone.name,
                    )

                    for instance in instances:
                        res.append(
                            {
                                "projectId": project_id,
                                "zoneName": zone.name,
                                "instanceGroupId": instance_group.id,
                                "instanceUrl": instance.instance,
                            }
                        )
    return res


def list_cloud_scheduler_jobs(project_id: str) -> List[dict]:
    """
    List cloud scheduler jobs.

    Args:
        project_id: String containing the projectId we want cloud scheduler
            jobs from
    Returns:
        A list of dicts with cloud scheduler jobs and corresponding project
            project ID and location.
    """
    res = []

    with discovery.build("cloudscheduler", "v1") as service:
        locations = safe_list(
            service.projects().locations(),
            {"name": "projects/" + project_id},
            "locations",
        )
        for l in locations:
            jobs = safe_list(
                service.projects().locations().jobs(),
                {"parent": l["name"]},
                "jobs",
            )
            for job in jobs:
                res.append(
                    {
                        "projectId": project_id,
                        "locationId": l["locationId"],
                        "job": job,
                    }
                )

    return res


def list_projects(parent: str) -> List[dict]:
    """
    Returns a list of projects.

    Args:
        parent: String containing the resource we want to collect projects from.
    Returns:
        A list of dicts with projects.  If the parent is a project, we only return
        data for that project (as a list).  Otherwise we return all of the projects
        from that parent.
    """
    res = []
    with discovery.build("cloudresourcemanager", "v3") as service:
        if parent.startswith("projects"):
            p = service.projects().get(name=parent).execute()
            projects = [p]
        else:
            projects = safe_list(
                service.projects(),
                {"parent": parent},
                "projects",
            )
        for p in projects:
            res.append(
                {
                    "parent": parent,
                    "project": p,
                }
            )
    return res


class PerProjectRegistry:
    """
    Helper class to collect various resources per project.
    NOTE: if observe_gcp_kind changes, corresponding content will need to be updated
    """

    def __init__(
        self,
        list_func: Callable[[str], List[dict]],
        observe_gcp_kind: str,
    ) -> None:
        self.list_func = list_func
        self.observe_gcp_kind = observe_gcp_kind


per_project_registry: List[PerProjectRegistry] = [
    PerProjectRegistry(
        list_service_accounts,
        "https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts",
    ),
    PerProjectRegistry(
        list_instance_to_instance_groups,
        "https://cloud.google.com/asset-inventory/docs/supported-asset-types#INSTANCE_TO_INSTANCEGROUP",
    ),
    PerProjectRegistry(
        list_cloud_scheduler_jobs,
        "https://cloud.google.com/scheduler/docs/reference/rest/v1/projects.locations.jobs",
    ),
]


def rest_of_assets(request):
    """
    Entry point for collecting assets that aren't captured in the asset export or the asset
    feed.  This will loop through all of the functions and publish them to pubsub.
    """
    project_records = list_projects(PARENT)
    publish(
        project_records,
        # If observe_gcp_kind is changed, the OPAL in terraform-observe-google may need
        # to be changed.
        "https://cloud.google.com/resource-manager/reference/rest/v3/projects",
    )

    if project_records:
        for p in project_records:
            pid = p["project"]["projectId"]
            # logging.warning(f"pid is {pid}")
            for r in per_project_registry:
                try:
                    records = r.list_func(pid)
                    publish(records, r.observe_gcp_kind)
                    # logging.warning(f"records is {records}")
                except Exception as e:
                    traceback.print_exception(e)


def export_assets(request):
    """
    Export assets from Google Cloud to a specified storage bucket.

    Args:
        request: HTTP request object with JSON data. The JSON should contain
                 'asset_types' and/or 'content_type' fields to specify assets.

    Returns:
        A tuple containing a success message and HTTP status code.
    """
    logging.debug("Received export assets request")
    try:
        data = request.get_json()
    except Exception as e:
        logging.critical(
            f"Failed decode json from request {request}. Error: {e}", exc_info=True
        )
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

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")  # format the timestamp

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
            logging.critical(
                f"Failed to export content type {content_type}. Error: {e}",
                exc_info=True,
            )
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

    # Skip processing if filename starts with "temp"
    if "/temp_" in data["name"]:
        logging.info("Blob name contains '/temp_', skipping processing")
        return

    # Skip processing folders
    if data["name"][-1] == "/":
        logging.info("Blob name ends in '/', skipping processing")
        return

    storage_client = storage.Client()
    bucket = storage_client.get_bucket(data["bucket"])

    blob = bucket.get_blob(data["name"])
    logging.debug(f"Retrieved blob: {blob}")

    # Check if blob is None
    if blob is None:
        logging.error(
            f'Blob is None, returning without further action for {data["name"]}'
        )
        raise

    content = blob.download_as_bytes()

    # exit early if content is empty
    if not content:
        logging.warning("Content is empty, returning without further action")
        return

    # parse the content as a list of JSON objects
    try:
        json_objects = [json.loads(line) for line in content.splitlines() if line]
    except json.JSONDecodeError as e:
        logging.warning(f'Error processing json for {data["name"]} {e}')
        return

    # Extract content_type and asset_type from the GCS bucket path
    folders = data["name"].split("/")
    if len(folders) < 5:
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
    return "Successfully processed file", 200


# Manual call for testing
# mock_request = Mock()
# mock_request.get_json.return_value = {
#     "asset_types": ["storage.googleapis.com.*"],
#     "content_types": ["RESOURCE"],
# }
# export_assets(mock_request)
