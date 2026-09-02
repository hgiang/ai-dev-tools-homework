from django.contrib import admin

from chores.models import Chore, Member, RotationSlot


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


class RotationSlotInline(admin.TabularInline):
    model = RotationSlot
    extra = 1
    ordering = ["position", "id"]


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    inlines = [RotationSlotInline]
    list_display = ["name", "recurrence"]
    list_filter = ["recurrence"]
    search_fields = ["name", "description"]
