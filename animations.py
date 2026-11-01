"""Self-contained, accessible SVG animations for Streamlit's isolated HTML iframe.

The only interpolated data are locally calculated numeric arrays and static UI
labels. No external scripts or network calls are used. The slider is independent
of the sidebar schedule, as explained in the UI.
"""
from __future__ import annotations
import json
import numpy as np
from ucf_core import Distribution, nominal_curve

_TEMPLATE = r'''<!doctype html>
<html lang="__LANG__">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
* { box-sizing:border-box; }
html,body { margin:0; background:#101d2c; color:#e7effb; font-family:Arial,sans-serif; }
.shell { width:100%; padding:14px 16px 17px; background:#101d2c; border-radius:8px; }
.legend { display:flex; flex-wrap:wrap; gap:10px 20px; align-items:center; font-size:12px; min-height:24px; color:#d8e6f7; }
.swatch { display:inline-block; width:19px; height:3px; vertical-align:middle; margin-right:6px; border-radius:2px; }
svg { width:100%; height:280px; display:block; overflow:visible; }
.scale-row { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:8px; font-size:12px; margin:4px 0 2px; color:#c3d2e2; }
output { font-variant-numeric:tabular-nums; color:#f3d381; font-weight:700; }
.cost-comparison { margin:4px 0 10px; padding:8px; border:1px solid #34495d; border-radius:7px; }
.barrow { display:grid; grid-template-columns:minmax(100px,140px) 1fr auto; gap:9px; align-items:center; margin:6px 0; font-size:12px; }
.bartrack { background:#29394b; height:11px; border-radius:8px; overflow:hidden; }
.barfill { display:block; width:0; height:100%; border-radius:8px; transition:width .05s linear; }
[hidden] { display:none !important; }
input[type=range] { width:100%; height:24px; accent-color:#4ce0bd; cursor:pointer; }
.buttons { display:flex; gap:8px; margin-top:5px; }
button { cursor:pointer; border:1px solid #4d677c; border-radius:6px; padding:8px 13px; background:#24384a; color:#f2f7fd; font-size:13px; }
button:hover { background:#31516a; } button:focus-visible, input:focus-visible { outline:3px solid #f3d381; outline-offset:2px; }
@media(max-width:420px) { .shell{padding:10px 10px 14px} .legend{font-size:11px;gap:6px 12px} }
</style></head>
<body><main class="shell">
<div class="legend" id="legend"></div>
<svg id="chart" role="img" aria-label="__ARIA__"></svg>
<div id="cost-comparison" class="cost-comparison" hidden>
  <div class="barrow"><span id="analytic-label"></span><span class="bartrack"><span id="analytic-fill" class="barfill" style="background:#81aaff"></span></span><strong id="analytic-cost"></strong></div>
  <div class="barrow"><span id="transport-label"></span><span class="bartrack"><span id="transport-fill" class="barfill" style="background:#f3d381"></span></span><strong id="transport-cost"></strong></div>
</div>
<div class="scale-row"><span id="scale-label"></span><output id="value"></output></div>
<input id="slider" type="range" min="0" step="1" aria-label="__RANGE_ARIA__">
<div class="buttons"><button id="play" type="button">__PLAY__</button><button id="pause" type="button">__PAUSE__</button></div>
</main><script>
"use strict";
const D = __DATA__;
const svg=document.getElementById('chart'), slider=document.getElementById('slider'), output=document.getElementById('value');
const NS='http://www.w3.org/2000/svg';
const C={blue:'#81aaff', orange:'#ff9d70', teal:'#4ce0bd', yellow:'#f3d381', grid:'#29394b', muted:'#a9bbce', ink:'#e7effb'};
let n=D.steps, current=0, playing=false, start=0, anim=0, dynamic=[];
slider.max=String(n);
function el(tag,attrs={},parent=svg){const x=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))x.setAttribute(k,String(v));parent.appendChild(x);return x;}
function text(x,y,s,attrs={}){let e=el('text',Object.assign({x,y,fill:C.muted,'font-size':11},attrs));e.textContent=s;return e;}
function line(x1,y1,x2,y2,color=C.grid,extra={}){return el('line',Object.assign({x1,y1,x2,y2,stroke:color,'stroke-width':1},extra));}
function marker(x,y,color,r=5){return el('circle',{cx:x,cy:y,r,fill:color,stroke:'#101d2c','stroke-width':1});}
function fmt(v,d=1){return Number(v).toLocaleString(D.locale,{minimumFractionDigits:d,maximumFractionDigits:d});}
function legendItem(name,color){const s=document.createElement('span'),sw=document.createElement('i');sw.className='swatch';sw.style.background=color;s.append(sw,document.createTextNode(name));document.getElementById('legend').appendChild(s);}
D.legend.forEach((item,i)=>{if(item)legendItem(item,[C.blue,C.orange,C.teal,C.yellow][i]);});
document.getElementById('scale-label').textContent=D.scaleLabel;
if(D.mode==='dirac'){
  document.getElementById('cost-comparison').hidden=false;
  document.getElementById('analytic-label').textContent=D.analyticLabel;
  document.getElementById('transport-label').textContent=D.transportLabel;
  document.getElementById('analytic-cost').textContent='€'+fmt(D.analytic,2);
  document.getElementById('analytic-fill').style.width=(100*D.analytic/Math.max(D.analytic,D.weightedCost,1e-12))+'%';
}
function build(){
  svg.innerHTML=''; dynamic=[];
  const W=Math.max(250,Math.round(svg.getBoundingClientRect().width)),H=280,L=60,R=18,T=16,B=47;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const xmax=D.mode==='mc' ? D.steps : D.capacity, ymin=D.ymin??0, yrange=Math.max(D.ymax-ymin,1e-12);
  const xx=v=>L+(W-L-R)*v/xmax, yy=v=>T+(H-T-B)*(1-(v-ymin)/yrange);
  for(let i=0;i<=4;i++){
    const f=i/4,x=xx(f*xmax),y=yy(ymin+f*yrange);
    const ydigits=(D.mode==='transport'||D.mode==='dirac'||yrange<1)?2:(yrange<10?1:0);
    const xtick=D.mode==='mc'?D.nValues[Math.round(f*D.steps)]:f*D.capacity;
    line(L,y,W-R,y);line(x,T,x,H-B);
    text(L-8,y+4,fmt(ymin+f*yrange,ydigits),{'text-anchor':'end'});
    text(x,H-B+20,fmt(xtick,0),{'text-anchor':'middle'});
  }
  text((L+W-R)/2,H-5,D.xTitle,{'text-anchor':'middle',fill:C.ink,'font-size':12});
  const yTitle=text(13,(T+H-B)/2,D.yTitle,{'text-anchor':'middle',fill:C.ink,'font-size':12});
  yTitle.setAttribute('transform',`rotate(-90 13 ${(T+H-B)/2})`);
  if(D.mode==='schedule'){
    const colors=[C.blue,C.orange,C.teal];
    for(let k=0;k<3;k++){
      let path=D.x.map((v,i)=>(i?'L':'M')+xx(v).toFixed(2)+','+yy(D.series[k][i]).toFixed(2)).join(' ');
      el('path',{d:path,fill:'none',stroke:colors[k],'stroke-width':2.4,'stroke-linejoin':'round'});
    }
    const cursor=line(xx(0),T,xx(0),H-B,C.yellow,{'stroke-dasharray':'4 4','stroke-width':1.2});
    dynamic=[cursor,...colors.map(c=>marker(xx(0),yy(0),c,5))];
  } else if(D.mode==='mc') {
    line(L,yy(D.analytic),W-R,yy(D.analytic),C.blue,{'stroke-width':2.5});
    const ribbon=el('polygon',{fill:'rgba(76,224,189,.18)',stroke:'none'});
    const curve=el('path',{fill:'none',stroke:C.orange,'stroke-width':2.5,'stroke-linejoin':'round'});
    dynamic=[ribbon,curve,marker(xx(0),yy(D.estimates[0]),C.orange,5)];
  } else {
    for(let i=0;i<D.quantiles.length;i++){
      const y=yy(D.quantiles[i]), a=xx(D.ref[i]), b=xx(D.comp[i]);
      line(a,y,b,y,'#596b7e',{'stroke-width':1.5});marker(a,y,C.teal,3.7);marker(b,y,C.blue,3.7);
      dynamic.push(marker(a,y,C.yellow,4.6));
    }
  }
  update(current);
}
function update(k){
  current=Math.max(0,Math.min(n,Math.round(k)));slider.value=String(current);
  const W=Math.max(250,Math.round(svg.getBoundingClientRect().width)),H=280,L=60,R=18,T=16,B=47;
  const xmax=D.mode==='mc' ? D.steps : D.capacity, ymin=D.ymin??0, yrange=Math.max(D.ymax-ymin,1e-12);
  const xx=v=>L+(W-L-R)*v/xmax, yy=v=>T+(H-T-B)*(1-(v-ymin)/yrange);
  if(D.mode==='schedule'){
    const x=xx(D.x[current]); dynamic[0].setAttribute('x1',x);dynamic[0].setAttribute('x2',x);
    for(let i=0;i<3;i++){dynamic[i+1].setAttribute('cx',x);dynamic[i+1].setAttribute('cy',yy(D.series[i][current]));}
    output.textContent=`Ps ${fmt(D.x[current],2)} MW · UCF €${fmt(D.series[0][current],2)}`;
  } else if(D.mode==='mc') {
    const upper=[],lower=[],curve=[];
    for(let i=0;i<=current;i++){
      upper.push(`${xx(i)},${yy(D.upper[i])}`);lower.push(`${xx(i)},${yy(D.lower[i])}`);
      curve.push((i?'L':'M')+xx(i)+','+yy(D.estimates[i]));
    }
    dynamic[0].setAttribute('points',upper.concat(lower.reverse()).join(' '));
    dynamic[1].setAttribute('d',curve.join(' '));
    dynamic[2].setAttribute('cx',xx(current));dynamic[2].setAttribute('cy',yy(D.estimates[current]));
    output.textContent=`N ${fmt(D.nValues[current],0)} · ${D.analyticShort} €${fmt(D.analytic,2)} · MC €${fmt(D.estimates[current],2)}`;
  } else {
    const t=current/n;
    for(let i=0;i<dynamic.length;i++) dynamic[i].setAttribute('cx',xx((1-t)*D.ref[i]+t*D.comp[i]));
    output.textContent=D.mode==='dirac' ? `t = ${fmt(t,2)} · W₁ = ${fmt(t*D.distance,2)} MW` : `t = ${fmt(t,2)}`;
    if(D.mode==='dirac'){
      const currentCost=t*D.weightedCost, maxCost=Math.max(D.analytic,D.weightedCost,1e-12);
      document.getElementById('transport-fill').style.width=(100*currentCost/maxCost)+'%';
      document.getElementById('transport-cost').textContent='€'+fmt(currentCost,2);
    }
  }
}
function tick(now){if(!playing)return; const elapsed=(now-start)/D.duration;update(elapsed*n);if(current>=n){playing=false;return;}anim=requestAnimationFrame(tick);}
document.getElementById('play').addEventListener('click',()=>{
  if(playing)return;if(current>=n)update(0);playing=true;start=performance.now()-(current/n)*D.duration;anim=requestAnimationFrame(tick);
});
document.getElementById('pause').addEventListener('click',()=>{playing=false;cancelAnimationFrame(anim);});
slider.addEventListener('input',()=>{playing=false;cancelAnimationFrame(anim);update(Number(slider.value));});
new ResizeObserver(()=>build()).observe(svg);build();
</script></body></html>'''


