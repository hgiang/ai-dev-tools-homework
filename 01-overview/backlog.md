# HouseShare — Implementation Backlog

**Spec:** [`_docs/plan.md`](_docs/plan.md)

Eight tasks, ordered. Each one leaves `main` in a working, demonstrable state:
migrations apply, `manage.py check` is clean, the test suite is green, and there
is something a person can actually look at or use. No task requires a later task
to be useful, and each depends only on tasks above it.

---

## Conventions (apply to every task)

- **TDD.** Write the failing test, watch it fail, implement the minimum, watch it
  pass, commit. Tests run with `uv run python manage.py test`.
- **Coverage.** 80% minimum, measured with `uv run coverage run manage.py test`.
- **Tests as a package,** not one growing `tests.py` — one module per concern
  under `chores/tests/`.
- **No mutation of persisted rows** beyond an explicit status transition.
  `Completion` is append-only; date helpers return new `date` objects.
- **No hardcoded literals** — recurrence kinds and assignment statuses are
  `models.TextChoices`.
- **Validate at the view boundary.** Any member id or assignment id arriving
  from a form is validated before use; unknown ids return 404, not a 500.
- **Small focused modules.** Pure logic lives outside `models.py` (see File Map).

## File Map

| File | Responsibility |
| --- | --- |
| `chores/models.py` | The four models and their `__str__`/`Meta` only |
| `chores/recurrence.py` | Pure date arithmetic: next due date per recurrence |
| `chores/rotation.py` | Pure rotation logic: who is next, ordered active roster |
| `chores/services.py` | Write operations: complete an assignment, roll forward |
| `chores/selectors.py` | Read queries for the dashboard and history buckets |
| `chores/views.py` | HTTP glue: validate input, call a service/selector, render |
| `chores/admin.py` | Admin registration and inlines |
| `chores/urls.py` | App URL patterns, included at `''` by the project |
| `chores/templates/chores/` | `base.html`, `dashboard.html`, `history.html` |
| `chores/tests/` | One module per concern: `test_members.py`, `test_chores.py`, `test_rotation.py`, `test_recurrence.py`, `test_assignments.py`, `test_dashboard.py`, `test_completion.py`, `test_rollover.py`, `test_history.py` |

Splitting logic out of `models.py` keeps each file single-purpose and lets the
rotation and recurrence rules — the parts most likely to be wrong — be tested as
plain functions with no database.

---

## Task 1 — Household roster in admin

- [ ] **Ships:** run the server, open `/admin/`, add and deactivate household members.

**Files:** create `chores/tests/__init__.py`, `chores/tests/test_members.py`;
modify `chores/models.py`, `chores/admin.py`; delete `chores/tests.py`;
add `coverage` as a dev dependency.

**Produces:** `Member(name, is_active)` — `name` unique, `is_active` defaults
`True`, `Meta.ordering = ["name"]`.

**Also folds in** the one-time setup the rest of the backlog assumes: first
`makemigrations`/`migrate`, a superuser, and the `chores/tests/` package layout.

**Acceptance:** members list in admin shows name and active flag, filterable by
active. Duplicate names are rejected.

**Tests:** `__str__`, `is_active` default, ordering, uniqueness violation.

---

## Task 2 — Chore catalogue in admin

- [ ] **Ships:** define chores with a name, optional description, and a recurrence.

**Files:** modify `chores/models.py`, `chores/admin.py`; create
`chores/tests/test_chores.py`.

**Produces:** `Chore(name, description, recurrence)` and
`Chore.Recurrence` (`DAILY`, `WEEKLY`, `MONTHLY`) as a `TextChoices`.
`description` is `blank=True`, never `null`.

**Acceptance:** chore list shows name and recurrence, filterable by recurrence.
Recurrence is a closed dropdown — an invalid value fails validation.

**Tests:** `__str__`, blank description permitted, invalid recurrence rejected by
`full_clean()`.

---

## Task 3 — Rotation order per chore

- [ ] **Ships:** set who is in a chore's rotation and in what order, edited inline on the chore page.

