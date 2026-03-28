"""
Tests for TurboDashboard — FastAPI server layer and CSV serialisation.

Run:  pytest tests/test_dashboard.py -v
Deps: pip install httpx
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from turbotable.dashboard import (
    TurboDashboard,
    _df_to_csv_str,
    _prepare_for_json,
    _WEBSOCKET_THRESHOLD,
    create_dashboard_app,
)
from turbotable.engine import TurboEngine
from turbotable.perspective_ui import build_perspective_html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small_df() -> pl.DataFrame:
    """200-row DataFrame — triggers HTTP mode (< WEBSOCKET_THRESHOLD)."""
    return pl.DataFrame({
        "id":      list(range(1, 201)),
        "name":    [f"User_{i:03d}" for i in range(1, 201)],
        "revenue": [float(i * 1.5) for i in range(1, 201)],
        "region":  ["North" if i % 2 == 0 else "South" for i in range(1, 201)],
    })


@pytest.fixture(scope="module")
def client(small_df) -> TestClient:
    engine = TurboEngine(small_df)
    app    = create_dashboard_app(engine, title="Test Dashboard", chunk_size=50)
    return TestClient(app)


# ---------------------------------------------------------------------------
# CSV serialisation helper
# ---------------------------------------------------------------------------

def test_df_to_csv_str_returns_string(small_df):
    result = _df_to_csv_str(small_df)
    assert isinstance(result, str)
    assert len(result) > 0


def test_df_to_csv_str_has_header(small_df):
    result = _df_to_csv_str(small_df)
    header = result.split("\n")[0]
    for col in small_df.columns:
        assert col in header


def test_df_to_csv_str_correct_row_count(small_df):
    result = _df_to_csv_str(small_df)
    # Lines: 1 header + 200 data rows (+ optional trailing newline)
    data_lines = [l for l in result.split("\n")[1:] if l]
    assert len(data_lines) == 200


def test_df_to_csv_str_roundtrip_values(small_df):
    result = _df_to_csv_str(small_df)
    reader = csv.DictReader(io.StringIO(result))
    rows = list(reader)
    assert rows[0]["id"] == "1"
    assert rows[-1]["id"] == "200"
    assert rows[0]["name"] == "User_001"


def test_prepare_for_json_converts_dates():
    """Date columns must become ISO strings, not integers."""
    import datetime
    df = pl.DataFrame({
        "d": pl.Series([datetime.date(2024, 1, 15), datetime.date(2024, 6, 30)],
                       dtype=pl.Date),
    })
    out = _prepare_for_json(df)
    assert out["d"].dtype == pl.String
    assert out["d"][0] == "2024-01-15"


def test_prepare_for_json_converts_duration():
    df = pl.DataFrame({"dur": pl.Series([1_000_000, 2_000_000], dtype=pl.Duration("us"))})
    out = _prepare_for_json(df)
    assert out["dur"].dtype == pl.Int64


def test_prepare_for_json_converts_categorical():
    df = pl.DataFrame({"cat": pl.Series(["a", "b", "a"], dtype=pl.Categorical)})
    out = _prepare_for_json(df)
    assert out["cat"].dtype == pl.String


# ---------------------------------------------------------------------------
# Root / UI
# ---------------------------------------------------------------------------

def test_root_returns_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_root_contains_perspective(client):
    html = client.get("/").text
    assert "perspective-viewer" in html


def test_root_contains_title(client):
    html = client.get("/").text
    assert "Test Dashboard" in html


def test_root_xss_title_escaped():
    """XSS: angle brackets in title must be HTML-escaped."""
    df     = pl.DataFrame({"x": [1, 2, 3]})
    engine = TurboEngine(df)
    xss    = create_dashboard_app(engine, title='<script>alert(1)</script>', chunk_size=50)
    c      = TestClient(xss)
    html   = c.get("/").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# /api/meta
# ---------------------------------------------------------------------------

def test_meta_endpoint_shape(client):
    body = client.get("/api/meta").json()
    assert body["total_rows"]  == 200
    assert body["chunk_size"]  == 50
    assert "schema" in body
    assert "columns" in body


def test_meta_use_websocket_is_bool(client):
    body = client.get("/api/meta").json()
    assert isinstance(body["use_websocket"], bool)


def test_meta_websocket_mode_triggered():
    """Datasets above the threshold must report use_websocket=True."""
    n = _WEBSOCKET_THRESHOLD + 1
    df = pl.DataFrame({"val": list(range(n))})
    engine = TurboEngine(df)
    app = create_dashboard_app(engine, title="Big", chunk_size=50_000)
    c = TestClient(app)
    body = c.get("/api/meta").json()
    assert body["use_websocket"] is True


def test_meta_http_mode_for_small_dataset(client):
    body = client.get("/api/meta").json()
    assert body["use_websocket"] is False


# ---------------------------------------------------------------------------
# /api/data — HTTP mode (CSV)
# ---------------------------------------------------------------------------

def test_data_endpoint_returns_200(client):
    r = client.get("/api/data")
    assert r.status_code == 200


def test_data_endpoint_content_type(client):
    r = client.get("/api/data")
    assert "text/csv" in r.headers["content-type"]


def test_data_endpoint_content_length_set(client):
    r = client.get("/api/data")
    assert "content-length" in r.headers
    assert int(r.headers["content-length"]) > 0


def test_data_endpoint_content_length_matches_body(client):
    r = client.get("/api/data")
    assert int(r.headers["content-length"]) == len(r.content)


def test_data_endpoint_has_header_row(client, small_df):
    r = client.get("/api/data")
    header = r.text.split("\n")[0]
    for col in small_df.columns:
        assert col in header


def test_data_endpoint_correct_row_count(client):
    r = client.get("/api/data")
    data_lines = [l for l in r.text.split("\n")[1:] if l]
    assert len(data_lines) == 200


def test_data_endpoint_correct_values(client):
    r = client.get("/api/data")
    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    assert rows[0]["id"] == "1"
    assert rows[-1]["id"] == "200"
    assert rows[0]["name"] == "User_001"


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------

def test_websocket_sends_meta(small_df):
    engine = TurboEngine(small_df)
    app    = create_dashboard_app(engine, title="WS Test", chunk_size=50)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"]       == "meta"
        assert msg["total"]      == 200
        assert msg["chunk_size"] == 50
        assert msg["chunks"]     == 4   # 200 / 50 = 4


def test_websocket_sends_data_chunks(small_df):
    """Every chunk message must carry a CSV string with correct column headers."""
    engine = TurboEngine(small_df)
    app    = create_dashboard_app(engine, title="WS Test", chunk_size=100)
    client = TestClient(app)

    chunk_count = 0
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()   # meta
        for _ in range(100):
            try:
                raw = ws.receive()
                text = raw.get("text", "")
                if not text:
                    continue
                msg = json.loads(text)
                if msg.get("type") == "chunk":
                    chunk_count += 1
                    assert isinstance(msg["data"], str), "chunk data must be a CSV string"
                    header_line = msg["data"].split("\n")[0]
                    for col in small_df.columns:
                        assert col in header_line
                elif msg.get("type") == "complete":
                    break
            except Exception:
                break
    assert chunk_count >= 1


def test_websocket_sends_complete_message(small_df):
    engine = TurboEngine(small_df)
    app    = create_dashboard_app(engine, title="WS Test", chunk_size=200)
    client = TestClient(app)

    complete_received = False
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()   # meta
        for _ in range(20):
            try:
                raw = ws.receive()
                text = raw.get("text", "")
                if text:
                    msg = json.loads(text)
                    if msg.get("type") == "complete":
                        complete_received = True
                        assert msg["total"] == 200
                        break
            except Exception:
                break
    assert complete_received


def test_websocket_progress_messages(small_df):
    engine = TurboEngine(small_df)
    app    = create_dashboard_app(engine, title="WS Test", chunk_size=50)
    client = TestClient(app)

    progress_msgs = []
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()   # meta
        for _ in range(50):
            try:
                raw = ws.receive()
                text = raw.get("text", "")
                if text:
                    msg = json.loads(text)
                    if msg.get("type") == "progress":
                        progress_msgs.append(msg)
                    elif msg.get("type") == "complete":
                        break
            except Exception:
                break

    assert len(progress_msgs) >= 1
    for m in progress_msgs:
        assert "chunk"        in m
        assert "total_chunks" in m
        assert "rows_loaded"  in m


# ---------------------------------------------------------------------------
# HTML template unit tests (perspective_ui.py)
# ---------------------------------------------------------------------------

def test_build_html_contains_cdn():
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=100,
        chunk_size=50, use_websocket=False,
    )
    assert "cdn.jsdelivr.net" in html
    assert "perspective" in html.lower()


def test_build_html_injects_total_rows():
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=12345,
        chunk_size=50, use_websocket=False,
    )
    assert "12345" in html


def test_build_html_http_mode_uses_api_data():
    """HTTP mode must fetch from /api/data, not /api/arrow."""
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=100,
        chunk_size=50, use_websocket=False,
    )
    assert "/api/data" in html
    assert "/api/arrow" not in html


def test_build_html_ws_mode_flag():
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=600_000,
        chunk_size=50_000, use_websocket=True,
    )
    assert "USE_WS" in html
    assert "true" in html


def test_build_html_schema_json():
    schema = {"price": "Float64", "name": "String", "qty": "Int32"}
    html = build_perspective_html(
        title="T", schema=schema, total_rows=10,
        chunk_size=10, use_websocket=False,
    )
    assert "price" in html
    assert "float" in html     # polars Float64 → perspective 'float'
    assert "string" in html    # polars String  → perspective 'string'


def test_build_html_col_count_injected():
    schema = {"a": "Int64", "b": "String", "c": "Float32"}
    html = build_perspective_html(
        title="T", schema=schema, total_rows=10,
        chunk_size=10, use_websocket=False,
    )
    assert "3" in html


def test_build_html_ws_uses_csv_chunks():
    """WebSocket handler must look for type=='chunk' with CSV data, not ArrayBuffer."""
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=600_000,
        chunk_size=50_000, use_websocket=True,
    )
    assert "chunk" in html
    assert "ArrayBuffer" not in html


def test_build_html_table_from_csv_string():
    """Table must be created from the CSV string directly, not from a JS object.

    worker.table(jsObject) triggers JS→Arrow encoding (Utf8View / type 24 crash).
    worker.table(csvString) routes to the C++ CSV parser — no Arrow encoding.
    """
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=100,
        chunk_size=50, use_websocket=False,
    )
    assert "worker.table(csvData)" in html       # HTTP mode: CSV string
    assert "worker.table(PSP_SCHEMA)" not in html  # schema-object form must be absent


def test_build_html_strips_csv_header():
    """JS must strip the CSV header before calling table.update()."""
    html = build_perspective_html(
        title="T", schema={"a": "Int64"}, total_rows=100,
        chunk_size=50, use_websocket=False,
    )
    assert "stripCsvHeader" in html


# ---------------------------------------------------------------------------
# TurboDashboard class
# ---------------------------------------------------------------------------

def test_turbodashboard_repr(small_df):
    dash = TurboDashboard(small_df, title="Test")
    r = repr(dash)
    assert "TurboDashboard" in r
    assert "Test" in r
    assert "Perspective" in r


def test_turbodashboard_head(small_df):
    dash = TurboDashboard(small_df)
    head = dash.head(5)
    assert isinstance(head, pl.DataFrame)
    assert len(head) == 5


def test_turbodashboard_schema(small_df):
    dash = TurboDashboard(small_df)
    s = dash.schema()
    assert isinstance(s, dict)
    assert "id" in s


def test_turbodashboard_describe(small_df):
    dash = TurboDashboard(small_df)
    desc = dash.describe()
    assert isinstance(desc, pl.DataFrame)