def _render(data: dict, es: bool, aria: str, range_aria: str) -> str:
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    return (_TEMPLATE.replace('__LANG__', 'es' if es else 'en')
            .replace('__ARIA__', aria).replace('__RANGE_ARIA__', range_aria)
            .replace('__PLAY__', '▶ Reproducir' if es else '▶ Play')
            .replace('__PAUSE__', '❚❚ Pausar' if es else '❚❚ Pause')
            .replace('__DATA__', encoded))


def schedule_animation(co: float, cu: float, hours: float, dist: Distribution, es: bool) -> str:
    x = np.linspace(0, dist.capacity_mw, 81)
    over, under, total = nominal_curve(x, co, cu, hours, dist)
    data = {"mode": "schedule", "capacity": dist.capacity_mw,
            "x": x.tolist(), "series": [total.tolist(), over.tolist(), under.tolist()],
            "ymax": max(float(total.max()), float(over.max()), float(under.max()), 1) * 1.12,
            "steps": 80, "duration": 7000, "locale": "es-ES" if es else "en-GB",
            "xTitle": "Ps programada (MW)" if es else "Scheduled Ps (MW)",
            "yTitle": "€ / intervalo" if es else "€ / interval",
            "scaleLabel": "Progreso de la animación" if es else "Animation progress",
            "legend": ["UCF", "Déficit", "Excedente"] if es else ["UCF", "Shortfall", "Surplus"]}
    return _render(data, es, "Animación de las curvas de costo según Ps" if es else "Animation of cost curves against Ps",
                   "Potencia programada en la animación" if es else "Animated scheduled power")


