"""
Unit tests for TurboEngine.

Run:  pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbotable.engine import TurboEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df() -> pl.DataFrame:
    return pl.DataFrame({
        "id":       [1, 2, 3, 4, 5],
        "name":     ["Alice Smith", "Bob Jones", "Carol White", "David Brown", "Eve Davis"],
        "score":    [88.5, 72.0, 95.1, 60.3, 81.0],
        "active":   [True, False, True, True, False],
        "category": ["A", "B", "A", "C", "B"],
    })


@pytest.fixture
def engine(sample_df) -> TurboEngine:
    return TurboEngine(sample_df)


# ---------------------------------------------------------------------------
# Schema & metadata
# ---------------------------------------------------------------------------

def test_schema_keys(engine, sample_df):
    assert set(engine.schema.keys()) == set(sample_df.columns)


def test_schema_values_are_strings(engine):
    assert all(isinstance(v, str) for v in engine.schema.values())


def test_columns_order_preserved(engine, sample_df):
    assert engine.columns == sample_df.columns


def test_string_columns(engine):
    sc = engine.string_columns
    assert "name" in sc
    assert "category" in sc
    # Numeric columns must not appear
    assert "score" not in sc
    assert "id" not in sc


# ---------------------------------------------------------------------------
# total_rows
# ---------------------------------------------------------------------------

def test_total_rows_no_filter(engine):
    assert engine.total_rows() == 5


def test_total_rows_with_filter(engine):
    f = [{"field": "category", "type": "=", "value": "A"}]
    assert engine.total_rows(filters=f) == 2


def test_total_rows_with_search(engine):
    # "Jones" is in Bob's name only
    assert engine.total_rows(search="Jones") == 1


def test_total_rows_filter_and_search(engine):
    # category B with name containing "Bo"
    f = [{"field": "category", "type": "=", "value": "B"}]
    assert engine.total_rows(filters=f, search="Bo") == 1


# ---------------------------------------------------------------------------
# get_view — pagination
# ---------------------------------------------------------------------------

def test_get_view_returns_dataframe(engine):
    assert isinstance(engine.get_view(start=0, size=3), pl.DataFrame)
    assert len(engine.get_view(start=0, size=3)) == 3


def test_get_view_page1(engine):
    assert engine.get_view(start=0, size=2)["id"].to_list() == [1, 2]


def test_get_view_page2(engine):
    assert engine.get_view(start=2, size=2)["id"].to_list() == [3, 4]


def test_get_view_size_clamps_to_total(engine):
    assert len(engine.get_view(start=0, size=1_000)) == 5


def test_get_view_start_beyond_total(engine):
    assert len(engine.get_view(start=100, size=10)) == 0


def test_get_view_negative_start_treated_as_zero(engine):
    # Negative start should be clamped rather than raising
    result = engine.get_view(start=-5, size=3)
    assert len(result) == 3


def test_get_view_size_one(engine):
    assert len(engine.get_view(start=0, size=1)) == 1


# ---------------------------------------------------------------------------
# get_view — sorting
# ---------------------------------------------------------------------------

def test_sort_ascending(engine):
    scores = engine.get_view(sort_col="score", sort_desc=False)["score"].to_list()
    assert scores == sorted(scores)


def test_sort_descending(engine):
    scores = engine.get_view(sort_col="score", sort_desc=True)["score"].to_list()
    assert scores == sorted(scores, reverse=True)


def test_sort_string_column(engine):
    names = engine.get_view(sort_col="name", sort_desc=False)["name"].to_list()
    assert names == sorted(names)


def test_sort_invalid_column_ignored(engine):
    result = engine.get_view(sort_col="nonexistent")
    assert len(result) == 5


# ---------------------------------------------------------------------------
# get_view — column filters
# ---------------------------------------------------------------------------

def test_filter_equals_string(engine):
    f = [{"field": "category", "type": "=", "value": "A"}]
    result = engine.get_view(filters=f)
    assert all(r == "A" for r in result["category"].to_list())
    assert len(result) == 2


def test_filter_equals_numeric(engine):
    f = [{"field": "score", "type": ">", "value": 80}]
    result = engine.get_view(filters=f)
    assert all(s > 80 for s in result["score"].to_list())


def test_filter_contains(engine):
    f = [{"field": "name", "type": "contains", "value": "Smith"}]
    result = engine.get_view(filters=f)
    assert "Alice Smith" in result["name"].to_list()
    assert len(result) == 1


def test_filter_like_alias_of_contains(engine):
    f = [{"field": "name", "type": "like", "value": "Jones"}]
    result = engine.get_view(filters=f)
    assert len(result) == 1


def test_filter_starts(engine):
    f = [{"field": "name", "type": "starts", "value": "Carol"}]
    result = engine.get_view(filters=f)
    assert result["name"].to_list() == ["Carol White"]


def test_filter_ends(engine):
    f = [{"field": "name", "type": "ends", "value": "Davis"}]
    result = engine.get_view(filters=f)
    assert result["name"].to_list() == ["Eve Davis"]


def test_filter_not_equal(engine):
    f = [{"field": "category", "type": "!=", "value": "A"}]
    result = engine.get_view(filters=f)
    assert "A" not in result["category"].to_list()
    assert len(result) == 3


def test_filter_lte(engine):
    f = [{"field": "score", "type": "<=", "value": 72}]
    result = engine.get_view(filters=f)
    assert all(s <= 72 for s in result["score"].to_list())


def test_filter_unknown_op_is_skipped(engine):
    f = [{"field": "name", "type": "INVALID_OP", "value": "Alice Smith"}]
    assert len(engine.get_view(filters=f)) == 5


def test_filter_missing_field_is_skipped(engine):
    f = [{"field": None, "type": "=", "value": "A"}]
    assert len(engine.get_view(filters=f)) == 5


def test_filter_nonexistent_column_is_skipped(engine):
    f = [{"field": "ghost_col", "type": "=", "value": "x"}]
    assert len(engine.get_view(filters=f)) == 5


def test_multiple_filters_and_chained(engine):
    f = [
        {"field": "active", "type": "=",  "value": True},
        {"field": "score",  "type": ">",  "value": 80},
    ]
    result = engine.get_view(filters=f)
    for row in result.iter_rows(named=True):
        assert row["active"] is True
        assert row["score"] > 80


# ---------------------------------------------------------------------------
# get_view — global search (OR across string columns)
# ---------------------------------------------------------------------------

def test_search_finds_by_name(engine):
    result = engine.get_view(search="Alice")
    assert "Alice Smith" in result["name"].to_list()


def test_search_finds_by_category(engine):
    # "C" appears only in category "C" (David Brown)
    result = engine.get_view(search="David")
    assert len(result) == 1
    assert result["name"].to_list()[0] == "David Brown"


def test_search_no_match_returns_empty(engine):
    result = engine.get_view(search="ZZZNOTPRESENT")
    assert len(result) == 0


def test_search_combined_with_filter(engine):
    f = [{"field": "category", "type": "=", "value": "B"}]
    # Category B: Bob Jones, Eve Davis. Search for "Bob"
    result = engine.get_view(filters=f, search="Bob")
    assert len(result) == 1
    assert result["name"].to_list()[0] == "Bob Jones"


def test_search_total_rows(engine):
    assert engine.total_rows(search="Smith") == 1


# ---------------------------------------------------------------------------
# column_stats
# ---------------------------------------------------------------------------

def test_column_stats_numeric_keys(engine):
    stats = engine.column_stats("score")
    assert {"min", "max", "mean", "std", "nulls"}.issubset(stats)
    assert stats["dtype"] == "Float64"


def test_column_stats_string_keys(engine):
    stats = engine.column_stats("name")
    assert {"unique", "nulls"}.issubset(stats)


def test_column_stats_unknown_raises_key_error(engine):
    with pytest.raises(KeyError):
        engine.column_stats("nonexistent")


# ---------------------------------------------------------------------------
# Arrow serialisation
# ---------------------------------------------------------------------------

def test_get_view_arrow_returns_bytes(engine):
    result = engine.get_view_arrow(start=0, size=3)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_get_view_arrow_with_search(engine):
    result = engine.get_view_arrow(search="Alice")
    assert isinstance(result, bytes)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

def test_load_csv(tmp_path, sample_df):
    p = tmp_path / "test.csv"
    sample_df.write_csv(str(p))
    assert TurboEngine(str(p)).total_rows() == 5


def test_load_parquet(tmp_path, sample_df):
    p = tmp_path / "test.parquet"
    sample_df.write_parquet(str(p))
    assert TurboEngine(str(p)).total_rows() == 5


def test_load_path_object(tmp_path, sample_df):
    p = tmp_path / "test.parquet"
    sample_df.write_parquet(str(p))
    assert TurboEngine(p).total_rows() == 5   # pathlib.Path


def test_load_lazyframe(sample_df):
    assert TurboEngine(sample_df.lazy()).total_rows() == 5


def test_load_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        TurboEngine("data.xlsx")


def test_load_unsupported_type_raises():
    with pytest.raises(TypeError, match="Cannot load"):
        TurboEngine({"not": "a dataframe"})


# ---------------------------------------------------------------------------
# sample()
# ---------------------------------------------------------------------------

def test_sample_default(engine):
    assert len(engine.sample()) == 5


def test_sample_n(engine):
    assert len(engine.sample(3)) == 3


def test_sample_invalid_n(engine):
    with pytest.raises(ValueError):
        engine.sample(0)
