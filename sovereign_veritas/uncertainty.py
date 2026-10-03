from __future__ import annotations

import math
from typing import Any


def _real(x: Any) -> float | None:
    """A finite int or float (never bool or str), else None (JG-1, F5)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    v = float(x)
    return v if math.isfinite(v) else None


def normalize_uncertainty(
    *,
    prediction_value: Any = None,
    interval: list[float] | tuple[float, float] | None = None,
    method: str = "unspecified",
    coverage_target: float | None = None,
    nonconformity: float | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], float]:
    """Produce a structured uncertainty dict and a coarse evidence_quality score.

    This is intentionally dependency-free. Real conformal predictors should
    supply interval / nonconformity; this helper only normalizes and scores.

    Quality heuristic (deterministic, explicit, not a statistical claim):
    - base 0.5
    - +0.2 if a finite interval is supplied
    - +0.2 if coverage_target is in (0, 1]
    - +0.1 if nonconformity is provided and finite
    Clamped to [0.0, 1.0].
    """
    uncertainty: dict[str, Any] = {
        "method": method,
        "prediction_value": prediction_value,
    }
    if interval is not None:
        uncertainty["interval"] = list(interval)
    if coverage_target is not None:
        uncertainty["coverage_target"] = coverage_target
    if nonconformity is not None:
        uncertainty["nonconformity"] = nonconformity
    if extra:
        uncertainty.update(extra)

    quality = 0.5
    if interval is not None and len(interval) >= 2:
        lo, hi = _real(interval[0]), _real(interval[1])
        if lo is not None and hi is not None and lo <= hi:
            quality += 0.2
    ct = _real(coverage_target)
    if ct is not None and 0.0 < ct <= 1.0:
        quality += 0.2
    if _real(nonconformity) is not None:
        quality += 0.1

    quality = max(0.0, min(1.0, quality))
    return uncertainty, quality
