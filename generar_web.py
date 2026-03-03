"""
generar_web.py - NURIABOT
Genera docs/index.html para GitHub Pages.
Havanna: alfajores, havannets, chocolates — precio unitario ARS y USD
"""

import json
from pathlib import Path
from datetime import datetime

DIR_DATA = Path("data")
DIR_DOCS = Path("docs")

ORDEN_CATS = ["Tortas Individuales", "Tortas y Postres", "Pasteleria y Panaderia", "Salados", "Otros"]

def leer_json(nombre):
    ruta = DIR_DATA / nombre
    if ruta.exists():
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None

def fmt_pct(v):
    if v is None: return "—"
    signo = "+" if v > 0 else ""
    return f"{signo}{v:.2f}%"

def color_pct(v):
    if v is None: return "#888"
    if v > 0: return "#ef4444"
    if v < 0: return "#22c55e"
    return "#888"

def main():
    DIR_DOCS.mkdir(exist_ok=True)

    resumen  = leer_json("resumen.json") or {}
    graficos = leer_json("graficos.json") or {}
    rank_dia = leer_json("ranking_dia.json") or []
    rank_7d  = leer_json("ranking_7d.json") or []
    rank_mes = leer_json("ranking_mes.json") or []

    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    var_dia   = resumen.get("variacion_dia")
    var_mes   = resumen.get("variacion_mes")
    total     = resumen.get("total_productos", 0)
    sube      = resumen.get("productos_subieron_dia", 0)
    baja      = resumen.get("productos_bajaron_dia", 0)
    igual     = resumen.get("productos_sin_cambio_dia", 0)
    cats_dia  = resumen.get("categorias_dia", [])

    # Ordenar cats según ORDEN_CATS
    cats_sorted = sorted(cats_dia, key=lambda x: ORDEN_CATS.index(x["categoria"]) if x["categoria"] in ORDEN_CATS else 99)

    filas_cats = ""
    for cat in cats_sorted:
        pct = cat.get("variacion_pct_promedio", 0)
        c = color_pct(pct)
        filas_cats += f"""
        <tr>
          <td><strong>{cat.get('categoria','')}</strong></td>
          <td style="color:{c};font-weight:700">{fmt_pct(pct)}</td>
          <td style="color:#ef4444">⬆ {cat.get('productos_subieron',0)}</td>
          <td style="color:#22c55e">⬇ {cat.get('productos_bajaron',0)}</td>
          <td>{cat.get('total_productos',0)}</td>
        </tr>"""

    graficos_js = json.dumps(graficos, ensure_ascii=False)
    rank_dia_js = json.dumps(rank_dia[:20], ensure_ascii=False)
    rank_7d_js  = json.dumps(rank_7d[:20], ensure_ascii=False)
    rank_mes_js = json.dumps(rank_mes[:20], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Havanna Price Tracker</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;600;700&display=swap');
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
    --accent: #ec4899; --red: #ef4444; --green: #22c55e;
    --text: #e2e8f0; --muted: #64748b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'IBM Plex Sans', sans-serif; }}
  header {{
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem; display: flex; justify-content: space-between;
    align-items: center; flex-wrap: wrap; gap: 1rem;
  }}
  header h1 {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.3rem; color: var(--accent); }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }}
  .hero {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .stat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.5rem; text-align: center;
  }}
  .stat-card .label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.5rem; }}
  .stat-card .value {{ font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 700; }}
  .section {{ margin-bottom: 2.5rem; }}
  .section-title {{
    font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.15em; color: var(--muted);
    margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);
  }}
  .tabs {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .tab {{
    padding: 0.4rem 1rem; border-radius: 6px; border: 1px solid var(--border);
    background: transparent; color: var(--muted); cursor: pointer;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; transition: all 0.2s;
  }}
  .tab.active, .tab:hover {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .chart-container {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.5rem; height: 320px;
  }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th {{
    background: var(--surface); padding: 0.7rem 1rem; text-align: left;
    font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--muted); border-bottom: 1px solid var(--border);
  }}
  td {{ padding: 0.65rem 1rem; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: rgba(255,255,255,0.02); }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
  @media (max-width: 700px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .rank-tabs {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }}
  .rank-tab {{
    padding: 0.35rem 0.9rem; border-radius: 6px; border: 1px solid var(--border);
    background: transparent; color: var(--muted); cursor: pointer; font-size: 0.8rem;
  }}
  .rank-tab.active {{ background: var(--surface); color: var(--text); border-color: var(--accent); }}
  footer {{
    text-align: center; padding: 2rem; color: var(--muted);
    font-size: 0.75rem; border-top: 1px solid var(--border);
    font-family: 'IBM Plex Mono', monospace;
  }}
  .cat-selector {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>🎂 NURIA PRICE TRACKER</h1>
    <div style="color:var(--muted);font-size:0.8rem;margin-top:0.2rem">Pasteleria, tortas y salados · nuria.com.ar</div>
  </div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.8rem;color:var(--muted)">Actualizado: {fecha_str}</div>
</header>

<div class="container">
  <div class="hero" style="margin-top:1.5rem">
    <div class="stat-card">
      <div class="label">Variación Hoy (precio unitario)</div>
      <div class="value" style="color:{color_pct(var_dia)}">{fmt_pct(var_dia)}</div>
      <div style="font-size:0.8rem;color:var(--muted);margin-top:0.3rem">{total} productos relevados</div>
    </div>
    <div class="stat-card">
      <div class="label">Variación 30 días</div>
      <div class="value" style="color:{color_pct(var_mes)}">{fmt_pct(var_mes)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Movimiento Hoy</div>
      <div style="display:flex;justify-content:center;gap:1rem;margin-top:0.5rem">
        <div><div style="color:#ef4444;font-size:1.3rem;font-weight:700;font-family:'IBM Plex Mono',monospace">⬆ {sube}</div><div style="font-size:0.7rem;color:var(--muted)">Subieron</div></div>
        <div><div style="color:#22c55e;font-size:1.3rem;font-weight:700;font-family:'IBM Plex Mono',monospace">⬇ {baja}</div><div style="font-size:0.7rem;color:var(--muted)">Bajaron</div></div>
        <div><div style="color:#888;font-size:1.3rem;font-weight:700;font-family:'IBM Plex Mono',monospace">➡ {igual}</div><div style="font-size:0.7rem;color:var(--muted)">Igual</div></div>
      </div>
    </div>
    <div class="stat-card">
      <div class="label">Fuente</div>
      <div style="margin-top:0.5rem">
        <div style="color:var(--accent);font-size:0.9rem;font-weight:600">nuria.com.ar</div>
        <div style="font-size:0.75rem;color:var(--muted);margin-top:0.3rem">Pasteleria de Rosario</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">📈 Evolución precio unitario promedio</div>
    <div class="tabs" id="tabs-periodo">
      <button class="tab active" onclick="cambiarPeriodo('7d',this)">7 días</button>
      <button class="tab" onclick="cambiarPeriodo('30d',this)">30 días</button>
      <button class="tab" onclick="cambiarPeriodo('6m',this)">6 meses</button>
    </div>
    <div class="chart-container"><canvas id="chartGeneral"></canvas></div>
  </div>

  <div class="section">
    <div class="section-title">📊 Evolución por categoría</div>
    <div class="cat-selector" id="selectorCat"></div>
    <div class="chart-container"><canvas id="chartCat"></canvas></div>
  </div>

  <div class="section">
    <div class="section-title">🗂 Variación por categoría — hoy</div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Categoría</th><th>Variación %</th><th>Subieron</th><th>Bajaron</th><th>Total</th></tr></thead>
        <tbody>{filas_cats}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-title">🏆 Rankings de productos</div>
    <div class="rank-tabs">
      <button class="rank-tab active" onclick="mostrarRanking('dia',this)">📅 Hoy</button>
      <button class="rank-tab" onclick="mostrarRanking('7d',this)">📆 7 días</button>
      <button class="rank-tab" onclick="mostrarRanking('mes',this)">📅 30 días</button>
    </div>
    <div class="grid2">
      <div>
        <div style="font-size:0.8rem;color:var(--muted);margin-bottom:0.7rem">🔥 Más subieron</div>
        <div class="table-wrap">
          <table><thead><tr><th>#</th><th>Producto</th><th>Var %</th><th>Precio unitario</th></tr></thead><tbody id="tabla-sube"></tbody></table>
        </div>
      </div>
      <div>
        <div style="font-size:0.8rem;color:var(--muted);margin-bottom:0.7rem">📉 Más bajaron</div>
        <div class="table-wrap">
          <table><thead><tr><th>#</th><th>Producto</th><th>Var %</th><th>Precio unitario</th></tr></thead><tbody id="tabla-baja"></tbody></table>
        </div>
      </div>
    </div>
  </div>
</div>

<footer>
  Datos de nuria.com.ar · Pasteleria de Rosario calculado desde paquetes · GitHub Actions diario<br>
  NURIABOT · Los precios pueden variar por promociones
</footer>

<script>
const GRAFICOS = {graficos_js};
const RANK_DIA = {rank_dia_js};
const RANK_7D  = {rank_7d_js};
const RANK_MES = {rank_mes_js};
let chartG = null, chartC = null;
let periodoActual = '7d', catActual = null;

function cambiarPeriodo(p, btn) {{
  periodoActual = p;
  document.querySelectorAll('#tabs-periodo .tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderGeneral(p);
  renderSelectorCat(p);
}}

function renderGeneral(p) {{
  const datos = GRAFICOS[p]?.total || [];
  if (chartG) chartG.destroy();
  chartG = new Chart(document.getElementById('chartGeneral').getContext('2d'), {{
    type: 'line',
    data: {{
      labels: datos.map(d => d.fecha),
      datasets: [{{ label: 'Variación %', data: datos.map(d => d.pct),
        borderColor: '#d97706', backgroundColor: 'rgba(217,119,6,0.08)',
        borderWidth: 2, pointRadius: datos.length > 60 ? 0 : 3, tension: 0.3, fill: true }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 8 }}, grid: {{ color: '#2a2d3a' }} }},
        y: {{ ticks: {{ color: '#64748b', callback: v => (v>0?'+':'')+v.toFixed(1)+'%' }}, grid: {{ color: '#2a2d3a' }} }}
      }}
    }}
  }});
}}

function renderSelectorCat(p) {{
  const cats = Object.keys(GRAFICOS[p]?.categorias || {{}});
  const cont = document.getElementById('selectorCat');
  cont.innerHTML = '';
  if (!catActual || !cats.includes(catActual)) catActual = cats[0];
  cats.forEach(cat => {{
    const btn = document.createElement('button');
    btn.className = 'tab' + (cat === catActual ? ' active' : '');
    btn.textContent = cat;
    btn.onclick = () => {{
      catActual = cat;
      document.querySelectorAll('#selectorCat .tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderCat(p, cat);
    }};
    cont.appendChild(btn);
  }});
  if (catActual) renderCat(p, catActual);
}}

function renderCat(p, cat) {{
  const datos = GRAFICOS[p]?.categorias?.[cat] || [];
  if (chartC) chartC.destroy();
  chartC = new Chart(document.getElementById('chartCat').getContext('2d'), {{
    type: 'line',
    data: {{
      labels: datos.map(d => d.fecha),
      datasets: [{{ label: cat + ' %', data: datos.map(d => d.pct),
        borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,0.08)',
        borderWidth: 2, pointRadius: datos.length > 60 ? 0 : 3, tension: 0.3, fill: true }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 8 }}, grid: {{ color: '#2a2d3a' }} }},
        y: {{ ticks: {{ color: '#64748b', callback: v => (v>0?'+':'')+v.toFixed(1)+'%' }}, grid: {{ color: '#2a2d3a' }} }}
      }}
    }}
  }});
}}

