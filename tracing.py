import os

from opentelemetry import trace
from opentelemetry.sdk import trace as sdktrace
from opentelemetry.sdk.trace import export
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

SERVICE_NAME_VAR = os.getenv("SERVICE_NAME", "cloud_function_asset_collection")

resource = Resource(attributes={SERVICE_NAME: SERVICE_NAME_VAR})

disable_logging = os.getenv("DISABLE_LOGGING")

provider = sdktrace.TracerProvider(resource=resource)


if disable_logging is None:
    _processor = export.BatchSpanProcessor(
        # Set indent to none to avoid multi-line logs
        export.ConsoleSpanExporter(formatter=lambda s: s.to_json(indent=None) + "\n")
    )
    provider.add_span_processor(_processor)
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
