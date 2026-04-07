# OpenTelemetry Integration Troubleshooting Log

This document records the issues encountered, root causes, and solutions implemented during the integration of OpenTelemetry into the generic document extraction service.

## 1. Missing `ai_token_usage` Metric
**Symptom**: The `ai_token_usage` metric was not appearing in the dashboard when using the `content_understanding` extractor.
**Root Cause**: The initial implementation only recorded token usage in `extractor.py` (Azure OpenAI). `extractor_cu.py` (Azure Content Understanding) lacked the recording logic.
**Investigation**: 
- Added logic to `extractor_cu.py` to parse `result['usage']['tokens']`.
- **Final Finding**: The Azure Content Understanding API (preview) **does not currently return a `usage` field** in its response. 
- **Status**: Logic is in place, but metric will only increment when using the `multimodal` (OpenAI) extractor until Azure updates the ACU API.

## 2. Missing `document_processing_duration_seconds`
**Symptom**: The duration histogram was not appearing in the dashboard during short tests.
**Root Cause**: The default OTLP export interval is 60 seconds. Tests finished and the container stopped before the first export cycle completed.
**Solution**: Reduced the export interval to 5 seconds in `telemetry.py` for the POC environment.
```python
PeriodicExportingMetricReader(otlp_metric_exporter, export_interval_millis=5000)
```

## 3. Histogram Visualization "Looks Wrong"
**Symptom**: The table view showed "No metric data found" or the graph showed values slightly higher than the actual log (e.g., 50s vs 34s).
**Explanation**:
- **Table View**: Tables struggle to display complex Histogram data (buckets).
- **Graph View (Blocky)**: Histograms store data in buckets (e.g., 0-5s, ..., 25-50s). If a request takes 34s, it falls into the 25-50s bucket. Visualizations often plot the upper bound or midpoint of the bucket, making single data points look "off".
- **Solution**: Use the **Traces** tab to view the exact duration of individual requests (down to the millisecond).

## 4. Metric Oscillation ("Sawtooth" Graph)
**Symptom**: The `ai_token_usage` counter seemed to jump up and down or fluctuate wildly in the dashboard.
**Root Cause**: The application uses `ProcessPoolExecutor`. Each worker process maintains its own local version of the `ai_token_usage` cumulative counter.
- Worker A: 10,000 tokens
- Worker B: 500 tokens
- Since they report as the same service instance, the dashboard sees the value jumping between 10,000 and 500.
**Solution**: Added `process.pid` to the OpenTelemetry Resource in `telemetry.py`.
```python
resource = Resource.create({
    SERVICE_NAME: service_name,
    "service.instance.id": str(os.getpid()), 
    "process.pid": str(os.getpid())
})
```
This ensures each worker reports as a distinct stream, fixing the collision.

## 5. "Flat Line" on Token Usage Graph
**Symptom**: The `ai_token_usage` graph is a flat horizontal line even when calls are made.
**Explanation**:
- **Cumulative Counter**: This metric tracks *total tokens since startup*. A flat line (at a non-zero value) means the total is stable and no *new* tokens are being added.
- **Cause**: As noted in Issue #1, ACU calls do not generate token usage, so the counter stays flat during ACU tests. It will slope upwards only during `multimodal` calls.

## 6. App Crash: `ModuleNotFoundError: No module named 'opentelemetry.sdk.logs'`
**Symptom**: The application crashed on startup with an import error for `opentelemetry.sdk.logs`, even after installing `opentelemetry-sdk`.
**Root Cause**: The Python OpenTelemetry SDK (specifically version `1.39.1` installed in the container) still treats the logging implementation as internal/experimental, placing the modules in `_logs` instead of `logs`.
**Solution**: 
- Updated `telemetry.py` to import from the internal paths:
    ```python
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    ```
- Pinned OpenTelemetry dependencies in `requirements.txt` to ensuring consistent versions (`>=1.29.0`).

## 7. Warning: `Transient error StatusCode.UNAVAILABLE`
**Symptom**: You see yellow warning logs in the dashboard saying "Transient error StatusCode.UNAVAILABLE encountered while exporting logs...".
**Explanation**: This means the application tried to send data to the Aspire Dashboard, but the connection failed temporarily.
- **Why?**: This is common during startup (the app starts faster than the dashboard) or during high load.
- **Impact**: The "Transient" part means the OpenTelemetry SDK knows it's a temporary glitch and **will retry automatically**. If you see successful logs appearing afterwards, this warning can be safely ignored.

## 8. Metric Drop (Counter Reset)
**Symptom**: The `ai_token_usage` (or any accumulation metric) graph drops suddenly (e.g., from 18k to 6k).
**Explanation**: OpenTelemetry counters track values **in-memory** for the life of the process.
- **Why?**: When we restart the Docker container (which we did to fix the crash), the process ends, and the counter is destroyed. The new process starts at 0.
- **Observation**: A sharp drop followed by a climb indicates a system restart. This is expected behavior, not a bug.

## 7. Warning: `Transient error StatusCode.UNAVAILABLE`
**Symptom**: You see yellow warning logs in the dashboard saying "Transient error StatusCode.UNAVAILABLE encountered while exporting logs...".
**Explanation**: This means the application tried to send data to the Aspire Dashboard, but the connection failed temporarily.
- **Why?**: This is common during startup (the app starts faster than the dashboard) or during high load.
- **Impact**: The "Transient" part means the OpenTelemetry SDK knows it's a temporary glitch and **will retry automatically**. If you see successful logs appearing afterwards, this warning can be safely ignored.
