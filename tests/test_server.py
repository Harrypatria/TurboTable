"""
Integration tests for the TurboTable FastAPI server layer.

Run:  pytest tests/ -v
Deps: pip install httpx
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbotable.engine import TurboEngine
from turbotable.server import create_app


# ---------------------------------------------------------------------------
# Test fixture — 200-row dataset
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> TestClient:
    df = pl.DataFrame({
        "id":    list(range(1, 201)),
        "name":  [f"User_{i:03d}" for i in range(1, 201)],
        "score": [float(i % 100) for i in range(1, 201)],
        "group": ["Alpha" if i % 2 == 0 else "Beta" for i in range(1, 201)],
        "city":  ["Paris" if i % 3 == 0 else "London" for i in range(1, 201)],
    })
    engine = TurboEngine(df)
    return TestClient(create_app(engine, title="Test App"))


# ---------------------------------------------------------------------------
# Root / UI
# ---------------------------------------------------------------------------

def test_root_returns_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Test App" in r.text
    # Verify Tabulator is referenced
    assert "tabulator" in r.text.lower()


def test_root_no_xss_in_title(client):
    # XSS title injection: the angle brackets must be HTML-escaped
    df = pl.DataFrame({"x": [1, 2, 3]})
    xss_app = create_app(TurboEngine(df), title='<script>alert(1)</script>')
    xss_client = TestClient(xss_app)
    html = xss_client.get("/").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# /api/schema
# ---------------------------------------------------------------------------

def test_schema_endpoint(client):
    r = client.get("/api/schema")
    assert r.status_code == 200
    schema = r.json()
    assert set(schema.keys()) == {"id", "name", "score", "group", "city"}


def test_schema_values_are_strings(client):
    schema = client.get("/api/schema").json()
    assert all(isinstance(v, str) for v in schema.values())


# ---------------------------------------------------------------------------
# /api/data — pagination
# ---------------------------------------------------------------------------

def test_data_default_page(client):
    r = client.get("/api/data")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 200
    assert len(body["data"]) == 100   # default page size
    assert body["page"] == 1


def test_data_page2(client):
    body = client.get("/api/data?page=2&size=100").json()
    assert body["page"] == 2
    assert len(body["data"]) == 100


def test_data_custom_size(client):
    assert len(client.get("/api/data?size=25").json()["data"]) == 25


def test_data_last_page_calculation(client):
    assert client.get("/api/data?size=50").json()["last_page"] == 4


def test_data_last_page_at_least_one(client):
    # Single-row dataset should have last_page=1
    df = pl.DataFrame({"x": [42]})
    c = TestClient(create_app(TurboEngine(df), title="T"))
    assert c.get("/api/data").json()["last_page"] == 1


# ---------------------------------------------------------------------------
# /api/data — sorting
# ---------------------------------------------------------------------------

def test_sort_asc(client):
    scores = [r["score"] for r in client.get("/api/data?sort=score&sort_dir=asc&size=200").json()["data"]]
    assert scores == sorted(scores)


def test_sort_desc(client):
    scores = [r["score"] for r in client.get("/api/data?sort=score&sort_dir=desc&size=200").json()["data"]]
    assert scores == sorted(scores, reverse=True)


def test_sort_string_column(client):
    names = [r["name"] for r in client.get("/api/data?sort=name&sort_dir=asc&size=200").json()["data"]]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# /api/data — column filters
# ---------------------------------------------------------------------------

def test_filter_equals(client):
    filters = json.dumps([{"field": "group", "type": "=", "value": "Alpha"}])
    body = client.get(f"/api/data?size=200&filters={filters}").json()
    assert body["total"] == 100
    assert all(r["group"] == "Alpha" for r in body["data"])


def test_filter_contains(client):
    filters = json.dumps([{"field": "name", "type": "contains", "value": "100"}])
    body = client.get(f"/api/data?size=200&filters={filters}").json()
    names = [r["name"] for r in body["data"]]
    assert all("100" in n for n in names)


def test_filter_not_equal(client):
    filters = json.dumps([{"field": "city", "type": "!=", "value": "Paris"}])
    body = client.get(f"/api/data?size=200&filters={filters}").json()
    assert all(r["city"] == "London" for r in body["data"])


def test_invalid_filters_json_returns_400(client):
    r = client.get("/api/data?filters=NOT_VALID_JSON")
    assert r.status_code == 400


def test_filters_not_a_list_returns_400(client):
    r = client.get('/api/data?filters={"field":"x"}')   # object, not array
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/data — global search (q param)
# ---------------------------------------------------------------------------

def test_global_search_finds_match(client):
    body = client.get("/api/data?q=Paris&size=200").json()
    assert body["total"] > 0
    assert all(r["city"] == "Paris" for r in body["data"])


def test_global_search_no_match(client):
    body = client.get("/api/data?q=ZZZNOTEXISTS").json()
    assert body["total"] == 0


def test_global_search_blank_ignored(client):
    # Blank q should not filter anything
    body = client.get("/api/data?q=   &size=200").json()
    assert body["total"] == 200


def test_global_search_combined_with_filter(client):
    filters = json.dumps([{"field": "group", "type": "=", "value": "Alpha"}])
    body = client.get(f"/api/data?q=Paris&filters={filters}&size=200").json()
    for r in body["data"]:
        assert r["group"] == "Alpha"
        assert r["city"] == "Paris"


# ---------------------------------------------------------------------------
# /api/data/arrow
# ---------------------------------------------------------------------------

def test_arrow_endpoint_returns_bytes(client):
    r = client.get("/api/data/arrow?size=10")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.apache.arrow.stream"
    assert len(r.content) > 0


def test_arrow_endpoint_invalid_filters_returns_400(client):
    r = client.get("/api/data/arrow?filters=BAD_JSON")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/stats
# ---------------------------------------------------------------------------

def test_stats_endpoint_returns_list(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_column_stats_numeric(client):
    body = client.get("/api/stats/score").json()
    assert {"min", "max", "mean", "std", "nulls"}.issubset(body)


def test_column_stats_string(client):
    body = client.get("/api/stats/name").json()
    assert "unique" in body
    assert "nulls" in body


def test_column_stats_missing_returns_404(client):
    r = client.get("/api/stats/ghost_column")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/sample
# ---------------------------------------------------------------------------

def test_sample_default(client):
    r = client.get("/api/sample")
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_sample_n(client):
    assert len(client.get("/api/sample?n=12").json()) == 12


def test_sample_max_enforced(client):
    r = client.get("/api/sample?n=99999")
    assert r.status_code == 422   # FastAPI validation rejects n > 1000
