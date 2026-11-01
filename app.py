"""UCF × UTOPYS — independent, bilingual research demonstration."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from ucf_core import (cost_parts, dro_curve, dro_value,
                      nominal_curve, nominal_optimum, parse_scenarios, subgradient,
                      synthetic_beta, w1)
from plots import (BLUE, MUTED, ORANGE, PURPLE, TEAL, YELLOW, cdf_figure,
                   component_bars, cost_curve, robust_figure, style)
from animations import (schedule_animation, transport_animation,
                        mc_convergence_animation, dirac_transport_animation)
from analytic_ucf import (beta_expected_parts, beta_dirac_cdf_components, beta_quantiles,
                          empirical_dirac_cdf_components, monte_carlo_convergence)
from firming import (FirmingConfig, backed_loss_for_samples, dispatch_samples,
                     expected_firming, scenario_response)

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="UCF × UTOPYS | Research Lab", page_icon="◈", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
  .stApp { background: #07121f; color: #e7effb; }
  [data-testid="stSidebar"] { background: #0c1a29; border-right: 1px solid #24364a; }
  .block-container { padding-top: 2.1rem; padding-bottom: 4rem; max-width: 1450px; }
  h1, h2, h3 { letter-spacing: -0.035em; }
  h1 { line-height: 1.05; }
  .hero { background: radial-gradient(circle at 86% 10%, rgba(76,224,189,.12), transparent 34%),
             linear-gradient(125deg,#142c3c,#101e30 58%,#162335); border: 1px solid #2a4254;
             border-radius: 18px; padding: 2rem 2.3rem; margin: 0 0 1.2rem; }
  .eyebrow { color: #61e6c4; font-size: .72rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; }
  .hero h1 { font-size: clamp(2rem, 4vw, 3.5rem); margin: .45rem 0 .65rem; color: #f3f8ff; }
  .hero p { max-width: 850px; font-size: 1.05rem; line-height: 1.6; color: #b7c8d9; margin: 0; }
  .hero .tagline { margin-top: 1rem; color: #90a9b9; font-size: .75rem; letter-spacing: .05em; }
  .section-kicker { color: #53d9b7; font-size: .73rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; margin-top: 1.2rem; }
  div[data-testid="stMetric"] { background: #102233; border: 1px solid #263d50; padding: 1rem; border-radius: 12px; }
  div[data-testid="stMetric"] label { color: #a8bdd1; }
  div[data-testid="stMetricValue"] { font-size: clamp(1.25rem,2.2vw,1.9rem); }
  [data-testid="stVerticalBlockBorderWrapper"] { background: #0e1d2c; border-radius: 13px; }
  .smallnote { color: #9fb2c5; font-size: .89rem; line-height: 1.5; }
  .footerline { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #263849; color: #90a5ba; font-size: .82rem; }
  .stDownloadButton button { border-color: #3e6d6b; }
  @media (max-width: 640px) { .hero { padding: 1.35rem; } .block-container { padding-top: 1.1rem; } }
</style>
""", unsafe_allow_html=True)

def preserve_language_settings():
    # Streamlit 1.50 includes translated labels/options in widget identity.
    # Save the underlying values before the language-change rerun creates new IDs.
    keys = ("page", "capacity", "schedule", "schedule_inpage", "co", "cu", "hours", "epsilon", "source",
            "mean0", "conc0", "mean1", "conc1", "mc_n", "backup_mode", "battery_dis", "battery_ch",
            "battery_energy", "battery_soc", "battery_eta_dis", "battery_eta_ch", "battery_cost",
            "reserve_power", "reserve_energy", "reserve_cost", "scenario_power")
    st.session_state["_language_backup"] = {key: st.session_state[key] for key in keys if key in st.session_state}


with st.sidebar:
    st.markdown('<div class="eyebrow">Independent research demo</div>', unsafe_allow_html=True)
    st.markdown("### ◈ UCF × UTOPYS")
    language = st.radio("IDIOMA / LANGUAGE", ["Español", "English"], horizontal=True, key="language",
                        on_change=preserve_language_settings)
    es = language == "Español"

for _key, _value in st.session_state.pop("_language_backup", {}).items():
    st.session_state[_key] = _value


def t(spanish: str, english: str) -> str:
    return spanish if es else english


def eur(x: float) -> str:
    return f"€{x:,.2f}"


def mw(x: float) -> str:
    return f"{x:,.2f} MW"


def sync_schedule_from_sidebar():
    st.session_state["schedule_inpage"] = st.session_state["schedule"]


def sync_schedule_from_page():
    st.session_state["schedule"] = st.session_state["schedule_inpage"]


