import typing
from googleapiclient import discovery

import tracing
import json

# A Resource is what GCP calls a REST Resource.
#
# Resources have methods like "get", "list", or "create".
#
# https://cloud.google.com/functions/docs/reference/rest/v1/projects.locations.functions
# https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts
Resource = discovery.Resource


def safe_list(
    resource: Resource, list_kwargs: dict, key: str, max_depth=1000
) -> typing.Iterable[typing.Any]:
    """safe_list returns an iterable of all elements in the Resource."""
    with tracing.tracer.start_as_current_span("safe_list") as span:
        span.set_attribute("list_kwargs", json.dumps(list_kwargs))
        span.set_attribute("key", key)

        for i in range(max_depth):
            span.set_attribute("depth", i)
            result: dict = resource.list(**list_kwargs).execute()
            for r in result.get(key, []):
                yield r

            if result.get("nextPageToken", "") == "":
                return
            list_kwargs["pageToken"] = result["nextPageToken"]

        raise Exception("max_depth exceeded")
