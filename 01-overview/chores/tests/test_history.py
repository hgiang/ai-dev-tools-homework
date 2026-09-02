"""Tests for the completion history selector and view (Task 8)."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, Completion, Member
from chores.selectors import completion_history


def make_chore(name="Dishes"):
    return Chore.objects.create(name=name, recurrence=Chore.Recurrence.DAILY)


def make_completion(chore, assigned_to, completed_by, days_ago, due_days_ago=None):
    due_date = timezone.localdate() - timedelta(
        days=due_days_ago if due_days_ago is not None else days_ago
    )
    assignment = ChoreAssignment.objects.create(
        chore=chore,
        member=assigned_to,
        due_date=due_date,
        status=ChoreAssignment.Status.DONE,
    )
    return Completion.objects.create(
        assignment=assignment,
        completed_by=completed_by,
        completed_at=timezone.now() - timedelta(days=days_ago),
    )


class CompletionHistoryTests(TestCase):
    def setUp(self):
        self.dishes = make_chore("Dishes")
        self.vacuum = make_chore("Vacuum")
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")

    def test_no_completions_is_an_empty_list(self):
        self.assertEqual(completion_history(), [])

    def test_ordered_newest_first(self):
        older = make_completion(self.dishes, self.ada, self.ada, days_ago=5)
        newer = make_completion(self.dishes, self.ada, self.ada, days_ago=1)

        self.assertEqual(completion_history(), [newer, older])

    def test_filter_by_member_alone(self):
        by_ada = make_completion(self.dishes, self.ada, self.ada, days_ago=1)
        make_completion(self.vacuum, self.mia, self.mia, days_ago=1)

        self.assertEqual(completion_history(member=self.ada.pk), [by_ada])

    def test_filter_by_chore_alone(self):
        dishes_completion = make_completion(self.dishes, self.ada, self.ada, days_ago=1)
        make_completion(self.vacuum, self.ada, self.ada, days_ago=1)

        self.assertEqual(completion_history(chore=self.dishes.pk), [dishes_completion])

    def test_filters_combine_with_and_not_or(self):
        target = make_completion(self.dishes, self.ada, self.ada, days_ago=1)
        make_completion(self.dishes, self.mia, self.mia, days_ago=1)
        make_completion(self.vacuum, self.ada, self.ada, days_ago=1)

        result = completion_history(member=self.ada.pk, chore=self.dishes.pk)

        self.assertEqual(result, [target])

    def test_an_unknown_member_id_returns_an_empty_list(self):
        make_completion(self.dishes, self.ada, self.ada, days_ago=1)

        self.assertEqual(completion_history(member=999_999), [])

    def test_an_unknown_chore_id_returns_an_empty_list(self):
        make_completion(self.dishes, self.ada, self.ada, days_ago=1)

        self.assertEqual(completion_history(chore=999_999), [])

    def test_the_due_date_recorded_is_the_original_due_date(self):
        completion = make_completion(
            self.dishes, self.ada, self.ada, days_ago=1, due_days_ago=4
        )

        result = completion_history()[0]
        self.assertEqual(result.assignment.due_date, completion.assignment.due_date)

    def test_query_count_does_not_grow_with_the_number_of_rows(self):
        make_completion(self.dishes, self.ada, self.ada, days_ago=1)
        with self.assertNumQueries(1):
            completion_history()

        for day in range(2, 7):
            make_completion(self.dishes, self.ada, self.ada, days_ago=day)
        with self.assertNumQueries(1):
            completion_history()


class HistoryViewTests(TestCase):
    def setUp(self):
        self.dishes = make_chore("Dishes")
        self.vacuum = make_chore("Vacuum")
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        self.history_url = reverse("chores:history")

    def test_returns_200(self):
        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, 200)

    def test_lists_chore_member_due_date_and_completed_at(self):
        make_completion(self.dishes, self.ada, self.ada, days_ago=1, due_days_ago=2)

        response = self.client.get(self.history_url)

        self.assertContains(response, "Dishes")
        self.assertContains(response, "Ada")

    def test_filtering_by_query_params_combines(self):
        target = make_completion(self.dishes, self.ada, self.ada, days_ago=1)
        make_completion(self.dishes, self.mia, self.mia, days_ago=1)
        make_completion(self.vacuum, self.ada, self.ada, days_ago=1)

        response = self.client.get(
            self.history_url, {"member": self.ada.pk, "chore": self.dishes.pk}
        )

        self.assertEqual(list(response.context["completions"]), [target])

    def test_an_unknown_member_query_param_does_not_crash(self):
        response = self.client.get(self.history_url, {"member": "999999"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["completions"]), [])

    def test_a_non_numeric_query_param_does_not_crash(self):
        response = self.client.get(self.history_url, {"member": "not-a-number"})

        self.assertEqual(response.status_code, 200)

    def test_dashboard_links_to_history(self):
        response = self.client.get(reverse("chores:dashboard"))

        self.assertContains(response, self.history_url)
