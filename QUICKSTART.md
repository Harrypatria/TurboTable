# ⚡ TurboTable — Quick Start Guide

**From zero to a live 1-million-row interactive table in your browser — step by step.**

No prior experience with FastAPI or Polars required.
If you can run `python --version` you can run TurboTable.

---

## Table of Contents

1. [What You Will Get](#1-what-you-will-get)
2. [Prerequisites](#2-prerequisites)
3. [Step 1 — Check Python](#step-1--check-python)
4. [Step 2 — Get the Code](#step-2--get-the-code)
5. [Step 3 — Create a Virtual Environment](#step-3--create-a-virtual-environment)
6. [Step 4 — Install Dependencies](#step-4--install-dependencies)
7. [Step 5 — Run the 1M-Row Demo](#step-5--run-the-1m-row-demo)
8. [Step 6 — Use With Your Own Data](#step-6--use-with-your-own-data)
9. [Step 7 — Jupyter Notebook](#step-7--jupyter-notebook)
10. [Step 8 — Google Colab](#step-8--google-colab)
11. [Understanding the Browser UI](#understanding-the-browser-ui)
12. [Understanding the Folder Structure](#understanding-the-folder-structure)
13. [Common Errors & Fixes](#common-errors--fixes)
14. [Running the Tests](#running-the-tests)

---

## 1. What You Will Get

A **live web app** like this, running at `http://localhost:8765`:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⚡ Sales Analytics — 1M Rows    Rows: 1,000,000  Cols: 15  Query: 12ms │
├─────────────────────────────────────────────────────────────────────────┤
│  [🔍 Search all text columns…]  [✕ Clear]  [↓ CSV]  [↓ JSON]  [📊]    │
├─────────────┬──────────────────┬────────────┬───────────┬───────────────┤
│  Order Id   │  Customer Name   │  Category  │  Revenue  │  Status       │
├─────────────┼──────────────────┼────────────┼───────────┼───────────────┤
│ ORD-000001  │  Alice Smith     │ Electronics│  4231.00  │ Completed     │
│ ORD-000002  │  Bob Jones       │ Apparel    │   812.50  │ Pending       │
│  …          │  …               │  …         │  …        │  …            │
└─────────────┴──────────────────┴────────────┴───────────┴───────────────┘
  Rows 1–100 of 1,000,000           Page 1 / 10,000         Query 11 ms
```

**What you can do in the browser:**
- Sort any column by clicking its header
- Filter each column individually with the header row inputs
- Search across *all* text columns at once with the search bar (OR logic)
- Export the current filtered/sorted view to CSV or JSON
- View min / max / mean statistics for every column

---

## 2. Prerequisites

| Requirement | Minimum version | How to get it |
|---|---|---|
| Python | 3.10 | [python.org/downloads](https://www.python.org/downloads/) |
| pip | any recent | Comes with Python |
| A terminal | — | Windows: Command Prompt or PowerShell · Mac/Linux: Terminal |
| A web browser | — | Chrome, Firefox, Edge, or Safari |

> **Windows users:** every command below works in Command Prompt, PowerShell, and Git Bash.

---

## Step 1 — Check Python

Open a terminal and run:

```bash
python --version
```

You need **Python 3.10 or newer**. If you see `Python 2.x` or an error, install a new
version from [python.org](https://www.python.org/downloads/) and tick
**"Add Python to PATH"** during installation.

Check pip is available:
```bash
pip --version
```

---

## Step 2 — Get the Code

### Option A — Git clone (recommended)
```bash
git clone https://github.com/harrypatria/TurboTable.git
cd TurboTable
```

### Option B — Download ZIP (no Git needed)
1. Go to `https://github.com/harrypatria/TurboTable`
2. Click **Code → Download ZIP**
3. Extract it, then open a terminal in the extracted folder:
   ```bash
   # Windows example
   cd C:\Projects\TurboTable

   # Mac / Linux example
   cd ~/Projects/TurboTable
   ```

Confirm you are in the right place — you should see `pyproject.toml` listed:
```bash
# Windows
dir

# Mac / Linux
ls
```

---

## Step 3 — Create a Virtual Environment

A virtual environment keeps TurboTable's packages isolated from your system Python.

```bash
python -m venv .venv
```

**Activate it:**

```bash
# Windows — Command Prompt
.venv\Scripts\activate.bat

# Windows — PowerShell
.venv\Scripts\Activate.ps1

# Mac / Linux
source .venv/bin/activate
```

Your prompt changes to show `(.venv)` — that means it is active.
To deactivate later, type `deactivate`.

> **PowerShell policy error?**
> Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
> then try activating again.

---

## Step 4 — Install Dependencies

With `.venv` active:

```bash
pip install polars fastapi "uvicorn[standard]" numpy
```

| Package | Role |
|---|---|
| `polars` | Query engine — reads files, filters, sorts at lightning speed |
| `fastapi` | REST API that the browser talks to |
| `uvicorn` | Web server that runs FastAPI |
| `numpy` | Used by the data generator |

**Verify:**
```bash
python -c "import polars, fastapi, uvicorn; print('Dependencies OK')"
```

Expected output: `Dependencies OK`

---

## Step 5 — Run the 1M-Row Demo

### 5a — Generate synthetic data (run once, ~4 seconds)

```bash
cd demo
python generate_data.py
```

Output:
```
  Generating 1,000,000 rows (seed=42) …
  Built in 3.1s  (1,000,000 rows × 15 cols)
  Writing CSV  → data/sales_1m.csv …
  CSV saved in 2.0s  (144.2 MB)
  Writing Parquet → data/sales_1m.parquet …
  Parquet saved in 0.6s  (18.4 MB)
```

The Parquet file is 8× smaller and loads much faster — TurboTable uses it automatically.

**Want fewer rows for a quick test?**
```bash
python generate_data.py --rows 100000
```

### 5b — Launch TurboTable

```bash
python demo_app.py
```

Output:
```
  Loading data/sales_1m.parquet …
  TurboTable(title='Sales Analytics — 1 M Rows', cols=15, engine=Polars/1.x.x)

  TurboTable ⚡  →  http://localhost:8765
  Press Ctrl-C to stop.
```

**Open your browser at `http://localhost:8765`.**

The table appears. Try clicking a column header to sort, or typing in the search box.

**To stop:** press `Ctrl + C` in the terminal.

---

## Step 6 — Use With Your Own Data

Create a file, for example `my_table.py`, in the `TurboTable/` root folder:

### From a CSV file
```python
from turbotable import TurboTable

TurboTable("path/to/your_data.csv", title="My Data").show()
```

### From a Parquet file (faster for large data)
```python
from turbotable import TurboTable

TurboTable("path/to/your_data.parquet").show()
```

### From a Polars DataFrame
```python
import polars as pl
from turbotable import TurboTable

df = pl.read_csv("sales.csv")

# Optionally filter or transform first
df_filtered = df.filter(pl.col("revenue") > 1000)

TurboTable(df_filtered, title="High Revenue Orders").show()
```

### Custom port (if 8765 is in use)
```python
TurboTable("data.csv").show(port=9000)
# → http://localhost:9000
```

### Expose on your local network (let colleagues access it)
```python
TurboTable("data.csv").show(host="0.0.0.0", port=8765)
# Others on the same WiFi visit http://YOUR_IP:8765
```

Run it:
```bash
python my_table.py
```

---

## Step 7 — Jupyter Notebook

TurboTable runs as a **background server** so your notebook stays responsive.

### Install Jupyter (if needed)
```bash
pip install jupyter
```

### Start Jupyter
```bash
jupyter notebook
```

### In notebook cells

```python
# Cell 1 — Add TurboTable to the path (if not installed as a package)
import sys
sys.path.insert(0, "../")   # adjust to where TurboTable/ folder lives
```

```python
# Cell 2 — Load data and start TurboTable
import polars as pl
from turbotable import TurboTable

df = pl.read_csv("your_data.csv")
tt = TurboTable(df, title="My Notebook Table")

# blocking=False → runs in a daemon thread, cell finishes immediately
tt.show(port=8765, blocking=False, open_browser=True)
```

```python
# Cell 3 — Stop the server when you are done
tt.stop()
```

> The server automatically stops when you restart the Jupyter kernel.

---

## Step 8 — Google Colab

Colab doesn't allow direct `localhost` access, but you can create a public tunnel with ngrok.

### Setup (once per Colab session)

```python
# Cell 1 — Install
!pip install polars fastapi "uvicorn[standard]" pyngrok -q

# Cell 2 — Authenticate ngrok (free account at ngrok.com)
from pyngrok import ngrok
ngrok.set_auth_token("YOUR_NGROK_TOKEN_HERE")
```

```python
# Cell 3 — Upload your data or create a DataFrame
import polars as pl
import sys

# If running from a Colab upload:
# from google.colab import files
# files.upload()

df = pl.DataFrame({
    "product": ["Widget A", "Widget B", "Gadget X"] * 100_000,
    "price":   [9.99, 24.50, 149.0] * 100_000,
    "units_sold": [120, 45, 8] * 100_000,
})
```

```python
# Cell 4 — Start TurboTable with a public ngrok tunnel
sys.path.insert(0, "/content/TurboTable")   # adjust path

from turbotable import TurboTable

tt = TurboTable(df, title="Colab Demo")
tt.show(host="0.0.0.0", port=8765, open_browser=False, blocking=False)

public_url = ngrok.connect(8765)
print(f"\n  Open this URL: {public_url}\n")
```

```python
# Cell 5 — Stop when done
tt.stop()
ngrok.kill()
```

---

## Understanding the Browser UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HEADER BAR                                                                  │
│  ⚡ Title  [Polars · FastAPI]   Rows: 1,000,000  Cols: 15  Query: 12ms      │
│  ↑ Shows live stats after each query: total rows, column count, load time   │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOOLBAR                                                                     │
│  [🔍 Search all text columns…]  [✕ Clear]  [↓ CSV]  [↓ JSON]  [📊]  [📖]  │
│  ↑ Global search      ↑ Reset   ↑ Export    ↑ Export ↑ Stats   ↑ API docs  │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│  TABLE                                                                       │
│  Column headers → click to sort (click again to reverse)                    │
│  Filter row     → type here to filter that column (AND logic)               │
│  Rows           → only 100 loaded at a time; the rest stay on the server    │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│  PAGINATION BAR    ◀  1  2  3 … 10 000  ▶    100 rows/page ▼               │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│  STATUS BAR   Rows 1–100 of 1,000,000    Page 1 / 10,000    Query 12ms     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Searching vs Filtering — what's the difference?

| Feature | What it does | Logic |
|---|---|---|
| **Global search box** | Searches across *all* text columns at once | OR — row matches if *any* column contains the term |
| **Column header filters** | Filters one column at a time | AND — all active filters must match |

You can combine both: e.g. search for `"Alice"` and also filter `category = Electronics`.

### Filter operators by column type

| Column type | Input | Matches |
|---|---|---|
| Text (String) | Any text | Any row where the column *contains* that text |
| Number (Int/Float) | A number | Exact equality; use the API for `>`, `<` etc. |

### Toolbar buttons

| Button | Action |
|---|---|
| **✕ Clear** | Removes all header filters and global search |
| **↓ CSV** | Downloads currently visible rows as CSV |
| **↓ JSON** | Downloads currently visible rows as JSON |
| **📊 Stats** | Opens statistics popup (min/max/mean for all columns) |
| **📖 API** | Opens interactive FastAPI docs at `/docs` |

---

## Understanding the Folder Structure

```
TurboTable/                 ← Root (clone this)
│
├── turbotable/             ← The Python library (import this)
│   ├── __init__.py         ← TurboTable class — the only thing you need to import
│   ├── engine.py           ← All Polars query logic
│   ├── server.py           ← FastAPI routes + background server
│   └── ui.py              ← Complete browser UI as a Python string
│
├── demo/                   ← Example application
│   ├── generate_data.py    ← Creates the 1M-row CSV + Parquet
│   ├── demo_app.py         ← Launches TurboTable on the demo data
│   └── data/              ← Generated files (created when you run step 5)
│       ├── sales_1m.csv
│       └── sales_1m.parquet
│
├── tests/                  ← Automated tests (80 tests, always green)
│   ├── test_engine.py      ← 50 unit tests for the query engine
│   └── test_server.py      ← 30 integration tests for the REST API
│
├── .github/
│   ├── workflows/test.yml  ← CI runs on every push (Python 3.10–3.13)
│   ├── ISSUE_TEMPLATE/     ← Bug & feature request forms
│   └── pull_request_template.md
│
├── CHANGELOG.md            ← Version history
├── CONTRIBUTING.md         ← How to contribute
├── CODE_OF_CONDUCT.md
├── SECURITY.md             ← How to report security issues
├── LICENSE                 ← MIT, Dr Harry Patria
├── pyproject.toml          ← Package metadata (pip install)
└── README.md               ← Technical reference
```

**The key insight:** you only ever use the `TurboTable` class. Everything else — Polars
queries, FastAPI routes, HTML/JS — is handled automatically inside the library.

---

## Common Errors & Fixes

### `ModuleNotFoundError: No module named 'turbotable'`

**Fix A** — Run from inside the `TurboTable/` folder:
```bash
cd TurboTable
python my_table.py
```

**Fix B** — Install as a package (works from anywhere):
```bash
cd TurboTable
pip install -e .
```

---

### `OSError: [Errno 98] Address already in use`

Another process is using port 8765.

**Fix** — Use a different port:
```python
TurboTable("data.csv").show(port=9000)
```

Or kill the existing process:
```bash
# Windows
netstat -ano | findstr :8765
taskkill /PID <NUMBER> /F

# Mac / Linux
lsof -ti:8765 | xargs kill
```

---

### `FileNotFoundError: data/sales_1m.parquet`

You haven't generated the demo data yet.

**Fix:**
```bash
cd demo
python generate_data.py
```

---

### Browser shows "Connection refused" or blank page

**Fix:**
1. Check the terminal still shows `TurboTable ⚡ → http://localhost:8765`
2. Wait 2–3 seconds after launching, then refresh the browser
3. Make sure you opened `http://localhost:8765` (not `https://`)

---

### The table shows no rows after searching

**If using the global search box:** this searches across all text columns with OR logic.
Check you are not also using a column filter that conflicts.

Click **✕ Clear** to reset everything.

---

### `pip` is not recognised

**Fix (Windows):**
Use `py -m pip` instead of `pip`:
```bash
py -m pip install polars fastapi uvicorn
```

Or reinstall Python and tick **"Add Python to PATH"**.

---

### PowerShell blocks virtual environment activation

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

---

## Running the Tests

Confirms everything is working after installation or code changes.

```bash
# Install test deps (once)
pip install httpx pytest

# Run all 80 tests
cd TurboTable
pytest tests/ -v
```

Expected result:
```
========================= 80 passed in 7.8s =========================
```

---

## Next Steps

Once comfortable with the basics:

1. Read **`README.md`** — full API reference and REST endpoint documentation
2. Open **`http://localhost:8765/docs`** — interactive API explorer (when server is running)
3. Explore **`turbotable/engine.py`** — see how Polars lazy queries work
4. Read **`CONTRIBUTING.md`** — help make TurboTable better

---

*Built with Polars · FastAPI · Tabulator 6 · Python 3.10+*

*Author: **Dr Harry Patria**, Chief Data AI — Patria & Co.*
