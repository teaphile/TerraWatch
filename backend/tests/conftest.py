"""Shared pytest configuration.

The test-suite must be deterministic and must not depend on third-party
services being reachable. These defaults are applied before ``app.config``
is imported, so every test exercises the offline/fallback paths. Individual
tests that need different behaviour monkeypatch the services explicitly.
"""

import os

os.environ.setdefault("OPEN_METEO_ENABLED", "false")
os.environ.setdefault("USGS_API_ENABLED", "false")
os.environ.setdefault("CACHE_PERSIST", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
