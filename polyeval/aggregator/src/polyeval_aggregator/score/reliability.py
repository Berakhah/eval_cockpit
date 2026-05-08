"""Reliability / flake detection — spec §8.2."""

from __future__ import annotations

import numpy as np

_FLAKY_THRESHOLD = 0.95


def score_reliability(outcomes: list[bool]) -> tuple[float, bool]:
    """Return (reliability, flaky).

    reliability = 1 - stddev(outcomes) / N  (spec §8.2).
    flaky if reliability < 0.95 (spec §8.2).
    """
    if not outcomes:
        return (0.0, True)
    n = len(outcomes)
    arr = np.asarray(outcomes, dtype=float)
    flake_rate = float(np.std(arr))  # stddev of binary = flake rate
    reliability = max(0.0, 1.0 - flake_rate)
    flaky = reliability < _FLAKY_THRESHOLD
    return (reliability, flaky)
