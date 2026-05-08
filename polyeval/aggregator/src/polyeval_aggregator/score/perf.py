"""Performance scoring — spec §8.3. Requires Slice 2 baseline."""

from __future__ import annotations

import numpy as np

from ..stats.bootstrap import bootstrap_ci
from ..stats.trim import trimmed_median


def score_perf(
    wall_ns_values: list[int],
    baseline_median_ns: int | None,
    seed: int = 0xCAFEF00D,
) -> tuple[float | None, float | None, float | None]:
    """Return (perf_normalized, ci_lo, ci_hi) or (None, None, None) if no baseline.

    perf_normalized = trimmed_median(wall_ns) / baseline_median_ns (spec §8.3).
    """
    if baseline_median_ns is None or baseline_median_ns <= 0 or not wall_ns_values:
        return (None, None, None)

    arr = np.asarray(wall_ns_values, dtype=float)
    median_wall = trimmed_median(arr)
    perf_normalized = median_wall / baseline_median_ns

    # Bootstrap CI on the ratio.
    ratios = arr / baseline_median_ns
    ci_lo, ci_hi = bootstrap_ci(ratios.tolist(), seed=seed)
    return (perf_normalized, ci_lo, ci_hi)
