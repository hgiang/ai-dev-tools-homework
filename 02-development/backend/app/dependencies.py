"""The repository dependency.

`create_app` overrides this with the store it was handed, which is how tests get
a fresh in-memory repository per test without touching the route code.
"""

from __future__ import annotations

from app.repository import CardRepository


def get_repository() -> CardRepository:  # pragma: no cover - always overridden
    raise RuntimeError(
        "No repository configured. Build the app with create_app(repository=...)."
    )
