"""Write operations on chore assignments."""

from django.db import transaction
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, Completion
from chores.recurrence import next_due_date
from chores.rotation import active_rotation, next_member


class EmptyRotationError(Exception):
    """Raised when a chore has no active member to assign to."""


def open_assignment_for(chore):
    """The chore's current open assignment, or None if it has none."""
    return chore.assignments.filter(status=ChoreAssignment.Status.OPEN).first()


def seed_first_assignment(chore):
    """Create the chore's first open assignment, for its first active member.

    Idempotent: if the chore already has an open assignment, that one is
    returned instead of creating a second.
    """
    existing = open_assignment_for(chore)
    if existing is not None:
        return existing

    eligible_members = active_rotation(chore)
    if not eligible_members:
        raise EmptyRotationError(
            f"{chore.name} has no active rotation members to seed."
        )

    return ChoreAssignment.objects.create(
        chore=chore,
        member=eligible_members[0],
        due_date=timezone.localdate(),
    )


def _create_successor(assignment, today):
    """The next occurrence after `assignment`, due one period past `today`.

    Returns None, creating nothing, if no active member is left to take it.
    """
    successor = next_member(assignment.chore, after=assignment.member)
    if successor is None:
        return None

    return ChoreAssignment.objects.create(
        chore=assignment.chore,
        member=successor,
        due_date=next_due_date(today, assignment.chore.recurrence),
    )


def complete_assignment(assignment, completed_by, today):
    """Mark `assignment` done and roll the rotation forward.

    Idempotent: if the assignment already has a completion, that one is
    returned and nothing else changes — a resubmitted "Mark done" does not
    advance the rotation a second time.

    The successor's due date is `today` plus one recurrence period, not the
    original due date plus one period, so a chore completed late doesn't
    inherit a due date that's already in the past.
    """
    existing = getattr(assignment, "completion", None)
    if existing is not None:
        return existing

    with transaction.atomic():
        assignment.status = ChoreAssignment.Status.DONE
        assignment.save(update_fields=["status"])

        completion = Completion.objects.create(
            assignment=assignment,
            completed_by=completed_by,
            completed_at=timezone.now(),
        )

        _create_successor(assignment, today)

    return completion


def roll_forward(today):
    """Advance every chore whose open assignment has fallen past due.

    The overdue assignment is left exactly as it is — still open, still
    attributed to the member who missed it — so it keeps showing up in the
    dashboard's overdue section and open-count imbalance. Only a fresh
    successor is created, for the next active member, due one period past
    `today`.

    Idempotent: a chore that already has an open assignment due today or
    later — whether freshly seeded or already rolled forward — is left
    alone. Returns the number of successors created.
    """
    created = 0
    for chore in Chore.objects.all():
        open_assignments = list(
            chore.assignments.filter(status=ChoreAssignment.Status.OPEN)
        )
        if not open_assignments:
            continue
        if any(assignment.due_date >= today for assignment in open_assignments):
            continue

        most_recent_overdue = open_assignments[-1]
        if _create_successor(most_recent_overdue, today) is not None:
            created += 1

    return created
