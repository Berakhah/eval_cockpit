"""Bootstrap confidence intervals — spec §8.4.

Pure NumPy, seeded RNG, 10 000 resamples, 95% CI by default.
Property invariant: ci_lo ≤ statistic(values) ≤ ci_hi on ≥95% of draws.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0xCAFEF00D,
) -> tuple[float, float]:
    """Return (lo, hi) bootstrap CI at the (1-alpha) level.

    - Deterministic: same seed → same CI.
    - Pure NumPy: no scipy dependency.
    - spec §8.4: 10 000 resamples, 95% level (alpha=0.05).
    """
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return (0.0, 0.0)
    if len(arr) == 1:
        v = float(arr[0])
        return (v, v)

    rng = np.random.default_rng(seed)
    n = len(arr)
    replicates = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        sample = rng.choice(arr, size=n, replace=True)
        replicates[i] = statistic(sample)

    lo = float(np.quantile(replicates, alpha / 2))
    hi = float(np.quantile(replicates, 1.0 - alpha / 2))
    return (lo, hi)
