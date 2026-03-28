# ⚡ TurboTable

> **Blazing-fast interactive data tables and dashboards for millions of rows.**
> Powered by [Polars](https://pola.rs/) · [FastAPI](https://fastapi.tiangolo.com/) · [Tabulator 6](https://tabulator.info/) · [Perspective WASM](https://perspective.finos.org/)

[![Tests](https://github.com/harrypatria/TurboTable/actions/workflows/test.yml/badge.svg)](https://github.com/harrypatria/TurboTable/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-brightgreen.svg)](CHANGELOG.md)
[![Polars](https://img.shields.io/badge/engine-Polars-CD8B2A.svg)](https://pola.rs/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

---

## Two Tools, One Package

| | **TurboTable** | **TurboDashboard** |
|---|---|---|
| **Best for** | Unlimited rows, server-side ops | Pivot tables, charts, heatmaps |
| **Row limit** | Unlimited (lazy Parquet/CSV) | Browser RAM (~50 M rows) |
| **Operations** | Server-side (Polars) | Client-side (C++/WASM) |
| **After load** | Every filter = server round-trip | All ops instant, zero round-trips |
| **UI** | Tabulator 6 data grid | Perspective Hypergrid + D3FC charts |
| **Port** | 8765 | 8766 |

```python
from turbotable import TurboTable, TurboDashboard

TurboTable("data.parquet").show()       # → http://localhost:8765
TurboDashboard("data.parquet").show()   # → http://localhost:8766
```

---

## Installation

### From GitHub
```bash
pip install git+https://github.com/harrypatria/TurboTable.git
```

### Local editable install (for development)
```bash
git clone https://github.com/harrypatria/TurboTable.git
cd TurboTable
pip install -e ".[dev,demo]"
```

### Core dependencies only
```bash
pip install polars fastapi "uvicorn[standard]"
```

---

## TurboTable — Server-Side Data Grid

Turns any CSV, Parquet, or Polars DataFrame into a live browser table with server-side
pagination, sorting, filtering, and full-text search. The browser only ever receives
the rows on screen — 10-million-row datasets load in milliseconds.

### Quick Start

```python
from turbotable import TurboTable

# From a file
TurboTable("sales.parquet").show()
TurboTable("data.csv", title="My CSV").show()

# From a Polars DataFrame
import polars as pl
df = pl.read_parquet("data.parquet").filter(pl.col("revenue") > 1_000)
TurboTable(df, title="High Revenue").show()

# Jupyter / non-blocking
tt = TurboTable("data.parquet")
tt.show(blocking=False)       # returns immediately
# ... work in other cells ...
tt.stop()

# LAN access
TurboTable("data.csv").show(host="0.0.0.0", port=9000)
```

### Running the 1-Million-Row Demo

```bash
cd demo

# Step 1 — generate synthetic sales data
python generate_data.py

# Step 2 — launch TurboTable
python demo_app.py
```

Open **http://localhost:8765** in your browser.

```bash
# Smaller dataset for faster generation
python generate_data.py --rows 100000
```

### Key Features

| Feature | Detail |
|---|---|
| **10M+ rows** | Polars lazy evaluation — data stays on disk until sliced |
| **Server-side ops** | Filter, sort, paginate — all inside Polars |
| **Global search** | `?q=` searches across all text columns (OR semantics) |
| **Apache Arrow** | `/api/data/arrow` binary transport endpoint |
| **Self-contained UI** | Dark-themed Tabulator 6 SPA — no npm, no build step |
| **Export** | Download filtered/sorted view as CSV or JSON |
| **Stats panel** | Per-column min/max/mean/unique + full `describe()` |
| **Jupyter-friendly** | `blocking=False` runs in a daemon thread |
| **XSS-safe** | All user-supplied values HTML-escaped before rendering |

### REST API Reference

Interactive docs at **`http://localhost:8765/docs`**.

#### `GET /api/data`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | `1` | 1-based page number |
| `size` | int | `100` | Rows per page (max 10 000) |
| `sort` | str | — | Column name to sort by |
| `sort_dir` | str | `"asc"` | `asc` or `desc` |
| `filters` | str | — | JSON array of `{field, type, value}` dicts |
| `q` | str | — | Global search across all string columns |

**Filter operators:** `=` `!=` `contains` `like` `starts` `ends` `>` `>=` `<` `<=`

**Example:**
```
GET /api/data?page=1&size=50&sort=revenue&sort_dir=desc
             &filters=[{"field":"region","type":"=","value":"North"}]
             &q=Alice
```

**Response:**
```json
{
  "data":      [...],
  "total":     42518,
  "page":      1,
  "size":      50,
  "last_page": 851
}
```

#### Other endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Interactive Tabulator UI (HTML) |
| `GET /api/schema` | Column name → dtype mapping |
| `GET /api/sample?n=5` | First N rows, no filtering |
| `GET /api/data/arrow` | Same as `/api/data` but Apache Arrow IPC bytes |
| `GET /api/stats` | Dataset-wide `describe()` statistics |
| `GET /api/stats/{column}` | Per-column lazy statistics |

### Python API — `TurboTable`

```python
TurboTable(source, title="TurboTable")
```

| Parameter | Type | Description |
|---|---|---|
| `source` | `str \| Path \| pl.DataFrame \| pl.LazyFrame` | Data source |
| `title` | `str` | Browser tab title (HTML-escaped) |

| Method | Returns | Description |
|---|---|---|
| `.show(host, port, open_browser, blocking)` | `None` | Start the web server |
| `.stop()` | `None` | Stop background server |
| `.head(n=10)` | `pl.DataFrame` | First *n* rows |
| `.schema()` | `dict` | Column → dtype mapping |
| `.describe()` | `pl.DataFrame` | Descriptive statistics |
| `.columns` | `list` | Column names |

---

## TurboDashboard — Client-Side Pivot & Charts

Loads all data once via Apache Arrow, then all pivoting, filtering, and charting
runs inside Perspective's C++/WASM engine in the browser — zero server round-trips.

### Quick Start

```python
from turbotable import TurboDashboard

# From a file
TurboDashboard("sales.parquet").show()
TurboDashboard("data.csv", title="KPI Dashboard").show()

# From a Polars DataFrame
import polars as pl
df = pl.read_parquet("data.parquet")
TurboDashboard(df, title="Sales Analytics").show()

# Jupyter / non-blocking
dash = TurboDashboard("data.parquet")
dash.show(blocking=False)
# ... work in other cells ...
dash.stop()

# Large dataset — tune chunk size for WebSocket streaming
TurboDashboard("big.parquet", chunk_size=100_000).show()
```

### Running the Dashboard Demo

```bash
cd demo

# Step 1 — generate data (skip if already done)
python generate_data.py

# Step 2 — launch TurboDashboard
python dashboard_app.py
```

Open **http://localhost:8766** in your browser.

```bash
# CLI options
python dashboard_app.py --source data/sales_1m.parquet
python dashboard_app.py --rows 500000 --chunk 100000
python dashboard_app.py --host 0.0.0.0 --port 9000
```

### What You Can Do in the Browser

- Switch between plugins via the toolbar: **Datagrid · X/Y Line · Y Bar · X Bar · Scatter · Heatmap · Treemap**
- Drag columns to the **Row / Column / Filter / Sort** pivot areas
- Use the built-in filter builder for complex expressions
- All operations run at native C++ speed — no server round-trips after load

### Loading Modes

TurboDashboard automatically selects the best loading strategy:

| Dataset size | Mode | How it works |
|---|---|---|
| ≤ 500 000 rows | **HTTP** | Single Arrow IPC file with `Content-Length` progress bar |
| > 500 000 rows | **WebSocket** | Progressive chunk-by-chunk streaming; grid renders as data arrives |

### REST API Reference

Interactive docs at **`http://localhost:8766/docs`**.

| Endpoint | Description |
|---|---|
| `GET /` | Perspective SPA (full-screen) |
| `GET /api/meta` | Dataset metadata: rows, schema, mode, chunk size |
| `GET /api/arrow` | Full dataset as Apache Arrow IPC file (HTTP mode) |
| `WS /ws` | Chunked Arrow IPC stream (WebSocket mode) |

#### WebSocket Protocol

```
S→C  JSON   {"type": "meta",     "total": N, "chunk_size": K, "chunks": C}
S→C  BINARY Arrow IPC file bytes  (chunk 1)
S→C  JSON   {"type": "progress", "chunk": 1, "total_chunks": C, "rows_loaded": K}
...
S→C  BINARY Arrow IPC file bytes  (chunk C)
S→C  JSON   {"type": "progress", "chunk": C, "total_chunks": C, "rows_loaded": N}
S→C  JSON   {"type": "complete",  "total": N}
```

### Python API — `TurboDashboard`

```python
TurboDashboard(source, title="TurboDashboard", chunk_size=50_000)
```

| Parameter | Type | Description |
|---|---|---|
| `source` | `str \| Path \| pl.DataFrame \| pl.LazyFrame` | Data source |
| `title` | `str` | Browser tab title (HTML-escaped) |
| `chunk_size` | `int` | Rows per WebSocket chunk (default 50 000) |

| Method | Returns | Description |
|---|---|---|
| `.show(host, port, open_browser, blocking)` | `None` | Start the dashboard server |
| `.stop()` | `None` | Stop background server |
| `.head(n=10)` | `pl.DataFrame` | First *n* rows |
| `.schema()` | `dict` | Column → dtype mapping |
| `.describe()` | `pl.DataFrame` | Descriptive statistics |

---

## Architecture

### TurboTable

```
Browser (Tabulator 6 SPA)
   │  AJAX  ?page=1&size=100&sort=revenue&sort_dir=desc&q=Alice
   ▼
FastAPI  GET /api/data
   │
   ▼
TurboEngine.get_view(start, size, sort_col, sort_desc, filters, search)
   │  .filter(AND chain for column filters)
   │  .filter(pl.any_horizontal OR for ?q= global search)
   │  .sort()  .slice(start, size)  .collect()
   ▼
CSV / Parquet / DataFrame on disk or in memory
```

### TurboDashboard

```
Browser (Perspective WASM)
   │  HTTP GET /api/arrow  OR  WebSocket /ws
   ▼
FastAPI
   │  asyncio.to_thread() → blocking Polars .collect()
   │  df.write_ipc() → Arrow IPC bytes (zero-copy columnar)
   ▼
Polars LazyFrame (CSV / Parquet / DataFrame)
```

---

## Running the Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run the full test suite (111 tests)
pytest tests/ -v

# Run individual test files
pytest tests/test_engine.py    # 50 engine unit tests
pytest tests/test_server.py    # 30 server integration tests
pytest tests/test_dashboard.py # 31 dashboard tests
```

---

## Project Structure

```
TurboTable/
├── turbotable/
│   ├── __init__.py          TurboTable + TurboDashboard public classes (v1.1.0)
│   ├── engine.py            Polars lazy query engine (shared by both)
│   ├── server.py            FastAPI app for TurboTable (Tabulator UI)
│   ├── ui.py                Tabulator 6 HTML/JS template
│   ├── dashboard.py         FastAPI app for TurboDashboard (Arrow + WebSocket)
│   └── perspective_ui.py    Perspective SPA HTML/JS template
├── demo/
│   ├── generate_data.py     Synthetic 1M-row dataset generator
│   ├── demo_app.py          TurboTable demo launcher
│   └── dashboard_app.py     TurboDashboard demo launcher
├── tests/
│   ├── test_engine.py       50 unit tests
│   ├── test_server.py       30 integration tests
│   └── test_dashboard.py    31 dashboard tests
├── .github/
│   ├── workflows/test.yml   CI (Python 3.10–3.13)
│   ├── ISSUE_TEMPLATE/      Bug & feature request templates
│   └── pull_request_template.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── LICENSE                  MIT
├── pyproject.toml
└── QUICKSTART.md            Step-by-step guide for first-time users
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

- **Bug reports** → [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature requests** → [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- **Security issues** → see [SECURITY.md](SECURITY.md) (do not open public issues)

---

## License

MIT © 2025 **Dr Harry Patria** — Chief Data AI, Patria & Co.

See [LICENSE](LICENSE) for full text and third-party attributions.

---

## Author

**Dr Harry Patria**
Chief Data AI — Patria & Co.
Built with AI-assisted development.

> *"Making big data exploration accessible to every analyst, scientist, and engineer."*
