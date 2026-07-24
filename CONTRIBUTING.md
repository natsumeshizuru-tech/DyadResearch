# Contributing

Use Python 3.12, install `.[research,web,dev]`, and run Ruff, strict mypy, and pytest before proposing a change. New research must include deterministic tests, a data fingerprint, point-in-time assumptions, limitations, and an honest reproduction classification.

Never commit vendor data, SQLite databases, QMT caches, credentials, absolute local paths, full research PDFs, or account information. Test fixtures must be generated synthetic data or clearly licensed public data.
