"""Read queries backing the dashboard."""

from datetime import timedelta

from django.db.models import Count, Q

from chores.models import ChoreAssignment, Member

UPCOMING_WINDOW_DAYS = 7


def dashboard_buckets(today, acting_member=None):
    """The household's current state: overdue, due today, upcoming, and load.

    `due_today` groups open assignments by member; if `acting_member` has
    any assignments due today, their group is moved to the front.
    """
    open_assignments = ChoreAssignment.objects.filter(
        status=ChoreAssignment.Status.OPEN
    ).select_related("chore", "member")

    return {
        "overdue": list(open_assignments.filter(due_date__lt=today)),
        "due_today": _grouped_by_member(
            open_assignments.filter(due_date=today), acting_member
        ),
        "upcoming_this_week": list(
            open_assignments.filter(
                due_date__gt=today,
                due_date__lte=today + timedelta(days=UPCOMING_WINDOW_DAYS),
            )
        ),
        "open_counts_by_member": _open_counts_by_member(),
    }


def _grouped_by_member(assignments, acting_member):
    groups = {}
    for assignment in assignments:
        groups.setdefault(assignment.member, []).append(assignment)

    ordered_members = sorted(groups, key=lambda member: member.name)
    if acting_member in groups:
        ordered_members.remove(acting_member)
        ordered_members.insert(0, acting_member)

    return [
        {"member": member, "assignments": groups[member]} for member in ordered_members
    ]


def _open_counts_by_member():
    members = Member.objects.annotate(
        open_count=Count(
            "assignments",
            filter=Q(assignments__status=ChoreAssignment.Status.OPEN),
        )
    ).order_by("name")

    return [{"member": member, "open_count": member.open_count} for member in members]
