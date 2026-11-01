from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def run_at():
    return AppTest.from_file(APP, default_timeout=30).run()


def metric(at, label):
    return next(x.value for x in at.metric if x.label == label)


def test_home_has_only_three_pages_in_requested_order():
    at = run_at()
    assert not at.exception
    assert 'Explorador de costo' in at.header[0].value
    assert at.radio(key='page').value == 'ucf'
    assert at.radio(key='page').options == ['02 · Explorador UCF', '03 · Wasserstein + DRO', '01 · Encaje UTOPYS']
    at.radio(key='language').set_value('English').run()
    assert not at.exception
    assert at.header[0].value == 'Uncertainty cost explorer'
    assert at.radio(key='page').options == ['02 · UCF explorer', '03 · Wasserstein + DRO', '01 · UTOPYS fit']


def test_default_battery_and_mc_compare_same_backed_loss():
    at = run_at()
    assert at.selectbox(key='backup_mode').value == 'battery'
    assert metric(at, 'Renovable disponible') == '40.00 MW'
    assert metric(at, 'Respaldo entrega') == '15.00 MW'
    assert metric(at, 'Potencia neta entregada') == '55.00 MW'
    assert metric(at, 'UCF sin respaldo') == '€659.32'
    assert metric(at, 'Desbalance residual') == '€43.15'
    assert metric(at, 'Operación de respaldo') == '€92.21'
    assert metric(at, 'Costo total esperado') == '€135.37'
    at.select_slider(key='mc_n').set_value(1000).run(timeout=30)
    assert not at.exception
    assert metric(at, 'Analítica · renovable + respaldo') == '€135.37'
    assert metric(at, 'Monte Carlo · N=1,000') == '€136.91'
    assert metric(at, 'Diferencia absoluta') == '€1.54'
    at.radio(key='language').set_value('English').run(timeout=30)
    assert not at.exception
    assert at.select_slider(key='mc_n').value == 1000
    assert metric(at, 'Analytic · renewable + backup') == '€135.37'


def test_schedule_bidirectional_page_controls_and_language_navigation():
    at = run_at()
    old = metric(at, 'Costo total esperado')
    at.slider(key='schedule_inpage').set_value(70.0).run(timeout=30)
    assert not at.exception
    assert at.slider(key='schedule').value == at.slider(key='schedule_inpage').value == 70.0
    assert metric(at, 'Costo total esperado') != old
    assert metric(at, 'Potencia neta entregada') == '58.00 MW' # energy-limited at D=18
    assert any('déficit 12.00 MW' in x.value for x in at.warning)
    at.slider(key='schedule').set_value(60.0).run(timeout=30)
    assert at.slider(key='schedule_inpage').value == 60.0
    at.radio(key='page').set_value('wasserstein').run(timeout=30)
    assert at.slider(key='schedule_inpage').value == 60.0
    w1_old = metric(at, 'W₁(μ, δₛ)')
    at.slider(key='schedule_inpage').set_value(75.0).run(timeout=30)
    assert at.slider(key='schedule').value == 75.0
    assert metric(at, 'W₁(μ, δₛ)') != w1_old
    at.radio(key='language').set_value('English').run(timeout=30)
    assert not at.exception
    assert at.radio(key='page').value == 'wasserstein'
    assert at.slider(key='schedule_inpage').value == 75.0
    assert at.slider(key='schedule').value == 75.0
    at.radio(key='page').set_value('fit').run(timeout=30)
    at.slider(key='schedule').set_value(65.0).run(timeout=30)
    at.radio(key='page').set_value('ucf').run(timeout=30)
    assert not at.exception
    assert at.slider(key='schedule_inpage').value == at.slider(key='schedule').value == 65.0


