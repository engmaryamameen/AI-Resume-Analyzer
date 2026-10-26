"""Operational metrics. Labels are low-cardinality enums only; never document content or ids."""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("http_request_seconds", "HTTP latency", ["route"])
EXTRACTION_RESULTS = Counter("extraction_results_total", "Résumé extraction outcomes", ["outcome"])
ANALYSIS_SECONDS = Histogram(
    "analysis_duration_seconds", "Analysis wall time", buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60)
)
ANALYSIS_RESULTS = Counter("analysis_results_total", "Analysis outcomes", ["outcome"])
JOB_RETRIES = Counter("job_retries_total", "Job retry count", ["kind"])
JOB_QUEUE_DEPTH = Gauge("job_queue_depth", "Queued jobs", ["kind"])
DB_QUERY_SECONDS = Histogram("db_query_seconds", "Database statement latency")
ML_STAGE_SECONDS = Histogram(
    "ml_stage_seconds", "Inference stage latency", ["stage", "mode"], buckets=(0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60))
ANALYSIS_ENGINE = Counter("analysis_engine_total", "Completed analyses by engine mode", ["mode"])
ENGINE_FALLBACKS = Counter("engine_fallbacks_total", "Analyses redone with the rules engine", ["reason"])
