"""Write operations on chore assignments."""

from django.db import transaction
from django.utils import timezone

from chores.models import ChoreAssignment, Completion
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

        successor = next_member(assignment.chore, after=assignment.member)
        if successor is not None:
            ChoreAssignment.objects.create(
                chore=assignment.chore,
                member=successor,
                due_date=next_due_date(today, assignment.chore.recurrence),
            )

    return completion
