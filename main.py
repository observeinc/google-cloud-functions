"""Functions for fetching gcp api data"""
import json
import os
import typing
import random
from google.protobuf.timestamp_pb2 import Timestamp
from datetime import datetime, timedelta
from unittest.mock import Mock
from google.cloud import compute_v1
from google.cloud import pubsub_v1
from google.cloud import tasks_v2
import requests
from googleapiclient import discovery
from google.cloud.pubsub_v1.publisher import exceptions

import unittest

import gzip
import tracing
import traceback

def assert_env_var(var_name):
    if var_name not in os.environ:
        raise Exception(f"Environment variable {var_name} is not set")

_required_env_vars = ["PARENT", "TOPIC_ID", "SERVICE_ACCOUNT_EMAIL", "QUEUE_NAME"]

for var in _required_env_vars:
    assert_env_var(var)

_parent = os.environ["PARENT"]
_topic_path = os.environ["TOPIC_ID"]
_service_account_email = os.environ["SERVICE_ACCOUNT_EMAIL"]
_queue_name = os.environ["QUEUE_NAME"]

_version = os.getenv("VERSION", "google-cloud-function")

_api_request_counter = 0

if "LOCATION_ALLOWLIST" in os.environ:
    _location_allowlist = [
        s.strip() for s in os.environ["LOCATION_ALLOWLIST"].split(",")
    ]
else:
    _location_allowlist = None

CLOUDASSET_CONTENT_TYPES = ["RESOURCE", "IAM_POLICY", "ORG_POLICY", "ACCESS_POLICY"]
Resource = discovery.Resource


def safe_list(
    resource: Resource, list_kwargs: dict, key: str, max_depth=1000, recursive=True
) -> typing.Iterable[typing.Any]:
    global _api_request_counter
    """safe_list returns an iterable of all elements in the Resource."""
    with tracing.tracer.start_as_current_span("safe_list") as span:
        span.set_attribute("list_kwargs", json.dumps(list_kwargs))
        span.set_attribute("key", key)

        json_data = _request.get_json(force=True, silent=True)
        if json_data and list_kwargs.get('contentType') == json_data.get('contentType'):
            page_token = json_data.get('pageToken')
            if page_token is not None:
                list_kwargs['pageToken'] = page_token

        for i in range(max_depth):
            span.set_attribute("depth", i)
            _api_request_counter += 1
            result: dict = resource.list(**list_kwargs).execute()
            for r in result.get(key, []):
                yield r

            if result.get("nextPageToken", "") == "":
                return
            elif recursive:
                list_kwargs['pageToken'] = result["nextPageToken"]
                list_kwargs['recursive'] = True
                
                delay = timedelta(seconds=random.randint(30, 60))
                now = datetime.now() + timedelta(seconds=_api_request_counter * 1.5) + delay
                timestamp = Timestamp()
                timestamp.FromDatetime(now)

                client = tasks_v2.CloudTasksClient()
                task = {
                    'http_request': {  # Specify the type of request.
                        'http_method': 'POST',
                        'url': 'https://us-east1-content-eng-colin.cloudfunctions.net/chutchinson-env',
                        'oidc_token': {
                            'service_account_email': _service_account_email,
                        },
                    },
                    'schedule_time': timestamp
                }

                task['http_request']['body'] = json.dumps(list_kwargs).encode('utf-8')
                
                response = client.create_task(request={'parent': _queue_name, 'task': task})
                print(f"Created task {response.name}")
                return
            list_kwargs["pageToken"] = result["nextPageToken"]

        raise Exception("max_depth exceeded")

