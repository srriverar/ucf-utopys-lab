"""Single-interval renewable firming with a battery or dispatchable reserve.

This is an illustrative, deterministic rule applied separately to each outcome,
not an optimal dispatch, a multi-period battery model or a reliability guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.special import betainc

from analytic_ucf import beta_expected_parts
from ucf_core import Distribution, validate_inputs


@dataclass(frozen=True)
class FirmingConfig:
    """AC-side power limits, energy budget, efficiency and marginal operating cost."""
    mode: str = "none"  # none | battery | reserve
    discharge_mw: float = 0.0
    charge_mw: float = 0.0
    energy_mwh: float = 0.0       # battery usable capacity or reserve energy available this interval
    soc: float = 0.5              # fraction of usable battery capacity at the start
    eta_dis: float = 1.0
    eta_ch: float = 1.0
    cost_eur_per_mwh: float = 0.0  # per MWh of AC-side backup throughput

    def __post_init__(self):
        numbers = np.array([self.discharge_mw, self.charge_mw, self.energy_mwh, self.soc,
                            self.eta_dis, self.eta_ch, self.cost_eur_per_mwh], dtype=float)
        if self.mode not in {"none", "battery", "reserve"} or not np.isfinite(numbers).all():
            raise ValueError("Invalid firming configuration.")
        if min(self.discharge_mw, self.charge_mw, self.energy_mwh, self.cost_eur_per_mwh) < 0:
            raise ValueError("Power, energy and operating cost must be nonnegative.")
        if not 0 <= self.soc <= 1 or not 0 < self.eta_dis <= 1 or not 0 < self.eta_ch <= 1:
            raise ValueError("SOC must be in [0,1] and efficiencies in (0,1].")

    def limits(self, hours: float) -> tuple[float, float]:
        """Maximum feasible discharge and charge during the whole interval (MW)."""
        if not np.isfinite(hours) or hours <= 0:
            raise ValueError("Interval duration must be positive and finite.")
        if self.mode == "none":
            return 0.0, 0.0
        if self.mode == "reserve":
            return min(self.discharge_mw, self.energy_mwh / hours), 0.0
        dis = min(self.discharge_mw, self.soc * self.energy_mwh * self.eta_dis / hours)
        ch = min(self.charge_mw, (1 - self.soc) * self.energy_mwh / (self.eta_ch * hours))
        return dis, ch


def dispatch_samples(schedule: float, power, hours: float, cfg: FirmingConfig):
    """Serve deficits, then absorb surpluses, up to limits; vectorised over power."""
    power = np.asarray(power, dtype=float)
    if not np.isfinite(schedule) or schedule < 0 or np.any(~np.isfinite(power)) or np.any(power < 0):
        raise ValueError("Schedule and power must be finite and nonnegative.")
    dis_limit, ch_limit = cfg.limits(hours)
    deficit = np.maximum(schedule - power, 0.0)
    surplus = np.maximum(power - schedule, 0.0)
    dis = np.minimum(deficit, dis_limit)
    ch = np.minimum(surplus, ch_limit)
    delivered = power + dis - ch
    residual_deficit = np.maximum(schedule - delivered, 0.0)
    residual_surplus = np.maximum(delivered - schedule, 0.0)
    return delivered, dis, ch, residual_deficit, residual_surplus


def backed_loss_for_samples(schedule: float, power, co: float, cu: float, hours: float, cfg: FirmingConfig):
    if not np.isfinite([co, cu]).all() or co < 0 or cu < 0:
        raise ValueError("Penalties must be finite and nonnegative.")
    _, dis, ch, deficit, surplus = dispatch_samples(schedule, power, hours, cfg)
    return hours * (co * deficit + cu * surplus + cfg.cost_eur_per_mwh * (dis + ch))


def scenario_response(schedule: float, power: float, hours: float, cfg: FirmingConfig) -> dict:
    delivered, dis, ch, deficit, surplus = dispatch_samples(schedule, [power], hours, cfg)
    result = {"renewable_mw": float(power), "delivered_mw": float(delivered[0]),
              "discharge_mw": float(dis[0]), "charge_mw": float(ch[0]),
              "residual_deficit_mw": float(deficit[0]), "residual_surplus_mw": float(surplus[0])}
    if cfg.mode == "battery":
        initial = cfg.energy_mwh * cfg.soc
        final = initial + cfg.eta_ch * float(ch[0]) * hours - float(dis[0]) * hours / cfg.eta_dis
        result["energy_initial_mwh"] = initial
        result["energy_final_mwh"] = float(np.clip(final, 0, cfg.energy_mwh))
        result["soc_final"] = result["energy_final_mwh"] / cfg.energy_mwh if cfg.energy_mwh > 0 else 0.0
    elif cfg.mode == "reserve":
        result["reserve_energy_remaining_mwh"] = max(0.0, cfg.energy_mwh - float(dis[0]) * hours)
    return result


@dataclass(frozen=True)
class FirmingSummary:
    discharge_limit_mw: float
    charge_limit_mw: float
    raw_deficit_mw: float
    raw_surplus_mw: float
    residual_deficit_mw: float
    residual_surplus_mw: float
    expected_discharge_mw: float
    expected_charge_mw: float
    baseline_cost_eur: float
    residual_cost_eur: float
    backup_cost_eur: float
    total_cost_eur: float
    shortfall_covered_probability: float
    schedule_matched_probability: float

    @property
    def post_w1_mw(self) -> float:
        return self.residual_deficit_mw + self.residual_surplus_mw


def expected_firming(schedule: float, co: float, cu: float, hours: float, dist: Distribution,
                     cfg: FirmingConfig, beta_parameters: tuple[float, float] | None = None) -> FirmingSummary:
    """Exact expected one-interval costs for the specified model and fixed policy.

    For beta this uses closed-form beta moments; for CSV the exact empirical sum.
    Storage always responds greedily, even when its operating cost is higher
    than an imbalance penalty; the policy is not economically optimised.
    """
    validate_inputs(schedule, co, cu, hours, dist)
    m = dist.capacity_mw
    dmax, cmax = cfg.limits(hours)

    def moments(at: float):
        at = float(np.clip(at, 0, m))
        if beta_parameters is not None:
            left, right, _ = beta_expected_parts(at, 1, 1, 1, beta_parameters[0], beta_parameters[1], m)
            return left, right
        p, w = dist.p_mw, dist.weight
        return float(np.dot(w, np.maximum(at-p, 0))), float(np.dot(w, np.maximum(p-at, 0)))

    raw_left, raw_right = moments(schedule)
    residual_left = moments(schedule - dmax)[0]
    residual_right = moments(schedule + cmax)[1]
    dis = max(0.0, raw_left - residual_left)
    ch = max(0.0, raw_right - residual_right)
    baseline = hours * (co * raw_left + cu * raw_right)
    residual = hours * (co * residual_left + cu * residual_right)
    operation = hours * cfg.cost_eur_per_mwh * (dis + ch)

    low, high = schedule - dmax, schedule + cmax
    if beta_parameters is not None:
        mu, k = map(float, beta_parameters)
        if not (0 < mu < 1 and k > 0):
            raise ValueError("Invalid beta parameters.")
        def cdf(x):
            return float(betainc(mu*k, (1-mu)*k, float(np.clip(x/m, 0, 1))))
        short_covered = 1.0 - cdf(low)
        matched = cdf(high) - cdf(low)
    else:
        p, w = dist.p_mw, dist.weight
        short_covered = float(w[p >= low - 1e-12].sum())
        matched = float(w[(p >= low - 1e-12) & (p <= high + 1e-12)].sum())
    return FirmingSummary(dmax, cmax, raw_left, raw_right, residual_left, residual_right,
                          dis, ch, baseline, residual, operation, residual + operation,
                          float(np.clip(short_covered, 0, 1)), float(np.clip(matched, 0, 1)))
