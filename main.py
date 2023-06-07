"""Functions for fetching gcp api data"""
import json
import os
import typing
from google.cloud import compute_v1
from google.cloud import pubsub_v1
from googleapiclient import discovery
from google.cloud.pubsub_v1.publisher import exceptions

import unittest

import lib
import tracing
import traceback

_parent = os.environ["PARENT"]
_topic_path = os.environ["TOPIC_ID"]

_version = os.getenv("VERSION", "google-cloud-function")

if "LOCATION_ALLOWLIST" in os.environ:
    _location_allowlist = [
        s.strip() for s in os.environ["LOCATION_ALLOWLIST"].split(",")
    ]
else:
    _location_allowlist = None

CLOUDASSET_CONTENT_TYPES = ["RESOURCE", "IAM_POLICY", "ORG_POLICY", "ACCESS_POLICY"]


def list_service_accounts(project_id: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span("list_service_accounts") as span:
        span.set_attribute("project_id", project_id)

        res = []
        with discovery.build("iam", "v1") as service:
            accounts = lib.safe_list(
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
        span.set_attribute("num_results", len(res))
        return res


def list_instance_to_instance_groups(project_id: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span(
        "list_instance_to_instance_groups"
    ) as span:
        span.set_attribute("project_id", project_id)
        res = []
        with compute_v1.ZonesClient() as zones_client:
            with compute_v1.InstanceGroupsClient() as instance_group_client:
                zones = zones_client.list(project=project_id)

                zones_skipped = 0
                num_instance_groups = 0
                for zone in zones:
                    if _location_allowlist is not None:
                        skipZone = True
                        for l in _location_allowlist:
                            if zone.name.startswith(l):
                                skipZone = False
                                break
                        if skipZone:
                            zones_skipped += 1
                            continue
                    instance_groups = instance_group_client.list(
                        project=project_id, zone=zone.name
                    )

                    for instance_group in instance_groups:
                        num_instance_groups += 1
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
            locations = lib.safe_list(
                service.projects().locations(),
                {"name": "projects/" + project_id},
                "locations",
            )
            for l in locations:
                if _location_allowlist is not None:
                    if l["locationId"] not in _location_allowlist:
                        continue
                jobs = lib.safe_list(
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
                projects = lib.safe_list(
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
        span.set_attribute("num_results", len(res))
        return res


def list_assets(parent: str, content_type: str) -> typing.List[dict]:
    with tracing.tracer.start_as_current_span("list_assets") as span:
        span.set_attribute("parent", parent)
        span.set_attribute("content_type", content_type)
        res = []
        with discovery.build("cloudasset", "v1") as service:
            assets = lib.safe_list(
                service.assets(),
                {"parent": parent, "contentType": content_type},
                "assets",
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


def project_main(request) -> typing.Tuple[str, int]:
    with tracing.tracer.start_as_current_span("project_main") as span:
        publisher = pubsub_v1.PublisherClient()

        def publish(records: typing.List[dict], observe_gcp_kind: str):
            futures = []
            for r in records:
                b = json.dumps(r).encode("utf-8")
                try:
                    f = publisher.publish(
                        _topic_path,
                        data=b,
                        observe_gcp_kind=observe_gcp_kind,
                        observe_cloud_function_version=_version,
                    )
                    futures.append(f)
                except exceptions.MessageTooLargeError:
                    span.add_event(
                        "message_too_large", {"observe_gcp_kind": observe_gcp_kind}
                    )
                    span.SetStatus(exceptions.MessageTooLargeError, "message_too_large")
                    span.RecordError(exceptions.MessageTooLargeError)

            for f in futures:
                _ = f.result()

        project_records = list_projects(_parent)
        publish(
            project_records,
            # If observe_gcp_kind is changed, the OPAL in terraform-observe-google may need
            # to be changed.
            "https://cloud.google.com/resource-manager/reference/rest/v3/projects",
        )

        for p in project_records:
            pid = p["project"]["projectId"]
            for r in per_project_registry:
                try:
                    records = r.list_func(pid)
                    publish(records, r.observe_gcp_kind)
                except Exception as e:
                    traceback.print_exception(e)
                    span.SetStatus(e.message)
                    span.RecordError(e.message)

        tracing.provider.force_flush()

        return "Ok", 200


def main(request) -> typing.Tuple[str, int]:
    with tracing.tracer.start_as_current_span("main-collector") as span:
        publisher = pubsub_v1.PublisherClient()

        def publish(records: typing.List[dict], observe_gcp_kind: str):
            futures = []
            for r in records:
                b = json.dumps(r).encode("utf-8")
                try:
                    f = publisher.publish(
                        _topic_path,
                        data=b,
                        observe_gcp_kind=observe_gcp_kind,
                        observe_cloud_function_version=_version,
                    )
                    futures.append(f)
                except exceptions.MessageTooLargeError:
                    span.add_event(
                        "message_too_large", {"observe_gcp_kind": observe_gcp_kind}
                    )
                    span.SetStatus(exceptions.MessageTooLargeError, "message_too_large")
                    span.RecordError(exceptions.MessageTooLargeError)
            for f in futures:
                _ = f.result()

        for ct in CLOUDASSET_CONTENT_TYPES:
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
                span.SetStatus(e.message)
                span.RecordError(e.message)

        tracing.provider.force_flush()

        return "Ok", 200


_PUBSUB_MAX_SIZE_BYTES = 1e7 - 1e6  # Subtract 1e6 just to be safe


class Test(unittest.TestCase):
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
