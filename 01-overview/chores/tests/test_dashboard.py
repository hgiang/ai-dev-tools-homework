"""Tests for the dashboard selector and view (Task 5)."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, Member
from chores.selectors import dashboard_buckets


def make_chore(name="Dishes"):
    return Chore.objects.create(name=name, recurrence=Chore.Recurrence.DAILY)


def make_assignment(chore, member, due_date, status=ChoreAssignment.Status.OPEN):
    return ChoreAssignment.objects.create(
        chore=chore, member=member, due_date=due_date, status=status
    )


class DashboardBucketsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")

    def test_every_list_bucket_is_empty_with_no_assignments(self):
        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["overdue"], [])
        self.assertEqual(buckets["due_today"], [])
        self.assertEqual(buckets["upcoming_this_week"], [])

    def test_open_counts_by_member_is_empty_with_no_members(self):
        Member.objects.all().delete()

        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["open_counts_by_member"], [])

    def test_an_assignment_due_yesterday_is_overdue_not_due_today(self):
        assignment = make_assignment(self.chore, self.ada, self.today - timedelta(days=1))

        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["overdue"], [assignment])
        self.assertEqual(buckets["due_today"], [])

    def test_an_assignment_due_today_is_due_today_not_overdue_or_upcoming(self):
        make_assignment(self.chore, self.ada, self.today)

        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["overdue"], [])
        self.assertEqual(buckets["upcoming_this_week"], [])
        self.assertEqual(len(buckets["due_today"]), 1)

    def test_upcoming_window_includes_seven_days_out(self):
        assignment = make_assignment(self.chore, self.ada, self.today + timedelta(days=7))

        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["upcoming_this_week"], [assignment])

    def test_upcoming_window_excludes_eight_days_out(self):
        make_assignment(self.chore, self.ada, self.today + timedelta(days=8))

        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["upcoming_this_week"], [])

    def test_a_done_assignment_appears_in_no_bucket(self):
        make_assignment(
            self.chore,
            self.ada,
            self.today - timedelta(days=1),
            status=ChoreAssignment.Status.DONE,
        )

        buckets = dashboard_buckets(self.today)

        self.assertEqual(buckets["overdue"], [])

    def test_open_counts_include_a_member_with_zero_open_assignments(self):
        buckets = dashboard_buckets(self.today)

        self.assertEqual(
            buckets["open_counts_by_member"],
            [
                {"member": self.ada, "open_count": 0},
                {"member": self.mia, "open_count": 0},
            ],
        )

    def test_open_counts_are_correct_per_member(self):
        make_assignment(self.chore, self.ada, self.today)
        make_assignment(self.chore, self.ada, self.today + timedelta(days=1))
        make_assignment(self.chore, self.mia, self.today)

        buckets = dashboard_buckets(self.today)

        self.assertEqual(
            buckets["open_counts_by_member"],
            [
                {"member": self.ada, "open_count": 2},
                {"member": self.mia, "open_count": 1},
            ],
        )

    def test_due_today_is_grouped_by_assignee(self):
        ada_assignment = make_assignment(self.chore, self.ada, self.today)
        mia_assignment = make_assignment(self.chore, self.mia, self.today)

        buckets = dashboard_buckets(self.today)

        self.assertEqual(
            buckets["due_today"],
            [
                {"member": self.ada, "assignments": [ada_assignment]},
                {"member": self.mia, "assignments": [mia_assignment]},
            ],
        )

    def test_due_today_groups_are_alphabetical_with_no_one_acting(self):
        make_assignment(self.chore, self.mia, self.today)
        make_assignment(self.chore, self.ada, self.today)

        buckets = dashboard_buckets(self.today)

        self.assertEqual(
            [group["member"] for group in buckets["due_today"]],
            [self.ada, self.mia],
        )

    def test_acting_members_group_is_pulled_to_the_top(self):
        make_assignment(self.chore, self.ada, self.today)
        make_assignment(self.chore, self.mia, self.today)

        buckets = dashboard_buckets(self.today, acting_member=self.mia)

        self.assertEqual(
            [group["member"] for group in buckets["due_today"]],
            [self.mia, self.ada],
        )

    def test_an_acting_member_with_nothing_due_today_adds_no_empty_group(self):
        make_assignment(self.chore, self.ada, self.today)

        buckets = dashboard_buckets(self.today, acting_member=self.mia)

        self.assertEqual(
            [group["member"] for group in buckets["due_today"]],
            [self.ada],
        )


class DashboardViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        self.dashboard_url = reverse("chores:dashboard")
        self.set_acting_member_url = reverse("chores:set_acting_member")

    def test_returns_200_on_an_empty_database(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)

    def test_renders_all_four_sections(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(response, "Overdue")
        self.assertContains(response, "Due today")
        self.assertContains(response, "Coming up this week")
        self.assertContains(response, "Open chores by member")

    def test_overdue_rows_carry_a_distinct_css_class(self):
        make_assignment(self.chore, self.ada, self.today - timedelta(days=1))

        response = self.client.get(self.dashboard_url)

        self.assertContains(response, 'class="overdue"')

    def test_setting_the_acting_member_persists_across_requests(self):
        self.client.post(self.set_acting_member_url, {"member_id": self.ada.pk})

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context["acting_member"], self.ada)

    def test_clearing_the_acting_member(self):
        self.client.post(self.set_acting_member_url, {"member_id": self.ada.pk})
        self.client.post(self.set_acting_member_url, {"member_id": ""})

        response = self.client.get(self.dashboard_url)

        self.assertIsNone(response.context["acting_member"])

    def test_an_unknown_acting_member_id_in_the_session_is_ignored(self):
        session = self.client.session
        session["acting_member_id"] = "999999"
        session.save()

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["acting_member"])

    def test_a_non_numeric_acting_member_id_in_the_session_is_ignored(self):
        session = self.client.session
        session["acting_member_id"] = "not-a-number"
        session.save()

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["acting_member"])

    def test_set_acting_member_rejects_get(self):
        response = self.client.get(self.set_acting_member_url)

        self.assertEqual(response.status_code, 405)
