"""
TurboTable Engine — Polars-powered lazy query processor.

Handles filtering, full-text search, sorting, and pagination
entirely inside a Polars LazyFrame. No data is materialised until
the final .slice().collect() call, so even 10M-row datasets remain
responsive.

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Operator map:  Tabulator filter operator → Polars expression builder
# The lambdas receive (polars_expr, coerced_value) and return a BooleanExpr.
# ---------------------------------------------------------------------------
_OP_MAP: Dict[str, Any] = {
    "=":        lambda c, v: c == v,
    "!=":       lambda c, v: c != v,
    "like":     lambda c, v: c.cast(pl.String).str.contains(str(v), literal=True),
    "contains": lambda c, v: c.cast(pl.String).str.contains(str(v), literal=True),
    "starts":   lambda c, v: c.cast(pl.String).str.starts_with(str(v)),
    "ends":     lambda c, v: c.cast(pl.String).str.ends_with(str(v)),
    ">":        lambda c, v: c > v,
    ">=":       lambda c, v: c >= v,
    "<":        lambda c, v: c < v,
    "<=":       lambda c, v: c <= v,
}

# Polars numeric dtype classes (used for isinstance checks against schema values)
_NUMERIC_DTYPE_CLASSES = (
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
    pl.Float32, pl.Float64,
)


class TurboEngine:
    """
    Core query engine wrapping a Polars LazyFrame.

    Parameters
    ----------
    source : str | Path | pl.DataFrame | pl.LazyFrame
        Accepted sources:
        - File path (str or Path) ending in .csv / .parquet / .json / .ndjson
        - A Polars DataFrame  → converted to LazyFrame in-place
        - A Polars LazyFrame  → used as-is (zero-copy)
    """

    def __init__(self, source: Union[str, Path, pl.DataFrame, pl.LazyFrame]) -> None:
        self.lf: pl.LazyFrame = self._load(source)
        # Eagerly cache the schema — collect_schema() is a no-op metadata call,
        # not a full scan. This avoids repeated PerformanceWarnings.
        self._schema_cache = self.lf.collect_schema()
        # Cache unfiltered row count so multiple callers don't trigger redundant scans.
        self._total_rows_cache: Optional[int] = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(source: Union[str, Path, pl.DataFrame, pl.LazyFrame]) -> pl.LazyFrame:
        if isinstance(source, pl.LazyFrame):
            return source
        if isinstance(source, pl.DataFrame):
            return source.lazy()
        if isinstance(source, (str, Path)):
            p = Path(source)
            suffix = p.suffix.lower()
            if suffix == ".parquet":
                return pl.scan_parquet(p)
            if suffix in {".json", ".ndjson"}:
                return pl.scan_ndjson(p)
            if suffix == ".csv":
                return pl.scan_csv(p)
            raise ValueError(
                f"Unsupported file extension {suffix!r}. "
                "Supported: .csv, .parquet, .json, .ndjson"
            )
        raise TypeError(
            f"Cannot load source of type {type(source).__name__!r}. "
            "Pass a file path (str/Path), pl.DataFrame, or pl.LazyFrame."
        )

    def _is_numeric(self, col: str) -> bool:
        dtype = self._schema_cache.get(col)
        return dtype is not None and isinstance(dtype, _NUMERIC_DTYPE_CLASSES)

    def _is_string_like(self, col: str) -> bool:
        """True for String / Categorical columns (searchable as text)."""
        dtype = self._schema_cache.get(col)
        if dtype is None:
            return False
        return isinstance(dtype, (pl.String, pl.Categorical, pl.Enum))

    def _coerce_value(self, col: str, value: Any) -> Any:
        """Cast a raw filter value to match the column's dtype."""
        if self._is_numeric(col):
            try:
                return float(value)
            except (TypeError, ValueError):
                logger.warning(
                    "Could not coerce filter value %r to float for column %r. "
                    "Filter will be applied as-is.",
                    value, col,
                )
        return value

    def _apply_filters(
        self, query: pl.LazyFrame, filters: List[Dict[str, Any]]
    ) -> pl.LazyFrame:
        """AND-chain all column-specific filters onto the LazyFrame."""
        for f in filters:
            col_name: Optional[str] = f.get("field") or f.get("column")
            op: str = f.get("type", "like")
            raw_value = f.get("value")

            if not col_name or raw_value is None or col_name not in self._schema_cache:
                continue

            expr_fn = _OP_MAP.get(op)
            if expr_fn is None:
                logger.debug("Unknown filter operator %r — skipping.", op)
                continue

            value = self._coerce_value(col_name, raw_value)
            try:
                query = query.filter(expr_fn(pl.col(col_name), value))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Filter on column %r (op=%r, value=%r) failed: %s — skipping.",
                    col_name, op, value, exc,
                )
        return query

    def _apply_search(self, query: pl.LazyFrame, q: str) -> pl.LazyFrame:
        """
        Full-text search: OR across all string-like columns.

        Rows are kept when the search term appears in *any* text column,
        which is the intuitive behaviour for a global search box.
        """
        string_cols = [c for c in self._schema_cache.keys() if self._is_string_like(c)]
        if not string_cols:
            return query
        exprs = [
            pl.col(c).str.contains(q, literal=True)
            for c in string_cols
        ]
        return query.filter(pl.any_horizontal(exprs))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def schema(self) -> Dict[str, str]:
        """Return ``{column_name: dtype_string}`` for all columns."""
        return {col: str(dtype) for col, dtype in self._schema_cache.items()}

    @property
    def columns(self) -> List[str]:
        """Ordered list of column names."""
        return list(self._schema_cache.keys())

    @property
    def string_columns(self) -> List[str]:
        """Columns that can be searched as text (used by global search)."""
        return [c for c in self._schema_cache.keys() if self._is_string_like(c)]

    def total_rows(
        self,
        filters: Optional[List[Dict[str, Any]]] = None,
        search: Optional[str] = None,
    ) -> int:
        """
        Row count after applying optional column filters and/or global search.

        Parameters
        ----------
        filters : column-specific filter dicts (AND-chained)
        search  : global full-text search term (OR across string columns)
        """
        if filters is None and search is None:
            if self._total_rows_cache is None:
                self._total_rows_cache = (
                    self.lf.select(pl.len()).collect().item()
                )
            return self._total_rows_cache

        query = self.lf
        if filters:
            query = self._apply_filters(query, filters)
        if search:
            query = self._apply_search(query, search)
        return query.select(pl.len()).collect().item()

    def get_view(
        self,
        start: int = 0,
        size: int = 100,
        sort_col: Optional[str] = None,
        sort_desc: bool = False,
        filters: Optional[List[Dict[str, Any]]] = None,
        search: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        Return a paginated slice of the dataset.

        Operations are applied in this order:
          1. Column filters (AND-chained)
          2. Global search (OR across string columns)
          3. Sort
          4. Slice (pagination)

        Parameters
        ----------
        start    : zero-based row offset
        size     : number of rows to return (clamped to ≥ 1)
        sort_col : column name to sort by (None = original order)
        sort_desc: True → descending sort
        filters  : list of ``{field, type, value}`` dicts (Tabulator format)
        search   : full-text search term applied across all string columns
        """
        if start < 0:
            start = 0
        if size < 1:
            size = 1

        query = self.lf

        if filters:
            query = self._apply_filters(query, filters)
        if search:
            query = self._apply_search(query, search)
        if sort_col and sort_col in self._schema_cache:
            query = query.sort(sort_col, descending=sort_desc)

        return query.slice(start, size).collect()

    def get_view_arrow(
        self,
        start: int = 0,
        size: int = 100,
        sort_col: Optional[str] = None,
        sort_desc: bool = False,
        filters: Optional[List[Dict[str, Any]]] = None,
        search: Optional[str] = None,
    ) -> bytes:
        """
        Same as ``get_view`` but serialised as Apache Arrow IPC (Feather v2).

        Arrow encoding is 5–10× faster to transfer than JSON for numeric-heavy
        datasets, making it ideal for programmatic clients or high-frequency
        dashboard refreshes.
        """
        df = self.get_view(start, size, sort_col, sort_desc, filters, search)
        buf = io.BytesIO()
        df.write_ipc(buf)
        return buf.getvalue()

    def describe(self) -> pl.DataFrame:
        """
        Descriptive statistics for all columns.

        Note: This collects the full dataset to compute statistics.
        For extremely large datasets (>50 M rows), prefer ``column_stats``
        for targeted per-column metrics.
        """
        return self.lf.collect().describe()

    def column_stats(self, col: str) -> Dict[str, Any]:
        """
        Targeted statistics for a single column using lazy aggregation.

        Returns min/max/mean/std/nulls for numeric columns,
        and unique/nulls for categorical/string columns.
        """
        if col not in self._schema_cache:
            raise KeyError(f"Column {col!r} not found in dataset.")

        if self._is_numeric(col):
            row = (
                self.lf.select(
                    pl.col(col).min().alias("min"),
                    pl.col(col).max().alias("max"),
                    pl.col(col).mean().alias("mean"),
                    pl.col(col).std().alias("std"),
                    pl.col(col).null_count().alias("nulls"),
                )
                .collect()
                .row(0, named=True)
            )
        else:
            row = (
                self.lf.select(
                    pl.col(col).n_unique().alias("unique"),
                    pl.col(col).null_count().alias("nulls"),
                )
                .collect()
                .row(0, named=True)
            )

        return {"column": col, "dtype": str(self._schema_cache[col]), **row}

    def sample(self, n: int = 5) -> pl.DataFrame:
        """Return the first *n* rows without scanning the full dataset."""
        if n < 1:
            raise ValueError(f"n must be ≥ 1, got {n}.")
        return self.lf.slice(0, n).collect()