# Preserve the original page numbers while moving 01 to the end.
pages = {
    "ucf": t("02 · Explorador UCF", "02 · UCF explorer"),
    "wasserstein": t("03 · Wasserstein + DRO", "03 · Wasserstein + DRO"),
    "fit": t("01 · Encaje UTOPYS", "01 · UTOPYS fit"),
}
with st.sidebar:
    page = st.radio(t("NAVEGACIÓN", "NAVIGATION"), options=list(pages), format_func=lambda key: pages[key], key="page")
    st.markdown("---")
    st.markdown(f"**{t('Parámetros del experimento', 'Experiment settings')}**")
    capacity = st.slider(t("Capacidad Pmax (MW)", "Capacity Pmax (MW)"), 20.0, 1000.0, 100.0, 10.0, key="capacity")
    if "schedule" not in st.session_state:
        st.session_state["schedule"] = min(55.0, capacity)
    elif st.session_state["schedule"] > capacity:
        st.session_state["schedule"] = capacity
    schedule = st.slider(t("Potencia programada Ps (MW)", "Scheduled power Ps (MW)"),
                         min_value=0.0, max_value=capacity, step=.25,
                         key="schedule", on_change=sync_schedule_from_sidebar)
    co = st.slider(t("Penalización por sobreestimar (€/MWh)", "Overestimation penalty (€/MWh)"), 0.0, 300.0, 100.0, 5.0, key="co",
                   help=t("Ps > P: déficit frente a lo programado.", "Ps > P: shortfall against the schedule."))
    cu = st.slider(t("Penalización por subestimar (€/MWh)", "Underestimation penalty (€/MWh)"), 0.0, 300.0, 35.0, 5.0, key="cu",
                   help=t("Ps < P: excedente frente a lo programado.", "Ps < P: surplus against the schedule."))
    hours = st.slider(t("Duración Δt (h)", "Interval Δt (h)"), .25, 4.0, 1.0, .25, key="hours")
    if st.session_state.get("epsilon", 0.0) > capacity:
        st.session_state["epsilon"] = capacity
    epsilon = st.slider(t("Radio Wasserstein ε (MW)", "Wasserstein radius ε (MW)"), 0.0, capacity, min(12.0, capacity), .5, key="epsilon")
    st.markdown("---")
    source = st.radio(t("Distribuciones", "Distributions"), ["beta", "csv"],
                      format_func=lambda x: t("Beta sintética", "Synthetic beta") if x == "beta" else t("Cargar CSV", "Upload CSV"), key="source")
    if source == "beta":
        with st.expander(t("Ajustar distribuciones sintéticas", "Adjust synthetic distributions"), expanded=False):
            mean0 = st.slider(t("Media objetivo referencia / Pmax", "Target reference mean / Pmax"), .10, .90, .55, .01, key="mean0")
            conc0 = st.slider(t("Concentración referencia", "Reference concentration"), 5.0, 40.0, 16.0, 1.0, key="conc0")
            mean1 = st.slider(t("Media objetivo comparación / Pmax", "Target comparison mean / Pmax"), .10, .90, .40, .01, key="mean1")
            conc1 = st.slider(t("Concentración comparación", "Comparison concentration"), 5.0, 40.0, 10.0, 1.0, key="conc1")
        reference = synthetic_beta(mean0, conc0, capacity)
        comparison = synthetic_beta(mean1, conc1, capacity)
        dataset_label = t("Beta sintética (200 puntos por distribución)", "Synthetic beta (200 points per distribution)")
    else:
        st.caption(t("CSV UTF-8: p_mw, split y weight opcional. split: reference o comparison. Hasta 5.000 filas y 2 MB.",
                     "UTF-8 CSV: p_mw, split and optional weight. split: reference or comparison. Up to 5,000 rows and 2 MB."))
        st.caption(t("El archivo se transmite al servidor de Streamlit. No cargue datos sensibles sin autorización e infraestructura adecuadas.",
                     "The file is sent to the Streamlit server. Do not upload sensitive data without appropriate permission and infrastructure."))
        sample = (ROOT / "examples" / "synthetic_scenarios.csv").read_bytes()
        st.download_button(t("Descargar CSV sintético de ejemplo", "Download synthetic example CSV"), sample,
                           file_name="synthetic_scenarios.csv", mime="text/csv", key="sample_download")
        # Keep the uploader's identity stable across language changes so an uploaded file survives.
        uploaded = st.file_uploader("Archivo de escenarios / Scenario file", type=["csv"], key="csv_file")
        if uploaded is None:
            st.info(t("Cargue el CSV para continuar o cambie a Beta sintética.", "Upload the CSV to continue, or switch to Synthetic beta."))
            st.stop()
        try:
            reference, comparison, clean_csv = parse_scenarios(uploaded.getvalue(), capacity)
        except ValueError as exc:
            st.error(t("El archivo no se utilizó. Verifique columnas, rangos y pesos.", "The file was not used. Check columns, ranges and weights.") + f"\n\n{exc}")
            st.stop()
        dataset_label = t("CSV del usuario", "User CSV") + f" · {len(clean_csv):,} " + t("filas", "rows")
    st.caption(t("Referencia: ", "Reference: ") + f"{reference.n_atoms:,} " + t("átomos", "atoms") + " · " +
               t("comparación: ", "comparison: ") + f"{comparison.n_atoms:,}")


# This is a research prototype, not a facility or production control system.
st.markdown(f"""
<div class="hero">
  <div class="eyebrow">{t('Laboratorio de investigación independiente', 'Independent research laboratory')}</div>
  <h1>UCF <span style="color:#58dfbd">×</span> UTOPYS</h1>
  <p>{t('De la incertidumbre renovable a decisiones interpretables: una propuesta para conectar funciones de costo, modelos estocásticos y validación física.', 'From renewable uncertainty to interpretable decisions: a proposal connecting uncertainty cost functions, stochastic models and physical validation.')}</p>
  <div class="tagline">{t('PROPUESTA DE COOPERACIÓN · PROTOTIPO NO OFICIAL · SIN CONEXIÓN A EMT', 'COLLABORATION PROPOSAL · UNOFFICIAL PROTOTYPE · NO EMT CONNECTION')}</div>
</div>""", unsafe_allow_html=True)
st.caption(t("Herramienta exploratoria asociada a la línea de investigación UCF del profesor Sergio Rivera. No está afiliada, conectada ni validada por UTOPYS.",
             "Exploratory tool associated with Professor Sergio Rivera’s UCF research. It is not affiliated, connected to, or validated by UTOPYS."))


_FIRMING_KEYS = ("backup_mode", "battery_dis", "battery_ch", "battery_energy", "battery_soc",
                 "battery_eta_dis", "battery_eta_ch", "battery_cost", "reserve_power",
                 "reserve_energy", "reserve_cost", "scenario_power")


def interactive_firming_controls(capacity: float, side_schedule: float):
    """Render the in-page schedule and one-interval backup settings on pages 02/03."""
    for key, value in st.session_state.get("_firming_snapshot", {}).items():
        if key not in st.session_state:
            st.session_state[key] = value
    # The sidebar and page sliders share a canonical value via callbacks.
    st.session_state["schedule_inpage"] = float(side_schedule)
    for key in ("battery_dis", "battery_ch", "reserve_power", "scenario_power"):
        if key in st.session_state and st.session_state[key] > capacity:
            st.session_state[key] = float(capacity)
    with st.container(border=True):
        st.markdown(f"#### {t('Ajuste interactivo de Ps', 'Interactive scheduled power Ps')}")
        chosen = st.slider(t("Ps · potencia programada (MW)", "Ps · scheduled power (MW)"),
                           min_value=0.0, max_value=capacity, step=.25, key="schedule_inpage",
                           on_change=sync_schedule_from_page)
        st.caption(t("Mueva Ps aquí o en la barra lateral: ambos controles están sincronizados y actualizan costos, escenario y animaciones.",
                     "Move Ps here or in the sidebar: both controls are linked and update costs, the scenario and animations."))
        live_summary = st.empty()
        with st.expander(t("Respaldo para la renovable · configuración", "Renewable backup · settings"), expanded=True):
            labels = {"battery": t("Batería / ESS", "Battery / ESS"),
                      "reserve": t("Respaldo despachable", "Dispatchable backup"),
                      "none": t("Sin respaldo", "No backup")}
            mode = st.selectbox(t("Tipo de respaldo", "Backup type"), options=list(labels),
                                format_func=lambda option: labels[option], key="backup_mode")
            if mode == "battery":
                x, y, z = st.columns(3)
                dis = x.number_input(t("Descarga máx. (MW)", "Max discharge (MW)"), min_value=0.0,
                                     max_value=capacity, value=min(20.0, capacity), step=1.0, key="battery_dis")
                ch = y.number_input(t("Carga máx. (MW)", "Max charge (MW)"), min_value=0.0,
                                    max_value=capacity, value=min(20.0, capacity), step=1.0, key="battery_ch")
                energy = z.number_input(t("Capacidad útil (MWh)", "Usable capacity (MWh)"), min_value=0.0,
                                        max_value=10000.0, value=40.0, step=5.0, key="battery_energy")
                x, y, z = st.columns(3)
                soc = x.slider(t("SOC inicial (%)", "Initial SOC (%)"), 0, 100, 50, 1, key="battery_soc")
                ed = y.slider(t("Eficiencia descarga (%)", "Discharge efficiency (%)"), 50, 100, 90, 1, key="battery_eta_dis")
                ec = z.slider(t("Eficiencia carga (%)", "Charge efficiency (%)"), 50, 100, 90, 1, key="battery_eta_ch")
                operating_cost = st.number_input(t("Costo de operación por energía AC (€/MWh)", "Operating cost per AC energy (€/MWh)"),
                                                 min_value=0.0, max_value=1000.0, value=10.0, step=1.0, key="battery_cost")
                cfg = FirmingConfig(mode="battery", discharge_mw=dis, charge_mw=ch, energy_mwh=energy,
                                    soc=soc/100, eta_dis=ed/100, eta_ch=ec/100, cost_eur_per_mwh=operating_cost)
            elif mode == "reserve":
                x, y, z = st.columns(3)
                reserve_power = x.number_input(t("Potencia máx. (MW)", "Max backup power (MW)"),
                                               min_value=0.0, max_value=capacity, value=min(20.0, capacity),
                                               step=1.0, key="reserve_power")
                reserve_energy = y.number_input(t("Energía disponible (MWh)", "Available energy (MWh)"),
                                                min_value=0.0, max_value=10000.0, value=40.0, step=5.0, key="reserve_energy")
                reserve_cost = z.number_input(t("Costo respaldo (€/MWh)", "Backup cost (€/MWh)"),
                                              min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key="reserve_cost")
                cfg = FirmingConfig(mode="reserve", discharge_mw=reserve_power, energy_mwh=reserve_energy,
                                    cost_eur_per_mwh=reserve_cost)
                st.caption(t("El respaldo despachable ideal cubre déficit; no absorbe excedentes. No se modelan rampas, arranque ni emisiones.",
                             "Ideal dispatchable backup covers shortfalls; it cannot absorb surplus. Ramps, start-up and emissions are not modelled."))
            else:
                cfg = FirmingConfig()
                st.caption(t("Sin capacidad de respaldo: los resultados corresponden a la renovable sola.",
                             "No backup capacity: results correspond to the renewable resource alone."))
            st.caption(t("Valores ilustrativos. La regla intenta cubrir déficit y absorber excedentes con los límites disponibles; no optimiza el despacho ni representa intervalos futuros.",
                         "Illustrative settings. The rule attempts to cover shortfalls and absorb surpluses within available limits; it does not optimise dispatch or represent future intervals."))
    st.session_state["_firming_snapshot"] = {key: st.session_state[key] for key in _FIRMING_KEYS if key in st.session_state}
    return float(chosen), cfg, live_summary


