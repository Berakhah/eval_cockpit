"""Correctness scoring — spec §8.1."""

from __future__ import annotations

from ..stats.bootstrap import bootstrap_ci


def score_correctness(
    trials_passed: int,
    trials_scored: int,
    seed: int = 0xCAFEF00D,
) -> tuple[float, float, float]:
    """Return (correctness, ci_lo, ci_hi).

    correctness = trials_passed / trials_scored (spec §8.1).
    CI is bootstrap (spec §8.4).
    """
    if trials_scored == 0:
        return (0.0, 0.0, 0.0)

    outcomes = [1.0] * trials_passed + [0.0] * (trials_scored - trials_passed)
    correctness = trials_passed / trials_scored
    ci_lo, ci_hi = bootstrap_ci(outcomes, seed=seed)
    return (correctness, ci_lo, ci_hi)
