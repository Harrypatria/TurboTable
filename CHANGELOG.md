# Changelog

All notable changes to TurboTable are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.1.0] — 2025-03-27

### Added — TurboDashboard (Perspective WASM Integration)

- **`TurboDashboard`** — new public class providing a full interactive
  pivot/chart dashboard powered by `@finos/perspective` (C++/WASM engine).

- **`turbotable/dashboard.py`**
  - `TurboDashboard` class: same source API as `TurboTable`
    (CSV / Parquet / DataFrame / LazyFrame).
  - `create_dashboard_app()` — FastAPI application factory.
  - `GET /api/arrow` — full dataset as Apache Arrow IPC file with
    `Content-Length` header for browser progress tracking.
  - `WS /ws` — chunked Arrow IPC streaming via WebSocket; enables
    progressive rendering of the Perspective grid chunk-by-chunk.
  - Auto-mode selection: datasets ≤ 500 000 rows → HTTP mode;
    > 500 000 rows → WebSocket mode.
  - `asyncio.to_thread()` for all blocking Polars `.collect()` calls,
    keeping the FastAPI event loop responsive during data collection.

- **`turbotable/perspective_ui.py`**
  - `build_perspective_html()` — generates a full-screen Perspective SPA.
  - HTTP mode: `ReadableStream` fetch with byte-level progress bar.
  - WebSocket mode: first chunk → `worker.table()`; subsequent chunks →
    `table.update()` for live progressive rendering.
  - All user-supplied values HTML-escaped or JSON-encoded before injection.
  - Perspective `2.10.1` CDN pinned from `cdn.jsdelivr.net`.
  - Includes Datagrid + D3FC plugins (bar, line, scatter, heatmap, treemap).
  - Status dot in header turns green when data is fully loaded.
  - Error banner displayed on fetch / WebSocket failure.
  - Responsive full-viewport layout (works on desktop and tablet).

- **`demo/dashboard_app.py`** — demo launcher for the 1M-row sales dataset;
  auto-generates data if not present; supports `--source`, `--host`,
  `--port`, `--rows`, `--chunk` CLI flags.

- **`tests/test_dashboard.py`** — 35 tests covering:
  - Arrow IPC serialisation and roundtrip validation
  - HTTP endpoint (status, content-type, content-length, magic bytes)
  - WebSocket protocol (meta, binary chunks, progress, complete messages)
  - Auto-mode selection threshold
  - XSS escaping in HTML title
  - Perspective HTML template (CDN, schema injection, mode flags)
  - `TurboDashboard` class API (repr, head, schema, describe)

### Changed
- `__version__` bumped to `1.1.0`.
- `pyproject.toml` keywords extended with `perspective`, `apache-arrow`,
  `dashboard`, `wasm`, `pivot`.
- `turbotable/__init__.py` docstring updated to document both classes.

---

## [1.0.0] — 2025-03-27

### Added
- `TurboEngine` — Polars LazyFrame query engine with lazy loading for CSV,
  Parquet, and NDJSON sources.
- Server-side **pagination**, **sorting**, **column filtering** (AND-chained),
  and **global full-text search** (OR across string columns, via `?q=` param).
- `TurboServer` — background daemon thread for Jupyter / notebook use
  (`blocking=False`).
- FastAPI application with endpoints:
  - `GET /` — self-contained Tabulator 6 single-page UI
  - `GET /api/data` — paginated JSON data
  - `GET /api/data/arrow` — Apache Arrow IPC binary transport
  - `GET /api/schema` — column metadata
  - `GET /api/sample` — quick preview
  - `GET /api/stats` — dataset-wide descriptive statistics
  - `GET /api/stats/{column}` — per-column lazy statistics
- Dark-themed Tabulator 6 UI with:
  - Per-column header filters
  - Global search box (debounced, 350 ms)
  - Sort by column header click
  - CSV and JSON export of current view
  - Stats modal
  - Live query-time display
  - API docs shortcut button
- 80 unit + integration tests (100 % pass rate).
- Synthetic 1M-row demo dataset generator (`demo/generate_data.py`).
- Full GitHub community health files: CONTRIBUTING, SECURITY, CODE_OF_CONDUCT,
  issue templates, PR template.

### Security
- HTML-escape `title` before injection into the UI template (XSS prevention).
- Validate `filters` JSON as a list; return HTTP 400 on malformed input
  (both `/api/data` and `/api/data/arrow`).
- `sort_dir` parameter replaces `dir` (avoids Python builtin shadowing).
- CORS policy documented; default `allow_origins=["*"]` appropriate for
  local/intranet use.

### Fixed
- Global search logic: previously sent one `contains` filter per column
  (AND semantics), which returned empty results for multi-column searches.
  Now uses a dedicated `?q=` parameter processed as `pl.any_horizontal` OR
  across all string columns in the engine.
- `pl.Utf8` (deprecated) replaced with `pl.String` throughout.
- Removed unused `StaticFiles` and `JSONResponse` imports from `server.py`.
- `build-backend` corrected to `"setuptools.build_meta"` in `pyproject.toml`.
- `random.choice` replaced with NumPy RNG in `generate_data.py` for
  full reproducibility with a fixed `--seed`.
- `import json` / `import threading` moved from function bodies to module level.
- URL shown as `http://localhost:<port>` (not `http://0.0.0.0:<port>`) when
  binding to all interfaces.
- Negative `start` clamped to 0 in `get_view` instead of raising.

[Unreleased]: https://github.com/harrypatria/TurboTable/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/harrypatria/TurboTable/releases/tag/v1.0.0
