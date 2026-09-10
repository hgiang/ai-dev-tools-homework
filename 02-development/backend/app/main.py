"""Application factory and the module-level app uvicorn serves."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.dependencies import get_repository
from app.domain import CardNotFound
from app.repository import CardRepository, InMemoryCardRepository
from app.routes import router

# The Vite dev server runs on a different origin during development.
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(repository: CardRepository | None = None) -> FastAPI:
    app = FastAPI(
        title="Laneway API",
        version="1.0.0",
        description="A single-user Kanban board: one board, three fixed lanes.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = repository if repository is not None else InMemoryCardRepository()
    app.dependency_overrides[get_repository] = lambda: store

    @app.exception_handler(CardNotFound)
    async def _card_not_found(_: Request, exc: CardNotFound) -> JSONResponse:
        """Keeps `raise CardNotFound` in the repository from leaking as a 500."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    app.include_router(router)
    return app


app = create_app()
