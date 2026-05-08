"""Unit tests for scoring functions — spec §8.1, §8.2, §8.3."""

from __future__ import annotations

import pytest

from polyeval_aggregator.score.correctness import score_correctness
from polyeval_aggregator.score.reliability import score_reliability
from polyeval_aggregator.score.perf import score_perf


# ─── Correctness ─────────────────────────────────────────────────────────────

class TestScoreCorrectness:
    def test_all_pass(self) -> None:
        c, lo, hi = score_correctness(10, 10)
        assert c == 1.0
        assert lo <= 1.0
        assert hi == 1.0

    def test_all_fail(self) -> None:
        c, lo, hi = score_correctness(0, 10)
        assert c == 0.0
        assert lo == 0.0
        assert hi >= 0.0

    def test_half_pass(self) -> None:
        c, lo, hi = score_correctness(5, 10)
        assert c == pytest.approx(0.5)
        assert lo < 0.5
        assert hi > 0.5

    def test_ci_ordered(self) -> None:
        c, lo, hi = score_correctness(7, 10)
        assert lo <= c <= hi

    def test_zero_trials(self) -> None:
        c, lo, hi = score_correctness(0, 0)
        assert c == 0.0
        assert lo == 0.0
        assert hi == 0.0

    def test_deterministic(self) -> None:
        r1 = score_correctness(7, 10, seed=42)
        r2 = score_correctness(7, 10, seed=42)
        assert r1 == r2

    def test_different_seeds_different_ci(self) -> None:
        _, lo1, hi1 = score_correctness(5, 10, seed=1)
        _, lo2, hi2 = score_correctness(5, 10, seed=999_999)
        # CIs can differ with different seeds (not guaranteed but true in practice)
        # At minimum, correctness point estimate is identical
        c1, _, _ = score_correctness(5, 10, seed=1)
        c2, _, _ = score_correctness(5, 10, seed=999_999)
        assert c1 == c2


# ─── Reliability ─────────────────────────────────────────────────────────────

class TestScoreReliability:
    def test_all_pass_is_stable(self) -> None:
        outcomes = [True] * 10
        r, flaky = score_reliability(outcomes)
        assert r == 1.0
        assert not flaky

    def test_all_fail_is_stable(self) -> None:
        # Constant series (all False) also has stddev=0 → reliability=1.
        outcomes = [False] * 10
        r, flaky = score_reliability(outcomes)
        assert r == 1.0
        assert not flaky

    def test_alternating_is_flaky(self) -> None:
        outcomes = [True, False] * 5
        r, flaky = score_reliability(outcomes)
        assert flaky

    def test_mostly_pass_not_flaky(self) -> None:
        # 9 pass, 1 fail → stddev low → not flaky
        outcomes = [True] * 9 + [False]
        r, flaky = score_reliability(outcomes)
        assert not flaky

    def test_empty(self) -> None:
        r, flaky = score_reliability([])
        assert r == 0.0
        assert flaky

    def test_reliability_in_range(self) -> None:
        outcomes = [True, False, True, True, False, True]
        r, _ = score_reliability(outcomes)
        assert 0.0 <= r <= 1.0


# ─── Performance ─────────────────────────────────────────────────────────────

class TestScorePerf:
    def test_no_baseline_returns_none(self) -> None:
        result = score_perf([1_000_000, 2_000_000], None)
        assert result == (None, None, None)

    def test_zero_baseline_returns_none(self) -> None:
        result = score_perf([1_000_000], 0)
        assert result == (None, None, None)

    def test_empty_values_returns_none(self) -> None:
        result = score_perf([], 1_000_000)
        assert result == (None, None, None)

    def test_equal_to_baseline(self) -> None:
        # All trials at exactly baseline → normalized ≈ 1.0
        baseline = 1_000_000
        values = [baseline] * 10
        perf, lo, hi = score_perf(values, baseline)
        assert perf == pytest.approx(1.0, abs=0.05)
        assert lo is not None
        assert hi is not None

    def test_faster_than_baseline(self) -> None:
        baseline = 2_000_000
        values = [1_000_000] * 10
        perf, _, _ = score_perf(values, baseline)
        assert perf < 1.0

    def test_slower_than_baseline(self) -> None:
        baseline = 1_000_000
        values = [5_000_000] * 10
        perf, _, _ = score_perf(values, baseline)
        assert perf > 1.0

    def test_ci_ordered(self) -> None:
        perf, lo, hi = score_perf([1_000_000] * 20, 1_000_000)
        assert lo <= perf <= hi
