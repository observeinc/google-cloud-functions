import os

from opentelemetry import trace
from opentelemetry.sdk import trace as sdktrace
from opentelemetry.sdk.trace import export

disable_logging = os.getenv("DISABLE_LOGGING")

provider = sdktrace.TracerProvider()

if disable_logging is None: 
    _processor = export.BatchSpanProcessor(
        # Set indent to none to avoid multi-line logs
        export.ConsoleSpanExporter(formatter=lambda s: s.to_json(indent=None) + "\n")
    )
    provider.add_span_processor(_processor)
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
