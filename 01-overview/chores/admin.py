from django.contrib import admin

from chores.models import Chore, Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = ["name", "recurrence"]
    list_filter = ["recurrence"]
    search_fields = ["name", "description"]