def list_service_accounts(project_id: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span("list_service_accounts") as span:
        span.set_attribute("project_id", project_id)
        res = []
        with discovery.build("iam", "v1") as service:
            accounts = safe_list(
                service.projects().serviceAccounts(),
                {"name": "projects/" + project_id},
                "accounts",
                recursive=False
            )
            for account in accounts:
                res.append(
                    {
                        "projectId": project_id,
                        "account": account,
                    }
                )
        span.set_attribute("num_results", len(res))
        return res


def list_instance_to_instance_groups(project_id: str) -> typing.List[dict]:
    global _api_request_counter
    with tracing.tracer.start_as_current_span(
        "list_instance_to_instance_groups"
    ) as span:
        span.set_attribute("project_id", project_id)
        res = []
        with compute_v1.ZonesClient() as zones_client:
            with compute_v1.InstanceGroupsClient() as instance_group_client:
                _api_request_counter += 1
                zones = zones_client.list(project=project_id)

                zones_skipped = 0
                num_instance_groups = 0
                for zone in zones:
                    if _location_allowlist is not None and not any(zone.name.startswith(location) for location in _location_allowlist):
                        zones_skipped += 1
                        continue
                    _api_request_counter += 1
                    instance_groups = instance_group_client.list(
                        project=project_id, zone=zone.name
                    )

                    for instance_group in instance_groups:
                        num_instance_groups += 1
                        _api_request_counter += 1
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

                span.set_attribute("zones_skipped", zones_skipped)
                span.set_attribute("num_instance_groups", num_instance_groups)

        span.set_attribute("num_results", len(res))
        return res


def list_cloud_scheduler_jobs(project_id: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span("list_cloud_scheduler_jobs") as span:
        span.set_attribute("project_id", project_id)
        res = []

        with discovery.build("cloudscheduler", "v1") as service:
            locations = safe_list(
                service.projects().locations(),
                {"name": "projects/" + project_id},
                "locations",
                recursive=False
            )
            for l in locations:
                if _location_allowlist is not None:
                    if l["locationId"] not in _location_allowlist:
                        continue
                jobs = safe_list(
                    service.projects().locations().jobs(),
                    {"parent": l["name"]},
                    "jobs",
                    recursive=False
                )
                for job in jobs:
                    res.append(
                        {
                            "projectId": project_id,
                            "locationId": l["locationId"],
                            "job": job,
                        }
                    )

        span.set_attribute("num_results", len(res))
        return res


def list_projects(parent: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span("list_projects") as span:
        span.set_attribute("parent", parent)
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
                    recursive=False
                )
            for p in projects:
                res.append(
                    {
                        "parent": parent,
                        "project": p,
                    }
                )
        span.set_attribute("num_results", len(res))
        return res


def list_assets(parent: str, content_type: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span("list_assets") as span:
        span.set_attribute("parent", parent)
        span.set_attribute("content_type", content_type)
        res = []
        with discovery.build("cloudasset", "v1") as service:
            assets = safe_list(
                service.assets(),
                {"parent": parent, "contentType": content_type},
                "assets",
                recursive=True
            )
            for a in assets:
                res.append(
                    {
                        "parent": parent,
                        "asset": a,
                    }
                )
        span.set_attribute("num_results", len(res))
        return res


class PerProjectRegistry:
    def __init__(
        self,
        list_func: typing.Callable[[str], typing.List[dict]],
        observe_gcp_kind: str,
    ) -> None:
        self.list_func = list_func
        self.observe_gcp_kind = observe_gcp_kind


per_project_registry: typing.List[PerProjectRegistry] = [
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


def main(request) -> typing.Tuple[str, int]:
    global _api_request_counter
    global _request
    _request = request
    with tracing.tracer.start_as_current_span("main") as span:
        try:
            publisher = pubsub_v1.PublisherClient()

            def publish(records: typing.List[dict], observe_gcp_kind: str):
                futures = []
                for r in records:
                    data = json.dumps(r).encode("utf-8")
                    original_length = len(data)
                    compressed_data = gzip.compress(data)

                    try:
                        f = publisher.publish(
                            _topic_path,
                            data=compressed_data,
                            observe_gcp_kind=observe_gcp_kind,
                            observe_cloud_function_version=_version,
                            observe_original_length=str(len(data)),
                            observe_content_encoding="gzip",
                        )
                        futures.append(f)
                    except exceptions.MessageTooLargeError:
                        span.add_event(
                            "message_too_large", {"observe_gcp_kind": observe_gcp_kind}
                        )
                print(f"Publishing {len(records)} records of type: {observe_gcp_kind}")
                for f in futures:
                    _ = f.result()

            request_data = None
            content_type = None
            if hasattr(request, 'get_json'):
                request_data = request.get_json(force=True, silent=True)
                content_type = request_data.get('contentType', None) if request_data else None

            if content_type is not None:
                content_types = [content_type]
            else:
                content_types = CLOUDASSET_CONTENT_TYPES
            
            for ct in content_types:
                try:
                    asset_records = list_assets(_parent, ct)
                    publish(
                        asset_records,
                        # If observe_gcp_kind is changed, the OPAL in terraform-observe-google may need
                        # to be changed.
                        "https://cloud.google.com/asset-inventory/docs/reference/rest/v1/assets",
                    )
                except Exception as e:
                    traceback.print_exception(e)

            if request_data is not None and request_data.get('recursive', False):
                return "Ok", 200

            project_records = list_projects(_parent)
            publish(
                project_records,
                # If observe_gcp_kind is changed, the OPAL in terraform-observe-google may need
                # to be changed.
                "https://cloud.google.com/resource-manager/reference/rest/v3/projects",
            )

            for project in project_records:
                project_id = project["project"]["projectId"]
                for registry in per_project_registry:
                    try:
                        _api_request_counter += 1
                        records = registry.list_func(project_id)
                        publish(records, registry.observe_gcp_kind)
                    except Exception as e:
                        traceback.print_exception(e)

            tracing.provider.force_flush()

            return "Ok", 200
        except Exception as e:
            traceback.print_exception(e)
            return "Internal Server Error", 500


_PUBSUB_MAX_SIZE_BYTES = 1e7 - 1e6  # Subtract 1e6 just to be safe

if __name__ == "__main__":
    # Create a mock request object
    request = Mock()

    # Add the get_json method to the mock object
    request.get_json = Mock(return_value=json.loads(
        '{"content_type": "RESOURCE"}'))

    # Call the function with the mock request
    main(request)


class Test(unittest.TestCase):
    def test_main(self):
        """test_main checks that calling main doesn't result in a panic"""
        main(None)

    def test_kinds(self):
        """test_kinds exists so that observe_gcp_kind is not accidentally changed.
        If observe_gcp_kind is changed, the OPAL in terraform-observe-google may need
        to be changed.
        """
        registry_kinds = [r.observe_gcp_kind for r in per_project_registry]
        self.assertTrue(
            "https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts"
            in registry_kinds
        )
        self.assertTrue(
            "https://cloud.google.com/asset-inventory/docs/supported-asset-types#INSTANCE_TO_INSTANCEGROUP"
            in registry_kinds
        )
        self.assertTrue(
            "https://cloud.google.com/scheduler/docs/reference/rest/v1/projects.locations.jobs"
            in registry_kinds
        )

    def test_service_accounts(self):
        for p in list_projects(_parent):
            res = list_service_accounts(p["project"]["projectId"])
            self.assertTrue(len(res) > 0)
            for r in res:
                b = json.dumps(r).encode("utf-8")
                self.assertTrue(len(b) < _PUBSUB_MAX_SIZE_BYTES)

    def test_instance_groups(self):
        for p in list_projects(_parent):
            res = list_instance_to_instance_groups(p["project"]["projectId"])
            self.assertTrue(len(res) > 0)
            for r in res:
                b = json.dumps(r).encode("utf-8")
                self.assertTrue(len(b) < _PUBSUB_MAX_SIZE_BYTES)

    def test_cloud_scheduler_jobs(self):
        for p in list_projects(_parent):
            res = list_cloud_scheduler_jobs(p["project"]["projectId"])
            self.assertTrue(len(res) > 0)
            for r in res:
                b = json.dumps(r).encode("utf-8")
                self.assertTrue(len(b) < _PUBSUB_MAX_SIZE_BYTES)

    def test_projects(self):
        res = list_projects("folders/437079763664")
        self.assertTrue(len(res) > 0)
        for r in res:
            b = json.dumps(r).encode("utf-8")
            self.assertTrue(len(b) < _PUBSUB_MAX_SIZE_BYTES)

    def test_assets(self):
        for ct in CLOUDASSET_CONTENT_TYPES:
            res = list_assets(_parent, ct)
            if ct == "RESOURCE" or ct == "IAM_POLICY":
                self.assertTrue(len(res) > 0)
            for r in res:
                b = json.dumps(r).encode("utf-8")
                self.assertTrue(len(b) < _PUBSUB_MAX_SIZE_BYTES)
