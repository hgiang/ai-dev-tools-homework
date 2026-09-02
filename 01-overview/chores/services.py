"""Write operations on chore assignments."""

from django.utils import timezone

from chores.models import ChoreAssignment
from chores.rotation import active_rotation


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
