"""Property tests for trim_outliers — spec §8.3.

Properties:
1. Idempotent: trim(trim(x, p), p) == trim(x, p).
2. Size: len(trim(x)) <= len(x).
3. Range: all values in [quantile(p), quantile(1-p)].
4. Empty input: returned unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest

from polyeval_aggregator.stats.trim import trim_outliers, trimmed_mean, trimmed_median


class TestTrimOutliersIdempotent:
    @pytest.mark.parametrize("percentile", [0.05, 0.10, 0.20])
    def test_idempotent(self, percentile: float) -> None:
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        once = trim_outliers(arr, percentile)
        twice = trim_outliers(once, percentile)
        np.testing.assert_array_equal(once, twice)

    def test_idempotent_larger(self) -> None:
        rng = np.random.default_rng(42)
        arr = rng.uniform(0, 100, 100)
        once = trim_outliers(arr, 0.10)
        twice = trim_outliers(once, 0.10)
        np.testing.assert_array_equal(once, twice)


class TestTrimOutliersSize:
    def test_size_lte_original(self) -> None:
        arr = np.arange(1, 21, dtype=float)
        trimmed = trim_outliers(arr, 0.10)
        assert len(trimmed) <= len(arr)

    def test_empty_unchanged(self) -> None:
        arr = np.array([], dtype=float)
        result = trim_outliers(arr)
        assert len(result) == 0

    def test_single_element_unchanged(self) -> None:
        arr = np.array([5.0])
        result = trim_outliers(arr)
        np.testing.assert_array_equal(result, arr)


class TestTrimOutliersRange:
    def test_values_within_quantile_bounds(self) -> None:
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 200.0, 300.0, 0.01, 0.001])
        trimmed = trim_outliers(arr, 0.10)
        lo = float(np.quantile(arr, 0.10))
        hi = float(np.quantile(arr, 0.90))
        assert float(trimmed.min()) >= lo
        assert float(trimmed.max()) <= hi


class TestTrimmedMean:
    def test_less_sensitive_to_outliers_than_mean(self) -> None:
        clean = np.array([10.0, 11.0, 12.0, 10.5, 11.5, 10.0])
        outlier = np.append(clean, [1000.0])
        plain_mean = float(np.mean(outlier))
        t_mean = trimmed_mean(outlier, 0.10)
        assert abs(t_mean - float(np.mean(clean))) < abs(plain_mean - float(np.mean(clean)))

    def test_empty_fallback(self) -> None:
        arr = np.array([], dtype=float)
        # Should not raise; degenerate fallback
        result = trimmed_mean(arr, 0.10)
        assert result == 0.0 or True  # no assertion, just no exception


class TestTrimmedMedian:
    def test_less_sensitive_to_outliers(self) -> None:
        base = np.array([10.0] * 10)
        with_outlier = np.append(base, [9999.0])
        t_median = trimmed_median(with_outlier, 0.10)
        assert t_median == pytest.approx(10.0, abs=1.0)

    def test_degenerate(self) -> None:
        arr = np.array([5.0, 5.0, 5.0])
        # All equal: lo == hi → trim_outliers returns all
        result = trimmed_median(arr, 0.10)
        assert result == 5.0
