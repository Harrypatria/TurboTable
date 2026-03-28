"""
TurboTable
==========
Blazing-fast interactive data tables and dashboards for millions of rows.

Two complementary tools:

TurboTable
    Server-side pagination, filtering, and sorting via Polars + FastAPI.
    Never loads all data — ideal for unlimited row counts.
    Powered by Tabulator 6 (browser grid).

TurboDashboard
    Client-side pivot, filter, and charting via Perspective (C++/WASM).
    Loads all data once via Apache Arrow; all further ops run at native speed.
    Powered by @finos/perspective (Hypergrid + D3FC charts).

Quick start — TurboTable
-------------------------
    from turbotable import TurboTable

    TurboTable("data.csv").show()
    TurboTable("data.parquet", title="Sales").show()

    import polars as pl
    TurboTable(pl.read_parquet("data.parquet")).show()

    # Jupyter / non-blocking
    tt = TurboTable("data.csv")
    tt.show(blocking=False)
    tt.stop()

Quick start — TurboDashboard
------------------------------
    from turbotable import TurboDashboard

    TurboDashboard("data.parquet").show()           # full pivot + charts
    TurboDashboard("data.csv", title="KPI").show()

    # Jupyter / non-blocking
    dash = TurboDashboard("data.parquet")
    dash.show(port=8766, blocking=False)
    dash.stop()

Author
------
Dr Harry Patria
Chief Data AI — Patria & Co.
AI-assisted development.

License : MIT
"""

from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional, Union

import polars as pl
import uvicorn

from .engine import TurboEngine
from .server import TurboServer, create_app
from .dashboard import TurboDashboard

__version__  = "1.1.0"
__author__   = "Dr Harry Patria"
__email__    = "harry@patriaco.ai"
__license__  = "MIT"
__all__      = ["TurboTable", "TurboDashboard"]


class TurboTable:
    """
    One-stop class for loading data and serving an interactive table.

    Parameters
    ----------
    source : str | Path | pl.DataFrame | pl.LazyFrame
        Data source.  Accepts file paths (.csv / .parquet / .json / .ndjson),
        a Polars DataFrame, or a Polars LazyFrame.
    title : str
        Browser-tab / page title. HTML-escaped before rendering.
    """

    def __init__(
        self,
        source: Union[str, Path, pl.DataFrame, pl.LazyFrame],
        title: str = "TurboTable",
    ) -> None:
        self.title  = title
        self.engine = TurboEngine(source)
        self._server: Optional[TurboServer] = None
        self._app   = None

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def show(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        open_browser: bool = True,
        blocking: bool = True,
    ) -> None:
        """
        Start the TurboTable web server and optionally open a browser tab.

        Parameters
        ----------
        host         : Bind address. Use ``"0.0.0.0"`` to expose on the LAN.
        port         : TCP port (default 8765).
        open_browser : Open the default web browser automatically.
        blocking     : If ``True``, run until Ctrl-C. If ``False``, run in a
                       background daemon thread (Jupyter-friendly).
        """
        self._app = create_app(self.engine, title=self.title)

        # When binding to all interfaces show a human-friendly localhost URL.
        display_host = "localhost" if host in ("0.0.0.0", "::") else host
        url = f"http://{display_host}:{port}"

        if blocking:
            if open_browser:
                def _open_after_delay() -> None:
                    time.sleep(0.8)   # give uvicorn a moment to bind
                    webbrowser.open(url)
                threading.Thread(target=_open_after_delay, daemon=True).start()
            print(f"\n  TurboTable ⚡  →  {url}")
            print("  Interactive API docs  →  {url}/docs")
            print("  Press Ctrl-C to stop.\n")
            uvicorn.run(self._app, host=host, port=port, log_level="warning")
        else:
            self._server = TurboServer(self._app, host=host, port=port)
            self._server.start()
            time.sleep(0.6)   # wait for uvicorn to bind before opening browser
            if open_browser:
                webbrowser.open(url)
            print(f"\n  TurboTable ⚡  running in background  →  {url}\n")

    def stop(self) -> None:
        """Stop a background server started with ``blocking=False``."""
        if self._server:
            self._server.stop()
            self._server = None
            print("  TurboTable stopped.")
        else:
            print("  No background server is running.")

    # ------------------------------------------------------------------
    # Convenience query methods (bypass the server entirely)
    # ------------------------------------------------------------------

    def head(self, n: int = 10) -> pl.DataFrame:
        """Return the first *n* rows as a Polars DataFrame."""
        return self.engine.sample(n)

    def schema(self) -> Dict:  # noqa: F821 (Dict resolved at runtime)
        """Return column name → dtype string mapping."""
        return self.engine.schema

    def describe(self) -> pl.DataFrame:
        """Descriptive statistics for the full dataset."""
        return self.engine.describe()

    @property
    def columns(self) -> list:
        """List of column names."""
        return self.engine.columns

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        n_cols = len(self.engine.columns)
        return (
            f"TurboTable(title={self.title!r}, cols={n_cols}, "
            f"engine=Polars/{pl.__version__})"
        )

    def __str__(self) -> str:
        return repr(self)
