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
backend/
  app/domain.py       lanes, the Card, and the validation limits
  app/schemas.py      wire format, mirrors openapi.yaml
  app/repository.py   CardRepository protocol + the in-memory store
  app/routes.py       the HTTP surface
  app/main.py         create_app() factory
  tests/              board, cards, and move
openapi.yaml       API contract between the two
_docs/specs.md     Product specification
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/board` | The whole board: three lanes with their cards |
| `POST` | `/api/cards` | Create a card |
| `GET` | `/api/cards/{id}` | Read one card |
| `PATCH` | `/api/cards/{id}` | Update title / description / labels / due date |
| `POST` | `/api/cards/{id}/move` | Move to a lane and position |
| `DELETE` | `/api/cards/{id}` | Delete a card |
| `GET` | `/api/health` | Liveness probe |

## Running

Start the backend first — the frontend talks to it on load.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves on http://localhost:5173, and calls the backend at
`http://localhost:8000/api`. Override with `VITE_API_BASE_URL`, or set
`VITE_USE_MOCK_API=true` to run the UI against the in-memory mock instead
(see `.env.example`).

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

39 tests cover the board, card CRUD, the validation rules, and every move case
(reorder, cross-lane, clamping, renormalizing).

## Status

- [x] Spec written
- [x] Frontend prototype (mocked API)
- [x] OpenAPI contract
- [x] FastAPI backend (mock repository)
- [x] Frontend connected to backend
- [ ] SQLAlchemy + SQLite
