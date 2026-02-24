"""Mathematical utility functions."""
from __future__ import annotations
import math
from typing import List, Tuple
import numpy as np


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to 0-1 range."""
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def weighted_average(values: List[float], weights: List[float]) -> float:
    """Calculate weighted average."""
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def linear_interpolate(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
    """Linear interpolation between two points."""
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)
