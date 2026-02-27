from __future__ import annotations

import os
from typing import Optional


def _is_enabled() -> bool:
    return os.getenv("OTEL_TRACING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    """
    Configure OpenTelemetry tracing.

    This is intentionally optional and must never crash the app if tracing is not configured.
    """
    if not _is_enabled():
        return

    # Lazy imports: keep startup fast and avoid hard-failing if deps are missing.
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Avoid double init when reloading / multiple imports.
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Client libs
    RequestsInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    # FastAPI is instrumented in app/main.py once the app instance exists.


def instrument_fastapi(app) -> None:
    if not _is_enabled():
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # Safe to call multiple times.
    excluded_urls = os.getenv("OTEL_EXCLUDED_URLS", r"^/health$|^/metrics$")
    FastAPIInstrumentor.instrument_app(app, excluded_urls=excluded_urls)


def get_otel_config() -> Optional[tuple[str, str]]:
    if not _is_enabled():
        return None
    service_name = os.getenv("OTEL_SERVICE_NAME", "gifty-api")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    return service_name, otlp_endpoint
