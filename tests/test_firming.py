import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import beta

from analytic_ucf import beta_dirac_cdf_components, monte_carlo_convergence
from firming import (FirmingConfig, backed_loss_for_samples, dispatch_samples,
                     expected_firming, scenario_response)
from ucf_core import Distribution, cost_parts, synthetic_beta


@pytest.fixture
def battery():
    return FirmingConfig('battery', discharge_mw=20, charge_mw=20, energy_mwh=40,
                         soc=.5, eta_dis=.9, eta_ch=.9, cost_eur_per_mwh=10)


def test_battery_scenario_firming_and_energy(battery):
    assert battery.limits(1) == pytest.approx((18,20))
    x = scenario_response(55,40,1,battery)
    assert x['delivered_mw'] == pytest.approx(55)
    assert x['discharge_mw'] == pytest.approx(15)
    assert x['charge_mw'] == 0
    assert x['residual_deficit_mw'] == 0
    assert x['energy_final_mwh'] == pytest.approx(20-15/.9)
    assert x['soc_final'] == pytest.approx((20-15/.9)/40)
    y = scenario_response(55,95,1,battery)
    assert y['charge_mw'] == 20
    assert y['delivered_mw'] == 75
    assert y['residual_surplus_mw'] == 20
    assert y['energy_final_mwh'] == pytest.approx(38)


def test_power_and_energy_limits_for_different_durations(battery):
    assert battery.limits(2) == pytest.approx((9, 20/(.9*2)))
    empty = FirmingConfig('battery',20,20,40,0,.9,.9,10)
    full = FirmingConfig('battery',20,20,40,1,.9,.9,10)
    assert empty.limits(1)[0] == 0
    assert full.limits(1)[1] == 0
    for cfg in [battery, empty, full]:
        for h in [.25,1,4]:
            for p in [0,10,55,80,100]:
                ans = scenario_response(55,p,h,cfg)
                assert 0 <= ans['energy_final_mwh'] <= cfg.energy_mwh
                assert ans['charge_mw'] * ans['discharge_mw'] == 0
                assert ans['residual_deficit_mw'] * ans['residual_surplus_mw'] == 0


def test_dispatchable_reserve_has_energy_limit_and_no_charging():
    cfg=FirmingConfig('reserve',discharge_mw=25,energy_mwh=10,cost_eur_per_mwh=30)
    assert cfg.limits(2)==pytest.approx((5,0))
    a=scenario_response(50,0,2,cfg)
    assert a['discharge_mw']==5
    assert a['residual_deficit_mw']==45
    assert a['reserve_energy_remaining_mwh']==0
    b=scenario_response(50,80,2,cfg)
    assert b['charge_mw']==0 and b['residual_surplus_mw']==30


def test_no_backup_equals_original_ucf():
    d=Distribution([0,30,60,100],[1,2,3,1],100)
    no=FirmingConfig()
    summary=expected_firming(55,100,35,1,d,no)
    assert summary.total_cost_eur == pytest.approx(cost_parts(55,100,35,1,d)[2])
    assert summary.baseline_cost_eur == pytest.approx(summary.total_cost_eur)
    p=np.array([0,30,60,100]); original=1*(100*np.maximum(55-p,0)+35*np.maximum(p-55,0))
    assert backed_loss_for_samples(55,p,100,35,1,no) == pytest.approx(original)


def test_beta_firmed_analytic_matches_pdf_quadrature_and_mc(battery):
    d=synthetic_beta(.55,16,100);s=55;co=100;cu=35;h=1
    summary=expected_firming(s,co,cu,h,d,battery,(.55,16))
    a,b=8.8,7.2; cuts=[0,(s-18)/100,s/100,(s+20)/100,1]
    expected=sum(quad(lambda z: float(backed_loss_for_samples(s,[100*z],co,cu,h,battery)[0]) * beta.pdf(z,a,b),x,y,epsabs=1e-8)[0]
                 for x,y in zip(cuts,cuts[1:]))
    assert summary.total_cost_eur == pytest.approx(expected, rel=1e-9, abs=1e-6)
    n,means,se=monte_carlo_convergence(s,co,cu,h,d,100000,beta_parameters=(.55,16),
        loss_function=lambda p: backed_loss_for_samples(s,p,co,cu,h,battery))
    assert abs(means[-1]-summary.total_cost_eur) < 5*se[-1]
    assert summary.shortfall_covered_probability == pytest.approx(1-beta.cdf(.37,a,b))
    assert summary.schedule_matched_probability == pytest.approx(beta.cdf(.75,a,b)-beta.cdf(.37,a,b))


