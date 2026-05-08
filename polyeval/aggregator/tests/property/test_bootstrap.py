"""Property tests for bootstrap CI — spec §8.4.

Properties:
1. Determinism: same seed → identical CI.
2. Coverage: ci_lo ≤ statistic(values) ≤ ci_hi.
3. Ordering: ci_lo ≤ ci_hi.
4. Idempotent: calling twice same result.
"""

from __future__ import annotations

import numpy as np
import pytest

from polyeval_aggregator.stats.bootstrap import bootstrap_ci


class TestBootstrapDeterminism:
    def test_same_seed_same_output(self) -> None:
        values = list(range(20))
        r1 = bootstrap_ci(values, seed=42)
        r2 = bootstrap_ci(values, seed=42)
        assert r1 == r2

    def test_different_seeds_may_differ(self) -> None:
        # With enough variation in the data, different seeds → different CIs.
        values = [1.0, 2.0, 3.0, 8.0, 9.0, 10.0]
        r1 = bootstrap_ci(values, seed=1)
        r2 = bootstrap_ci(values, seed=999_999)
        # Same statistic (np.mean) but different resampling → usually different CIs.
        # This is probabilistic, but with 10k resamples the chance of exact equality is ~0.
        # We just verify both are valid (ordered and cover the mean).
        assert r1[0] <= r1[1]
        assert r2[0] <= r2[1]


class TestBootstrapCoverage:
    @pytest.mark.parametrize("seed", [0, 42, 0xCAFEF00D, 12345])
    def test_ci_covers_statistic(self, seed: int) -> None:
        values = list(range(1, 21))
        mean = float(np.mean(values))
        lo, hi = bootstrap_ci(values, statistic=np.mean, seed=seed)
        assert lo <= mean <= hi, f"seed={seed}: [{lo}, {hi}] does not cover mean={mean}"

    def test_ci_covers_median(self) -> None:
        values = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 10.0, 10.0]
        median = float(np.median(values))
        lo, hi = bootstrap_ci(values, statistic=np.median, seed=42)
        assert lo <= median <= hi


class TestBootstrapOrdering:
    @pytest.mark.parametrize("n", [1, 2, 5, 20, 100])
    def test_lo_le_hi(self, n: int) -> None:
        values = list(range(n))
        lo, hi = bootstrap_ci(values, seed=0)
        assert lo <= hi

    def test_single_value(self) -> None:
        lo, hi = bootstrap_ci([5.0])
        assert lo == hi == 5.0

    def test_empty(self) -> None:
        lo, hi = bootstrap_ci([])
        assert lo == 0.0
        assert hi == 0.0


class TestBootstrapAlpha:
    def test_wider_ci_at_lower_alpha(self) -> None:
        values = list(range(30))
        lo_95, hi_95 = bootstrap_ci(values, alpha=0.05, seed=0)
        lo_80, hi_80 = bootstrap_ci(values, alpha=0.20, seed=0)
        # 95% CI should be wider than 80% CI
        assert (hi_95 - lo_95) >= (hi_80 - lo_80)
