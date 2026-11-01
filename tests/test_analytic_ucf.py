import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import beta as beta_dist

from analytic_ucf import (beta_dirac_cdf_components, beta_expected_parts, beta_quantiles,
                          empirical_dirac_cdf_components, monte_carlo_convergence)
from ucf_core import Distribution, cost_parts, synthetic_beta


@pytest.mark.parametrize('mu,k,s', [(0.55,16,55),(.10,5,5),(.90,5,90),(.50,40,20),(.70,12,0),(.30,12,100)])
def test_beta_closed_form_matches_independent_pdf_quadrature(mu,k,s):
    m=100; co=95; cu=35; h=1.5; a=mu*k; b=(1-mu)*k; z=s/m
    over_int = quad(lambda x: (s-m*x)*beta_dist.pdf(x,a,b), 0,z,epsabs=1e-9)[0] if z else 0.0
    under_int = quad(lambda x: (m*x-s)*beta_dist.pdf(x,a,b), z,1,epsabs=1e-9)[0] if z < 1 else 0.0
    over, under, total = beta_expected_parts(s,co,cu,h,mu,k,m)
    assert over == pytest.approx(h*co*over_int, rel=2e-8, abs=1e-6)
    assert under == pytest.approx(h*cu*under_int, rel=2e-8, abs=1e-6)
    assert total == pytest.approx(over+under)


@pytest.mark.parametrize('mu,k,s', [(0.55,16,55),(.10,5,5),(.90,5,90),(.50,40,20),(.70,12,0),(.30,12,100)])
@pytest.mark.parametrize('co,cu', [(100,35),(50,50),(0,80),(90,0)])
def test_dirac_cdf_transport_reproduces_beta_ucf(mu,k,s,co,cu):
    over,under,analytic=beta_expected_parts(s,co,cu,2,mu,k,100)
    left,right,distance=beta_dirac_cdf_components(s,mu,k,100)
    assert left >= 0 and right >= 0
    assert distance == pytest.approx(left+right)
    assert 2*(co*left+cu*right) == pytest.approx(analytic, abs=1e-6, rel=1e-9)
    if co==cu:
        assert 2*co*distance == pytest.approx(analytic, abs=1e-6, rel=1e-9)


@pytest.mark.parametrize('s', [0,20,50,100])
def test_dirac_transport_empirical_atoms_and_asymmetric_penalties(s):
    d=Distribution([0,20,50,100],[1,3,2,4],100)
    left,right,distance=empirical_dirac_cdf_components(s,d)
    assert distance == pytest.approx(left+right)
    assert left == pytest.approx(np.dot(d.weight,np.maximum(s-d.p_mw,0)))
    assert right == pytest.approx(np.dot(d.weight,np.maximum(d.p_mw-s,0)))
    assert 1.25*(100*left+35*right) == pytest.approx(cost_parts(s,100,35,1.25,d)[2])
    assert 1.25*40*distance == pytest.approx(cost_parts(s,40,40,1.25,d)[2])


def test_continuous_beta_mc_reproducible_and_agrees_with_exact_ucf():
    d=synthetic_beta(.55,16,100)
    target=beta_expected_parts(55,100,35,1,.55,16,100)[2]
    n, mean, se=monte_carlo_convergence(55,100,35,1,d,100000,seed=42,beta_parameters=(.55,16))
    n2, mean2, se2=monte_carlo_convergence(55,100,35,1,d,100000,seed=42,beta_parameters=(.55,16))
    assert n[-1] == 100000 and np.all(np.diff(n)>0)
    assert mean == pytest.approx(mean2) and se == pytest.approx(se2)
    assert abs(mean[-1]-target) < 4*se[-1]
    assert abs(mean[-1]-target)/target < .01


def test_empirical_mc_and_zero_cost():
    d=Distribution([0,50,100],[1,2,1],100)
    n, mean, se=monte_carlo_convergence(60,0,0,1,d,1000)
    assert np.all(mean==0) and np.all(se==0)
    n, mean, se=monte_carlo_convergence(60,100,35,1,d,100000)
    assert abs(mean[-1]-cost_parts(60,100,35,1,d)[2]) < 5*se[-1]


def test_beta_quantiles_for_visualisation():
    u=np.array([.03,.5,.97]); q=beta_quantiles(u,.55,16,100)
    assert np.all(np.diff(q)>0)
    assert q == pytest.approx(100*beta_dist.ppf(u,8.8,7.2))
