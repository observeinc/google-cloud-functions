from opentelemetry import trace
from opentelemetry.sdk import trace as sdktrace
from opentelemetry.sdk.trace import export

provider = sdktrace.TracerProvider()
processor = export.BatchSpanProcessor(
    # Set indent to none to avoid multi-line logs
    export.ConsoleSpanExporter(formatter=lambda s: s.to_json(indent=None) + "\n")
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
