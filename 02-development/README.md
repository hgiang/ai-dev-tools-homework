# Laneway

A minimal single-user Kanban board — one board, three fixed lanes
(To Do / In Progress / Done), drag-and-drop cards with labels and due dates.

Homework 2 of the [AI Dev Tools Zoomcamp](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).

Full specification: [`_docs/specs.md`](_docs/specs.md)

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + TypeScript |
| Backend | FastAPI, managed with `uv` |
| Database | SQLite via SQLAlchemy |

## Layout

```
frontend/          React app; all backend calls live in src/api/
backend/           FastAPI app; persistence behind a repository interface
openapi.yaml       API contract between the two
_docs/specs.md     Product specification
```

## Running

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves on http://localhost:5173

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Serves on http://localhost:8000 — interactive docs at `/docs`.

## Testing

```bash
cd backend
uv run pytest
```

## Status

- [x] Spec written
- [x] Frontend prototype (mocked API)
- [ ] OpenAPI contract
- [ ] FastAPI backend (mock repository)
- [ ] Frontend connected to backend
- [ ] SQLAlchemy + SQLite
