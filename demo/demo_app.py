"""
TurboTable demo — 1-million-row synthetic sales dataset.

Steps
-----
    # 1. Generate data (first run only, ~4 seconds)
    python generate_data.py

    # 2. Launch
    python demo_app.py

Then open  http://localhost:8765  in your browser.

Options
-------
    --source PATH   CSV or Parquet file  (default: data/sales_1m.parquet)
    --host  HOST    Bind host            (default: 127.0.0.1)
    --port  PORT    TCP port             (default: 8765)
    --rows  N       Rows to generate if source is missing (default: 1_000_000)
    --seed  N       RNG seed for generation               (default: 42)

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the demo/ folder without installing the package
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from turbotable import TurboTable         # noqa: E402
from generate_data import build, main as _gen_main   # type: ignore[import]  # noqa: E402


def _auto_generate(out_csv: Path, rows: int, seed: int) -> None:
    """Generate demo data when the source file is absent."""
    print(f"\n  Source file not found: {out_csv}")
    print(f"  Auto-generating {rows:,} synthetic rows (seed={seed}) …\n")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df = build(n=rows, seed=seed)
    df.write_csv(str(out_csv))
    df.write_parquet(str(out_csv.with_suffix(".parquet")), compression="snappy")
    print(f"  Data written to {out_csv.parent}/\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TurboTable demo — 1M-row interactive table",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", default="data/sales_1m.parquet",
                        help="Path to CSV or Parquet file")
    parser.add_argument("--host",   default="127.0.0.1")
    parser.add_argument("--port",   type=int, default=8765)
    parser.add_argument("--rows",   type=int, default=1_000_000,
                        help="Rows to generate if source file is missing")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    source = Path(args.source)
    csv_fallback = source.with_suffix(".csv")

    # Auto-generate if neither parquet nor csv exists
    if not source.exists():
        if csv_fallback.exists():
            source = csv_fallback
        else:
            _auto_generate(csv_fallback, args.rows, args.seed)
            source = source if source.exists() else csv_fallback

    print(f"\n  Loading {source} …")
    tt = TurboTable(str(source), title="Sales Analytics — 1 M Rows")

    print(f"  {tt}\n")
    print(f"  Schema: {tt.schema()}\n")
    print(f"  Preview:\n{tt.head(3)}\n")

    tt.show(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