**Files:** create `chores/rotation.py`, `chores/tests/test_rotation.py`; modify
`chores/models.py`, `chores/admin.py`.

**Produces:**
- `RotationSlot(chore, member, position)` — unique on `(chore, position)` and
  `(chore, member)`, ordered by `position`.
- `active_rotation(chore) -> list[Member]` — slot order, inactive members omitted.
- `next_member(chore, after=Member) -> Member | None` — wraps past the end,
  skips inactive, returns `None` for an empty rotation.

**Acceptance:** a `RotationSlot` inline on the chore admin page. Deactivating a
member drops them from `active_rotation` without deleting their slot, so
reactivating restores their place.

**Tests:** ordering by position; inactive members skipped; wrap-around from the
last slot to the first; empty and single-member rotations; the member currently
`after` being inactive.

---

## Task 4 — Assignments and due dates

- [ ] **Ships:** every chore has one open assignment with a real due date, visible in admin.

**Files:** create `chores/recurrence.py`, `chores/tests/test_recurrence.py`,
`chores/tests/test_assignments.py`; modify `chores/models.py`, `chores/admin.py`.

**Produces:**
- `ChoreAssignment(chore, member, due_date, status)` with
  `ChoreAssignment.Status` (`OPEN`, `DONE`), indexed on `(status, due_date)`.
- `next_due_date(from_date, recurrence) -> date` — pure, returns a new `date`.
- `open_assignment_for(chore) -> ChoreAssignment | None`, plus a way to seed the
  first assignment for a chore to its first rotation member.

**Acceptance:** admin lists open assignments sorted by due date, filterable by
member and status. A chore with no rotation cannot be seeded and says so rather
than raising.

**Tests:** daily `+1` day, weekly `+7` days, monthly `+1` month; month-end
clamping (Jan 31 → Feb 28/29, and a leap year); the first assignment going to
rotation position 0; seeding twice not creating a second open assignment.

---

## Task 5 — Dashboard (read-only) and "acting as"

- [ ] **Ships:** a real home page showing the household's current state, with an "acting as…" selector.

**Files:** create `chores/selectors.py`, `chores/urls.py`,
`chores/templates/chores/base.html`, `chores/templates/chores/dashboard.html`,
`chores/tests/test_dashboard.py`; modify `houseshare/urls.py`, `chores/views.py`.

**Consumes:** `ChoreAssignment`, `Member` (Tasks 1, 4).

**Produces:** `dashboard_buckets(today, acting_member=None) -> dict` with
`overdue`, `due_today` (grouped by assignee), `upcoming_this_week`, and
`open_counts_by_member`. The acting member id is stored in the session.

**Acceptance:** `/` renders the four sections; overdue rows are visually
distinct; the "acting as" choice persists across requests and pulls that
member's rows to the top. Per-member open counts include members with zero, so
imbalance is legible. No settings change needed — `APP_DIRS` already loads app
templates.

**Tests:** view returns 200 with an empty database; an assignment due yesterday
lands in `overdue` and not `due_today`; boundary dates for the week window;
counts correct per member and zero-inclusive; an unknown acting-member id in the
session is ignored rather than crashing.

---

## Task 6 — Mark done, and the rotation advances

- [ ] **Ships:** the core loop — click "Mark done", the chore reassigns to the next person.

**Files:** create `chores/services.py`, `chores/tests/test_completion.py`;
modify `chores/models.py`, `chores/views.py`, `chores/urls.py`,
`chores/admin.py`, `chores/templates/chores/dashboard.html`.

**Consumes:** `next_member` (Task 3), `next_due_date` (Task 4), the session
acting member (Task 5).

**Produces:**
- `Completion(assignment, completed_by, completed_at)` — append-only.
- `complete_assignment(assignment, completed_by, today) -> Completion` — inside
  one transaction: flips status to `DONE`, writes the `Completion`, and creates
  the successor assignment for `next_member` due `next_due_date`.
