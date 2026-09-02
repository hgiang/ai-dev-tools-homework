from django.contrib import admin, messages

from chores.models import Chore, ChoreAssignment, Member, RotationSlot
from chores.services import EmptyRotationError, seed_first_assignment


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


class RotationSlotInline(admin.TabularInline):
    model = RotationSlot
    extra = 1
    ordering = ["position", "id"]


@admin.action(description="Seed first assignment for selected chores")
def seed_rotation_assignment(modeladmin, request, queryset):
    seeded = 0
    for chore in queryset:
        try:
            seed_first_assignment(chore)
        except EmptyRotationError as exc:
            modeladmin.message_user(request, str(exc), level=messages.ERROR)
        else:
            seeded += 1
    if seeded:
        modeladmin.message_user(
            request, f"Seeded {seeded} chore(s).", level=messages.SUCCESS
        )


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    inlines = [RotationSlotInline]
    list_display = ["name", "recurrence"]
    list_filter = ["recurrence"]
    search_fields = ["name", "description"]
    actions = [seed_rotation_assignment]


@admin.register(ChoreAssignment)
class ChoreAssignmentAdmin(admin.ModelAdmin):
    list_display = ["chore", "member", "due_date", "status"]
    list_filter = ["status", "member"]
    ordering = ["due_date"]
    search_fields = ["chore__name", "member__name"]
