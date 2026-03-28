"""
TurboDashboard v2 — Server-Side Analytics Dashboard
====================================================
Replaces the Perspective WASM approach (stream all rows to browser) with
server-side Polars aggregations + Chart.js visualisations.

Architecture
------------
  Polars LazyFrame  (stays on the server)
       │  .group_by().agg()  →  tiny JSON payloads  (< 2 KB per chart)
       ▼
  FastAPI
       ├── GET /api/meta        → schema + auto-detected column types
       ├── GET /api/kpis        → aggregate KPIs  (sum/mean of numeric cols)
       ├── GET /api/dist/{col}  → value-distribution  (group_by + count/sum)
       ├── GET /api/trend       → time-series  (group_by month/week/year)
       ├── GET /api/preview     → paginated table preview
       └── GET /                → Chart.js SPA
       ▼
  Browser  —  Chart.js 4.x  (~200 KB CDN, no WASM)
       └── Interactive filters → re-query aggregations server-side
           1M-row Polars aggregations return in < 200 ms

Why this is faster
------------------
Old approach: stream 1M rows → browser  (~100 MB transfer, slow)
New approach: send aggregated JSON only  (~2 KB per chart, instant)
The browser never sees raw rows — only computed summaries.

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import html as _html_mod
import json as _json
import logging
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import polars as pl
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .engine import TurboEngine

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK = 100_000  # kept for API compatibility

_NUMERIC_BASES = (
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
    pl.Float32, pl.Float64,
)


# ── Column classifier ─────────────────────────────────────────────────────────

def _classify(schema) -> Dict[str, List[str]]:
    """
    Auto-classify columns into categorical, numeric (non-ID), and date buckets.
    ID-like columns (name == 'id', ends with '_id', starts with 'id_') are
    excluded from numeric so that meaningless sums don't appear on charts.

    Note: uses isinstance(dtype, cls) directly — base_type() returns the class
    itself, not an instance, so isinstance checks on base_type() always fail.
    """
    cat, num, dates = [], [], []
    for col, dtype in schema.items():
        lo    = col.lower()
        is_id = lo == "id" or lo.endswith("_id") or lo.startswith("id_")
        if isinstance(dtype, (pl.String, pl.Categorical, pl.Enum)) and not is_id:
            cat.append(col)
        elif isinstance(dtype, _NUMERIC_BASES) and not is_id:
            num.append(col)
        elif isinstance(dtype, (pl.Date, pl.Datetime)):
            dates.append(col)
    return {"categorical": cat, "numeric": num, "date": dates}


# ── Query helpers ─────────────────────────────────────────────────────────────

def _filtered_lf(engine: TurboEngine, filters_json: Optional[str]) -> pl.LazyFrame:
    """Return a LazyFrame with JSON-encoded column filters applied."""
    q = engine.lf
    if filters_json:
        try:
            fs = _json.loads(filters_json)
            if isinstance(fs, list) and fs:
                q = engine._apply_filters(q, fs)
        except Exception:
            pass
    return q


# ── HTML / JS template ───────────────────────────────────────────────────────

def _build_html(title: str, engine: TurboEngine, cols: Dict) -> str:
    safe_title = _html_mod.escape(title, quote=True)
    rows_fmt   = f"{engine.total_rows():,}"

    # Pre-generate chart card HTML (avoids nested f-string brace escaping)
    chart_cards = "".join(
        f'<div class="card" id="card-{i}">'
        f'<div class="card-hdr">'
        f'<span class="card-title" id="ct-{i}">Loading\u2026</span>'
        f'<span class="qt" id="qt-{i}"></span>'
        f'</div>'
        f'<div class="cwrap" id="cw-{i}">'
        f'<div class="spin-wrap"><div class="spinner"></div>Querying Polars\u2026</div>'
        f'</div>'
        f'</div>'
        for i in range(4)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{safe_title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0f172a;--panel:#162032;--card:#1a2844;
  --border:#2d4060;--text:#e2e8f0;--muted:#64748b;
  --accent:#38bdf8;--green:#34d399;--amber:#fbbf24;
  --red:#f87171;--purple:#a78bfa;
}}
html,body{{height:100%;background:var(--bg);color:var(--text);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:14px;overflow-x:hidden}}

/* ── Header ── */
#hdr{{background:var(--panel);border-bottom:1px solid var(--border);
  padding:10px 20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  position:sticky;top:0;z-index:20;box-shadow:0 2px 8px rgba(0,0,0,.4)}}
#hdr h1{{font-size:1.05rem;font-weight:700;white-space:nowrap;
  background:linear-gradient(135deg,var(--accent),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.badge{{font-size:.6rem;font-weight:700;padding:2px 8px;border-radius:999px;
  text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}}
.badge-blue{{background:#1a3050;color:#7dd3fc;border:1px solid #1e4070}}
.badge-green{{background:#0f2a1a;color:#86efac;border:1px solid #14532d}}
#kpis{{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}}
.kpi{{background:var(--bg);border:1px solid var(--border);border-radius:8px;
  padding:5px 14px;text-align:center;min-width:96px}}
.kpi-lbl{{font-size:.58rem;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}}
.kpi-val{{font-size:.92rem;font-weight:700;color:var(--accent)}}

/* ── Filter bar ── */
#fbar{{background:var(--panel);border-bottom:1px solid var(--border);
  padding:6px 20px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;min-height:38px}}
.flbl{{font-size:.65rem;color:var(--muted);font-weight:700;text-transform:uppercase}}
.fgroup{{display:flex;align-items:center;gap:4px}}
.fgroup span{{font-size:.68rem;color:var(--muted)}}
select{{background:var(--card);color:var(--text);border:1px solid var(--border);
  border-radius:5px;padding:3px 8px;font-size:.75rem;cursor:pointer;
  transition:border-color .15s}}
select:focus{{outline:none;border-color:var(--accent)}}
#clr{{background:transparent;color:var(--red);border:1px solid var(--red);
  border-radius:5px;padding:3px 12px;font-size:.72rem;cursor:pointer;
  margin-left:auto;transition:background .15s}}
#clr:hover{{background:rgba(239,68,68,.1)}}
#finfo{{font-size:.7rem;color:var(--amber);font-weight:600}}

/* ── Charts grid ── */
#grid{{display:grid;
  grid-template-columns:repeat(auto-fit,minmax(400px,1fr));
  gap:14px;padding:14px 20px}}
.card{{background:var(--card);border:1px solid var(--border);
  border-radius:10px;padding:14px;
  box-shadow:0 1px 4px rgba(0,0,0,.3)}}
.card-hdr{{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:10px;gap:8px}}
.card-title{{font-size:.78rem;font-weight:600;color:var(--text)}}
.qt{{font-size:.65rem;color:var(--green);font-family:monospace;
  background:rgba(52,211,153,.08);padding:1px 5px;border-radius:3px}}
.cwrap{{position:relative;height:220px}}

/* ── Data preview ── */
#prev{{margin:0 20px 24px;background:var(--card);border:1px solid var(--border);
  border-radius:10px;overflow:hidden;
  box-shadow:0 1px 4px rgba(0,0,0,.3)}}
.prev-hdr{{display:flex;justify-content:space-between;align-items:center;
  padding:9px 14px;border-bottom:1px solid var(--border)}}
.prev-hdr b{{font-size:.8rem;font-weight:600}}
.tscroll{{overflow:auto;max-height:260px}}
table{{width:100%;border-collapse:collapse;font-size:.72rem}}
thead th{{background:var(--panel);color:var(--muted);font-weight:700;
  text-transform:uppercase;font-size:.62rem;letter-spacing:.4px;
  padding:6px 10px;position:sticky;top:0;text-align:left;
  border-bottom:1px solid var(--border);white-space:nowrap}}
tbody tr:nth-child(even){{background:rgba(255,255,255,.015)}}
tbody tr:hover{{background:rgba(56,189,248,.04)}}
tbody td{{padding:5px 10px;border-bottom:1px solid rgba(45,64,96,.5);
  white-space:nowrap;max-width:180px;overflow:hidden;text-overflow:ellipsis;
  color:var(--text)}}

/* ── Spinner ── */
.spin-wrap{{display:flex;align-items:center;justify-content:center;
  height:220px;color:var(--muted);font-size:.78rem;gap:8px}}
.spinner{{width:16px;height:16px;border:2px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;
  animation:spin .7s linear infinite;flex-shrink:0}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
</head>
<body>

<div id="hdr">
  <h1>⚡ {safe_title}</h1>
  <span class="badge badge-blue">Polars · Chart.js</span>
  <span class="badge badge-green">{rows_fmt} rows</span>
  <div id="kpis"></div>
</div>

<div id="fbar">
  <span class="flbl">Filter</span>
  <div id="fselects" style="display:flex;gap:8px;flex-wrap:wrap"></div>
  <span id="finfo"></span>
  <button id="clr" onclick="clearFilters()">✕ Clear</button>
</div>

<div id="grid">{chart_cards}</div>

<div id="prev">
  <div class="prev-hdr">
    <b>Data Preview</b>
    <span class="qt" id="qt-prev"></span>
  </div>
  <div class="tscroll"><table id="tbl"></table></div>
</div>

<script>
"use strict";

// ── Chart.js dark defaults ────────────────────────────────────────────────────
Chart.defaults.color           = '#94a3b8';
Chart.defaults.borderColor     = '#2d4060';
Chart.defaults.font.family     = 'system-ui,-apple-system,"Segoe UI",sans-serif';
Chart.defaults.font.size       = 11;
Chart.defaults.plugins.tooltip.mode = 'index';

const PALETTE = [
  '#38bdf8','#818cf8','#34d399','#fbbf24','#f87171',
  '#a78bfa','#fb923c','#4ade80','#f472b6','#60a5fa',
  '#2dd4bf','#e879f9','#facc15','#86efac','#c084fc',
];

// ── App state ─────────────────────────────────────────────────────────────────
let charts  = {{}};
let filters = {{}};
let cfgs    = [];

// ── Utility ───────────────────────────────────────────────────────────────────
const cap = s => {{ const t = s.replace(/_/g,' '); return t.charAt(0).toUpperCase()+t.slice(1).replace(/ (.)/g, m => ' '+m[1].toUpperCase()); }};

const esc = s => String(s ?? '')
  .replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function fmt(n) {{
  if (n == null) return '\u2014';
  const abs = Math.abs(n);
  if (abs >= 1e9) return (n/1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return (n/1e6).toFixed(2) + 'M';
  if (abs >= 1e3) return (n/1e3).toFixed(1) + 'K';
  return typeof n === 'number'
    ? n.toLocaleString(undefined, {{maximumFractionDigits: 2}})
    : String(n);
}}

async function api(url) {{
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${{r.status}} \u2014 ${{url}}`);
  return r.json();
}}

// ── Filter helpers ────────────────────────────────────────────────────────────
function filtersParam() {{
  const arr = Object.entries(filters)
    .filter(([, v]) => v !== '')
    .map(([field, value]) => ({{ field, type: '=', value }}));
  return arr.length ? '&filters=' + encodeURIComponent(JSON.stringify(arr)) : '';
}}

function onFilter(col, val) {{
  if (val === '') delete filters[col]; else filters[col] = val;
  const n = Object.keys(filters).length;
  document.getElementById('finfo').textContent = n
    ? n + ' filter' + (n > 1 ? 's' : '') + ' active' : '';
  refreshAll();
}}

function clearFilters() {{
  filters = {{}};
  document.querySelectorAll('#fselects select').forEach(s => s.value = '');
  document.getElementById('finfo').textContent = '';
  refreshAll();
}}

// ── Chart configuration auto-builder ─────────────────────────────────────────
function buildCfgs(cols) {{
  const cat  = cols.categorical || [];
  const num  = cols.numeric     || [];
  const dt   = cols.date        || [];

  // Prefer a revenue/sales/profit column as primary metric
  const mainNum = num.find(c => /revenue|sales|profit|amount|total/i.test(c)) || num[0];

  const defs = [];

  // Chart 0 — bar: first categorical × primary numeric (sum)
  if (cat[0] && mainNum)
    defs.push({{
      id: 0, type: 'bar',
      title: cap(cat[0]) + ' by ' + cap(mainNum),
      url: fp => `/api/dist/${{cat[0]}}?metric=sum&value_col=${{mainNum}}` + fp,
    }});

  // Chart 1 — horizontal bar: second categorical × row count
  const cat1 = cat[1] || cat[0];
  if (cat1)
    defs.push({{
      id: 1, type: 'bar-h',
      title: 'Volume by ' + cap(cat1),
      url: fp => `/api/dist/${{cat1}}?metric=count` + fp,
    }});

  // Chart 2 — line trend OR bar for third categorical
  if (dt[0] && mainNum)
    defs.push({{
      id: 2, type: 'line',
      title: cap(mainNum) + ' Trend',
      url: fp => `/api/trend?` + fp.replace(/^&/,''),
    }});
  else if (cat[2])
    defs.push({{
      id: 2, type: 'bar',
      title: cap(cat[2]) + ' Distribution',
      url: fp => `/api/dist/${{cat[2]}}?metric=count` + fp,
    }});

  // Chart 3 — doughnut: third (or fallback second/first) categorical
  const dCol = cat[2] || cat[1] || cat[0];
  if (dCol)
    defs.push({{
      id: 3, type: 'doughnut',
      title: cap(dCol) + ' Share',
      url: fp => `/api/dist/${{dCol}}?metric=count&top=8` + fp,
    }});

  return defs.slice(0, 4);
}}

// ── Chart renderer ────────────────────────────────────────────────────────────
function drawChart(id, type, labels, values) {{
  if (charts[id]) {{ charts[id].destroy(); delete charts[id]; }}

  const wrap = document.getElementById('cw-' + id);
  wrap.innerHTML = '<canvas id="cv-' + id + '"></canvas>';
  const ctx  = document.getElementById('cv-' + id).getContext('2d');

  const isDonut = type === 'doughnut';
  const isLine  = type === 'line';
  const chartType = isDonut ? 'doughnut' : isLine ? 'line' : 'bar';

  const bg = isDonut  ? PALETTE.slice(0, labels.length)
           : isLine   ? 'rgba(56,189,248,0.1)'
           : PALETTE.slice(0, labels.length).map(c => c + 'bb');

  const border = isDonut ? PALETTE.slice(0, labels.length)
               : isLine  ? '#38bdf8'
               : PALETTE.slice(0, labels.length);

  charts[id] = new Chart(ctx, {{
    type: chartType,
    data: {{
      labels,
      datasets: [{{
        data: values,
        backgroundColor: bg,
        borderColor: border,
        borderWidth: isLine ? 2 : 1,
        fill: isLine,
        tension: isLine ? 0.35 : 0,
        pointRadius: isLine ? (labels.length > 60 ? 0 : 3) : 0,
        pointHoverRadius: isLine ? 5 : 0,
      }}],
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: type === 'bar-h' ? 'y' : 'x',
      animation: {{ duration: 250 }},
      plugins: {{
        legend: {{
          display: isDonut,
          position: 'right',
          labels: {{ boxWidth: 11, padding: 10, font: {{ size: 10 }} }},
        }},
        tooltip: {{
          callbacks: {{
            label: ctx => ' ' + fmt(isDonut ? ctx.parsed : ctx.parsed.y),
          }},
        }},
      }},
      scales: isDonut ? {{}} : {{
        x: {{
          grid: {{ color: 'rgba(45,64,96,.5)' }},
          ticks: {{ maxRotation: 35, font: {{ size: 10 }} }},
        }},
        y: {{
          grid: {{ color: 'rgba(45,64,96,.5)' }},
          ticks: {{
            callback: v => fmt(v),
            font: {{ size: 10 }},
          }},
        }},
      }},
    }},
  }});
}}

function setSpinner(id) {{
  document.getElementById('cw-' + id).innerHTML =
    '<div class="spin-wrap"><div class="spinner"></div>Querying Polars\u2026</div>';
}}

// ── KPI renderer ──────────────────────────────────────────────────────────────
function renderKPIs(data) {{
  const kl = [['Rows', fmt(data.__rows__)]];
  for (const [k, v] of Object.entries(data))
    if (k.startsWith('sum_')  && kl.length < 3) kl.push([cap(k.slice(4)), fmt(v)]);
  for (const [k, v] of Object.entries(data))
    if (k.startsWith('mean_') && kl.length < 4) kl.push(['Avg ' + cap(k.slice(5)), fmt(v)]);
  document.getElementById('kpis').innerHTML = kl.map(([l, v]) =>
    `<div class="kpi"><div class="kpi-lbl">${{l}}</div><div class="kpi-val">${{v}}</div></div>`
  ).join('');
}}

// ── Filter select UI ──────────────────────────────────────────────────────────
async function buildFilterUI(cols) {{
  const cat  = (cols.categorical || []).slice(0, 4);
  const wrap = document.getElementById('fselects');
  if (!cat.length) {{ wrap.innerHTML = '<span style="font-size:.7rem;color:var(--muted)">No categorical columns detected</span>'; return; }}

  const dists = await Promise.all(
    cat.map(col => api(`/api/dist/${{col}}?metric=count&top=20`).catch(() => ({{ labels: [] }})))
  );
  wrap.innerHTML = cat.map((col, i) => {{
    const opts = (dists[i].labels || []).map(v =>
      `<option value="${{esc(String(v))}}">${{esc(String(v))}}</option>`
    ).join('');
    return `<div class="fgroup">
      <span>${{cap(col)}}</span>
      <select onchange="onFilter('${{col}}',this.value)">
        <option value="">All</option>${{opts}}
      </select></div>`;
  }}).join('');
}}

// ── Refresh ───────────────────────────────────────────────────────────────────
async function refreshAll() {{
  const fp = filtersParam();

  // KPIs — non-blocking
  api('/api/kpis?' + fp.replace(/^&/,''))
    .then(d => renderKPIs(d.data))
    .catch(console.error);

  // Charts — parallel
  cfgs.forEach(c => setSpinner(c.id));
  await Promise.all(cfgs.map(async c => {{
    try {{
      const d = await api(c.url(fp));
      drawChart(c.id, c.type, d.labels, d.values);
      document.getElementById('ct-' + c.id).textContent = c.title;
      document.getElementById('qt-' + c.id).textContent = d.query_ms + ' ms';
    }} catch (e) {{
      document.getElementById('cw-' + c.id).innerHTML =
        `<div class="spin-wrap" style="color:var(--red)">\u26a0 ${{esc(e.message)}}</div>`;
    }}
  }}));

  // Preview table — non-blocking
  api('/api/preview?size=200' + fp)
    .then(d => {{
      document.getElementById('qt-prev').textContent =
        d.query_ms + ' ms \u00b7 ' + d.total.toLocaleString() + ' rows';
      const th = d.columns.map(c => `<th>${{esc(c)}}</th>`).join('');
      const tb = d.data.map(row =>
        '<tr>' + d.columns.map(c =>
          `<td title="${{esc(String(row[c] ?? ''))}}">${{esc(String(row[c] ?? ''))}}</td>`
        ).join('') + '</tr>'
      ).join('');
      document.getElementById('tbl').innerHTML =
        `<thead><tr>${{th}}</tr></thead><tbody>${{tb}}</tbody>`;
    }}).catch(console.error);
}}

// ── Boot ──────────────────────────────────────────────────────────────────────
(async () => {{
  try {{
    const meta = await api('/api/meta');
    cfgs = buildCfgs(meta.columns);
    await buildFilterUI(meta.columns);
    await refreshAll();
  }} catch (e) {{
    document.getElementById('grid').innerHTML =
      `<div style="padding:40px;color:var(--red)">Boot failed: ${{esc(e.message)}}</div>`;
  }}
}})();
</script>
</body>
</html>"""


