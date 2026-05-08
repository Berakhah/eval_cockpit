"""Trimmed-mean utilities — spec §8.3.

drop_top_bottom_percentile(values, 0.10) removes the top and bottom 10%
before any aggregation. Idempotent: trim(trim(x)) == trim(x).
"""

from __future__ import annotations

import numpy as np


def trim_outliers(values: np.ndarray, percentile: float = 0.10) -> np.ndarray:
    """Return values with top/bottom `percentile` fraction removed.

    spec §8.3: drop top and bottom 10%.
    Property: trim(trim(x, p), p) == trim(x, p)  [idempotent].
    """
    if len(values) == 0:
        return values
    lo = float(np.quantile(values, percentile))
    hi = float(np.quantile(values, 1.0 - percentile))
    if lo == hi:
        return values  # degenerate — return all
    return values[(values >= lo) & (values <= hi)]


def trimmed_mean(values: np.ndarray, percentile: float = 0.10) -> float:
    trimmed = trim_outliers(values, percentile)
    if len(trimmed) == 0:
        return float(np.mean(values))
    return float(np.mean(trimmed))


def trimmed_median(values: np.ndarray, percentile: float = 0.10) -> float:
    trimmed = trim_outliers(values, percentile)
    if len(trimmed) == 0:
        return float(np.median(values))
    return float(np.median(trimmed))
