# Laneway — Product Specification

A minimal, single-user Kanban board. One board, three fixed lanes, drag-and-drop cards.

**Version:** 1.0 · **Status:** approved for implementation

---

## 1. Purpose

Laneway is a personal task board. The user drops tasks into a lane, drags them
across as work progresses, and sees everything on one screen with no setup, no
login, and no project hierarchy.

**Non-goals (explicitly out of scope for v1):** authentication, multiple boards,
custom lanes, real-time multi-user sync, comments, attachments, subtasks,
notifications, card assignees.

## 2. Users

A single user on a single device. No accounts, no permissions. Any client that
reaches the backend sees and edits the same one board.

## 3. Domain model

### Board

There is exactly one board. It is implicit — not a resource the user creates,
lists, or deletes.

### Lane

Three fixed lanes, in this order, identified by a stable enum:

| id | Display name |
|----|--------------|
| `todo` | To Do |
| `doing` | In Progress |
| `done` | Done |

Lanes cannot be added, renamed, reordered, or removed.

### Card

| Field | Type | Rules |
|-------|------|-------|
| `id` | string (uuid) | Server-generated, immutable |
| `title` | string | **Required.** 1–200 chars, trimmed, non-empty after trim |
| `description` | string | Optional. 0–2000 chars. Defaults to `""` |
| `labels` | string[] | Optional. 0–10 items, each 1–30 chars, trimmed, de-duplicated case-insensitively, order preserved |
| `due_date` | date (`YYYY-MM-DD`) or null | Optional. Date only, no time, no timezone |
| `lane` | enum (`todo`\|`doing`\|`done`) | **Required.** Defaults to `todo` on create |
| `position` | integer | Rank within its lane, ascending. Server-managed |
| `created_at` | datetime (UTC, ISO 8601) | Server-generated, immutable |
| `updated_at` | datetime (UTC, ISO 8601) | Server-managed, bumped on every mutation |

### Ordering

Within a lane, cards are ordered by `position` ascending. `position` values are
contiguous integers starting at 0 and are renormalized by the server after every
move so no gaps or ties exist. A new card is appended to the end of `todo`.

## 4. Features

### F1 — View the board

The board loads all lanes and all cards in one request. Each lane renders as a
column with its display name and a count of the cards it holds. An empty lane
shows a placeholder, not a blank space.

### F2 — Create a card

An "Add card" affordance at the bottom of each lane opens an inline composer.
Title is required; the save action stays disabled while the title is empty.
Description, labels, and due date are editable in the composer. On save the card
appends to the end of that lane. `Esc` cancels; `Enter` saves a
title-only card.

### F3 — Edit a card

Clicking a card opens a detail panel where title, description, labels, and due
date can be changed. Saving with an empty title is rejected. Cancel discards.

### F4 — Delete a card

The card detail panel offers delete, behind a confirmation step. Deletion is
permanent; remaining cards in that lane renormalize to close the gap.

### F5 — Move a card (drag and drop)

A card can be dragged within its lane to reorder, or into another lane to change
its `lane`. The drop target is visibly indicated during the drag. On drop the
client optimistically reorders and issues a single move request; a failed request
rolls the board back to the server's state and surfaces an error.

Keyboard support: a focused card can be moved with the arrow keys while the
drag-and-drop library's keyboard sensor is active.

### F6 — Labels

Labels are free-text tags entered in the composer or detail panel. Each renders
as a chip on the card face. A label's chip color is derived deterministically
from its text, so the same tag always looks the same. Duplicates within one card
are rejected silently (case-insensitive).

### F7 — Due dates

A card with a `due_date` shows it on the card face. A due date strictly before
today is styled as overdue; today is styled as due-today. Cards in the `done`
lane are never styled as overdue.

### F8 — Persistence

All state lives on the server. A page refresh, or a second browser tab, shows the
same board. The client holds no authoritative state.

## 5. API contract

REST over JSON, served under `/api`. `openapi.yaml` at the repository root is the
source of truth once written; this section defines its shape.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/board` | The whole board: lanes with their cards, ordered |
| `POST` | `/api/cards` | Create a card |
| `GET` | `/api/cards/{id}` | Read one card |
| `PATCH` | `/api/cards/{id}` | Update title / description / labels / due_date |
| `POST` | `/api/cards/{id}/move` | Move: `{ "lane": "doing", "position": 2 }` |
| `DELETE` | `/api/cards/{id}` | Delete a card |
| `GET` | `/api/health` | Liveness probe |

Conventions:

- `422` for validation failures, with a field-level error body.
- `404` for an unknown card id.
- `204` with no body for a successful delete.
- Move is its own endpoint, not a `PATCH`, because it has side effects on the
  positions of sibling cards.
- A `position` beyond the end of the target lane clamps to the end. A negative
  `position` clamps to 0.

## 6. Architecture

```
frontend/   React + Vite + TypeScript
            src/api/  — every backend call lives here, nowhere else
backend/    FastAPI, managed by uv
            SQLAlchemy over SQLite; the storage layer is database-agnostic
```

The frontend reaches the backend only through the single module under
`src/api/`. In the prototype phase that module is backed by an in-memory mock so
the UI is fully usable before any backend exists; swapping to real HTTP touches
that module and nothing else.

The backend keeps persistence behind a repository interface. Phase 1 implements
it in memory; phase 2 implements it with SQLAlchemy. No route handler talks to
the database directly.

## 7. Quality requirements

- Backend endpoints are covered by tests written before their implementation.
- The test suite runs against the in-memory repository and, for the storage
  layer, against a temporary SQLite database.
- Validation rules in section 3 are enforced server-side and mirrored in the UI.
- The board renders and is operable at 1280px and at 375px width.

## 8. Milestones

1. Spec committed (this document).
2. Frontend prototype against the mocked API module.
3. `openapi.yaml` derived from the prototype's needs.
4. FastAPI backend with a mock repository, tests first.
5. Frontend wired to the live backend, verified in a browser.
6. SQLAlchemy + SQLite behind the repository interface, tests still green.