if page in ("ucf", "wasserstein"):
    schedule, backup, live_summary = interactive_firming_controls(capacity, schedule)
else:
    backup = FirmingConfig()

over, under, nominal = cost_parts(schedule, co, cu, hours, reference)
_, _, comparison_cost = cost_parts(schedule, co, cu, hours, comparison)
distance = w1(reference, comparison)
L = hours * max(co, cu)
nom_opt = nominal_optimum(co, cu, reference)
inside = distance <= epsilon + 1e-10
beta_params = (mean0, conc0) if source == "beta" else None
analytic_over, analytic_under, analytic_cost = (
    beta_expected_parts(schedule, co, cu, hours, mean0, conc0, capacity)
    if beta_params else (over, under, nominal)
)
firming_summary = expected_firming(schedule, co, cu, hours, reference, backup, beta_params)
if page in ("ucf", "wasserstein"):
    with live_summary.container():
        l1, l2, l3 = st.columns(3)
        l1.metric(t("Costo sin respaldo", "Cost without backup"), eur(firming_summary.baseline_cost_eur))
        l2.metric(t("Costo con respaldo", "Cost with backup"), eur(firming_summary.total_cost_eur))
        l3.metric(t("Salida igual a Ps*", "Output equals Ps*"), f"{100*firming_summary.schedule_matched_probability:,.1f}%")
        st.caption(t("*Proporción esperada bajo los supuestos ilustrativos de un intervalo; no es una garantía.",
                     "*Expected proportion under the illustrative single-interval assumptions; not a guarantee."))


def heading(kicker: str, title: str, description: str):
    st.markdown(f'<div class="section-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.header(title)
    st.write(description)


def robust_grid():
    # Includes the nominal optimum and baseline, but remains a grid-based minimum.
    extra = [schedule, reference.mean]
    if nom_opt is not None:
        extra.append(nom_opt)
    grid = np.unique(np.r_[np.linspace(0, capacity, 201), extra])
    reference_curve = nominal_curve(grid, co, cu, hours, reference)[2]
    robust = dro_curve(grid, co, cu, hours, epsilon, reference)
    i = int(np.argmin(robust))
    return grid, reference_curve, robust, (float(grid[i]), float(robust[i]))


def show_firming_dashboard(cfg: FirmingConfig, summary, schedule: float, capacity: float):
    st.subheader(t("Renovable + respaldo · respuesta en un intervalo", "Renewable + backup · one-interval response"))
    observed = st.slider(t("Escenario: potencia renovable disponible P (MW)", "Scenario: available renewable power P (MW)"),
                         0.0, capacity, min(40.0, capacity), .25, key="scenario_power",
                         help=t("Solo cambia el escenario ilustrativo, no la distribución de probabilidad.",
                                "Changes only the illustrative scenario, not the probability distribution."))
    st.session_state.setdefault("_firming_snapshot", {})["scenario_power"] = observed
    response = scenario_response(schedule, observed, hours, cfg)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("Renovable disponible", "Available renewable"), mw(response['renewable_mw']))
    m2.metric(t("Respaldo entrega", "Backup discharges"), mw(response['discharge_mw']))
    m3.metric(t("Respaldo absorbe", "Backup charges"), mw(response['charge_mw']))
    m4.metric(t("Potencia neta entregada", "Net delivered power"), mw(response['delivered_mw']))
    residual_short, residual_surplus = response['residual_deficit_mw'], response['residual_surplus_mw']
    if residual_short < 1e-8 and residual_surplus < 1e-8:
        st.success(t(f"Para este escenario, la salida neta alcanza Ps = {schedule:,.2f} MW. Esto no garantiza el cumplimiento en otros escenarios o intervalos.",
                     f"For this scenario, net output reaches Ps = {schedule:,.2f} MW. This does not guarantee delivery in other scenarios or intervals."))
    else:
        st.warning(t(f"Para este escenario quedan déficit {residual_short:,.2f} MW y excedente {residual_surplus:,.2f} MW frente a Ps = {schedule:,.2f} MW.",
                     f"For this scenario, the remaining shortfall is {residual_short:,.2f} MW and surplus is {residual_surplus:,.2f} MW versus Ps = {schedule:,.2f} MW."))
    if cfg.mode == "battery":
        st.caption(t(f"Energía de batería: {response['energy_initial_mwh']:,.2f} → {response['energy_final_mwh']:,.2f} MWh; SOC final {100*response['soc_final']:,.1f} %. ",
                     f"Battery energy: {response['energy_initial_mwh']:,.2f} → {response['energy_final_mwh']:,.2f} MWh; final SOC {100*response['soc_final']:,.1f}%. ") +
                   t("Cada escenario parte del mismo SOC inicial.", "Each scenario starts from the same initial SOC."))
    elif cfg.mode == "reserve":
        st.caption(t(f"Energía despachable restante en este escenario: {response['reserve_energy_remaining_mwh']:,.2f} MWh.",
                     f"Dispatchable energy remaining in this scenario: {response['reserve_energy_remaining_mwh']:,.2f} MWh."))
    st.caption(t(f"Límites efectivos para Δt = {hours:g} h: descarga ≤ {summary.discharge_limit_mw:,.2f} MW y carga ≤ {summary.charge_limit_mw:,.2f} MW.",
                 f"Effective limits for Δt = {hours:g} h: discharge ≤ {summary.discharge_limit_mw:,.2f} MW and charge ≤ {summary.charge_limit_mw:,.2f} MW."))
    st.markdown(t("**Comparación esperada para la distribución activa**", "**Expected comparison for the active distribution**"))
    e1, e2, e3, e4 = st.columns(4)
    e1.metric(t("UCF sin respaldo", "UCF without backup"), eur(summary.baseline_cost_eur))
    e2.metric(t("Desbalance residual", "Residual imbalance"), eur(summary.residual_cost_eur))
    e3.metric(t("Operación de respaldo", "Backup operation"), eur(summary.backup_cost_eur))
    e4.metric(t("Costo total esperado", "Total expected cost"), eur(summary.total_cost_eur))
    st.caption(t(f"Con los supuestos del modelo: sin déficit residual en {100*summary.shortfall_covered_probability:,.1f} % de los escenarios (incluidos aquellos sin déficit inicial); coincidencia exacta con Ps en {100*summary.schedule_matched_probability:,.1f} %. El excedente residual podría gestionarse de otra forma, pero aquí no se modela vertimiento.",
                 f"Under the model assumptions: no residual shortfall in {100*summary.shortfall_covered_probability:,.1f}% of scenarios (including those without an initial shortfall); exact matching of Ps in {100*summary.schedule_matched_probability:,.1f}%. Residual surplus might be handled differently, but curtailment is not modelled here."))
    st.caption(t("Se supone potencia constante durante Δt, respuesta ideal inmediata y disponibilidad del respaldo, con SOC/energía inicial fijados para cada escenario. No incluye red, fallas, degradación detallada, costo de inversión ni acoplamiento entre intervalos: no es una garantía de firmeza ni de estabilidad.",
                 "Power is assumed constant during Δt, with ideal instantaneous response and backup availability and the same initial SOC/energy for each scenario. Network limits, failures, detailed degradation, capital cost and inter-temporal coupling are omitted: this is not a firmness or stability guarantee."))


