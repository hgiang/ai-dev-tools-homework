from django.contrib import admin

from chores.models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
