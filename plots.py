"""Plotly views and client-side animations for the scalar demonstration."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ucf_core import Distribution, binned_components, nominal_curve

TEAL = "#4ce0bd"
ORANGE = "#ff9d70"
BLUE = "#81aaff"
PURPLE = "#c6a6ff"
YELLOW = "#f3d381"
INK = "#e7effb"
MUTED = "#9dafc3"
GRID = "#29394b"
PAPER = "#101d2c"


def style(fig, height=390):
    fig.update_layout(template="plotly_dark", paper_bgcolor=PAPER, plot_bgcolor=PAPER,
                      font=dict(family="Arial, sans-serif", size=12, color=INK),
                      margin=dict(l=54, r=24, t=32, b=55), height=height,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      hovermode="x unified", bargap=0)
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, automargin=True)
    return fig


def component_bars(s, co, cu, hours, dist: Distribution, es: bool):
    d = binned_components(s, co, cu, hours, dist, bins=40)
    ref = ("Sobrestimación / déficit", "Subestimación / excedente", "P = Pₛ") if es else ("Overestimate / shortfall", "Underestimate / surplus", "P = Pₛ")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.12)
    x, width = d['centres'], d['width']
    for name, key, color in zip(ref, ('prob_over', 'prob_under', 'prob_equal'), (ORANGE, TEAL, MUTED)):
        fig.add_trace(go.Bar(x=x, y=d[key], width=width, name=name, marker_color=color,
                             legendgroup=name, hovertemplate="P≈%{x:.2f} MW<br>density=%{y:.5f}/MW<extra>%{fullData.name}</extra>"), row=1, col=1)
    for name, key, color in zip(ref[:2], ('cost_over', 'cost_under'), (ORANGE, TEAL)):
        fig.add_trace(go.Bar(x=x, y=d[key], width=width, name=name, marker_color=color,
                             legendgroup=name, showlegend=False,
                             hovertemplate="P≈%{x:.2f} MW<br>density=%{y:.3f} €/MW<extra>%{fullData.name}</extra>"), row=2, col=1)
    fig.add_vline(x=s, line_dash="dash", line_color=YELLOW, line_width=2, row="all", col=1)
    fig.update_yaxes(title_text=("Probabilidad / MW" if es else "Probability / MW"), row=1, col=1)
    fig.update_yaxes(title_text=("Costo esperado / MW" if es else "Expected cost / MW"), row=2, col=1)
    fig.update_xaxes(title_text=("Potencia disponible P (MW)" if es else "Available power P (MW)"), row=2, col=1, range=[0, dist.capacity_mw])
    fig.update_layout(barmode="stack")
    style(fig, 550)
    fig.update_layout(margin=dict(l=74, r=24, t=70, b=55), legend=dict(orientation="h", yanchor="bottom", y=1.05, x=0))
    return fig


def cost_curve(s, co, cu, hours, dist: Distribution, opt, es: bool):
    grid = np.linspace(0, dist.capacity_mw, 201)
    over, under, total = nominal_curve(grid, co, cu, hours, dist)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grid, y=total, mode="lines", name="UCF", line=dict(color=BLUE, width=3)))
    fig.add_trace(go.Scatter(x=grid, y=over, mode="lines", name=("Déficit" if es else "Shortfall"), line=dict(color=ORANGE, width=2)))
    fig.add_trace(go.Scatter(x=grid, y=under, mode="lines", name=("Excedente" if es else "Surplus"), line=dict(color=TEAL, width=2)))
    current = nominal_curve(np.array([s]), co, cu, hours, dist)[2][0]
    fig.add_trace(go.Scatter(x=[s], y=[current], mode="markers", marker=dict(color=YELLOW, size=12, line=dict(color=PAPER, width=2)),
                             name=("Programación actual" if es else "Current schedule")))
    if opt is not None:
        opt_cost = nominal_curve(np.array([opt]), co, cu, hours, dist)[2][0]
        fig.add_trace(go.Scatter(x=[opt], y=[opt_cost], mode="markers", marker=dict(color=PURPLE, symbol="diamond", size=12),
                                 name=("Mínimo nominal" if es else "Nominal minimum")))
    fig.update_xaxes(title=("Potencia programada Pₛ (MW)" if es else "Scheduled power Pₛ (MW)"), range=[0, dist.capacity_mw])
    fig.update_yaxes(title=("Coste esperado (€ / intervalo)" if es else "Expected cost (€ / interval)"), rangemode="tozero")
    return style(fig, 410)


def cdf_figure(a: Distribution, b: Distribution, es: bool):
    x = np.unique(np.r_[0, a.p_mw, b.p_mw, a.capacity_mw])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=a.cdf(x), mode="lines", name=("Referencia" if es else "Reference"),
                             line=dict(color=TEAL, width=2.5, shape="hv")))
    fig.add_trace(go.Scatter(x=x, y=b.cdf(x), mode="lines", name=("Comparación" if es else "Comparison"),
                             fill="tonexty", fillcolor="rgba(129,170,255,.18)", line=dict(color=BLUE, width=2.5, shape="hv")))
    fig.update_xaxes(title="P (MW)", range=[0, a.capacity_mw])
    fig.update_yaxes(title="F(P)", range=[0, 1.02])
    return style(fig, 380)


def robust_figure(grid, nominal, robust, ceiling, s, nominal_at_s, robust_at_s, robust_opt, es: bool):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grid, y=nominal, mode="lines", name=("UCF nominal" if es else "Nominal UCF"), line=dict(color=TEAL, width=2.6)))
    fig.add_trace(go.Scatter(x=grid, y=robust, mode="lines", name=("Peor caso DRO" if es else "DRO worst case"), line=dict(color=ORANGE, width=3)))
    fig.add_trace(go.Scatter(x=grid, y=ceiling, mode="lines", name=("Cota genérica" if es else "Generic bound"), line=dict(color=MUTED, width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=[s], y=[nominal_at_s], mode="markers", marker=dict(color=TEAL, size=10), name=("Nominal en Pₛ" if es else "Nominal at Pₛ")))
    fig.add_trace(go.Scatter(x=[s], y=[robust_at_s], mode="markers", marker=dict(color=YELLOW, size=11), name=("DRO en Pₛ" if es else "DRO at Pₛ")))
    fig.add_trace(go.Scatter(x=[robust_opt[0]], y=[robust_opt[1]], mode="markers", marker=dict(color=PURPLE, size=12, symbol="diamond"),
                             name=("Mínimo DRO en malla" if es else "DRO grid minimum")))
    fig.update_xaxes(title=("Potencia programada Pₛ (MW)" if es else "Scheduled power Pₛ (MW)"), range=[0, float(grid[-1])])
    fig.update_yaxes(title="€ / " + ("intervalo" if es else "interval"), rangemode="tozero")
    return style(fig, 440)
