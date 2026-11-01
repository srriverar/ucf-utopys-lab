from io import BytesIO

import numpy as np
import pytest
from scipy.optimize import linprog

from ucf_core import (Distribution, binned_components, cost_parts, dro_curve, dro_value,
                      monte_carlo, nominal_curve, nominal_optimum, parse_scenarios,
                      subgradient, synthetic_beta, w1)


def transport_lp(schedule, co, cu, hours, radius, dist):
    """Independent primal transport LP, including all potential optimal destinations."""
    xs, weights, cap = dist.p_mw, dist.weight, dist.capacity_mw
    targets = np.unique(np.r_[0.0, xs, cap])
    n, m = len(xs), len(targets)
    loss = hours * (co * np.maximum(schedule - targets, 0) + cu * np.maximum(targets - schedule, 0))
    cost = -np.tile(loss, n)
    aeq = np.zeros((n, n*m))
    for i in range(n):
        aeq[i, i*m:(i+1)*m] = 1
    transport = np.abs(xs[:, None] - targets[None, :]).reshape(1, -1)
    result = linprog(cost, A_ub=transport, b_ub=[radius], A_eq=aeq,
                     b_eq=weights, bounds=(0, None), method="highs")
    assert result.success, result.message
    return -result.fun


def test_defaults_and_components():
    d = synthetic_beta(.55, 16, 100)
    e = synthetic_beta(.4, 10, 100)
    over, under, total = cost_parts(55, 100, 35, 1, d)
    assert total == pytest.approx(over + under)
    assert (over, under, total) == pytest.approx((488.42, 170.95, 659.37), abs=.03)
    assert d.mean == pytest.approx(55, abs=.01)
    assert w1(d, e) == pytest.approx(15, abs=.01)
    assert nominal_optimum(100, 35, d) == 47.25
    assert cost_parts(55, 100, 35, 1, e)[2] == pytest.approx(1681.23, abs=.03)
    assert dro_value(55, 100, 35, 1, 12, d) == pytest.approx(1859.37, abs=.03)


def test_w1_exact_unbalanced_and_symmetry():
    a = Distribution([0, 100], [1, 1], 100)
    b = Distribution([25], [1], 100)
    assert w1(a, b) == pytest.approx(50)
    assert w1(b, a) == pytest.approx(w1(a, b))
    assert w1(a, a) == 0
    assert w1(Distribution([0, 0, 2], [1, 2, 3], 2), Distribution([2], [1], 2)) == pytest.approx(1)


def test_discrete_quantiles_and_subgradient():
    d = Distribution([20, 50, 80], [2, 6, 2], 100)
    assert nominal_optimum(3, 7, d) == 50
    left, right = subgradient(50, 3, 7, 1, d)
    assert left < 0 < right
    assert nominal_optimum(0, 0, d) is None
    assert nominal_optimum(10, 0, d) == 0
    assert nominal_optimum(0, 10, d) == 100
    assert nominal_optimum(10, 0, Distribution([0, 70], [1, 1], 100)) == 0
    assert nominal_optimum(0, 10, Distribution([30, 100], [1, 1], 100)) == 100


def test_dual_matches_independent_transport_primal():
    rng = np.random.default_rng(732)
    for _ in range(40):
        cap = float(rng.uniform(20, 150))
        xs = np.round(rng.uniform(0, cap, 5), 4)
        weights = rng.uniform(.1, 1.0, len(xs))
        d = Distribution(xs, weights, cap)
        s = float(rng.uniform(0, cap))
        co, cu, hours = rng.uniform(0, 120), rng.uniform(0, 120), rng.uniform(.2, 3)
        for radius in [0, cap * .04, cap * .37, cap * 1.2]:
            dual = dro_value(s, co, cu, hours, radius, d)
            lp = transport_lp(s, co, cu, hours, radius, d)
            assert dual == pytest.approx(lp, abs=2e-6, rel=2e-8)


def test_dro_bounds_monotonic_and_limits():
    d = Distribution([0, 18, 61, 100], [1, 2, 3, 4], 100)
    grid = np.linspace(0, 100, 21)
    nominal = nominal_curve(grid, 100, 30, .5, d)[2]
    assert dro_curve(grid, 100, 30, .5, 0, d) == pytest.approx(nominal)
    a = dro_curve(grid, 100, 30, .5, 5, d)
    b = dro_curve(grid, 100, 30, .5, 20, d)
    assert np.all(a >= nominal - 1e-7)
    assert np.all(b >= a - 1e-7)
    assert np.all(b <= nominal + .5 * 100 * 20 + 1e-6)
    assert dro_curve(grid, 0, 0, 1, 50, d) == pytest.approx(np.zeros_like(grid))
    high = dro_curve(grid, 100, 30, .5, 100, d)
    assert high == pytest.approx(.5 * np.maximum(100 * grid, 30 * (100-grid)), abs=1e-6)


