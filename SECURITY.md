# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes     |
| < 1.0   | ❌ No      |

## Design Scope

TurboTable is designed for **local and intranet use** — a data scientist or analyst running it
on their own machine or within a trusted network to explore large datasets interactively.

It is **not** designed to be exposed to the public internet as-is. If you deploy it publicly,
review the security considerations below and add appropriate controls.

## Security Considerations

### CORS policy
The default `allow_origins=["*"]` is intentional for local use.
If you expose TurboTable on a public server, restrict this in `server.py`:
```python
app.add_middleware(CORSMiddleware, allow_origins=["https://yourdomain.com"])
```

### No authentication
TurboTable ships without authentication. Add an auth layer (e.g. HTTP Basic via
FastAPI dependencies, or a reverse proxy like nginx with auth) before any public deployment.

### File path access
`TurboEngine` accepts file paths. Only pass paths to files you own and trust.
Do not expose the `source` parameter to untrusted user input.

### HTML injection
`title` is HTML-escaped before rendering (XSS-safe).
Column definitions are JSON-encoded (injection-safe).
Filter values are processed by Polars, not SQL (no SQL injection risk).

### Dependency updates
Keep `polars`, `fastapi`, and `uvicorn` up to date to receive upstream security patches.

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public GitHub issue.

Instead, email: **harry@patriaco.ai**

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You will receive a response within **72 hours**. Confirmed vulnerabilities will be patched
and disclosed in `CHANGELOG.md` with appropriate credit (or anonymously, as you prefer).