if page == "fit":
    heading("01 / RESEARCH FIT", t("Dónde encajan las UCF", "Where UCFs fit"),
            t("UTOPYS investiga cómo interactúan física, renovables, control y mercados. La propuesta añade una capa de decisión económica interpretable, sin sustituir sus modelos dinámicos.",
              "UTOPYS studies interactions among physics, renewables, control and markets. This proposal adds an interpretable economic decision layer without replacing its dynamic models."))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(t("Horizonte del programa", "Programme horizon"), t("10 años", "10 years"))
        st.caption(t("Ocho instituciones neerlandesas; redes de 2050.", "Eight Dutch institutions; the grid of 2050."))
    with c2:
        st.metric(t("Infraestructura prevista", "Planned infrastructure"), "EMT · RTDS")
        st.caption(t("Simulación en tiempo real y biblioteca de modelos y datos.", "Real-time simulation and a model and data library."))
    with c3:
        st.metric(t("Acceso externo previsto", "Expected external access"), "2029")
        st.caption(t("Solicitudes independientes previstas; sujeta a reglas y disponibilidad.", "Independent applications expected; subject to rules and availability."))
    st.info(t("La instalación está en puesta en servicio; el acceso actual está limitado a socios. La cooperación con un socio y el uso de su cupo dependen de acuerdos. Las interfaces de cosimulación se desplegarán gradualmente. [Ver información oficial](https://www.utopys.org/facility).",
              "The facility is being commissioned; current access is limited to partners. Collaboration through a partner’s allocation depends on agreement. Co-simulation interfaces will be introduced gradually. [See the official facility page](https://www.utopys.org/facility)."))
    st.subheader(t("De una necesidad publicada a una hipótesis comprobable", "From a published need to a testable hypothesis"))
    st.caption(t("En cada tarjeta: objetivo descrito por UTOPYS → contribución UCF propuesta → evidencia que habría que obtener. Las contribuciones no son capacidades ya implantadas en UTOPYS.",
                 "Each card: UTOPYS’s stated objective → proposed UCF contribution → evidence still needed. These contributions are not presented as existing UTOPYS capabilities."))
    research_cards = [
      ("M1", t("Surrogates estocásticos dinámicos", "Dynamic stochastic surrogates"),
       t("UTOPYS: modelos dinámicos más manejables que EMT, calibrados y contrastados con datos de la instalación.", "UTOPYS: dynamic models more tractable than EMT, calibrated and checked against facility data."),
       t("Propuesta: usar UCF y costos marginales como cantidades de interés para priorizar escenarios y medir error relevante para decisiones.", "Proposal: use UCFs and marginal costs as quantities of interest to prioritise scenarios and measure decision-relevant error."),
       t("Evidencia: error de costo y decisión, calibración, coste computacional y contraste contra EMT o un benchmark acordado.", "Evidence: cost and decision error, calibration, computational cost and comparison against EMT or an agreed benchmark.")),
      ("M2", t("Estabilidad de sistemas complejos", "Stability of complex systems"),
       t("UTOPYS: criterios verificables para sistemas autoorganizados y decisiones distribuidas bajo incertidumbre.", "UTOPYS: verifiable criteria for self-organising systems and distributed decisions under uncertainty."),
       t("Propuesta: comparar decisiones sensibles a costos junto a frecuencia, voltaje y límites físicos; mantener los indicadores de estabilidad separados.", "Proposal: compare cost-sensitive decisions alongside frequency, voltage and physical limits; keep stability indicators separate."),
       t("Evidencia: resultados dinámicos y criterios físicos específicos; un bajo costo UCF no demuestra estabilidad.", "Evidence: dynamic results and specific physical criteria; low UCF cost does not demonstrate stability.")),
      ("M3", t("Apagones y eventos raros", "Blackouts and rare events"),
       t("UTOPYS: riesgo de propagación, modelos dinámicos y simulación de eventos raros.", "UTOPYS: propagation risk, dynamic models and rare-event simulation."),
       t("Propuesta: priorizar escenarios con UCF y estudiar separadamente cola, fallos y riesgo económico asociado a resultados físicos.", "Proposal: prioritise scenarios with UCFs and separately study tails, failures and economic risk associated with physical outcomes."),
       t("Evidencia: probabilidades de evento e incertidumbre estadística; la cota Lipschitz escalar no cubre automáticamente fallos discontinuos.", "Evidence: event probabilities and statistical uncertainty; the scalar Lipschitz bound does not automatically cover discontinuous failures.")),
      ("C1", t("Monitoreo y contingencias WAMPAC", "WAMPAC monitoring and contingencies"),
       t("UTOPYS: detección y localización bajo observabilidad limitada, incertidumbre y latencia, con PMU y medidas point-on-wave.", "UTOPYS: detection and localisation with limited observability, uncertainty and latency, using PMU and point-on-wave measurements."),
       t("Propuesta: inferir familias plausibles de parámetros y escenarios, y medir cómo cambian las decisiones y sus costos.", "Proposal: infer plausible parameter families and scenarios, and measure how decisions and their costs change."),
       t("Evidencia: identificabilidad, modelo de error y datos suficientes; PMU por sí sola puede no resolver parámetros rápidos de convertidores.", "Evidence: identifiability, an error model and sufficient data; PMUs alone may not resolve fast converter parameters.")),
      ("C2", t("Gemelos y control predictivo", "Digital twins and predictive control"),
       t("UTOPYS: gemelos con datos en vivo para control y despacho predictivo, con surrogates escalables como objetivo.", "UTOPYS: live-data twins for predictive control and dispatch, with scalable surrogates as a longer-term goal."),
       t("Propuesta: incorporar UCF nominal o robusta en una función objetivo, junto con restricciones y estados físicos explícitos.", "Proposal: incorporate nominal or robust UCFs into an objective alongside explicit physical states and constraints."),
       t("Evidencia: ensayos comparables en lazo cerrado; esta app no implementa control ni conexión con un gemelo.", "Evidence: comparable closed-loop tests; this app implements neither control nor a connection to a twin.")),
      ("P3", t("Mercados y estabilidad", "Markets and stability"),
       t("UTOPYS: evaluar efectos físicos de esquemas de mercado y sus incentivos.", "UTOPYS: evaluate the physical effects of market designs and their incentives."),
       t("Propuesta: examinar cómo penalizaciones por déficit y excedente cambian la programación y, después, los resultados dinámicos.", "Proposal: examine how shortfall and surplus penalties change schedules and, subsequently, dynamic outcomes."),
       t("Evidencia: datos de liquidación y reglas de mercado justificadas; comparar incentivos y restricciones físicas sin doble contabilización.", "Evidence: justified settlement data and market rules; compare incentives and physical constraints without double counting.")),
    ]
    for i in range(0, len(research_cards), 2):
        cols = st.columns(2)
        for col, (code, title, published, proposed, evidence) in zip(cols, research_cards[i:i+2]):
            with col, st.container(border=True):
                st.markdown(f'<span class="eyebrow">{code} / UTOPYS</span>', unsafe_allow_html=True)
                st.markdown(f"#### {title}")
                st.write(published)
                st.markdown(f"**{proposed}**")
                st.caption(evidence)
    st.markdown(t("**Otros temas del dossier.** C3 aborda capas de datos y seguridad; P1, política y regulación; P2, expansión sostenible y segura. También pueden influir en datos, gobernanza y horizontes del piloto, pero no se modelan aquí.",
                  "**Other topics in the dossier.** C3 covers data and security; P1 covers policy and regulation; P2 covers sustainable, secure network growth. They may shape the pilot’s data, governance and time horizons, but are not modelled here."))
    st.caption(t("Fuente del mapa: [UTOPYS · Research](https://www.utopys.org/research). Gabriel Lord figura como colíder del eje Mathematical Principles.",
                 "Research map source: [UTOPYS · Research](https://www.utopys.org/research). Gabriel Lord is listed as a co-lead of the Mathematical Principles track."))

