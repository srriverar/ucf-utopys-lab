"""Closed-form beta UCF, Dirac transport comparisons, and MC convergence.

The beta formula uses regularised incomplete beta functions. The Dirac W1
comparison independently integrates the beta CDF numerically; for a discrete
measure it uses the existing exact discrete W1 solver. All costs include Δt.
"""
from __future__ import annotations

from typing import Callable
import numpy as np
from scipy.integrate import quad
from scipy.special import betainc, betaincinv

from ucf_core import Distribution, loss_for_samples, validate_inputs, w1


def _beta_parameters(mean_fraction: float, concentration: float, capacity_mw: float):
    mu, k, m = float(mean_fraction), float(concentration), float(capacity_mw)
    if not (np.isfinite(mu) and np.isfinite(k) and np.isfinite(m)
            and 0 < mu < 1 and k > 0 and m > 0):
        raise ValueError("Invalid beta model parameters.")
    return mu, mu * k, (1-mu) * k, m


def beta_expected_parts(schedule: float, co: float, cu: float, hours: float,
                        mean_fraction: float, concentration: float, capacity_mw: float):
    """Exact continuous-beta expected loss, up to special-function precision.

    A = E[(s-P)+], B = E[(P-s)+].  For Z=P/M ~ Beta(a,b),
    E[Z 1{Z<=z}] = (a/(a+b)) I_z(a+1,b).
    """
    mu, a, b, m = _beta_parameters(mean_fraction, concentration, capacity_mw)
    # Reuse the same input validation as the discrete model.
    validate_inputs(schedule, co, cu, hours, Distribution([0.0], [1.0], m))
    z = schedule / m
    F = float(betainc(a, b, z))
    lower_first = m * mu * float(betainc(a + 1, b, z))
    left = max(0.0, schedule * F - lower_first)
    right = max(0.0, m * mu - lower_first - schedule * (1.0 - F))
    over = hours * co * left
    under = hours * cu * right
    return over, under, over + under


def beta_dirac_cdf_components(schedule: float, mean_fraction: float, concentration: float,
                               capacity_mw: float):
    """Independently integrate CDF-based one-sided transport distances in MW.

    W_- = ∫_0^s F(p) dp; W_+ = ∫_s^M [1-F(p)] dp. Their sum is
    W1(Beta, δ_s). Adaptive integration is split at the Dirac atom; unlike
    the closed-form UCF, it does not use truncated beta first moments.
    """
    _, a, b, m = _beta_parameters(mean_fraction, concentration, capacity_mw)
    if not np.isfinite(schedule) or not 0 <= schedule <= m:
        raise ValueError("Invalid schedule.")
    z = schedule / m
    left = m * quad(lambda x: betainc(a, b, x), 0, z, epsabs=1e-11, epsrel=1e-11, limit=200)[0] if z > 0 else 0.0
    right = m * quad(lambda x: 1.0 - betainc(a, b, x), z, 1, epsabs=1e-11, epsrel=1e-11, limit=200)[0] if z < 1 else 0.0
    return float(left), float(right), float(left + right)


def empirical_dirac_cdf_components(schedule: float, dist: Distribution):
    """Exact W1 to δ_s for a finite measure, split by direction (MW)."""
    validate_inputs(schedule, 0.0, 0.0, 1.0, dist)
    distance = w1(dist, Distribution([schedule], [1.0], dist.capacity_mw))
    # E(P-s) = W_+ - W_-, W1 = W_- + W_+.
    delta_mean = dist.mean - schedule
    left = max(0.0, (distance - delta_mean) / 2.0)
    right = max(0.0, (distance + delta_mean) / 2.0)
    return left, right, distance


def beta_quantiles(levels, mean_fraction: float, concentration: float, capacity_mw: float):
    _, a, b, m = _beta_parameters(mean_fraction, concentration, capacity_mw)
    u = np.asarray(levels, dtype=float)
    if np.any(~np.isfinite(u)) or np.any(u < 0) or np.any(u > 1):
        raise ValueError("Quantile levels must be in [0,1].")
    return m * betaincinv(a, b, u)


def monte_carlo_convergence(schedule: float, co: float, cu: float, hours: float,
                            dist: Distribution, n_max: int, seed: int = 42,
                            beta_parameters: tuple[float, float] | None = None,
                            loss_function: Callable[[np.ndarray], np.ndarray] | None = None):
    """Reproducible running MC means and standard errors at up to 81 checkpoints.

    For beta mode, sample the continuous beta itself, not the midpoint atoms.
    Otherwise sample the empirical measure according to its normalised weights.
    An optional loss function may model backup policy and operating cost.
    Confidence bands derived from the standard error are pointwise approximations.
    """
    validate_inputs(schedule, co, cu, hours, dist)
    if not isinstance(n_max, (int, np.integer)) or not 1000 <= n_max <= 100_000:
        raise ValueError("The maximum sample size must be between 1,000 and 100,000.")
    rng = np.random.default_rng(seed)
    if beta_parameters is None:
        values = rng.choice(dist.p_mw, size=n_max, replace=True, p=dist.weight)
    else:
        _, a, b, m = _beta_parameters(beta_parameters[0], beta_parameters[1], dist.capacity_mw)
        values = m * rng.beta(a, b, size=n_max)
    costs = (loss_for_samples(schedule, co, cu, hours, values) if loss_function is None
             else np.asarray(loss_function(values), dtype=float))
    if costs.shape != values.shape or np.any(~np.isfinite(costs)) or np.any(costs < -1e-10):
        raise ValueError("The selected loss must return one finite nonnegative value per sample.")
    counts = np.unique(np.rint(np.geomspace(100, n_max, 81)).astype(int))
    sums = np.cumsum(costs)[counts - 1]
    sumsq = np.cumsum(costs * costs)[counts - 1]
    means = sums / counts
    variances = np.maximum(0.0, (sumsq - counts * means * means) / (counts - 1))
    standard_errors = np.sqrt(variances / counts)
    return counts, means, standard_errors
