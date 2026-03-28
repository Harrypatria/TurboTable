"""
TurboTable UI — self-contained HTML/JS single-page application.

Uses Tabulator 6 (MIT licence) loaded from a pinned unpkg CDN URL.
No npm, no build step — the entire UI is a Python string rendered by FastAPI.

Security note
-------------
All Python values injected into HTML are either:
  - HTML-escaped via ``html.escape()`` (title)
  - JSON-encoded via ``json.dumps()`` (column definitions — already safe)
  - Plain integers (len(schema) — no escaping needed)

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import html
import json
from typing import Dict, List

# ---------------------------------------------------------------------------
# Polars dtype string → Tabulator filter editor type
# ---------------------------------------------------------------------------
_NUMERIC_POLARS: frozenset = frozenset({
    "Int8", "Int16", "Int32", "Int64",
    "UInt8", "UInt16", "UInt32", "UInt64",
    "Float32", "Float64",
})

_POLARS_TO_TABULATOR: Dict[str, str] = {
    **{k: "number"    for k in _NUMERIC_POLARS},
    "Boolean":        "tickCross",
    "Date":           "date",
    "Datetime":       "input",   # Tabulator's datetime filter needs a format string; use text
}


def _tab_col_def(name: str, dtype: str) -> Dict:
    """Build one Tabulator column definition dict from a column name and dtype."""
    tab_type = _POLARS_TO_TABULATOR.get(dtype, "input")
    col: Dict = {
        "title":        name.replace("_", " ").title(),
        "field":        name,
        "headerFilter": tab_type,
        "sorter":       "number" if dtype in _NUMERIC_POLARS else "string",
        "resizable":    True,
        "minWidth":     80,
        "tooltip":      True,
    }
    if dtype in _NUMERIC_POLARS:
        col["hozAlign"] = "right"
    return col


def _string_columns(schema: Dict[str, str]) -> List[str]:
    """Return column names that are searchable as plain text."""
    non_text = _NUMERIC_POLARS | {"Boolean", "Date", "Datetime"}
    return [c for c, d in schema.items() if d not in non_text]


def build_html(title: str, schema: Dict[str, str]) -> str:
    """
    Render the complete TurboTable single-page application as an HTML string.

    Parameters
    ----------
    title  : arbitrary user-supplied string — HTML-escaped before injection.
    schema : ``{column_name: dtype_string}`` from TurboEngine.
    """
    # --- Security: escape user-controlled values before HTML injection ------
    safe_title = html.escape(title, quote=True)

    # Column defs and string-column list are JSON-encoded → injection-safe
    col_defs_json   = json.dumps([_tab_col_def(n, d) for n, d in schema.items()], indent=2)
    str_cols_json   = json.dumps(_string_columns(schema))
    n_cols          = len(schema)   # plain int — safe

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_title}</title>

  <!-- Tabulator 6.2.1 (MIT) — pinned CDN, SRI hash omitted for brevity -->
  <link  href="https://unpkg.com/tabulator-tables@6.2.1/dist/css/tabulator.min.css" rel="stylesheet" />
  <script src="https://unpkg.com/tabulator-tables@6.2.1/dist/js/tabulator.min.js"></script>

  <style>
    /* ── Reset & base ───────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}

    /* ── Header ─────────────────────────────────────────────────── */
    header {{
      background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
      border-bottom: 1px solid #334155;
      padding: 12px 20px;
      display: flex;
      align-items: center;
      gap: 14px;
      flex-shrink: 0;
    }}
    header h1 {{
      font-size: 1.2rem;
      font-weight: 700;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      white-space: nowrap;
    }}
    .badge {{
      background: #1e3a5f;
      color: #7dd3fc;
      font-size: 0.62rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 999px;
      letter-spacing: 0.6px;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .hdr-meta {{
      margin-left: auto;
      display: flex;
      gap: 18px;
      font-size: 0.76rem;
      color: #64748b;
      white-space: nowrap;
    }}
    .hdr-meta span b {{ color: #38bdf8; font-weight: 600; }}

    /* ── Toolbar ─────────────────────────────────────────────────── */
    .toolbar {{
      padding: 8px 20px;
      background: #1e293b;
      border-bottom: 1px solid #334155;
      display: flex;
      gap: 8px;
      align-items: center;
      flex-shrink: 0;
      flex-wrap: wrap;
    }}
    .toolbar input[type="text"] {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 6px;
      color: #e2e8f0;
      padding: 5px 12px;
      font-size: 0.82rem;
      width: 230px;
      transition: border-color 0.15s;
    }}
    .toolbar input[type="text"]:focus {{
      outline: none;
      border-color: #38bdf8;
    }}
    .btn {{
      background: #1e3a5f;
      border: 1px solid #1e40af;
      border-radius: 6px;
      color: #93c5fd;
      cursor: pointer;
      font-size: 0.78rem;
      font-weight: 600;
      padding: 5px 13px;
      transition: background 0.15s, border-color 0.15s;
      white-space: nowrap;
    }}
    .btn:hover {{ background: #1e40af; border-color: #3b82f6; color: #bfdbfe; }}
    .btn.green  {{ background: #14432d; border-color: #166534; color: #86efac; }}
    .btn.green:hover {{ background: #166534; }}
    .btn.red    {{ background: #4c1d1d; border-color: #7f1d1d; color: #fca5a5; }}
    .btn.red:hover {{ background: #7f1d1d; }}

    /* ── Table wrapper ───────────────────────────────────────────── */
    #table-wrap {{
      flex: 1;
      overflow: hidden;
      padding: 10px 20px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-height: 0;
    }}
    #turbotable {{
      flex: 1;
      border-radius: 8px;
      overflow: hidden;
      min-height: 0;
    }}

    /* ── Tabulator dark-theme overrides ─────────────────────────── */
    .tabulator {{
      background: #1e293b !important;
      border: 1px solid #334155 !important;
      font-size: 0.79rem;
    }}
    .tabulator .tabulator-header {{
      background: #0f172a !important;
      border-bottom: 2px solid #1e40af !important;
      color: #7dd3fc;
      font-weight: 700;
      text-transform: uppercase;
      font-size: 0.68rem;
      letter-spacing: 0.6px;
    }}
    .tabulator .tabulator-header .tabulator-col {{
      background: #0f172a !important;
      border-right: 1px solid #1e293b !important;
    }}
    .tabulator .tabulator-header .tabulator-col.tabulator-sortable:hover {{
      background: #1e293b !important;
    }}
    .tabulator .tabulator-header .tabulator-col.tabulator-col-sorter-element:focus {{
      outline: 2px solid #38bdf8;
      outline-offset: -2px;
    }}
    .tabulator-row {{
      background: #1e293b !important;
      border-bottom: 1px solid #0f172a !important;
      color: #cbd5e1;
    }}
    .tabulator-row:hover {{ background: #263548 !important; }}
    .tabulator-row.tabulator-row-even {{ background: #172033 !important; }}
    .tabulator-row.tabulator-row-even:hover {{ background: #1e2f48 !important; }}
    .tabulator-cell {{
      border-right: 1px solid #1a2740 !important;
      padding: 5px 10px !important;
    }}
    .tabulator-footer {{
      background: #0f172a !important;
      border-top: 1px solid #334155 !important;
      color: #64748b;
      font-size: 0.73rem;
    }}
    .tabulator-footer .tabulator-page {{
      background: #1e293b;
      border: 1px solid #334155;
      color: #94a3b8;
      border-radius: 4px;
      padding: 2px 8px;
      margin: 0 2px;
      cursor: pointer;
      transition: background 0.12s;
    }}
    .tabulator-footer .tabulator-page.active {{
      background: #1e40af;
      color: #bfdbfe;
      border-color: #1e40af;
    }}
    .tabulator-footer .tabulator-page:hover:not(.active) {{
      background: #263548;
    }}
    .tabulator-header-filter input,
    .tabulator-header-filter select {{
      background: #0f172a !important;
      border: 1px solid #334155 !important;
      color: #e2e8f0 !important;
      border-radius: 4px;
      font-size: 0.72rem;
      padding: 2px 6px;
    }}

    /* ── Status bar ─────────────────────────────────────────────── */
    #status {{
      font-size: 0.7rem;
      color: #475569;
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .pill {{
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 4px;
      padding: 1px 9px;
      color: #64748b;
    }}
    .pill b {{ color: #38bdf8; font-weight: 600; }}
    .pill.warn {{ border-color: #78350f; color: #fbbf24; }}

    /* ── Stats modal ─────────────────────────────────────────────── */
    dialog {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      color: #e2e8f0;
      padding: 24px;
      max-width: 560px;
      width: 90vw;
      max-height: 80vh;
      overflow-y: auto;
    }}
    dialog h2 {{
      font-size: 0.95rem;
      margin-bottom: 12px;
      color: #7dd3fc;
    }}
    dialog pre {{
      font-size: 0.72rem;
      white-space: pre-wrap;
      color: #94a3b8;
      line-height: 1.6;
    }}
    dialog::backdrop {{ background: rgba(0,0,0,0.55); }}
  </style>
</head>
<body>

<!-- ── Header ─────────────────────────────────────────────────── -->
<header>
  <h1>⚡ {safe_title}</h1>
  <span class="badge">Polars · FastAPI</span>
  <div class="hdr-meta">
    <span>Rows: <b id="hdr-total">…</b></span>
    <span>Cols: <b id="hdr-cols">{n_cols}</b></span>
    <span>Page: <b id="hdr-page">1</b></span>
    <span>Query: <b id="hdr-ms">—</b></span>
  </div>
</header>

<!-- ── Toolbar ────────────────────────────────────────────────── -->
<div class="toolbar">
  <input type="text" id="global-search"
         placeholder="🔍 Search all text columns…"
         aria-label="Global search" />
  <button class="btn red"   onclick="clearAll()">✕ Clear</button>
  <button class="btn green" onclick="table.download('csv',  'turbotable_export.csv')">↓ CSV</button>
  <button class="btn green" onclick="table.download('json', 'turbotable_export.json')">↓ JSON</button>
  <button class="btn"       onclick="openStats()">📊 Stats</button>
  <button class="btn"       onclick="window.open('/docs','_blank')">📖 API</button>
</div>

<!-- ── Table ──────────────────────────────────────────────────── -->
<div id="table-wrap">
  <div id="turbotable" role="grid" aria-label="Data table"></div>
  <div id="status" aria-live="polite">Loading…</div>
</div>

<!-- ── Stats modal ────────────────────────────────────────────── -->
<dialog id="stats-modal" aria-labelledby="stats-title">
  <h2 id="stats-title">📊 Dataset Statistics</h2>
  <pre id="stats-content"></pre>
  <button class="btn" style="margin-top:14px"
          onclick="document.getElementById('stats-modal').close()">Close</button>
</dialog>

<script>
"use strict";

// ── Server-injected constants ────────────────────────────────────────────
const COL_DEFS   = {col_defs_json};
const STR_COLS   = {str_cols_json};   // string-like columns for global search

// ── Timing state ─────────────────────────────────────────────────────────
let _t0 = 0;

// ── Custom AJAX function ─────────────────────────────────────────────────
// Tabulator calls this instead of its built-in fetcher so we can:
//  1. Build the correct query string (incl. sort_dir, q)
//  2. Measure round-trip latency
function turboAjax(url, config, params) {{
  _t0 = performance.now();
  const qs = new URLSearchParams();

  qs.set("page", params.page  ?? 1);
  qs.set("size", params.size  ?? 100);

  if (params.sorters && params.sorters.length > 0) {{
    const s = params.sorters[0];
    qs.set("sort",     s.field);
    qs.set("sort_dir", s.dir);
  }}

  // Column-specific header filters (AND semantics — server honours this)
  const colFilters = [];
  if (params.filters) {{
    params.filters.forEach(f => {{
      if (f.value !== "" && f.value !== null && f.value !== undefined) {{
        colFilters.push({{ field: f.field, type: f.type, value: f.value }});
      }}
    }});
  }}
  if (colFilters.length > 0) {{
    qs.set("filters", JSON.stringify(colFilters));
  }}

  // Global search — sent as a separate ?q= param (OR across string columns)
  const q = document.getElementById("global-search").value.trim();
  if (q) qs.set("q", q);

  return fetch(`/api/data?${{qs.toString()}}`)
    .then(res => {{
      if (!res.ok) {{
        return res.json().catch(() => ({{}})).then(body => {{
          throw new Error(`Server error ${{res.status}}: ${{body.detail ?? res.statusText}}`);
        }});
      }}
      return res.json();
    }})
    .then(data => {{
      const ms = (performance.now() - _t0).toFixed(1);
      document.getElementById("hdr-ms").textContent    = ms + " ms";
      document.getElementById("hdr-total").textContent = data.total.toLocaleString();
      document.getElementById("hdr-page").textContent  = data.page;
      updateStatus(data, ms);
      return data;
    }})
    .catch(err => {{
      updateStatusError(err.message);
      throw err;   // re-throw so Tabulator shows its placeholder
    }});
}}

// ── Tabulator init ────────────────────────────────────────────────────────
const table = new Tabulator("#turbotable", {{
  ajaxRequestFunc:      turboAjax,
  ajaxURL:              "/api/data",
  pagination:           true,
  paginationMode:       "remote",
  sortMode:             "remote",
  filterMode:           "remote",
  paginationSize:       100,
  paginationSizeSelector: [50, 100, 250, 500],
  layout:               "fitDataFill",
  virtualDom:           true,
  columns:              COL_DEFS,
  placeholder:          "No rows match the current filters.",
  movableColumns:       true,
  responsiveLayout:     false,
}});

// ── Global search (debounced, 350 ms) ────────────────────────────────────
let _searchTimer;
document.getElementById("global-search").addEventListener("input", () => {{
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => table.setPage(1), 350);
}});

// ── Toolbar helpers ───────────────────────────────────────────────────────
function clearAll() {{
  document.getElementById("global-search").value = "";
  table.clearHeaderFilter();
  table.setPage(1);
}}

function openStats() {{
  document.getElementById("stats-content").textContent = "Loading…";
  document.getElementById("stats-modal").showModal();
  fetch("/api/stats")
    .then(r => r.json())
    .then(data => {{
      document.getElementById("stats-content").textContent =
        JSON.stringify(data, null, 2);
    }})
    .catch(err => {{
      document.getElementById("stats-content").textContent = "Error: " + err.message;
    }});
}}

// ── Status bar ─────────────────────────────────────────────────────────────
function updateStatus(data, ms) {{
  const el      = document.getElementById("status");
  const showing = Math.min(data.size, data.total - (data.page - 1) * data.size);
  const from    = ((data.page - 1) * data.size + 1).toLocaleString();
  const to      = ((data.page - 1) * data.size + showing).toLocaleString();
  el.innerHTML  =
    `<span class="pill">Rows <b>${{from}}–${{to}}</b> of <b>${{data.total.toLocaleString()}}</b></span>` +
    `<span class="pill">Page <b>${{data.page}}</b> / <b>${{data.last_page}}</b></span>` +
    `<span class="pill">Query <b>${{ms}} ms</b></span>`;
}}

function updateStatusError(msg) {{
  const el = document.getElementById("status");
  el.innerHTML = `<span class="pill warn">⚠ ${{msg}}</span>`;
}}
</script>
</body>
</html>"""
