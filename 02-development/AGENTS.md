# AGENTS.md — Laneway

Instructions for AI coding agents working in this directory.

## What this is

`Laneway`, a single-user Kanban board. The product specification in
[`_docs/specs.md`](_docs/specs.md) is authoritative: implement what it says, and
if a request conflicts with it, say so rather than silently diverging. When the
spec is genuinely silent on something, pick the simpler option and note the
choice.

Once `openapi.yaml` exists it is the contract between frontend and backend.
Neither side may drift from it; change the contract first, then both sides.

## Stack and conventions

- **Frontend:** React + Vite + TypeScript in `frontend/`. Every call that
  crosses to the backend lives in `frontend/src/api/` — components never call
  `fetch` directly. Drag and drop uses `@dnd-kit`.
- **Backend:** FastAPI in `backend/`, dependencies managed with `uv` only
  (`uv add`, `uv sync`, `uv run`) — never `pip install`.
- **Persistence:** behind a repository interface. Route handlers never touch the
  database or the ORM session directly.
- Times are UTC and ISO 8601. Due dates are date-only strings (`YYYY-MM-DD`).

## Tests

Write tests before the implementation for backend endpoints, as the spec
requires. Run them with:

```bash
cd backend && uv run pytest
```

Do not mark work complete while tests fail. Do not delete or weaken a failing
test to make the suite pass — fix the code, or explain why the test is wrong.

## Git

Commit after each completed step, from the repository root.

```bash
git add 02-development
git commit -m "<type>: <imperative summary>"
git push
```

Rules:

- Conventional Commit prefixes: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- Subject in the imperative mood, under 72 characters, no trailing period.
- One logical change per commit. Never bundle a refactor with a feature.
- Never `git push --force`, never rewrite pushed history, never amend a pushed
  commit.
- Never commit secrets, `.env` files, `node_modules/`, `.venv/`, or `*.db`.
- Do not add "Co-authored-by" or tool-attribution trailers.
- Ask before any destructive operation (`reset --hard`, `clean -fd`,
  branch deletion).

To report the hash of the commit just made:

```bash
git rev-parse HEAD
```

## Working style

- Prefer editing existing files over creating new ones.
- No new dependency without saying what it is for.
- No README or docs file unless it was asked for — this file and `_docs/` aside.
- Keep changes scoped to what was requested.
