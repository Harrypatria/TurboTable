"""
TurboDashboard demo — 1-million-row interactive Perspective dashboard.

Steps
-----
    # 1. Generate data (if not already done from the TurboTable demo)
    python generate_data.py

    # 2. Launch the dashboard
    python dashboard_app.py

Then open  http://localhost:8766  in your browser.

What you can do in the browser
------------------------------
  * Switch between plugins via the top-left toolbar:
      Datagrid · X/Y Line · Y Bar · X Bar · Scatter · Heatmap · Treemap
  * Drag columns to the Row / Column / Filter / Sort pivots
  * Click any column header to sort
  * Use the built-in filter builder for complex expressions
  * All operations run at native C++ speed inside Perspective WASM —
    no server round-trips after the initial data load

CLI options
-----------
    --source  PATH   CSV or Parquet file  (default: data/sales_1m.parquet)
    --host    HOST   Bind address         (default: 127.0.0.1)
    --port    PORT   TCP port             (default: 8766)
    --rows    N      Rows to generate if source is missing  (default: 1_000_000)
    --chunk   N      WebSocket chunk size  (default: 50_000)

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly from the demo/ folder without pip-installing the package
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from turbotable import TurboDashboard                               # noqa: E402
from generate_data import build as _build_df                        # type: ignore[import]  # noqa: E402


def _auto_generate(out_csv: Path, rows: int, seed: int = 42) -> None:
    """Generate demo data when the source file is absent."""
    print(f"\n  Source file not found: {out_csv}")
    print(f"  Auto-generating {rows:,} synthetic rows (seed={seed}) …\n")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df = _build_df(n=rows, seed=seed)
    df.write_csv(str(out_csv))
    df.write_parquet(str(out_csv.with_suffix(".parquet")), compression="snappy")
    print(f"  Data written to {out_csv.parent}/\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TurboDashboard — Polars + Perspective 1M-row demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", default="data/sales_1m.parquet")
    parser.add_argument("--host",   default="127.0.0.1")
    parser.add_argument("--port",   type=int, default=8766)
    parser.add_argument("--rows",   type=int, default=1_000_000,
                        help="Rows to auto-generate if source is missing")
    parser.add_argument("--chunk",  type=int, default=50_000,
                        help="Rows per WebSocket chunk (WebSocket mode only)")
    args = parser.parse_args()

    source = Path(args.source)
    csv_fallback = source.with_suffix(".csv")

    if not source.exists():
        if csv_fallback.exists():
            source = csv_fallback
        else:
            _auto_generate(csv_fallback, args.rows)
            source = source if source.exists() else csv_fallback

    print(f"\n  Loading {source} …")
    dash = TurboDashboard(
        str(source),
        title="Sales Analytics Dashboard — 1M Rows",
        chunk_size=args.chunk,
    )

    print(f"  {dash}\n")
    print(f"  Schema: {dash.schema()}\n")
    print(f"  Preview:\n{dash.head(3)}\n")

    dash.show(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
