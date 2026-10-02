"""OpenTelemetry setup exporting Agent Framework traces and metrics to Azure Monitor (Application Insights).

When a connection string is configured, every agent run, tool call, chat call, and workflow step becomes a span.
Prompt and response contents are never exported unless explicitly enabled.
"""

import logging
import os

from agent_framework.observability import enable_instrumentation

APPLICATIONINSIGHTS_CONNECTION_STRING: str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
TELEMETRY_SENSITIVE_DATA: bool = os.getenv("TELEMETRY_SENSITIVE_DATA", "false").lower() == "true"
SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "inside-the-game")

logger = logging.getLogger(__name__)


def setup_telemetry() -> bool:
    """Configure Azure Monitor export and agent instrumentation; returns whether telemetry is active."""
    if not APPLICATIONINSIGHTS_CONNECTION_STRING:
        logger.info("Telemetry disabled: no Application Insights connection string")
        return False
    from azure.monitor.opentelemetry import configure_azure_monitor

    os.environ.setdefault("OTEL_SERVICE_NAME", SERVICE_NAME)
    configure_azure_monitor(connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING)
    enable_instrumentation(enable_sensitive_data=TELEMETRY_SENSITIVE_DATA)
    logger.info("Telemetry enabled for %s", SERVICE_NAME)
    return True