elif page == "ucf":
    heading("02 / UNCERTAINTY COST", t("Explorador de costo de incertidumbre", "Uncertainty cost explorer"),
            t("Cambie Ps en esta página y las penalizaciones, Δt y distribuciones en la barra lateral. Los resultados corresponden a una renovable y un intervalo.",
              "Change Ps on this page and the penalties, Δt and distributions in the sidebar. Results represent one renewable resource and one settlement interval."))
    show_firming_dashboard(backup, firming_summary, schedule, capacity)
    st.caption(t("Modelo activo: ", "Active model: ") + dataset_label + " · " + t("media discreta de referencia: ", "discrete reference mean: ") + mw(reference.mean))
    a, b, c, d = st.columns(4)
    a.metric(t("Déficit sin respaldo", "Shortfall without backup"), eur(over))
    b.metric(t("Excedente sin respaldo", "Surplus without backup"), eur(under))
    c.metric(t("UCF discreta sin respaldo", "Discrete UCF without backup"), eur(nominal))
    d.metric(t("Mínimo UCF sin respaldo", "UCF-only minimum"), mw(nom_opt) if nom_opt is not None else t("Todos", "All"))
    st.caption(t("Estos cuatro indicadores y las curvas originales corresponden a la renovable sin respaldo y usan la medida discreta. El mínimo no es un óptimo conjunto de renovable y respaldo.",
                 "These four metrics and the original curves describe the renewable resource without backup and use the discrete measure. The minimum is not a joint renewable-plus-backup optimum."))
    st.latex(r"\ell(s,p)=\Delta t\,[c_o(s-p)_+ + c_u(p-s)_+],\qquad U_0(s)=\mathbb{E}_{0}[\ell(s,P)]")
    st.markdown(t("**Sobrestimación:** s > P, déficit. **Subestimación:** s < P, excedente. Las penalizaciones son hipótesis y deben ajustarse a las reglas reales de liquidación.",
                  "**Overestimate:** s > P, shortfall. **Underestimate:** s < P, surplus. Penalties are assumptions and must be calibrated to actual settlement rules."))
    st.subheader(t("Animación · renovable + respaldo: analítica y Monte Carlo", "Animation · renewable + backup: analytic and Monte Carlo"))
    st.write(t("Ambos métodos evalúan la misma regla de respaldo seleccionada: penalización residual más costo operativo. La banda Monte Carlo usa ±1,96 errores estándar; es aproximada en cada punto, no una garantía simultánea.",
               "Both methods evaluate the same selected backup rule: residual penalty plus operating cost. The Monte Carlo band uses ±1.96 standard errors; it is approximate at each point, not a simultaneous guarantee."))
    st.latex(r"L_B(s,p)=\Delta t\,[c_o(s-p-d)_+ +c_u(p-s-q)_+ +c_B(d+q)]")
    st.caption(t("d: descarga/despacho; q: carga; cB: costo por MWh AC. El modelo actúa por regla fija incluso si su operación resulta más cara.",
                 "d: discharge/dispatch; q: charge; cB: cost per AC MWh. The fixed rule acts even if operating it is more expensive."))
    n_mc = st.select_slider(t("Máximo de muestras Monte Carlo", "Maximum Monte Carlo sample count"),
                            options=[1000, 10000, 50000, 100000], value=100000, key="mc_n")
    counts, mc_values, mc_errors = monte_carlo_convergence(
        schedule, co, cu, hours, reference, int(n_mc), seed=42, beta_parameters=beta_params,
        loss_function=lambda samples: backed_loss_for_samples(schedule, samples, co, cu, hours, backup))
    analytic_backed = firming_summary.total_cost_eur
    ma, mb, md = st.columns(3)
    ma.metric(t("Analítica · renovable + respaldo", "Analytic · renewable + backup"), eur(analytic_backed))
    mb.metric(t(f"Monte Carlo · N={n_mc:,}", f"Monte Carlo · N={n_mc:,}"), eur(float(mc_values[-1])))
    md.metric(t("Diferencia absoluta", "Absolute difference"), eur(abs(float(mc_values[-1])-analytic_backed)))
    components.html(mc_convergence_animation(counts, mc_values, mc_errors, analytic_backed, es), height=445, scrolling=False)
    st.caption(t("Las tarjetas muestran el resultado con el N máximo; la animación parte de 100 muestras anidadas (semilla 42). La banda es un IC normal aproximado puntual del 95 %, no una garantía para cada muestra ni de error de modelo.",
                 "Cards show the result at maximum N; the animation starts with 100 nested samples (seed 42). The band is an approximate pointwise 95% normal CI, not a guarantee for every sample or for model error."))
    if beta_params:
        st.caption(t("El costo analítico con respaldo usa la beta continua y funciones beta incompletas; Monte Carlo muestrea la misma beta. Las curvas originales y el DRO sin respaldo usan una aproximación discreta de 200 puntos y pueden diferir, especialmente cerca de los extremos.",
                     "The analytic cost with backup uses the continuous beta and incomplete beta functions; Monte Carlo samples that same beta. The original curves and unbacked DRO use a 200-point discrete approximation and may differ, especially near the boundaries."))
        with st.expander(t("Expresión analítica para beta", "Analytic beta expression")):
            st.markdown(t("Para la renovable sin respaldo, con P = M Z, Z ~ Beta(α, β), μ = α/(α+β), z = Ps/M e I la beta incompleta regularizada:",
                          "For the renewable resource without backup, with P = M Z, Z ~ Beta(α, β), μ = α/(α+β), z = Ps/M and I the regularised incomplete beta function:"))
            st.latex(r"U(s)=\Delta t\left[c_o\left(s I_z(\alpha,\beta)-M\mu I_z(\alpha+1,\beta)\right)+c_u\left(M\mu\left(1-I_z(\alpha+1,\beta)\right)-s\left(1-I_z(\alpha,\beta)\right)\right)\right]")
            st.caption(t("Con respaldo, los términos residuales se evalúan en los umbrales desplazados Ps−D y Ps+C; se añade el costo esperado del respaldo.",
                         "With backup, residual terms are evaluated at the shifted thresholds Ps−D and Ps+C; expected backup operating cost is added."))
    else:
        st.caption(t("Con CSV, el costo esperado es la suma exacta de la medida empírica ponderada; Monte Carlo remuestrea esa misma medida. No valida que el CSV represente el sistema real.",
                     "With CSV, expected cost is the exact weighted empirical sum; Monte Carlo resamples that same measure. This does not validate the CSV as a representation of the real system."))

    st.subheader(t("Sin respaldo · de la probabilidad al costo esperado", "Without backup · from probability to expected cost"))
    st.plotly_chart(component_bars(schedule, co, cu, hours, reference, es), theme=None, use_container_width=True, config={"displaylogo": False}, key="components")
    st.caption(t("Barras apiladas sobre 40 intervalos: área superior = 1; las áreas inferiores reproducen exactamente los costos de la medida discreta usada. La línea amarilla marca Ps; no se presupone una densidad continua para datos empíricos.",
                 "Stacked bars over 40 bins: upper area = 1; lower areas exactly reproduce the costs of the discrete measure used. The yellow line marks Ps; no continuous density is assumed for empirical data."))
    st.subheader(t("Sin respaldo · curva UCF y decisiones", "Without backup · UCF curve and decisions"))
    st.plotly_chart(cost_curve(schedule, co, cu, hours, reference, nom_opt, es), theme=None, use_container_width=True, config={"displaylogo": False}, key="cost_curve")
    if nom_opt is None:
        st.info(t("Ambas penalizaciones son cero: todas las programaciones minimizan la UCF y su costo es cero.",
                  "Both penalties are zero: every schedule minimises the UCF and the cost is zero."))
    else:
        left, right = subgradient(schedule, co, cu, hours, reference)
        st.write(t("Subgradiente en Ps", "Subgradient at Ps") + f": **[{left:,.2f}, {right:,.2f}] €/MW** " +
                 t("por intervalo. En átomos, las pendientes izquierda y derecha pueden diferir.", "per interval. At atoms, left and right slopes may differ."))
        st.latex(r"s^* = F_0^{-1}\!\left(\frac{c_u}{c_o+c_u}\right)")
        st.caption(t("Con ambas penalizaciones positivas, un cuantil generalizado es un mínimo. Si una penalización es cero se muestra un mínimo de borde; con ambas cero todos son mínimos.",
                     "For positive penalties, a generalised quantile is a minimum. If one penalty is zero an endpoint minimum is shown; with both zero all schedules are minima."))
    st.subheader(t("Sin respaldo · animación de barrido de Ps", "Without backup · animated Ps sweep"))
    st.write(t("Reproduzca o arrastre el control para ver cómo cambian los costos de la renovable sin respaldo al recorrer el rango de programación.",
               "Play or drag the control to see how the renewable resource's costs without backup change as the schedule is swept."))
    components.html(schedule_animation(co, cu, hours, reference, es), height=445, scrolling=False)
    st.caption(t("La animación recorre 81 puntos ilustrativos y no modifica Ps de la barra lateral ni los indicadores de arriba.",
                 "The animation sweeps 81 illustrative points and does not change the sidebar Ps or the metrics above."))

