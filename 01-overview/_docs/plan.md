# HouseShare — Shared Household Chores Manager

## 1. Problem

People sharing a home lose track of who is supposed to do which chore and when.
Chores get forgotten, or the same person ends up doing them repeatedly. Verbal
agreements and group-chat reminders don't hold.

## 2. Scope

A small Django web app for **one household** (2–6 members) to define recurring
chores, rotate them fairly among members, mark them done, and see at a glance
who owes what.

**Explicitly out of scope** for this version: multiple households, user accounts
and passwords, notifications/email, mobile app, points or gamification.

## 3. Users

- **Household member** — sees their assigned chores, marks them complete.
- **Anyone in the household** — can create and edit chores. No roles or
  permissions; the household is assumed to be trusted.

Members are chosen from a dropdown ("acting as…"); there is no login.

## 4. Features

### F1 — Members and chores

Manage the household roster (name, active/inactive) and a catalogue of chores.
A chore has a name, an optional description, and a recurrence: daily, weekly, or
monthly.

### F2 — Automatic rotation

Each chore keeps an ordered rotation of members. When an occurrence is completed
(or its due date passes), the next occurrence is generated for the following
member in the rotation, due one recurrence period later. Adding or deactivating
a member updates the rotation without losing history.

### F3 — Dashboard

The home page shows the current state of the household:

- chores due today, grouped by assignee
- overdue chores, highlighted
- what is coming up this week
- a per-member count of open chores, so imbalance is visible

Each open chore has a "Mark done" action.

### F4 — Completion history

An append-only log of completions: which chore, which member, when it was due,
when it was actually completed. Filterable by member and by chore. This is the
record the household uses to settle disputes.

## 5. Data model (initial sketch)

- `Member` — name, is_active
- `Chore` — name, description, recurrence, rotation order of members
- `ChoreAssignment` — chore, assigned member, due date, status (open/done)
- `Completion` — assignment, completed_by, completed_at

## 6. Tech

- Python + Django, dependencies managed with `uv`
- SQLite (Django default)
- Server-rendered Django templates
- Django admin for quick data entry
- Tests with Django's built-in test runner (`python manage.py test`)

## 7. Definition of done

A member can open the site, see the chores due for the household today, mark one
complete, watch it reassign to the next person in the rotation, and find that
completion in the history log — with tests covering rotation and completion.