def test_backup_settings_scenario_and_mode_persist():
    at = run_at()
    at.slider(key='scenario_power').set_value(95.0).run(timeout=30)
    assert metric(at, 'Respaldo absorbe') == '20.00 MW'
    assert metric(at, 'Potencia neta entregada') == '75.00 MW'
    at.slider(key='battery_soc').set_value(0).run(timeout=30)
    at.slider(key='scenario_power').set_value(40.0).run(timeout=30)
    assert metric(at, 'Respaldo entrega') == '0.00 MW'
    assert metric(at, 'Potencia neta entregada') == '40.00 MW'
    at.radio(key='page').set_value('wasserstein').run(timeout=30)
    at.radio(key='language').set_value('English').run(timeout=30)
    assert at.slider(key='battery_soc').value == 0
    assert at.slider(key='scenario_power').value == 40.0
    at.selectbox(key='backup_mode').set_value('reserve').run(timeout=30)
    at.number_input(key='reserve_power').set_value(10.0).run(timeout=30)
    at.number_input(key='reserve_energy').set_value(5.0).run(timeout=30)
    assert metric(at, 'Backup discharges') == '5.00 MW'  # 5 MWh in 1 h
    at.radio(key='page').set_value('fit').run(timeout=30)
    at.radio(key='page').set_value('ucf').run(timeout=30)
    assert at.selectbox(key='backup_mode').value == 'reserve'
    assert at.number_input(key='reserve_power').value == 10.0
    assert at.number_input(key='reserve_energy').value == 5.0
    at.selectbox(key='backup_mode').set_value('none').run(timeout=30)
    assert metric(at, 'Backup discharges') == '0.00 MW'
    assert metric(at, 'Net delivered power') == '40.00 MW'
    assert metric(at, 'Total expected cost') == metric(at, 'UCF without backup')
    at.selectbox(key='backup_mode').set_value('battery').run(timeout=30)
    assert at.slider(key='battery_soc').value == 0
    assert not at.exception


@pytest.mark.parametrize('page', ['ucf', 'wasserstein', 'fit'])
def test_each_remaining_page_runs(page):
    at = run_at()
    at.radio(key='page').set_value(page).run(timeout=30)
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.header) > 0


def test_zero_penalties_still_count_the_fixed_rule_operating_cost():
    at = run_at()
    at.slider(key='co').set_value(0.0)
    at.slider(key='cu').set_value(0.0)
    at.slider(key='epsilon').set_value(0.0).run(timeout=30)
    assert not at.exception
    assert metric(at, 'UCF discreta sin respaldo') == '€0.00'
    assert metric(at, 'Mínimo UCF sin respaldo') == 'Todos'
    assert metric(at, 'Costo total esperado') == '€92.21' # dispatch is fixed, not optimised
    at.selectbox(key='backup_mode').set_value('none').run(timeout=30)
    assert metric(at, 'Costo total esperado') == '€0.00'
    at.radio(key='page').set_value('wasserstein').run(timeout=30)
    assert not at.exception
    assert metric(at, 'UCF analítica sin respaldo') == '€0.00'
    assert metric(at, 'Transporte ponderado') == '€0.00'
    assert any('penalizaciones son iguales' in x.value.lower() for x in at.success)


def test_dirac_before_and_after_backup_and_symmetric_case():
    at = run_at()
    at.radio(key='page').set_value('wasserstein').run(timeout=30)
    assert not at.exception
    assert metric(at, 'UCF analítica sin respaldo') == '€659.32'
    assert metric(at, 'W₁(μ, δₛ)') == '9.7678 MW'
    assert metric(at, 'Transporte ponderado') == '€659.32'
    assert metric(at, 'W₁ antes del respaldo') == '9.7678 MW'
    assert metric(at, 'W₁ después del respaldo') == '0.5467 MW'
    assert metric(at, 'Transporte residual ponderado') == '€43.15'
    assert any('está en MW' in x.value for x in at.info)
    at.slider(key='cu').set_value(100.0).run(timeout=30)
    assert not at.exception
    assert metric(at, 'UCF analítica sin respaldo') == metric(at, 'Transporte ponderado')
    assert any('penalizaciones son iguales' in x.value.lower() for x in at.success)


def test_capacity_clamps_both_schedules_scenario_and_power_limits():
    at = run_at()
    at.number_input(key='battery_dis').set_value(80.0).run(timeout=30)
    at.slider(key='schedule_inpage').set_value(80.0).run(timeout=30)
    at.slider(key='scenario_power').set_value(90.0).run(timeout=30)
    at.slider(key='capacity').set_value(20.0).run(timeout=30)
    assert not at.exception
    assert at.slider(key='schedule').value == at.slider(key='schedule_inpage').value == 20.0
    assert at.slider(key='scenario_power').value == 20.0
    assert at.number_input(key='battery_dis').value <= 20.0
    assert at.slider(key='epsilon').value <= 20.0


def test_csv_upload_prompts_without_fallback():
    at = run_at()
    at.radio(key='source').set_value('csv').run()
    assert not at.exception
    assert any('Cargue el CSV' in x.value for x in at.info)