elif page == "wasserstein":
    heading("03 / DISTRIBUTIONAL ROBUSTNESS", t("Wasserstein y robustez distribucional", "Wasserstein and distributional robustness"),
            t("Compare dos distribuciones y explore un peor caso dentro de una bola W₁ sobre el soporte físico [0, Pmax].", "Compare two distributions and explore a worst case inside a W₁ ball over the physical support [0, Pmax]."))
    show_firming_dashboard(backup, firming_summary, schedule, capacity)
    st.subheader(t("Antes del respaldo · transporte de la renovable hacia Ps", "Before backup · transport renewable output towards Ps"))
    st.write(t("La programación fija s = Ps se representa como una delta de Dirac δₛ. Esta primera animación transporta cuantiles de la renovable original, antes de aplicar cualquier respaldo.",
               "The fixed schedule s = Ps is represented as a Dirac delta δₛ. This first animation transports quantiles of the original renewable output, before any backup is applied."))
    if beta_params:
        w_minus, w_plus, w_dirac = beta_dirac_cdf_components(schedule, mean0, conc0, capacity)
        illustrative_points = beta_quantiles(np.linspace(.03, .97, 17), mean0, conc0, capacity)
    else:
        w_minus, w_plus, w_dirac = empirical_dirac_cdf_components(schedule, reference)
        illustrative_points = reference.quantile(np.linspace(.03, .97, 17))
    dirac_cost = hours * (co * w_minus + cu * w_plus)
    st.latex(r"W_1(\mu,\delta_s)=\mathbb E_{\mu}|P-s|=W_-+W_+")
    st.latex(r"W_-=\int_0^sF(p)\,dp,\quad W_+=\int_s^{P_{\max}}(1-F(p))\,dp,\quad U(s)=\Delta t\,[c_oW_-+c_uW_+]")
    wa, wb, wc, wd = st.columns(4)
    wa.metric(t("UCF analítica sin respaldo", "Analytic UCF without backup"), eur(analytic_cost))
    wb.metric("W₁(μ, δₛ)", f"{w_dirac:,.4f} MW")
    wc.metric(t("Transporte ponderado", "Weighted transport"), eur(dirac_cost))
    wd.metric(t("Diferencia numérica", "Numerical difference"), eur(abs(dirac_cost-analytic_cost)))
    st.caption(f"W₋ = {w_minus:,.4f} MW · W₊ = {w_plus:,.4f} MW · " +
               t("costos en € por intervalo", "costs in € per interval"))
    if co == cu:
        st.success(t("Las penalizaciones son iguales: U(Ps) = Δt · c · W₁(μ, δₛ).", "The penalties are equal: U(Ps) = Δt · c · W₁(μ, δₛ)."))
    else:
        st.info(t("Las penalizaciones son distintas: W₁ está en MW y no es un costo en euros. Es necesario ponderar por separado W₋ y W₊; el transporte ponderado no es el W₁ métrico habitual. Para ver la identidad simple, iguale ambas penalizaciones.",
                  "The penalties differ: W₁ is in MW, not euros. W₋ and W₊ must be weighted separately; this weighted transport cost is not the usual metric W₁. Set both penalties equal to see the simple identity."))
    components.html(dirac_transport_animation(illustrative_points, capacity, schedule, w_dirac, dirac_cost, analytic_cost, es),
                    height=535, scrolling=False)
    st.caption(t("Las 17 partículas ilustran cuantiles; las barras usan la distribución completa. Al llegar a δₛ, el transporte ponderado coincide con la UCF para esta pérdida, salvo tolerancias numéricas. t no es el radio ε.",
                 "The 17 particles illustrate quantiles; the bars use the full distribution. On reaching δₛ, weighted transport agrees with the UCF for this loss up to numerical tolerance. t is not the radius ε."))
    if beta_params:
        st.caption(t("Para beta, la UCF usa una fórmula analítica continua y las distancias se calculan independientemente integrando su CDF. Las comparaciones entre distribuciones y el DRO de abajo usan las medidas discretizadas de 200 puntos.",
                     "For beta, the UCF uses a continuous closed-form expression and distances are computed independently by integrating its CDF. The distribution comparison and DRO below use 200-point discrete measures."))
    else:
        st.caption(t("Para CSV, tanto la UCF como el transporte se evalúan sobre la misma medida empírica ponderada; la igualdad no valida los datos de origen.",
                     "For CSV, the UCF and transport are evaluated on the same weighted empirical measure; their equality does not validate the source data."))
    st.subheader(t("Después del respaldo · transporte residual hacia Ps", "After backup · residual transport towards Ps"))
    st.write(t("Ahora se transporta la distribución de la potencia neta entregada, después de aplicar la regla ideal de respaldo a cada escenario. El costo operativo se añade por separado: reducir W₁ no implica que el respaldo sea gratis.",
               "Now transport the distribution of net delivered power after applying the ideal backup rule to each scenario. Operating cost is added separately: reducing W₁ does not mean backup is free."))
    lo = max(0.0, schedule - firming_summary.discharge_limit_mw)
    hi = min(capacity, schedule + firming_summary.charge_limit_mw)
    if beta_params:
        post_minus = beta_dirac_cdf_components(lo, mean0, conc0, capacity)[0]
        post_plus = beta_dirac_cdf_components(hi, mean0, conc0, capacity)[1]
    else:
        post_minus = empirical_dirac_cdf_components(lo, reference)[0]
        post_plus = empirical_dirac_cdf_components(hi, reference)[1]
    post_distance = post_minus + post_plus
    post_weighted = hours * (co * post_minus + cu * post_plus)
    delivered_quantiles = dispatch_samples(schedule, illustrative_points, hours, backup)[0]
    st.latex(r"\nu_B=\mathrm{Law}(P+d-q),\qquad W_1(\nu_B,\delta_s)=\mathbb E|P+d-q-s|")
    pb1, pb2, pb3, pb4 = st.columns(4)
    pb1.metric(t("W₁ antes del respaldo", "W₁ before backup"), f"{w_dirac:,.4f} MW")
    pb2.metric(t("W₁ después del respaldo", "W₁ after backup"), f"{post_distance:,.4f} MW")
    pb3.metric(t("Transporte residual ponderado", "Weighted residual transport"), eur(post_weighted))
    pb4.metric(t("Operación de respaldo", "Backup operation"), eur(firming_summary.backup_cost_eur))
    st.caption(t(f"Penalización residual analítica: {eur(firming_summary.residual_cost_eur)}; más operación {eur(firming_summary.backup_cost_eur)} = costo total esperado {eur(firming_summary.total_cost_eur)}. W₁ se mide en MW, no en euros.",
                 f"Analytic residual penalty: {eur(firming_summary.residual_cost_eur)}; plus operation {eur(firming_summary.backup_cost_eur)} = expected total cost {eur(firming_summary.total_cost_eur)}. W₁ is measured in MW, not euros."))
    if backup.mode != "none":
        components.html(dirac_transport_animation(
            delivered_quantiles, capacity, schedule, post_distance, post_weighted,
            firming_summary.residual_cost_eur, es,
            source_label=t("Potencia neta", "Net delivered"),
            analytic_label=t("Penalización residual", "Residual penalty"),
            transport_label=t("Transporte residual", "Residual transport")), height=535, scrolling=False)
        st.caption(t("Los cuantiles se transforman con la misma regla de despacho; las barras representan solo la penalización residual, no el costo operativo. La distribución posrespaldo depende de Ps y del estado inicial.",
                     "Quantiles are transformed by the same dispatch rule; the bars show the residual penalty only, not the operating cost. The post-backup distribution depends on Ps and the initial state."))
    else:
        st.caption(t("Seleccione una batería o un respaldo despachable para visualizar cómo cambia el transporte residual.",
                     "Select a battery or dispatchable backup to visualise the change in residual transport."))
    st.subheader(t("Sin respaldo · comparación de distribuciones y bola DRO", "Without backup · distribution comparison and DRO ball"))
    st.caption(t("Esta sección y el DRO usan exclusivamente la pérdida original sin respaldo, aunque arriba se haya seleccionado una batería. Aquí W₁ compara dos distribuciones, no la distancia a δₛ.",
                 "This section and the DRO use only the original unbacked loss, even if a battery is selected above. Here W₁ compares two distributions, not the distance to δₛ."))
    a, b, c, d = st.columns(4)
    a.metric("W₁", mw(distance))
    b.metric("ε", mw(epsilon))
    c.metric(t("Diferencia calculada de UCF", "Calculated UCF difference"), eur(abs(comparison_cost - nominal)))
    d.metric(t("Cota L · W₁", "Bound L · W₁"), eur(L * distance))
    if inside:
        st.success(t("La distribución de comparación está dentro de la bola elegida (W₁ ≤ ε).", "The comparison distribution lies inside the chosen ball (W₁ ≤ ε)."))
    else:
        st.warning(t("La distribución de comparación está fuera de la bola elegida (W₁ > ε); no es un escenario admisible para este DRO.", "The comparison distribution is outside the chosen ball (W₁ > ε); it is not an admissible scenario for this DRO."))
    st.latex(r"W_1(F_0,F_1)=\int_0^{P_{\max}} |F_0(p)-F_1(p)|\,dp")
    st.plotly_chart(cdf_figure(reference, comparison, es), theme=None, use_container_width=True, config={"displaylogo": False}, key="cdf")
    st.caption(t("Funciones de distribución escalonadas. El cálculo integra exactamente la diferencia entre las dos medidas discretas; el área sombreada ilustra ese resultado.",
                 "Step cumulative distributions. The calculation exactly integrates the difference between the two discrete measures; the shaded area illustrates it."))
    st.latex(r"|\mathbb E_1\ell(s,P)-\mathbb E_0\ell(s,P)|\le \Delta t\,\max(c_o,c_u)\,W_1(F_0,F_1)")
    st.write(t("Esta es una **cota** para el costo lineal especificado: no suele ser una igualdad y no es una garantía física de estabilidad.",
               "This is a **bound** for the specified linear cost: it is generally not an equality and is not a physical stability guarantee."))
    st.subheader(t("Animación · transporte por cuantiles", "Animation · quantile transport"))
    st.write(t("Los marcadores amarillos se desplazan entre cuantiles de la referencia y de la comparación; use Reproducir, Pausar o el control t.",
               "Yellow markers move between quantiles of the reference and comparison; use Play, Pause or the t slider."))
    components.html(transport_animation(reference, comparison, es), height=445, scrolling=False)
    st.caption(t("Solo se muestran 17 cuantiles representativos. t es una interpolación visual, no tiempo físico ni radio ε. La comparación no es necesariamente el peor caso DRO.",
                 "Only 17 representative quantiles are shown. t is a visual interpolation, not physical time or the radius ε. The comparison is not necessarily the DRO worst case."))
    st.subheader(t("Sin respaldo · peor caso con soporte acotado", "Without backup · bounded-support worst case"))
    st.latex(r"U_{\rm DRO}(s)=\sup_{Q:\,W_1(Q,\hat P_0)\le\epsilon,\;\mathrm{supp}(Q)\subseteq[0,P_{\max}]}\mathbb E_Q[\ell(s,P)]")
    grid, ref_values, robust_values, robust_opt = robust_grid()
    robust_at_s = dro_value(schedule, co, cu, hours, epsilon, reference)
    x1, x2, x3 = st.columns(3)
    x1.metric(t("DRO en Ps", "DRO at Ps"), eur(robust_at_s))
    x2.metric(t("Cota en Ps", "Bound at Ps"), eur(nominal + L*epsilon))
    x3.metric(t("Mínimo DRO en malla", "DRO grid minimum"), mw(robust_opt[0]))
    st.plotly_chart(robust_figure(grid, ref_values, robust_values, ref_values+L*epsilon, schedule, nominal, robust_at_s, robust_opt, es),
                    theme=None, use_container_width=True, config={"displaylogo": False}, key="robust_curve")
    st.caption(t("El mínimo DRO se busca en una malla de 201 puntos más Ps, la media y el mínimo nominal: resolución básica Pmax/200. La curva es un resultado numérico, no un despacho óptimo de red.",
                 "The DRO minimum is searched on 201 grid points plus Ps, the mean and nominal minimum: base resolution Pmax/200. The curve is a numerical result, not a network-optimal dispatch."))
    with st.expander(t("Ver sensibilidad al radio ε", "View sensitivity to radius ε")):
        radii = np.linspace(0, capacity, 31)
        losses = np.array([dro_value(schedule, co, cu, hours, float(r), reference) for r in radii])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=radii, y=losses, mode="lines", name=("DRO"), line=dict(color=ORANGE, width=3)))
        fig.add_trace(go.Scatter(x=radii, y=nominal+L*radii, mode="lines", name=t("Cota", "Bound"), line=dict(color=MUTED, dash="dash")))
        fig.add_trace(go.Scatter(x=[epsilon], y=[robust_at_s], mode="markers", marker=dict(color=YELLOW, size=11), name="ε"))
        fig.update_xaxes(title="ε (MW)"); fig.update_yaxes(title="€ / " + t("intervalo", "interval"), rangemode="tozero")
        st.plotly_chart(style(fig, 350), theme=None, use_container_width=True, config={"displaylogo": False}, key="epsilon_curve")
        st.caption(t("El peor caso no disminuye al aumentar ε; la cota genérica puede ser conservadora y seguir creciendo cuando el soporte limita el costo.",
                     "The worst case cannot decrease with ε; the generic bound may be conservative and keep increasing when support limits the cost."))
    with st.expander(t("Detalle matemático y condiciones", "Mathematical detail and conditions")):
        st.markdown(t("Para la referencia discreta P̂₀ = Σᵢ wᵢδₚᵢ, el dual siguiente se resuelve numéricamente en λ. El máximo interno se reduce a 0, pᵢ o Pmax por la forma convexa y lineal a tramos de esta pérdida particular.",
                      "For discrete reference P̂₀ = Σᵢ wᵢδₚᵢ, the dual below is solved numerically in λ. The inner maximum reduces to 0, pᵢ or Pmax because this particular loss is convex and piecewise linear."))
        st.latex(r"\min_{\lambda\ge0}\left\{\lambda\epsilon+\sum_i w_i\max\left[\ell(s,p_i),\;\Delta t c_o s-\lambda p_i,\;\Delta t c_u(P_{\max}-s)-\lambda(P_{\max}-p_i)\right]\right\}")
        st.markdown(t("Un radio debe calibrarse y evaluarse fuera de muestra; no se afirma cobertura estadística. La formulación escalar no captura correlaciones, trayectorias temporales, topología ni respuestas EMT no lineales.",
                      "A radius must be calibrated and assessed out of sample; statistical coverage is not claimed. The scalar formulation does not capture correlations, trajectories, topology or nonlinear EMT responses."))

st.markdown(f'<div class="footerline">UCF × UTOPYS · {t("Prototipo independiente para discusión científica", "Independent prototype for scientific discussion")} · {t("No oficial · Sin conexión a UTOPYS", "Unofficial · Not connected to UTOPYS")}</div>', unsafe_allow_html=True)
