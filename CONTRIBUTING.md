# Contributing to TurboTable

Thank you for your interest in contributing! TurboTable is an open project and welcomes
contributions of all kinds — bug fixes, new features, documentation, tests, and ideas.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Report a Bug](#how-to-report-a-bug)
3. [How to Request a Feature](#how-to-request-a-feature)
4. [Development Setup](#development-setup)
5. [Submitting a Pull Request](#submitting-a-pull-request)
6. [Code Style](#code-style)
7. [Testing](#testing)
8. [Commit Message Format](#commit-message-format)

---

## Code of Conduct

By participating in this project you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md). Be respectful and constructive.

---

## How to Report a Bug

1. Search [existing issues](https://github.com/harrypatria/TurboTable/issues) first.
2. If not found, open a new issue using the **Bug Report** template.
3. Include:
   - Python version (`python --version`)
   - Polars version (`python -c "import polars; print(polars.__version__)"`)
   - Full error traceback
   - A minimal reproducible example

---

## How to Request a Feature

1. Search [existing issues](https://github.com/harrypatria/TurboTable/issues) first.
2. Open a new issue using the **Feature Request** template.
3. Describe the use case clearly — what problem does it solve?

---

## Development Setup

```bash
# 1. Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/TurboTable.git
cd TurboTable

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev,demo]"

# 4. Verify everything works
pytest tests/ -v
```

---

## Submitting a Pull Request

1. **Branch** from `main`: `git checkout -b feat/your-feature-name`
2. **Write tests** for any new or changed behaviour (aim to keep coverage ≥ 90 %).
3. **Run the full test suite** and confirm all 80+ tests pass.
4. **Update the docstring** of any public function you change.
5. **Add a changelog entry** in `CHANGELOG.md` under `[Unreleased]`.
6. **Open the PR** against `main` with a clear description and link to any related issue.

PRs that add tests are much more likely to be merged quickly.

---

## Code Style

- **Formatter**: [Ruff](https://docs.astral.sh/ruff/) with `line-length = 100`.
- **Docstrings**: NumPy style (Parameters / Returns / Raises sections).
- **Type hints**: Required on all public functions and methods.
- **No silent exceptions**: Use `logger.warning()` instead of bare `except: pass`.

Run the formatter before committing:
```bash
pip install ruff
ruff format .
ruff check .
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pip install pytest-cov
pytest tests/ --cov=turbotable --cov-report=term-missing
```

Every PR **must** keep the test suite green. New behaviour **must** have tests.

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]
[optional footer]
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

Examples:
```
feat(engine): add multi-column OR search via ?q= parameter
fix(server): return HTTP 400 for invalid JSON in filters param
docs(readme): add Colab usage section
test(engine): add negative start_row edge case
```

---

## Questions?

Open a [Discussion](https://github.com/harrypatria/TurboTable/discussions) or reach out
via the Issues page. We aim to respond within 48 hours.

Thank you for making TurboTable better!

— Dr Harry Patria, Chief Data AI, Patria & Co.