def transport_animation(a: Distribution, b: Distribution, es: bool) -> str:
    u = np.linspace(.03, .97, 17)
    data = {"mode": "transport", "capacity": a.capacity_mw, "ymax": 1.0,
            "quantiles": u.tolist(), "ref": a.quantile(u).tolist(), "comp": b.quantile(u).tolist(),
            "steps": 100, "duration": 6500, "locale": "es-ES" if es else "en-GB",
            "xTitle": "P (MW)", "yTitle": "Cuantil u" if es else "Quantile u",
            "scaleLabel": "Progreso del transporte" if es else "Transport progress",
            # The series palette follows the template: blue, orange, teal, yellow.
            "legend": ["Comparación", "", "Referencia", "Desplazamiento"] if es else ["Comparison", "", "Reference", "Movement"]}
    return _render(data, es, "Transporte ilustrativo entre cuantiles" if es else "Illustrative transport between quantiles",
                   "Progreso del transporte" if es else "Transport progress")


def mc_convergence_animation(counts, estimates, standard_errors, analytic: float, es: bool) -> str:
    """Animate a nested Monte Carlo estimate against the exact model expectation."""
    counts = np.asarray(counts, dtype=int)
    estimates = np.asarray(estimates, dtype=float)
    se = np.asarray(standard_errors, dtype=float)
    if len(counts) < 2 or len(counts) != len(estimates) or len(se) != len(counts):
        raise ValueError("MC checkpoints must have matching nonempty arrays.")
    lower = np.maximum(0.0, estimates - 1.96 * se)
    upper = estimates + 1.96 * se
    lo, hi = min(float(lower.min()), analytic), max(float(upper.max()), analytic)
    span = max(hi - lo, max(abs(analytic), 1.0) * 0.05)
    ymin = max(0.0, lo - .08 * span)
    ymax = max(hi + .08 * span, ymin + .1)
    data = {"mode": "mc", "capacity": int(len(counts)-1), "steps": int(len(counts)-1),
            "duration": 8000, "locale": "es-ES" if es else "en-GB",
            "nValues": counts.tolist(), "estimates": estimates.tolist(),
            "lower": lower.tolist(), "upper": upper.tolist(), "analytic": float(analytic),
            "ymin": ymin, "ymax": ymax, "xTitle": "Muestras N (escala logarítmica)" if es else "Sample size N (log scale)",
            "yTitle": "€ / intervalo" if es else "€ / interval",
            "scaleLabel": "Progreso de Monte Carlo" if es else "Monte Carlo progress",
            "analyticShort": "Analítica" if es else "Analytic",
            "legend": ["UCF exacta", "Monte Carlo", "IC aprox. 95 %"] if es else ["Exact UCF", "Monte Carlo", "Approx. 95% CI"]}
    return _render(data, es, "Convergencia Monte Carlo hacia la UCF" if es else "Monte Carlo convergence to the UCF",
                   "Número de muestras de Monte Carlo" if es else "Monte Carlo sample count")


