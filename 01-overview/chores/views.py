from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from chores.models import ChoreAssignment, Member
from chores.selectors import dashboard_buckets
from chores.services import complete_assignment

ACTING_MEMBER_SESSION_KEY = "acting_member_id"


def dashboard(request):
    acting_member = _get_acting_member(request)
    buckets = dashboard_buckets(timezone.localdate(), acting_member=acting_member)
    context = {
        **buckets,
        "acting_member": acting_member,
        "members": Member.objects.filter(is_active=True),
    }
    return render(request, "chores/dashboard.html", context)


def set_acting_member(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    member_id = request.POST.get("member_id")
    if member_id:
        request.session[ACTING_MEMBER_SESSION_KEY] = member_id
    else:
        request.session.pop(ACTING_MEMBER_SESSION_KEY, None)
    return redirect("chores:dashboard")


def _get_acting_member(request):
    member_id = request.session.get(ACTING_MEMBER_SESSION_KEY)
    if member_id is None:
        return None
    try:
        member_id = int(member_id)
    except (TypeError, ValueError):
        return None
    return Member.objects.filter(pk=member_id).first()


def mark_done(request, assignment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    assignment = get_object_or_404(ChoreAssignment, pk=assignment_id)
    acting_member = _get_acting_member(request)
    if acting_member is None:
        messages.error(request, "Choose who's acting before marking a chore done.")
        return redirect("chores:dashboard")

    complete_assignment(
        assignment, completed_by=acting_member, today=timezone.localdate()
    )
    messages.success(request, f'Marked "{assignment.chore.name}" done.')
    return redirect("chores:dashboard")