def test_firmed_transport_uses_shifted_thresholds(battery):
    d=synthetic_beta(.55,16,100); summary=expected_firming(55,100,35,1,d,battery,(.55,16))
    lower=beta_dirac_cdf_components(55-18,.55,16,100)[0]
    upper=beta_dirac_cdf_components(55+20,.55,16,100)[1]
    assert summary.residual_deficit_mw == pytest.approx(lower,abs=1e-9)
    assert summary.residual_surplus_mw == pytest.approx(upper,abs=1e-9)
    assert summary.post_w1_mw == pytest.approx(lower+upper)
    assert summary.residual_cost_eur == pytest.approx(100*lower+35*upper)
    assert summary.post_w1_mw < summary.raw_deficit_mw+summary.raw_surplus_mw


def test_high_throughput_cost_can_raise_total_cost():
    d=Distribution([0,100],[1,1],100)
    cfg=FirmingConfig('battery',100,100,100,.5,1,1,1000)
    summary=expected_firming(50,10,10,1,d,cfg)
    assert summary.residual_cost_eur == 0
    assert summary.total_cost_eur > summary.baseline_cost_eur


@pytest.mark.parametrize('kwargs',[{'soc':1.1}, {'eta_dis':0}, {'eta_ch':1.1}, {'discharge_mw':-1}, {'mode':'other'}])
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        FirmingConfig(**kwargs)


def test_weighted_empirical_atoms_at_backup_boundaries():
    dist=Distribution([0,40,50,70,100],[1,2,3,4,5],100)
    cfg=FirmingConfig('battery',discharge_mw=10,charge_mw=20,energy_mwh=100,soc=.5,
                      eta_dis=1,eta_ch=1,cost_eur_per_mwh=7)
    out=expected_firming(50,100,35,1,dist,cfg)
    sample=backed_loss_for_samples(50,dist.p_mw,100,35,1,cfg)
    assert out.total_cost_eur == pytest.approx(np.dot(dist.weight,sample))
    assert out.shortfall_covered_probability == pytest.approx(14/15)
    assert out.schedule_matched_probability == pytest.approx(9/15)
    assert out.residual_deficit_mw == pytest.approx(40/15)
    assert out.residual_surplus_mw == pytest.approx(150/15)


def test_zero_energy_battery_behaves_like_no_backup():
    dist=synthetic_beta(.55,16,100)
    cfg=FirmingConfig('battery',20,20,0,.5,.9,.9,10)
    out=expected_firming(55,100,35,1,dist,cfg,(.55,16))
    assert out.discharge_limit_mw == out.charge_limit_mw == 0
    assert out.backup_cost_eur == 0
    assert out.total_cost_eur == pytest.approx(out.baseline_cost_eur)


def test_custom_mc_loss_validates_shape_and_values():
    dist=synthetic_beta(.55,16,100)
    with pytest.raises(ValueError):
        monte_carlo_convergence(55,100,35,1,dist,1000,loss_function=lambda p: np.array([1]))
    with pytest.raises(ValueError):
        monte_carlo_convergence(55,100,35,1,dist,1000,loss_function=lambda p: np.full_like(p,np.nan))


def test_random_weighted_scenarios_match_direct_vectorised_dispatch():
    rng=np.random.default_rng(20261031)
    for _ in range(80):
        m=100.; s=float(rng.uniform(0,m)); h=float(rng.uniform(.25,4))
        p=rng.uniform(0,m,20); w=rng.uniform(.01,1,20); d=Distribution(p,w,m)
        cfg=FirmingConfig('battery',float(rng.uniform(0,50)),float(rng.uniform(0,50)),
                          float(rng.uniform(0,100)),float(rng.uniform()),
                          float(rng.uniform(.5,1)),float(rng.uniform(.5,1)),float(rng.uniform(0,100)))
        co,cu=rng.uniform(0,200,2)
        summary=expected_firming(s,co,cu,h,d,cfg)
        delivered,dis,ch,short,surplus=dispatch_samples(s,d.p_mw,h,cfg)
        assert summary.total_cost_eur == pytest.approx(float(d.weight@backed_loss_for_samples(s,d.p_mw,co,cu,h,cfg)),abs=1e-9)
        assert summary.post_w1_mw == pytest.approx(float(d.weight@np.abs(delivered-s)),abs=1e-10)
        assert summary.post_w1_mw <= summary.raw_deficit_mw+summary.raw_surplus_mw+1e-10
        assert summary.expected_discharge_mw == pytest.approx(float(d.weight@dis),abs=1e-10)
        assert summary.expected_charge_mw == pytest.approx(float(d.weight@ch),abs=1e-10)
        assert np.all(dis<=cfg.limits(h)[0]+1e-12) and np.all(ch<=cfg.limits(h)[1]+1e-12)
        assert np.all(short*surplus == 0)