def test_binned_areas_reconstruct_measures_and_costs():
    d = Distribution([0, 20, 50, 80, 100], [1, 2, 3, 4, 5], 100)
    h = binned_components(50, 100, 35, 2, d, bins=10)
    assert sum((h['prob_over'] + h['prob_under'] + h['prob_equal']) * h['width']) == pytest.approx(1)
    over, under, total = cost_parts(50, 100, 35, 2, d)
    assert sum(h['cost_over'] * h['width']) == pytest.approx(over)
    assert sum(h['cost_under'] * h['width']) == pytest.approx(under)
    assert sum((h['cost_over'] + h['cost_under']) * h['width']) == pytest.approx(total)


def test_monte_carlo_standard_error():
    d = Distribution([0, 40, 100], [1, 2, 2], 100)
    estimate, se = monte_carlo(45, 30, 50, 1, d, 100000, seed=123)
    assert abs(estimate - cost_parts(45, 30, 50, 1, d)[2]) < 5 * se
    assert se > 0


def test_csv_with_weights_and_duplicates():
    raw = b"p_mw,split,weight\n0,reference,1\n10,reference,2\n10,reference,1\n7,comparison,10\n"
    a, b, clean = parse_scenarios(raw, 100)
    assert a.n_atoms == 2
    assert a.mean == pytest.approx(7.5)
    assert b.mean == pytest.approx(7)
    assert len(clean) == 4


@pytest.mark.parametrize('raw', [
    b'p_mw,split\n1,reference\n',
    b'p_mw,split\n1,reference\n1,other\n',
    b'p_mw,split,weight\n1,reference,0\n1,comparison,1\n',
    b'p_mw,split\nnan,reference\n1,comparison\n',
    b'p_mw,split\n-1,reference\n1,comparison\n',
    b'p_mw,split\n101,reference\n1,comparison\n',
    b'p_mw,split\n1,reference\ninf,comparison\n',
    b'p_mw,split,p_mw\n1,reference,2\n1,comparison,2\n',
])
def test_invalid_csv_fails_closed(raw):
    with pytest.raises(ValueError):
        parse_scenarios(raw, 100)


def test_different_support_and_validation():
    with pytest.raises(ValueError):
        w1(Distribution([1], [1], 3), Distribution([1], [1], 4))
    with pytest.raises(ValueError):
        Distribution([0], [-1], 100)
    with pytest.raises(ValueError):
        dro_value(55, 1, 2, 1, -1, Distribution([20], [1], 100))
    with pytest.raises(ValueError):
        cost_parts(101, 1, 2, 1, Distribution([20], [1], 100))


@pytest.mark.parametrize('co,cu', [(0, 70), (90, 0)])
@pytest.mark.parametrize('schedule', [0, 50, 100])
@pytest.mark.parametrize('radius', [0, 12, 100])
def test_dual_primal_when_one_penalty_is_zero(co, cu, schedule, radius):
    d = Distribution([0, 20, 80, 100], [2, 1, 3, 1], 100)
    assert dro_value(schedule, co, cu, 1.5, radius, d) == pytest.approx(
        transport_lp(schedule, co, cu, 1.5, radius, d), abs=2e-6)


def test_comparison_inside_ball_respects_dro_and_sensitivity_bound():
    rng = np.random.default_rng(916)
    for _ in range(30):
        a = Distribution(rng.uniform(0, 100, 7), rng.uniform(.1, 1, 7), 100)
        b = Distribution(rng.uniform(0, 100, 8), rng.uniform(.1, 1, 8), 100)
        s, co, cu, h = float(rng.uniform(0, 100)), float(rng.uniform(0, 200)), float(rng.uniform(0, 200)), .75
        dist = w1(a, b)
        ac = cost_parts(s, co, cu, h, a)[2]
        bc = cost_parts(s, co, cu, h, b)[2]
        assert abs(ac-bc) <= h * max(co, cu) * dist + 1e-7
        assert bc <= dro_value(s, co, cu, h, dist, a) + 1e-6


def test_repository_example_is_valid():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / 'examples' / 'synthetic_scenarios.csv'
    a, b, df = parse_scenarios(p.read_bytes(), 100)
    assert len(df) == 120
    assert a.n_atoms == 60 and b.n_atoms == 60
