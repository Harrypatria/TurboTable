"""
TurboDashboard — Perspective SPA HTML template.

Generates a self-contained single-page application that:
  1. Loads Apache Arrow IPC data from the FastAPI backend
  2. Renders it in a full-screen <perspective-viewer> web component
  3. Supports HTTP streaming (progress bar) and WebSocket chunked loading
  4. Provides the full Perspective plugin suite: Datagrid, XY Line, Bar,
     Scatter, Heatmap, Treemap — all switchable via the built-in toolbar

Security note
-------------
``title`` is HTML-escaped via ``html.escape()`` before injection.
All other injected values are Python integers, booleans, or
``json.dumps()``-encoded — injection-safe by construction.

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import html
import json
from typing import Dict

# ---------------------------------------------------------------------------
# Perspective CDN — pinned to 2.10.1 for API stability.
# To upgrade, change the version in all four URLs below consistently.
# The four packages that must be loaded together:
#   perspective          — core WASM engine + worker bridge
#   perspective-viewer   — <perspective-viewer> web component
#   perspective-viewer-datagrid — high-performance Hypergrid plugin
#   perspective-viewer-d3fc     — D3FC charting plugin
#                                  (bar, line, scatter, heatmap, treemap)
# ---------------------------------------------------------------------------
# 2.6.0 is pinned deliberately.
# Perspective 2.7+ bundled apache-arrow ≥13 which emits Utf8View (Arrow type 24)
# for string columns when serialising JS objects to send to the Web Worker.
# The WASM C++ Arrow decoder compiled into Perspective 2.7+ cannot read type 24
# and aborts with "Unrecognized type: 24".
# Perspective 2.6.0 used apache-arrow ≤12 which does NOT emit Utf8View, so the
# JS↔WASM Arrow round-trip is always compatible.
_PSP_VERSION = "2.6.0"
_CDN_BASE    = f"https://cdn.jsdelivr.net/npm/@finos"

_CDN = {
    "core":     f"{_CDN_BASE}/perspective@{_PSP_VERSION}/dist/cdn/perspective.js",
    "viewer":   f"{_CDN_BASE}/perspective-viewer@{_PSP_VERSION}/dist/cdn/perspective-viewer.js",
    "datagrid": f"{_CDN_BASE}/perspective-viewer-datagrid@{_PSP_VERSION}/dist/cdn/perspective-viewer-datagrid.js",
    "d3fc":     f"{_CDN_BASE}/perspective-viewer-d3fc@{_PSP_VERSION}/dist/cdn/perspective-viewer-d3fc.js",
}


def _polars_to_psp_type(dtype: str) -> str:
    """Map a Polars dtype string to a Perspective column type hint."""
    if any(t in dtype for t in ("Int", "UInt", "Float")):
        return "float"
    if "Datetime" in dtype or "Time" in dtype:
        return "datetime"
    if "Date" in dtype:
        return "date"
    if "Boolean" in dtype:
        return "boolean"
    return "string"


def build_perspective_html(
    title: str,
    schema: Dict[str, str],
    total_rows: int,
    chunk_size: int,
    use_websocket: bool = False,
) -> str:
    """
    Render the complete TurboDashboard single-page application.

    Parameters
    ----------
    title         : User-supplied page title (HTML-escaped before injection).
    schema        : ``{column_name: polars_dtype_string}`` from TurboEngine.
    total_rows    : Total row count (used for progress calculation).
    chunk_size    : Rows per WebSocket chunk (used for progress text).
    use_websocket : If True, use WebSocket chunked loading; else HTTP fetch.
    """
    # ── Security: escape user-controlled string values ──────────────────────
    safe_title = html.escape(title, quote=True)
    n_cols     = len(schema)   # plain int — safe

    # ── Column type hints for Perspective (optional, improves rendering) ────
    psp_schema = {col: _polars_to_psp_type(dtype) for col, dtype in schema.items()}

    # JSON-encode Python values injected into JavaScript (injection-safe)
    psp_schema_json    = json.dumps(psp_schema)
    total_rows_js      = int(total_rows)      # plain int literal
    chunk_size_js      = int(chunk_size)
    use_websocket_js   = "true" if use_websocket else "false"
    cdn_core           = html.escape(_CDN["core"])
    cdn_viewer         = html.escape(_CDN["viewer"])
    cdn_datagrid       = html.escape(_CDN["datagrid"])
    cdn_d3fc           = html.escape(_CDN["d3fc"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_title}</title>

  <!--
    Perspective {_PSP_VERSION} — MIT licence
    Core WASM + viewer web component + Datagrid + D3FC chart plugins
    All four packages must be loaded for full functionality.
  -->
  <script type="module" src="{cdn_viewer}"></script>
  <script type="module" src="{cdn_datagrid}"></script>
  <script type="module" src="{cdn_d3fc}"></script>

  <style>
    /* ── Reset ─────────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg-deep:   #0b1120;
      --bg-panel:  #111827;
      --bg-card:   #1e293b;
      --border:    #2d3f55;
      --accent:    #38bdf8;
      --accent-2:  #818cf8;
      --text:      #e2e8f0;
      --text-muted:#64748b;
      --green:     #34d399;
      --amber:     #fbbf24;
    }}

    html, body {{
      height: 100%;
      overflow: hidden;
      background: var(--bg-deep);
      color: var(--text);
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }}

    /* ── App shell ──────────────────────────────────────────────── */
    #app {{
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}

    /* ── Header ─────────────────────────────────────────────────── */
    #header {{
      background: linear-gradient(90deg, var(--bg-panel) 0%, var(--bg-deep) 100%);
      border-bottom: 1px solid var(--border);
      padding: 10px 18px;
      display: flex;
      align-items: center;
      gap: 14px;
      flex-shrink: 0;
      z-index: 10;
    }}
    #header h1 {{
      font-size: 1.1rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      white-space: nowrap;
    }}
    .badge {{
      background: #1a3050;
      color: #7dd3fc;
      font-size: 0.6rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 999px;
      letter-spacing: 0.7px;
      text-transform: uppercase;
      white-space: nowrap;
      border: 1px solid #1e4070;
    }}
    .hdr-stats {{
      margin-left: auto;
      display: flex;
      gap: 18px;
      font-size: 0.74rem;
      color: var(--text-muted);
    }}
    .hdr-stats span b {{ color: var(--accent); font-weight: 600; }}
    .hdr-stats .status-dot {{
      display: inline-block;
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--amber);
      margin-right: 4px;
      vertical-align: middle;
      transition: background 0.4s;
    }}
    .hdr-stats .status-dot.ready {{ background: var(--green); }}

    /* ── Viewer container ────────────────────────────────────────── */
    #viewer-wrap {{
      flex: 1;
      position: relative;
      min-height: 0;
      overflow: hidden;
    }}
    perspective-viewer {{
      width: 100%;
      height: 100%;
      --psp-font-size: 13px;
    }}

    /* ── Loading overlay ─────────────────────────────────────────── */
    #overlay {{
      position: absolute;
      inset: 0;
      background: rgba(11, 17, 32, 0.96);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 18px;
      z-index: 50;
      transition: opacity 0.4s ease;
    }}
    #overlay.hidden {{
      opacity: 0;
      pointer-events: none;
    }}

    .spinner {{
      width: 40px;
      height: 40px;
      border: 3px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

    #overlay-title {{
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
    }}
    #overlay-status {{
      font-size: 0.78rem;
      color: var(--text-muted);
      text-align: center;
      max-width: 380px;
      line-height: 1.5;
    }}

    .progress-track {{
      width: 360px;
      height: 5px;
      background: var(--bg-card);
      border-radius: 999px;
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
      border-radius: 999px;
      width: 0%;
      transition: width 0.25s ease;
    }}
    #progress-pct {{
      font-size: 0.72rem;
      color: var(--text-muted);
      font-variant-numeric: tabular-nums;
    }}

    /* ── Error banner ────────────────────────────────────────────── */
    #error-banner {{
      display: none;
      position: fixed;
      bottom: 16px;
      left: 50%;
      transform: translateX(-50%);
      background: #450a0a;
      border: 1px solid #7f1d1d;
      color: #fca5a5;
      font-size: 0.78rem;
      padding: 8px 16px;
      border-radius: 6px;
      z-index: 100;
      max-width: 600px;
      text-align: center;
    }}
  </style>
</head>
<body>

<div id="app">

  <!-- ── Header ──────────────────────────────────────────────────── -->
  <div id="header">
    <h1>⚡ {safe_title}</h1>
    <span class="badge">Polars · Arrow · Perspective</span>
    <div class="hdr-stats">
      <span>Rows: <b id="hdr-rows">—</b></span>
      <span>Cols: <b id="hdr-cols">{n_cols}</b></span>
      <span>
        <span class="status-dot" id="status-dot"></span>
        <span id="hdr-status">Loading…</span>
      </span>
    </div>
  </div>

  <!-- ── Perspective viewer ───────────────────────────────────────── -->
  <div id="viewer-wrap">
    <perspective-viewer id="viewer" theme="Material Dark"></perspective-viewer>

    <!-- Loading overlay (removed after data is in Perspective) -->
    <div id="overlay">
      <div class="spinner"></div>
      <div id="overlay-title">TurboDashboard</div>
      <div id="overlay-status">Initialising Perspective WASM…</div>
      <div class="progress-track">
        <div class="progress-fill" id="progress-fill"></div>
      </div>
      <div id="progress-pct">0 %</div>
    </div>
  </div>
</div>

<!-- Error banner -->
<div id="error-banner"></div>

<script type="module">
"use strict";

// ── Server-injected constants ────────────────────────────────────────────────
const TOTAL_ROWS   = {total_rows_js};
const CHUNK_SIZE   = {chunk_size_js};
const USE_WS       = {use_websocket_js};
const PSP_SCHEMA   = {psp_schema_json};  // column → perspective type hints

// ── DOM refs ─────────────────────────────────────────────────────────────────
const viewer     = document.getElementById("viewer");
const overlay    = document.getElementById("overlay");
const hdrRows    = document.getElementById("hdr-rows");
const hdrStatus  = document.getElementById("hdr-status");
const statusDot  = document.getElementById("status-dot");
const fill       = document.getElementById("progress-fill");
const pct        = document.getElementById("progress-pct");
const statusTxt  = document.getElementById("overlay-status");
const errBanner  = document.getElementById("error-banner");

// ── UI helpers ────────────────────────────────────────────────────────────────
function setProgress(fraction, statusText) {{
  const p = Math.min(100, Math.round(fraction * 100));
  fill.style.width = p + "%";
  pct.textContent  = p + " %";
  if (statusText) statusTxt.textContent = statusText;
}}

function setReady(rows) {{
  hdrRows.textContent = rows.toLocaleString();
  hdrStatus.textContent = "Ready";
  statusDot.classList.add("ready");
  overlay.classList.add("hidden");
  setTimeout(() => {{ overlay.style.display = "none"; }}, 450);
}}

function showError(msg) {{
  errBanner.textContent = "⚠ " + msg;
  errBanner.style.display = "block";
  statusTxt.textContent = "Error — see banner below";
  console.error("[TurboDashboard]", msg);
}}

// ── Perspective initialisation ────────────────────────────────────────────────
import perspective from "{cdn_core}";

// perspective.worker() returns a proxy immediately; the WASM initialises
// asynchronously inside the spawned Worker thread.
const worker = perspective.worker();

async function configureViewer(table) {{
  await viewer.load(table);
  // Default view: Datagrid, settings panel closed.
  // The user can switch plugins via the built-in toolbar.
  await viewer.restore({{
    plugin:   "Datagrid",
    settings: false,
  }});
}}

// ── CSV header stripper ───────────────────────────────────────────────────────
// Used when calling table.update() with a CSV string that already has a header
// row from a previous worker.table() call.  Strips the first line so
// Perspective does not interpret the column names as a data row.
function stripCsvHeader(csv) {{
  const nl = csv.indexOf("\n");
  return nl >= 0 ? csv.slice(nl + 1) : csv;
}}

// ── HTTP loading mode (for datasets ≤ 500 000 rows) ──────────────────────────
// Fetches a CSV string from /api/data and passes it AS A STRING to
// worker.table().
//
// Critical design note — why we pass a STRING, not a JS object
// -------------------------------------------------------------
// Any JS object (column-oriented dict, row-oriented array, schema dict) passed
// to worker.table() is re-encoded to Arrow by Perspective's bundled
// apache-arrow JS library before being sent to the Web Worker.
// In apache-arrow ≥13 (used by Perspective 2.7+) this encoding uses Utf8View
// (Arrow type 24) for strings.  The WASM C++ decoder can't read type 24 and
// aborts with "Unrecognized type: 24".
//
// Passing a plain STRING bypasses the Arrow encoder entirely: the string is
// sent via postMessage as-is, and the WASM's built-in C++ CSV parser reads it
// directly — no Arrow type mismatch possible.
//
// We pin Perspective to 2.6.0 (apache-arrow ≤12, pre-Utf8View) as an extra
// layer of protection.
async function loadViaHTTP() {{
  setProgress(0, "Requesting data from server…");

  const resp = await fetch("/api/data", {{ cache: "no-store" }});
  if (!resp.ok) throw new Error(`HTTP ${{resp.status}} ${{resp.statusText}}`);

  const contentLength = parseInt(resp.headers.get("Content-Length") || "0");
  const reader = resp.body.getReader();
  const chunks = [];
  let received = 0;

  while (true) {{
    const {{ done, value }} = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    if (contentLength > 0) {{
      const frac = received / contentLength;
      const mb   = (received / 1e6).toFixed(1);
      const tot  = (contentLength / 1e6).toFixed(1);
      setProgress(frac, `Downloading data — ${{mb}} / ${{tot}} MB`);
    }} else {{
      const mb = (received / 1e6).toFixed(1);
      setProgress(0.5, `Downloading data — ${{mb}} MB received…`);
    }}
  }}

  setProgress(0.9, "Loading into Perspective…");

  // Decode bytes → UTF-8 string.  Pass the CSV string directly to
  // worker.table() — Perspective detects it as CSV (because it is a string,
  // not a binary buffer or plain object) and routes it to the C++ CSV parser,
  // completely bypassing the JS Arrow encoder.
  const totalBytes = chunks.reduce((s, c) => s + c.length, 0);
  const merged = new Uint8Array(totalBytes);
  let pos = 0;
  for (const ch of chunks) {{ merged.set(ch, pos); pos += ch.length; }}
  const csvData = new TextDecoder().decode(merged);

  hdrRows.textContent = TOTAL_ROWS.toLocaleString();
  const table = await worker.table(csvData);   // string → CSV path, no Arrow
  await configureViewer(table);
  setReady(TOTAL_ROWS);
}}

// ── WebSocket streaming mode (for large datasets > 500 000 rows) ──────────────
// All messages are JSON text.  Each "chunk" message carries a CSV string in
// msg.data.  The first chunk creates the table via worker.table(csvString)
// (string → CSV path, no Arrow encoding).  Subsequent chunks use
// table.update(csvNoHeader) — also plain string, no Arrow encoding.
async function loadViaWebSocket() {{
  return new Promise((resolve, reject) => {{
    const ws = new WebSocket(`ws://${{location.host}}/ws`);

    let table   = null;
    let total   = TOTAL_ROWS;
    let nChunks = Math.ceil(TOTAL_ROWS / CHUNK_SIZE);

    ws.onmessage = async (event) => {{
      try {{
        const msg = JSON.parse(event.data);

        if (msg.type === "chunk") {{
          // ── Data chunk: CSV string (with header row) ───────────────────
          // First chunk: worker.table(csvString) — string bypasses Arrow encoder.
          // Subsequent: table.update(csvNoHeader) — also a string.
          if (table === null) {{
            table = await worker.table(msg.data);  // CSV string, no Arrow
            await configureViewer(table);
            hdrRows.textContent = TOTAL_ROWS.toLocaleString();
          }} else {{
            await table.update(stripCsvHeader(msg.data));
          }}

        }} else if (msg.type === "meta") {{
          total   = msg.total;
          nChunks = msg.chunks;
          hdrRows.textContent = total.toLocaleString();
          setProgress(0, `Streaming ${{total.toLocaleString()}} rows in ${{nChunks}} chunks…`);

        }} else if (msg.type === "progress") {{
          const frac = msg.rows_loaded / total;
          setProgress(
            frac,
            `${{msg.rows_loaded.toLocaleString()}} / ${{total.toLocaleString()}} rows`
            + ` (chunk ${{msg.chunk}} / ${{msg.total_chunks}})`
          );

        }} else if (msg.type === "complete") {{
          ws.close();
          setReady(msg.total);
          resolve(table);

        }} else if (msg.type === "error") {{
          ws.close();
          reject(new Error(msg.message));
        }}

      }} catch (err) {{
        ws.close();
        reject(err);
      }}
    }};

    ws.onerror = () => reject(new Error("WebSocket connection failed"));
    ws.onclose = (e) => {{
      if (!e.wasClean && table === null) {{
        reject(new Error("WebSocket closed unexpectedly before data arrived"));
      }}
    }};

    setProgress(0, "Connecting to server…");
  }});
}}

// ── Entry point ───────────────────────────────────────────────────────────────
(async function main() {{
  try {{
    if (USE_WS) {{
      await loadViaWebSocket();
    }} else {{
      await loadViaHTTP();
    }}
  }} catch (err) {{
    showError(err.message);
  }}
}})();
</script>
</body>
</html>"""
