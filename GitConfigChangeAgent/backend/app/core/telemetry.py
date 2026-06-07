from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from app.core.config import settings


def configure_telemetry() -> None:
    resource = Resource.create({"service.name": settings.app_name, "service.version": settings.app_version})
    provider = TracerProvider(resource=resource)
    if settings.opentelemetry_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.opentelemetry_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