def dirac_transport_animation(quantiles, capacity: float, schedule: float, distance: float,
                              weighted_cost: float, analytic: float, es: bool,
                              source_label: str | None = None,
                              analytic_label: str | None = None,
                              transport_label: str | None = None) -> str:
    """Show illustrative transport to δ_s and the full-distribution cost comparison."""
    points = np.asarray(quantiles, dtype=float)
    if points.ndim != 1 or len(points) < 2 or np.any(~np.isfinite(points)):
        raise ValueError("Representative quantiles must be a finite vector.")
    u = np.linspace(.03, .97, len(points))
    data = {"mode": "dirac", "capacity": float(capacity), "ymax": 1.0,
            "quantiles": u.tolist(), "ref": points.tolist(), "comp": np.full(len(points), schedule).tolist(),
            "steps": 100, "duration": 6500, "locale": "es-ES" if es else "en-GB",
            "xTitle": "P (MW)", "yTitle": "Cuantil u" if es else "Quantile u",
            "scaleLabel": "Transporte hacia δ(P − Ps)" if es else "Transport towards δ(P − Ps)",
            "distance": float(distance), "weightedCost": float(weighted_cost), "analytic": float(analytic),
            "analyticLabel": analytic_label or ("UCF analítica" if es else "Analytic UCF"),
            "transportLabel": transport_label or ("Transporte ponderado" if es else "Weighted transport"),
            "legend": (["Destino δ(P − Ps)", "", source_label or "Referencia", "Masa en movimiento"] if es else
                       ["Destination δ(P − Ps)", "", source_label or "Reference", "Moving mass"])}
    return _render(data, es, "Transporte de la distribución a la delta de Dirac en Ps" if es else "Transport of the distribution to the Dirac delta at Ps",
                   "Progreso hacia la delta de Dirac" if es else "Progress towards the Dirac delta")