# ── FastAPI application ───────────────────────────────────────────────────────

def create_dashboard_app(engine: TurboEngine, title: str, chunk_size: int) -> FastAPI:
    """Build and return the TurboDashboard FastAPI application (v2)."""
    cols = _classify(engine._schema_cache)

    app = FastAPI(
        title=f"{title} — TurboDashboard",
        version="2.0.0",
        description=(
            "TurboDashboard v2: Polars server-side aggregations + Chart.js. "
            "Browser receives only aggregated JSON — no row streaming."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # ── SPA ──────────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> str:
        return _build_html(title, engine, cols)

    # ── Metadata ─────────────────────────────────────────────────────────────

    @app.get("/api/meta", summary="Dataset metadata + column classification")
    def get_meta():
        return {
            "title":      title,
            "total_rows": engine.total_rows(),
            "schema":     engine.schema,
            "columns":    cols,
        }

    # ── KPIs ─────────────────────────────────────────────────────────────────

    @app.get("/api/kpis", summary="Aggregate KPI metrics")
    def get_kpis(filters: Optional[str] = Query(None)):
        t0 = time.perf_counter()
        q  = _filtered_lf(engine, filters)

        agg = [pl.len().alias("__rows__")]
        for c in cols["numeric"][:6]:
            agg += [
                pl.col(c).sum().alias(f"sum_{c}"),
                pl.col(c).mean().alias(f"mean_{c}"),
            ]

        row = q.select(agg).collect().row(0, named=True)
        return {
            "data":     row,
            "query_ms": round((time.perf_counter() - t0) * 1e3, 1),
        }

    # ── Distribution ─────────────────────────────────────────────────────────

    @app.get("/api/dist/{column}", summary="Value distribution for a column")
    def get_dist(
        column:    str,
        top:       int           = Query(15, ge=1, le=100),
        metric:    str           = Query("count"),
        value_col: Optional[str] = Query(None),
        filters:   Optional[str] = Query(None),
    ):
        if column not in engine._schema_cache:
            return {"labels": [], "values": [], "query_ms": 0,
                    "error": f"Column {column!r} not found"}

        t0 = time.perf_counter()
        q  = _filtered_lf(engine, filters)

        if metric == "sum" and value_col and value_col in engine._schema_cache:
            agg_expr = pl.col(value_col).sum().alias("v")
        elif metric == "mean" and value_col and value_col in engine._schema_cache:
            agg_expr = pl.col(value_col).mean().alias("v")
        else:
            agg_expr = pl.len().alias("v")

        res = (
            q.group_by(column)
            .agg(agg_expr)
            .sort("v", descending=True)
            .head(top)
            .collect()
        )

        vals = res["v"]
        if vals.dtype in (pl.Float32, pl.Float64):
            vals = vals.round(2)

        return {
            "labels":   res[column].fill_null("(null)").cast(pl.String).to_list(),
            "values":   vals.to_list(),
            "query_ms": round((time.perf_counter() - t0) * 1e3, 1),
        }

    # ── Time-series trend ────────────────────────────────────────────────────

    @app.get("/api/trend", summary="Time-series aggregation")
    def get_trend(
        date_col:  Optional[str] = Query(None),
        value_col: Optional[str] = Query(None),
        period:    str           = Query("month"),
        filters:   Optional[str] = Query(None),
    ):
        dc = date_col  or (cols["date"][0]    if cols["date"]    else None)
        vc = value_col or (cols["numeric"][0]  if cols["numeric"] else None)

        if not dc or not vc:
            return {"labels": [], "values": [], "query_ms": 0}

        t0 = time.perf_counter()
        q  = _filtered_lf(engine, filters)

        if period == "year":
            fmt_expr = pl.col(dc).dt.year().cast(pl.String)
        elif period == "week":
            fmt_expr = pl.col(dc).dt.strftime("%Y-W%V")
        else:
            fmt_expr = pl.col(dc).dt.strftime("%Y-%m")

        res = (
            q.with_columns(fmt_expr.alias("__p__"))
            .group_by("__p__")
            .agg(pl.col(vc).sum().alias("v"))
            .sort("__p__")
            .collect()
        )

        vals = res["v"]
        if vals.dtype in (pl.Float32, pl.Float64):
            vals = vals.round(2)

        return {
            "labels":    res["__p__"].to_list(),
            "values":    vals.to_list(),
            "query_ms":  round((time.perf_counter() - t0) * 1e3, 1),
            "date_col":  dc,
            "value_col": vc,
        }

    # ── Data preview ─────────────────────────────────────────────────────────

    @app.get("/api/preview", summary="Paginated data preview")
    def get_preview(
        size:    int           = Query(200, ge=1, le=500),
        page:    int           = Query(1,   ge=1),
        filters: Optional[str] = Query(None),
    ):
        t0     = time.perf_counter()
        q      = _filtered_lf(engine, filters)
        offset = (page - 1) * size
        df     = q.slice(offset, size).collect()

        if filters:
            total = q.select(pl.len()).collect().item()
        else:
            total = engine.total_rows()

        return {
            "columns":  df.columns,
            "data":     df.to_dicts(),
            "total":    total,
            "query_ms": round((time.perf_counter() - t0) * 1e3, 1),
        }

    return app


# ── Background server ─────────────────────────────────────────────────────────

class _DashboardServer:
    """Runs uvicorn in a daemon thread (Jupyter / notebook-friendly)."""

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        self._config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(self._config)
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None


# ── Public class ──────────────────────────────────────────────────────────────

class TurboDashboard:
    """
    Lightweight analytics dashboard: Polars server-side aggregations + Chart.js.

    All aggregations run in Polars on the server; the browser receives only
    summary JSON payloads (< 2 KB per chart). Works for any dataset size.

    Parameters
    ----------
    source     : str | Path | pl.DataFrame | pl.LazyFrame
        Data source (same as TurboTable).
    title      : str
        Page title (HTML-escaped before rendering).
    chunk_size : int
        Retained for API compatibility; not used in v2.

    Examples
    --------
    >>> TurboDashboard("sales.parquet").show()
    >>> TurboDashboard(df, title="Sales Analytics").show()
    >>> dash = TurboDashboard("data.csv")
    >>> dash.show(blocking=False)
    >>> dash.stop()
    """

    def __init__(
        self,
        source:     Union[str, Path, "pl.DataFrame", "pl.LazyFrame"],
        title:      str = "TurboDashboard",
        chunk_size: int = _DEFAULT_CHUNK,
    ) -> None:
        self.title      = title
        self.chunk_size = chunk_size
        self.engine     = TurboEngine(source)
        self._server: Optional[_DashboardServer] = None
        self._app       = None

    def show(
        self,
        host:         str  = "127.0.0.1",
        port:         int  = 8766,
        open_browser: bool = True,
        blocking:     bool = True,
    ) -> None:
        """Start the dashboard server and open the browser."""
        self._app = create_dashboard_app(self.engine, self.title, self.chunk_size)
        display_host = "localhost" if host in ("0.0.0.0", "::") else host
        url = f"http://{display_host}:{port}"

        if blocking:
            if open_browser:
                def _open() -> None:
                    time.sleep(0.8)
                    webbrowser.open(url)
                threading.Thread(target=_open, daemon=True).start()

            print(f"\n  TurboDashboard ⚡  →  {url}")
            print(f"  Rows: {self.engine.total_rows():,}  |  Engine: Polars + Chart.js")
            print(f"  API docs  →  {url}/docs")
            print("  Press Ctrl-C to stop.\n")
            uvicorn.run(self._app, host=host, port=port, log_level="warning")
        else:
            self._server = _DashboardServer(self._app, host=host, port=port)
            self._server.start()
            time.sleep(0.6)
            if open_browser:
                webbrowser.open(url)
            print(f"\n  TurboDashboard ⚡  running  →  {url}\n")

    def stop(self) -> None:
        """Stop a background server started with ``blocking=False``."""
        if self._server:
            self._server.stop()
            self._server = None
            print("  TurboDashboard stopped.")
        else:
            print("  No background server is running.")

    def head(self, n: int = 10) -> "pl.DataFrame":
        return self.engine.sample(n)

    def schema(self) -> Dict[str, str]:
        return self.engine.schema

    def describe(self) -> "pl.DataFrame":
        return self.engine.describe()

    def __repr__(self) -> str:
        total = self.engine.total_rows()
        return (
            f"TurboDashboard(title={self.title!r}, rows={total:,}, "
            f"engine=Polars/{pl.__version__}+Chart.js)"
        )

    def __str__(self) -> str:
        return repr(self)
