# Pushing TurboTable to GitHub

Step-by-step guide to publish this project to **https://github.com/Harrypatria/TurboTable**.

---

## Prerequisites

- Git is installed (`git --version`)
- GitHub CLI (`gh`) is installed — already installed at `C:\Program Files\GitHub CLI\gh.exe`

---

## Step 1 — Authenticate with GitHub CLI

Open a terminal and run:

```bash
gh auth login
```

When prompted, select:
1. **GitHub.com**
2. **HTTPS**
3. **Login with a web browser**

A one-time code appears in the terminal. The browser opens — paste the code and click **Authorize**.

Verify login:

```bash
gh auth status
```

Expected output:
```
Logged in to github.com as Harrypatria
```

---

## Step 2 — Create the new GitHub repository

```bash
cd "C:\Users\harry\Documents\PC\Convergeni\TurboTable"

gh repo create TurboTable \
  --public \
  --description "Blazing-fast interactive tables and analytics dashboard for millions of rows — Polars + FastAPI + Chart.js" \
  --homepage "https://github.com/Harrypatria/TurboTable"
```

> Use `--private` instead of `--public` if you want a private repo.

---

## Step 3 — Set the remote and push

```bash
cd "C:\Users\harry\Documents\PC\Convergeni\TurboTable"

git remote add origin https://github.com/Harrypatria/TurboTable.git

git push -u origin master
```

---

## All steps in one block (copy-paste)

```bash
cd "C:\Users\harry\Documents\PC\Convergeni\TurboTable"

gh auth login

gh repo create TurboTable \
  --public \
  --description "Blazing-fast interactive tables and analytics dashboard for millions of rows — Polars + FastAPI + Chart.js"

git remote add origin https://github.com/Harrypatria/TurboTable.git
git push -u origin master
```

---

## After pushing — verify

```bash
gh repo view Harrypatria/TurboTable --web
```

This opens the repo in your browser at `https://github.com/Harrypatria/TurboTable`.

---

## Future updates

After making code changes:

```bash
cd "C:\Users\harry\Documents\PC\Convergeni\TurboTable"

git add turbotable/ demo/ tests/
git commit -m "Your change description"
git push
```

---

## What gets pushed

| Path | Contents |
|------|----------|
| `turbotable/` | Core package — engine, dashboard, server, UI |
| `demo/` | `dashboard_app.py`, `demo_app.py`, `generate_data.py` |
| `tests/` | Unit tests |
| `README.md` | Project documentation |
| `QUICKSTART.md` | Quick-start guide |
| `requirements.txt` | Python dependencies |
| `pyproject.toml` | Package metadata |
| `LICENSE` | MIT licence |

The `.gitignore` already excludes:
- `.venv/` — virtual environment
- `demo/data/` — generated parquet/CSV files (too large for GitHub)
- `__pycache__/`, `*.pyc` — compiled Python
- `.env` — secrets

---

## Troubleshooting

**`gh: command not found`**
```bash
export PATH="$PATH:/c/Program Files/GitHub CLI"
```

**`remote origin already exists`**
```bash
git remote remove origin
git remote add origin https://github.com/Harrypatria/TurboTable.git
```

**Authentication prompt on push**
If the browser login didn't persist, use a Personal Access Token:
1. Go to https://github.com/settings/tokens → **Generate new token (classic)**
2. Select scopes: `repo`, `workflow`
3. Copy the token
4. Run: `gh auth login --with-token` and paste the token
