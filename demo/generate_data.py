"""
Synthetic dataset generator for TurboTable benchmarking.

Creates a realistic e-commerce sales dataset with configurable row count.
All randomness flows through a single NumPy Generator seeded deterministically,
so the same --seed value always produces identical output.

Usage
-----
    python generate_data.py                          # 1 M rows → data/
    python generate_data.py --rows 100000            # 100 k rows (quick test)
    python generate_data.py --rows 5000000 --seed 7  # 5 M rows, fixed seed

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import polars as pl

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------
CATEGORIES    = ["Electronics", "Apparel", "Grocery", "Furniture", "Automotive",
                 "Sports", "Books", "Toys", "Health", "Beauty"]
REGIONS       = ["North", "South", "East", "West", "Central"]
STATUSES      = ["Completed", "Pending", "Cancelled", "Refunded", "Processing"]
PAYMENT_MODES = ["Credit Card", "Debit Card", "Cash", "PayPal", "Bank Transfer"]

FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Hank",
    "Iris", "Jack", "Karen", "Leo", "Mia", "Nick", "Olivia", "Pete",
    "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zane",
]
LAST_NAMES = [
    "Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson",
    "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
    "Martin", "Garcia", "Lee", "Walker", "Hall", "Allen",
]

# Unix timestamps bracketing the synthetic date range (2021-01-01 → 2026-01-01)
_TS_START = 1_609_459_200
_TS_END   = 1_767_225_600


def build(n: int = 1_000_000, seed: int = 42) -> pl.DataFrame:
    """
    Generate a synthetic sales DataFrame with *n* rows.

    All columns are derived from a single seeded NumPy Generator,
    ensuring reproducibility across runs.

    Parameters
    ----------
    n    : Number of rows.
    seed : Random seed (any integer).
    """
    rng = np.random.default_rng(seed)

    # --- Identifiers --------------------------------------------------------
    order_ids    = [f"ORD-{i:09d}" for i in range(1, n + 1)]
    customer_ids = rng.integers(1_000, 9_999, size=n)

    # --- Categorical columns (all via numpy for reproducibility) ------------
    fn_idx  = rng.integers(0, len(FIRST_NAMES), size=n)
    ln_idx  = rng.integers(0, len(LAST_NAMES),  size=n)
    names   = [f"{FIRST_NAMES[fi]} {LAST_NAMES[li]}" for fi, li in zip(fn_idx, ln_idx)]

    categories    = [CATEGORIES[i]    for i in rng.integers(0, len(CATEGORIES),    size=n)]
    regions       = [REGIONS[i]       for i in rng.integers(0, len(REGIONS),       size=n)]
    statuses      = [STATUSES[i]      for i in rng.integers(0, len(STATUSES),      size=n)]
    payment_modes = [PAYMENT_MODES[i] for i in rng.integers(0, len(PAYMENT_MODES), size=n)]

    # --- Numeric columns ----------------------------------------------------
    quantity      = rng.integers(1, 50, size=n)
    unit_price    = (rng.random(n) * 999.0 + 1.0).round(2)
    revenue       = (quantity * unit_price).round(2)
    discount_pct  = (rng.random(n) * 30.0).round(1)
    profit_margin = (rng.random(n) * 40.0 + 5.0).round(2)
    rating        = (rng.random(n) * 4.0 + 1.0).round(1)

    # --- Boolean / date columns --------------------------------------------
    return_flag   = rng.random(n) < 0.08   # ~8 % return rate

    ts    = rng.integers(_TS_START, _TS_END, size=n)
    dates = pl.from_epoch(pl.Series("ts", ts.tolist()), time_unit="s").dt.date()

    return pl.DataFrame({
        "order_id":      order_ids,
        "customer_id":   customer_ids.tolist(),
        "customer_name": names,
        "category":      categories,
        "region":        regions,
        "status":        statuses,
        "payment_mode":  payment_modes,
        "quantity":      quantity.tolist(),
        "unit_price":    unit_price.tolist(),
        "revenue":       revenue.tolist(),
        "discount_pct":  discount_pct.tolist(),
        "profit_margin": profit_margin.tolist(),
        "order_date":    dates,
        "rating":        rating.tolist(),
        "returned":      return_flag.tolist(),
    })


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic TurboTable demo data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--rows",   type=int, default=1_000_000,
                        help="Number of rows to generate")
    parser.add_argument("--seed",   type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, default="data/sales_1m.csv",
                        help="Output CSV path (Parquet written alongside)")
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n  Generating {args.rows:,} rows (seed={args.seed}) …")
    t0 = time.perf_counter()
    df = build(n=args.rows, seed=args.seed)
    print(f"  Built in {time.perf_counter() - t0:.1f}s  "
          f"({len(df):,} rows × {len(df.columns)} cols)")

    print(f"  Writing CSV  → {out} …")
    t1 = time.perf_counter()
    df.write_csv(str(out))
    print(f"  CSV saved in {time.perf_counter() - t1:.1f}s  "
          f"({out.stat().st_size / 1e6:.1f} MB)")

    parquet_out = out.with_suffix(".parquet")
    print(f"  Writing Parquet → {parquet_out} …")
    t2 = time.perf_counter()
    df.write_parquet(str(parquet_out), compression="snappy")
    print(f"  Parquet saved in {time.perf_counter() - t2:.1f}s  "
          f"({parquet_out.stat().st_size / 1e6:.1f} MB)\n")


if __name__ == "__main__":
    main()
