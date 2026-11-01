"""Decision-oriented UCF and one-dimensional W1 calculations.

This module is deliberately independent of Streamlit and external services.
A distribution is a weighted set of atoms on [0, capacity_mw]. The synthetic
beta model is represented by a midpoint quadrature measure; user CSVs are
weighted empirical measures. Transport distance is exact for those measures.
The bounded-support DRO value is evaluated by its convex 1-D dual.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
from io import BytesIO, StringIO
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Distribution:
    """A normalised discrete probability measure with bounded MW support."""

    p_mw: np.ndarray
    weight: np.ndarray
    capacity_mw: float

    def __post_init__(self) -> None:
        x = np.asarray(self.p_mw, dtype=float).reshape(-1)
        w = np.asarray(self.weight, dtype=float).reshape(-1)
        m = float(self.capacity_mw)
        if not np.isfinite(m) or m <= 0:
            raise ValueError("Installed capacity must be finite and positive.")
        if x.size == 0 or x.size != w.size:
            raise ValueError("A distribution must contain matching, nonempty values and weights.")
        if not np.isfinite(x).all() or not np.isfinite(w).all():
            raise ValueError("Power and weights must be finite numbers.")
        if (x < 0).any() or (x > m).any():
            raise ValueError("Power must lie in [0, Pmax].")
        if (w <= 0).any() or not np.isfinite(w.sum()) or w.sum() <= 0:
            raise ValueError("Each weight must be strictly positive and finite.")
        unique, inverse = np.unique(x, return_inverse=True)
        weights = np.zeros(unique.size, dtype=float)
        np.add.at(weights, inverse, w)
        weights /= weights.sum()
        # Prevent accidental mutation across calculations and cached figures.
        unique.setflags(write=False)
        weights.setflags(write=False)
        object.__setattr__(self, "p_mw", unique)
        object.__setattr__(self, "weight", weights)
        object.__setattr__(self, "capacity_mw", m)

    @property
    def mean(self) -> float:
        return float(np.dot(self.p_mw, self.weight))

    @property
    def n_atoms(self) -> int:
        return int(self.p_mw.size)

    def cdf(self, points: Iterable[float]) -> np.ndarray:
        pts = np.asarray(points, dtype=float)
        cum = np.r_[0.0, np.cumsum(self.weight)]
        idx = np.searchsorted(self.p_mw, pts, side="right")
        return cum[idx]

    def quantile(self, levels: Iterable[float]) -> np.ndarray:
        levels = np.asarray(levels, dtype=float)
        if np.any(~np.isfinite(levels)) or np.any(levels < 0) or np.any(levels > 1):
            raise ValueError("Quantile levels must be between zero and one.")
        cum = np.cumsum(self.weight)
        idx = np.searchsorted(cum, levels, side="left")
        return self.p_mw[np.clip(idx, 0, self.n_atoms - 1)]


def synthetic_beta(mean_fraction: float, concentration: float, capacity_mw: float, n: int = 200) -> Distribution:
    """Midpoint-normalised beta density, returned as a discrete measure."""
    mu, k, m = float(mean_fraction), float(concentration), float(capacity_mw)
    if not (0 < mu < 1 and k > 0 and n >= 2 and m > 0):
        raise ValueError("Invalid beta parameters.")
    z = (np.arange(n, dtype=float) + 0.5) / n
    a, b = mu * k, (1.0 - mu) * k
    logw = (a - 1) * np.log(z) + (b - 1) * np.log1p(-z)
    weights = np.exp(logw - np.max(logw))
    return Distribution(z * m, weights, m)


def validate_inputs(schedule: float, co: float, cu: float, hours: float, dist: Distribution) -> None:
    vals = np.array([schedule, co, cu, hours], dtype=float)
    if not np.isfinite(vals).all():
        raise ValueError("Inputs must be finite.")
    if not 0 <= schedule <= dist.capacity_mw:
        raise ValueError("Scheduled power must lie within [0, Pmax].")
    if co < 0 or cu < 0 or hours <= 0:
        raise ValueError("Penalties must be nonnegative and interval duration positive.")


def cost_parts(schedule: float, co: float, cu: float, hours: float, dist: Distribution) -> tuple[float, float, float]:
    """Return expected overestimation, underestimation, and total cost (€)."""
    validate_inputs(schedule, co, cu, hours, dist)
    over = hours * co * float(np.dot(dist.weight, np.maximum(schedule - dist.p_mw, 0.0)))
    under = hours * cu * float(np.dot(dist.weight, np.maximum(dist.p_mw - schedule, 0.0)))
    return over, under, over + under


def loss_for_samples(schedule: float, co: float, cu: float, hours: float, values: np.ndarray) -> np.ndarray:
    return hours * (co * np.maximum(schedule - values, 0.0) + cu * np.maximum(values - schedule, 0.0))


def nominal_curve(grid: np.ndarray, co: float, cu: float, hours: float, dist: Distribution) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid = np.asarray(grid, dtype=float).reshape(-1)
    if len(grid) == 0:
        return np.array([]), np.array([]), np.array([])
    validate_inputs(float(grid.min()), co, cu, hours, dist)
    validate_inputs(float(grid.max()), co, cu, hours, dist)
    diff = grid[:, None] - dist.p_mw[None, :]
    over = hours * co * (np.maximum(diff, 0) @ dist.weight)
    under = hours * cu * (np.maximum(-diff, 0) @ dist.weight)
    return over, under, over + under


def nominal_optimum(co: float, cu: float, dist: Distribution) -> float | None:
    """A minimiser of the standalone UCF; None indicates all schedules optimal."""
    if not np.isfinite(co) or not np.isfinite(cu) or co < 0 or cu < 0:
        raise ValueError("Penalties must be finite and nonnegative.")
    if co == 0 and cu == 0:
        return None
    if cu == 0:
        return 0.0
    if co == 0:
        return dist.capacity_mw
    return float(dist.quantile([cu / (co + cu)])[0])


def subgradient(schedule: float, co: float, cu: float, hours: float, dist: Distribution) -> tuple[float, float]:
    """Return the left and right slopes; at an atom these may differ."""
    validate_inputs(schedule, co, cu, hours, dist)
    below = float(dist.weight[dist.p_mw < schedule].sum())
    through = float(dist.weight[dist.p_mw <= schedule].sum())
    return hours * ((co + cu) * below - cu), hours * ((co + cu) * through - cu)


def w1(a: Distribution, b: Distribution) -> float:
    """Exact 1-Wasserstein distance for two bounded 1-D discrete measures."""
    if not np.isclose(a.capacity_mw, b.capacity_mw, rtol=0, atol=1e-12):
        raise ValueError("Distributions must use the same capacity/support.")
    x = np.unique(np.r_[0.0, a.p_mw, b.p_mw, a.capacity_mw])
    return float(np.sum(np.abs(a.cdf(x[:-1]) - b.cdf(x[:-1])) * np.diff(x)))


def dro_curve(grid: np.ndarray, co: float, cu: float, hours: float, epsilon_mw: float,
              dist: Distribution, iterations: int = 38, batch_size: int = 80) -> np.ndarray:
    """Worst E[loss] over the continuous support [0,M] and W1 ball of the discrete reference.

    For each reference atom x, max_z(loss(s,z) - λ|z-x|) is attained at
    z in {0, x, M}: on each side of x it is a convex piecewise-linear function.
    The dual is convex in λ and minimised by bisection on its subgradient.
    """
    grid = np.asarray(grid, dtype=float).reshape(-1)
    if grid.size == 0:
        return np.array([])
    validate_inputs(float(grid.min()), co, cu, hours, dist)
    validate_inputs(float(grid.max()), co, cu, hours, dist)
    if not np.isfinite(epsilon_mw) or epsilon_mw < 0:
        raise ValueError("Wasserstein radius must be nonnegative and finite.")
    if iterations < 1 or batch_size < 1:
        raise ValueError("Invalid solver settings.")
    _, _, nominal = nominal_curve(grid, co, cu, hours, dist)
    aa, bb, m = co * hours, cu * hours, dist.capacity_mw
    lip = max(aa, bb)
    if epsilon_mw == 0 or lip == 0:
        return nominal
    x = dist.p_mw[None, :]
    w = dist.weight
    results = np.empty_like(grid)
    for start in range(0, grid.size, batch_size):
        s = grid[start:start + batch_size, None]
        stay = aa * np.maximum(s - x, 0.0) + bb * np.maximum(x - s, 0.0)
        low = np.zeros(s.shape[0]); high = np.full(s.shape[0], lip)
        for _ in range(iterations):
            lam = (low + high) / 2
            left = aa * s - lam[:, None] * x
            right = bb * (m - s) - lam[:, None] * (m - x)
            choose_left = (left > stay) & (left >= right)
            choose_right = (right > stay) & (right > left)
            distance = choose_left * x + choose_right * (m - x)
            movement = distance @ w
            low = np.where(movement > epsilon_mw, lam, low)
            high = np.where(movement > epsilon_mw, high, lam)
        lam = (low + high) / 2
        left = aa * s - lam[:, None] * x
        right = bb * (m - s) - lam[:, None] * (m - x)
        values = lam * epsilon_mw + (np.maximum(np.maximum(stay, left), right) @ w)
        results[start:start + s.shape[0]] = values
    return results


def dro_value(schedule: float, co: float, cu: float, hours: float, epsilon_mw: float, dist: Distribution) -> float:
    return float(dro_curve(np.array([schedule]), co, cu, hours, epsilon_mw, dist)[0])


def binned_components(schedule: float, co: float, cu: float, hours: float, dist: Distribution, bins: int = 40):
    """For each bin return probability- and cost-density heights (bar area = total)."""
    validate_inputs(schedule, co, cu, hours, dist)
    if bins < 1:
        raise ValueError("At least one bin is required.")
    edges = np.linspace(0, dist.capacity_mw, bins + 1)
    width = edges[1] - edges[0]
    x, w = dist.p_mw, dist.weight
    over = x < schedule
    under = x > schedule
    equal = ~(over | under)
    hist = lambda ww: np.histogram(x, bins=edges, weights=ww)[0] / width
    return {
        "centres": (edges[:-1] + edges[1:]) / 2,
        "width": float(width),
        "prob_over": hist(w * over), "prob_under": hist(w * under), "prob_equal": hist(w * equal),
        "cost_over": hist(w * hours * co * np.maximum(schedule - x, 0)),
        "cost_under": hist(w * hours * cu * np.maximum(x - schedule, 0)),
    }


def parse_scenarios(raw: bytes, capacity_mw: float, row_limit: int = 5000) -> tuple[Distribution, Distribution, pd.DataFrame]:
    """Parse p_mw,split[,weight] CSV. No rows are silently discarded."""
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("CSV exceeds the 2 MB limit.")
    try:
        header = next(csv.reader(StringIO(raw.decode("utf-8-sig"))))
        names = [c.strip().lower() for c in header]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate CSV column names are not allowed.")
        frame = pd.read_csv(BytesIO(raw))
    except Exception as exc:
        raise ValueError("CSV could not be read; use UTF-8 with unique headers and comma separators.") from exc
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if len(frame) == 0 or len(frame) > row_limit:
        raise ValueError(f"CSV must contain between 1 and {row_limit} rows.")
    if frame.columns.duplicated().any() or not {"p_mw", "split"}.issubset(frame.columns):
        raise ValueError("Required unique columns are p_mw and split; weight is optional.")
    p = pd.to_numeric(frame["p_mw"], errors="coerce")
    wt = pd.to_numeric(frame["weight"], errors="coerce") if "weight" in frame else pd.Series(np.ones(len(frame)))
    split = frame["split"].astype(str).str.strip().str.lower()
    if not np.isfinite(p.to_numpy()).all() or not np.isfinite(wt.to_numpy()).all():
        raise ValueError("All power and weight values must be finite numbers.")
    if not split.isin(["reference", "comparison"]).all():
        raise ValueError("split values must be reference or comparison.")
    if not (split == "reference").any() or not (split == "comparison").any():
        raise ValueError("Both reference and comparison rows are required.")
    clean = pd.DataFrame({"p_mw": p.to_numpy(), "split": split.to_numpy(), "weight": wt.to_numpy()})
    def group(which: str) -> Distribution:
        part = clean[clean.split == which]
        return Distribution(part.p_mw.to_numpy(), part.weight.to_numpy(), capacity_mw)
    return group("reference"), group("comparison"), clean


def monte_carlo(schedule: float, co: float, cu: float, hours: float, dist: Distribution, n: int, seed: int = 42):
    validate_inputs(schedule, co, cu, hours, dist)
    if n < 2 or n > 500_000:
        raise ValueError("Monte Carlo sample size must be in [2, 500000].")
    rng = np.random.default_rng(seed)
    points = rng.choice(dist.p_mw, size=n, replace=True, p=dist.weight)
    costs = loss_for_samples(schedule, co, cu, hours, points)
    return float(costs.mean()), float(costs.std(ddof=1) / np.sqrt(n))