function mostrarRanking(p, btn) {{
  document.querySelectorAll('.rank-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const data = p === 'dia' ? RANK_DIA : p === '7d' ? RANK_7D : RANK_MES;
  const sube = data.filter(x => (x.diff_pct||0) > 0).slice(0,10);
  const baja = [...data].filter(x => (x.diff_pct||0) < 0).sort((a,b)=>a.diff_pct-b.diff_pct).slice(0,10);
  renderTabla('tabla-sube', sube, false);
  renderTabla('tabla-baja', baja, true);
}}

function renderTabla(id, data, esBaja) {{
  const tb = document.getElementById(id);
  if (!data.length) {{ tb.innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center;padding:1rem">Sin datos aún</td></tr>'; return; }}
  tb.innerHTML = data.map((p,i) => {{
    const color = esBaja ? '#22c55e' : '#ef4444';
    const signo = p.diff_pct > 0 ? '+' : '';
    return `<tr>
      <td style="color:var(--muted);font-size:0.75rem">${{i+1}}</td>
      <td><div style="font-size:0.85rem">${{(p.nombre||'').substring(0,32)}}</div><div style="font-size:0.7rem;color:var(--muted)">${{p.categoria||''}}</div></td>
      <td style="color:${{color}};font-weight:700;font-family:'IBM Plex Mono',monospace">${{signo}}${{p.diff_pct?.toFixed(1)}}%</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:0.82rem">${{p.precio_hoy ? '$'+Number(p.precio_hoy).toLocaleString('es-AR') : '—'}}</td>
    </tr>`;
  }}).join('');
}}

renderGeneral('7d');
renderSelectorCat('7d');
mostrarRanking('dia', document.querySelector('.rank-tab'));
</script>
</body>
</html>"""

    ruta = DIR_DOCS / "index.html"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Web NURIABOT generada: {ruta}")

if __name__ == "__main__":
    main()
