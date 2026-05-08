"""Unit tests for baseline selection logic — spec §8.3."""

from __future__ import annotations

import numpy as np
import pytest

from polyeval_aggregator.score.perf import score_perf
from polyeval_aggregator.stats.trim import trimmed_median


class TestBaselineLogic:
    def test_perf_normalized_with_baseline(self) -> None:
        wall_ns = [1_000_000] * 10
        baseline_ns = 500_000
        perf, ci_lo, ci_hi = score_perf(wall_ns, baseline_ns)
        assert perf == pytest.approx(2.0, rel=0.01)
        assert ci_lo is not None and ci_hi is not None
        assert ci_lo <= perf <= ci_hi

    def test_perf_no_baseline_returns_none(self) -> None:
        wall_ns = [1_000_000] * 10
        perf, ci_lo, ci_hi = score_perf(wall_ns, None)
        assert perf is None
        assert ci_lo is None
        assert ci_hi is None

    def test_perf_zero_baseline_returns_none(self) -> None:
        perf, _, _ = score_perf([1_000_000], 0)
        assert perf is None

    def test_rust_median_is_trimmed_median(self) -> None:
        # Simulate what pipeline upserts: trimmed_median of wall_ns.
        values = [1_000, 1_100, 1_050, 5_000_000, 950]  # outlier at 5M
        arr = np.asarray(values, dtype=float)
        median = trimmed_median(arr)
        # Trimmed median should be much less than raw mean (5M outlier removed).
        assert median < np.mean(arr)
        assert median > 0

    def test_perf_faster_than_baseline(self) -> None:
        # Python faster than Rust (unusual but representable).
        perf, _, _ = score_perf([250_000], 1_000_000)
        assert perf == pytest.approx(0.25, rel=0.01)

    def test_perf_equal_to_baseline(self) -> None:
        perf, _, _ = score_perf([1_000_000] * 5, 1_000_000)
        assert perf == pytest.approx(1.0, rel=0.01)
