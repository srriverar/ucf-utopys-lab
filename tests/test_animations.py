import json
import re

import pytest
from animations import schedule_animation, transport_animation
from ucf_core import Distribution, cost_parts


def embedded_data(html):
    return json.loads(re.search(r'const D = (.*);\nconst svg=', html).group(1))


def test_schedule_animation_uses_current_measure_and_penalties():
    dist = Distribution([0, 20, 100], [1, 2, 1], 100)
    html = schedule_animation(80, 30, 2, dist, True)
    data = embedded_data(html)
    assert data['mode'] == 'schedule'
    assert len(data['x']) == 81
    assert data['x'][40] == 50
    assert data['series'][0][40] == pytest.approx(cost_parts(50, 80, 30, 2, dist)[2])
    assert 'Reproducir' in html and 'Pausar' in html
    assert '<script src=' not in html


def test_transport_animation_endpoints_and_english():
    a = Distribution([10], [1], 100)
    b = Distribution([60], [1], 100)
    html = transport_animation(a, b, False)
    data = embedded_data(html)
    assert data['mode'] == 'transport'
    assert data['ref'] == pytest.approx([10] * 17)
    assert data['comp'] == pytest.approx([60] * 17)
    assert '▶ Play' in html and '❚❚ Pause' in html
    assert '<script src=' not in html


def test_mc_convergence_animation_uses_estimates_and_confidence_band():
    from animations import mc_convergence_animation
    html=mc_convergence_animation([100,1000], [12,10.2], [1,.1], 10.0, False)
    data=embedded_data(html)
    assert data['mode']=='mc'
    assert data['analytic']==10.0
    assert data['nValues']==[100,1000]
    assert data['estimates'][-1]==10.2
    assert data['lower'][-1] == pytest.approx(10.2-1.96*.1)
    assert data['upper'][-1] == pytest.approx(10.2+1.96*.1)
    assert 'Monte Carlo' in html


def test_dirac_animation_targets_the_scheduled_atom():
    from animations import dirac_transport_animation
    html=dirac_transport_animation([10,40,90],100,55,30,1200,1200,False)
    data=embedded_data(html)
    assert data['mode']=='dirac'
    assert data['comp']==[55,55,55]
    assert data['distance']==30
    assert data['weightedCost']==1200
    assert data['analytic']==1200
    assert 'Weighted transport' in html


def test_dirac_animation_can_label_post_backup_residual_only():
    from animations import dirac_transport_animation
    html=dirac_transport_animation([40,55,60],100,55,.75,45,45,False,
        source_label='Net delivered',analytic_label='Residual penalty',transport_label='Residual transport')
    data=embedded_data(html)
    assert data['ref']==[40,55,60]
    assert data['comp']==[55,55,55]
    assert data['analyticLabel']=='Residual penalty'
    assert data['transportLabel']=='Residual transport'
    assert data['legend'][2]=='Net delivered'
    assert data['weightedCost']==data['analytic']==45
