"""Prometheus metrics for the API service."""

from prometheus_client import Counter, Histogram

submissions_total = Counter(
    "api_submissions_total",
    "Total submissions accepted by language",
    ["language"],
)

cache_hits_total = Counter(
    "api_cache_hits_total",
    "Result cache hits",
)

cache_misses_total = Counter(
    "api_cache_misses_total",
    "Result cache misses",
)

auth_failures_total = Counter(
    "api_auth_failures_total",
    "HMAC authentication failures by reason",
    ["reason"],
)

request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "HTTP request latency by endpoint",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