- A POST-only `mark_done` view, CSRF-protected.

**Acceptance:** marking done from the dashboard writes history, moves the chore
to the next member, and sets the new due date one period out. Re-posting the
same assignment does not advance the rotation twice. Marking done with no
"acting as" selected is refused with a clear message, not a 500.

**Tests:** rotation advances one place and wraps at the end; an inactive next
member is skipped; the `Completion` records both the original due date and the
actual completion time; idempotency on double-submit; a rotation of one member
reassigns to themselves; GET is rejected.

---

## Task 7 — Overdue rollover

- [ ] **Ships:** `manage.py roll_forward` — a passed due date advances the rotation without anyone clicking.

**Files:** create `chores/management/commands/roll_forward.py`,
`chores/tests/test_rollover.py`; modify `chores/services.py`.

**Consumes:** `next_member`, `next_due_date`, and the successor-creation logic
extracted in Task 6.

**Produces:** `roll_forward(today) -> int` (number of successors created),
reusing Task 6's successor logic rather than duplicating it.

**Acceptance:** for each chore whose open assignment is past due and has no
newer open assignment, the next member gets one. The overdue assignment stays
open and attributed to the original member — it does not vanish, which is what
keeps the dashboard's overdue section and the imbalance counts honest. Running
the command twice in a row creates nothing the second time.

**Tests:** an overdue assignment produces exactly one successor; idempotent on
re-run; a chore due today produces nothing; a chore already holding a newer open
assignment produces nothing; the return count is accurate.

---

## Task 8 — Completion history

- [ ] **Ships:** the filterable, append-only record the household uses to settle disputes.

**Files:** create `chores/templates/chores/history.html`,
`chores/tests/test_history.py`; modify `chores/selectors.py`, `chores/views.py`,
`chores/urls.py`, `chores/admin.py`, `chores/templates/chores/base.html`.

**Consumes:** `Completion` (Task 6).

**Produces:** `completion_history(member=None, chore=None)` — newest first, with
`select_related` so the page is a fixed number of queries.

**Acceptance:** `/history/` lists chore, member, due date, and completed-at,
filterable by member and by chore via query parameters that combine. The log is
append-only: no edit or delete view exists, and the admin registers `Completion`
read-only. Unknown filter values return an empty list, not a 500.

**Tests:** ordering newest first; each filter alone and both together; an
unknown filter id; query count does not grow with the number of rows.

---

## Decisions I assumed — override any of these

1. **Overdue advances the rotation.** F2 says the next occurrence is generated
   when an occurrence is completed *or its due date passes*, so Task 7 advances
   past an unfinished chore. The consequence is deliberate: a member can
   accumulate overdue items, and F3's per-member count is what makes that
   visible. The alternative — block the rotation until someone does the chore —
   would make the dashboard quieter but let one person stall the household.
2. **Monthly recurrence clamps to month end.** The 31st + one month is Feb 28
   (or 29). It does not skip to March.
3. **A deactivated member keeps their open assignments.** They are excluded from
   future rotation but history and current obligations stay attributed to them.
   Reassigning on deactivation would rewrite who owed what.
4. **"Acting as" lives in the session,** not a URL parameter, so it survives
   navigation. It is an identity convenience, not authentication — the spec puts
   accounts and permissions out of scope.

## Spec coverage

| Spec | Tasks |
| --- | --- |
| F1 — members and chores | 1, 2 |
| F2 — automatic rotation | 3, 4, 6, 7 |
| F3 — dashboard | 5, 6 |
| F4 — completion history | 6, 8 |
| §5 data model — `Member`, `Chore`, `ChoreAssignment`, `Completion` | 1, 2, 4, 6 |
| §6 tech — uv, SQLite, templates, admin, `manage.py test` | Conventions, 1, 5 |
| §7 definition of done | complete after 6; 8 closes the history half |

The `RotationSlot` model is the one addition to the §5 sketch — §5 lists
"rotation order of members" as a field on `Chore`, which needs a through-model to
hold an ordered, history-preserving list.
