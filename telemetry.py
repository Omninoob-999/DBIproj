import os
import logging
from ddtrace import tracer
from ddtrace.llmobs import LLMObs

# Global instruments (Mock objects for compatibility)
document_processed_total = None
document_processing_duration_seconds = None
ai_token_usage = None

class MockMetric:
    def add(self, value, attributes=None):
        pass
    
    def record(self, value, attributes=None):
        pass
    
    def create_counter(self, name, description=None, unit=None):
        return self

    def create_histogram(self, name, description=None, unit=None):
        return self

class TracerWrapper:
    """Wrapper to make Datadog tracer behave like OTel tracer"""
    def __init__(self, name):
        self.name = name

    def start_as_current_span(self, name):
        # Maps OTel start_as_current_span to Datadog trace
        return tracer.trace(name, service="content-process-api", resource=name)

def setup_telemetry(service_name="content-process-api"):
    """
    Configures Datadog LLMObs and Tracing.
    """
    global document_processed_total, document_processing_duration_seconds, ai_token_usage

    # Initialize Datadog LLMObs
    try:
        if os.getenv("DD_API_KEY"):
            LLMObs.enable(
                ml_app=os.getenv("DD_LLMOBS_ML_APP") or "content-process",
                api_key=os.getenv("DD_API_KEY"),
                site=os.getenv("DD_SITE") or "us3.datadoghq.com",
                agentless_enabled=True,
                service=os.getenv("DD_SERVICE") or service_name,
                env=os.getenv("DD_ENV") or "dev"
            )
            logging.info("Datadog LLMObs enabled.")
        else:
            logging.warning("DD_API_KEY not found. LLMObs may not be enabled.")

    except Exception as e:
         logging.error(f"Failed to initialize Datadog LLMObs: {e}")

    # Initialize simple mock metrics to prevent crashes in main.py
    # Datadog metrics (statsd) can be added here if needed in future
    mock_meter = MockMetric()
    document_processed_total = mock_meter.create_counter("document_processed_total")
    document_processing_duration_seconds = mock_meter.create_histogram("document_processing_duration_seconds")
    ai_token_usage = mock_meter.create_counter("ai_token_usage")

    logging.info(f"Telemetry initialized for service: {service_name} (Datadog Mode)")

def get_tracer(name):
    return TracerWrapper(name)
