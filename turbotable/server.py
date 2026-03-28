"""
TurboTable — FastAPI application layer.

Exposes a REST API consumed by the embedded Tabulator grid.
All heavy lifting (filter, sort, paginate) is delegated to TurboEngine
which keeps queries inside Polars and never materialises the full dataset.

Author  : Dr Harry Patria — Chief Data AI, Patria & Co.
License : MIT
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from .engine import TurboEngine
from .ui import build_html

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------


def create_app(engine: TurboEngine, title: str = "TurboTable") -> FastAPI:
    """
    Build and return a fully configured FastAPI application.

    Parameters
    ----------
    engine : TurboEngine
        Pre-loaded data engine.
    title  : str
        Page title shown in the browser tab and the Swagger docs.
    """
    app = FastAPI(
        title=title,
        version="1.0.0",
        description=(
            "TurboTable REST API — server-side pagination, sorting, filtering, "
            "and full-text search powered by Polars."
        ),
    )

    # CORS is intentionally open (allow_origins=["*"]) because TurboTable is
    # designed to run locally or in a controlled intranet environment.
    # If you expose this to the internet, restrict allow_origins to your domain.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------
    # UI — serves the self-contained Tabulator SPA
    # ---------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> str:
        return build_html(title=title, schema=engine.schema)

    # ---------------------------------------------------------------
    # Metadata endpoints
    # ---------------------------------------------------------------

    @app.get(
        "/api/schema",
        summary="Column schema",
        description="Returns a mapping of column name → Polars dtype string.",
    )
    def get_schema() -> Dict[str, str]:
        return engine.schema

    @app.get(
        "/api/sample",
        summary="Quick preview",
        description="First N rows of the dataset (no filtering applied).",
    )
    def get_sample(
        n: int = Query(5, ge=1, le=1_000, description="Number of rows to return"),
    ) -> List[Dict[str, Any]]:
        return engine.sample(n).to_dicts()

    # ---------------------------------------------------------------
    # Main data endpoint — consumed by Tabulator AJAX
    # ---------------------------------------------------------------

    @app.get(
        "/api/data",
        summary="Paginated data",
        description=(
            "Returns a page of data after applying column filters, "
            "global search, and sorting. All operations run inside Polars."
        ),
    )
    def get_data(
        page: int = Query(1, ge=1, description="1-based page number"),
        size: int = Query(
            100, ge=1, le=10_000, description="Rows per page (max 10 000)"
        ),
        sort: Optional[str] = Query(None, description="Column name to sort by"),
        sort_dir: str = Query(
            "asc", description="Sort direction: 'asc' or 'desc'"
        ),
        filters: Optional[str] = Query(
            None,
            description=(
                "JSON array of column filter objects: "
                '[{"field": "col", "type": "=", "value": "x"}, ...]'
            ),
        ),
        q: Optional[str] = Query(
            None,
            description=(
                "Global full-text search term. "
                "Matches rows where ANY string column contains this value."
            ),
        ),
    ) -> Dict[str, Any]:
        filter_list: Optional[List[Dict[str, Any]]] = None
        if filters:
            try:
                filter_list = json.loads(filters)
                if not isinstance(filter_list, list):
                    raise ValueError("filters must be a JSON array")
            except (json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid 'filters' parameter: {exc}",
                )

        search_term = q.strip() if q and q.strip() else None

        start = (page - 1) * size
        df = engine.get_view(
            start=start,
            size=size,
            sort_col=sort,
            sort_desc=(sort_dir.lower() == "desc"),
            filters=filter_list,
            search=search_term,
        )
        total = engine.total_rows(filters=filter_list, search=search_term)

        return {
            "last_page": max(1, (total + size - 1) // size),
            "data": df.to_dicts(),
            "total": total,
            "page": page,
            "size": size,
        }

    # ---------------------------------------------------------------
    # Arrow binary endpoint — for high-throughput programmatic clients
    # ---------------------------------------------------------------

    @app.get(
        "/api/data/arrow",
        summary="Paginated data (Apache Arrow IPC)",
        description=(
            "Same query parameters as /api/data but returns raw "
            "Apache Arrow IPC bytes. Typically 5–10× faster than JSON "
            "for numeric-heavy pages."
        ),
        response_class=Response,
    )
    def get_data_arrow(
        page: int = Query(1, ge=1),
        size: int = Query(100, ge=1, le=10_000),
        sort: Optional[str] = Query(None),
        sort_dir: str = Query("asc"),
        filters: Optional[str] = Query(None),
        q: Optional[str] = Query(None),
    ) -> Response:
        filter_list: Optional[List[Dict[str, Any]]] = None
        if filters:
            try:
                filter_list = json.loads(filters)
                if not isinstance(filter_list, list):
                    raise ValueError("filters must be a JSON array")
            except (json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid 'filters' parameter: {exc}",
                )

        search_term = q.strip() if q and q.strip() else None
        start = (page - 1) * size
        arrow_bytes = engine.get_view_arrow(
            start=start,
            size=size,
            sort_col=sort,
            sort_desc=(sort_dir.lower() == "desc"),
            filters=filter_list,
            search=search_term,
        )
        return Response(
            content=arrow_bytes,
            media_type="application/vnd.apache.arrow.stream",
        )

    # ---------------------------------------------------------------
    # Statistics endpoints
    # ---------------------------------------------------------------

    @app.get(
        "/api/stats",
        summary="Dataset statistics",
        description=(
            "Descriptive statistics for all columns (min/max/mean/std/nulls). "
            "Collects the full dataset — may be slow for very large files."
        ),
    )
    def get_stats() -> List[Dict[str, Any]]:
        return engine.describe().to_dicts()

    @app.get(
        "/api/stats/{column}",
        summary="Per-column statistics",
        description=(
            "Targeted statistics for a single column using lazy aggregation. "
            "Much faster than /api/stats for large datasets."
        ),
    )
    def get_column_stats(column: str) -> Dict[str, Any]:
        try:
            return engine.column_stats(column)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    return app


# ---------------------------------------------------------------------------
# Background server (Jupyter / notebook use)
# ---------------------------------------------------------------------------


class TurboServer:
    """
    Runs uvicorn in a daemon thread so ``TurboTable.show(blocking=False)``
    returns immediately inside a Jupyter notebook cell.

    The server is automatically stopped when the Python process exits
    because the thread is a daemon.
    """

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        self._config = uvicorn.Config(
            app, host=host, port=port, log_level="warning"
        )
        self._server = uvicorn.Server(self._config)
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
