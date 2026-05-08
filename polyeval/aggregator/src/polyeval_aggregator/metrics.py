"""Prometheus metrics for the aggregator service."""

from prometheus_client import Counter, Histogram

scored_total = Counter(
    "aggregator_scored_total",
    "Submissions fully scored by language",
    ["language"],
)

non_deterministic_total = Counter(
    "aggregator_non_deterministic_total",
    "Submissions flagged as non-deterministic by language",
    ["language"],
)

sandbox_violations_total = Counter(
    "aggregator_sandbox_violations_total",
    "Trials with sandbox_violation=true by language",
    ["language"],
)

scoring_duration_seconds = Histogram(
    "aggregator_scoring_duration_seconds",
    "Wall time to score one trial bundle end-to-end",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

correctness_score = Histogram(
    "aggregator_correctness_score",
    "Distribution of correctness scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
