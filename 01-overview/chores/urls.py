from django.urls import path

from chores import views

app_name = "chores"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("acting-as/", views.set_acting_member, name="set_acting_member"),
]
