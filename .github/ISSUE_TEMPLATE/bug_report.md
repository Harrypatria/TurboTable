---
name: Bug Report
about: Something isn't working as expected
title: "[BUG] "
labels: bug
assignees: harrypatria
---

## Describe the Bug

A clear and concise description of what the bug is.

## Steps to Reproduce

```python
# Minimal reproducible example
from turbotable import TurboTable
import polars as pl

df = pl.DataFrame({"col": [1, 2, 3]})
TurboTable(df).show()
# describe what you expected vs what happened
```

## Expected Behaviour

What you expected to happen.

## Actual Behaviour

What actually happened. Include the **full error traceback** if applicable.

```
Paste traceback here
```

## Environment

| Item | Version |
|------|---------|
| TurboTable | e.g. 1.0.0 |
| Python | e.g. 3.11.5 |
| Polars | e.g. 0.20.4 |
| FastAPI | e.g. 0.110.0 |
| OS | e.g. Windows 11, macOS 14, Ubuntu 22.04 |

## Additional Context

Any other context, screenshots, or notes.
