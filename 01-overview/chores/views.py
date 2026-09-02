from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils import timezone

from chores.models import Member
from chores.selectors import dashboard_buckets

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
