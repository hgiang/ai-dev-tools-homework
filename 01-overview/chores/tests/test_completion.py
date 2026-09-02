"""Tests for marking a chore done and advancing the rotation (Task 6)."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, Completion, Member, RotationSlot
from chores.services import complete_assignment


def make_chore(recurrence=Chore.Recurrence.DAILY, name="Dishes"):
    return Chore.objects.create(name=name, recurrence=recurrence)


def add_to_rotation(chore, member, position):
    return RotationSlot.objects.create(chore=chore, member=member, position=position)


def make_assignment(chore, member, due_date):
    return ChoreAssignment.objects.create(chore=chore, member=member, due_date=due_date)


class CompletionModelTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.assignment = make_assignment(self.chore, self.ada, timezone.localdate())

    def test_str_names_the_chore_completer_and_date(self):
        completion = Completion.objects.create(
            assignment=self.assignment,
            completed_by=self.ada,
            completed_at=timezone.datetime(2026, 3, 10, 9, 30, tzinfo=timezone.get_current_timezone()),
        )

        self.assertEqual(str(completion), "Dishes completed by Ada on 2026-03-10")

    def test_an_assignment_cannot_be_completed_twice(self):
        Completion.objects.create(
            assignment=self.assignment, completed_by=self.ada, completed_at=timezone.now()
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Completion.objects.create(
                    assignment=self.assignment, completed_by=self.ada, completed_at=timezone.now()
                )

    def test_deleting_a_completer_is_refused(self):
        Completion.objects.create(
            assignment=self.assignment, completed_by=self.ada, completed_at=timezone.now()
        )

        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.ada.delete()


class CompleteAssignmentTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        self.zoe = Member.objects.create(name="Zoe")

    def build_rotation(self, *members):
        for position, member in enumerate(members):
            add_to_rotation(self.chore, member, position)

    def test_marks_the_assignment_done(self):
        self.build_rotation(self.ada, self.mia)
        assignment = make_assignment(self.chore, self.ada, timezone.localdate())

        complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ChoreAssignment.Status.DONE)

    def test_advances_to_the_next_member(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        assignment = make_assignment(self.chore, self.ada, timezone.localdate())

        complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())

        successor = ChoreAssignment.objects.exclude(pk=assignment.pk).get()
        self.assertEqual(successor.member, self.mia)

    def test_wraps_at_the_end_of_the_rotation(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        assignment = make_assignment(self.chore, self.zoe, timezone.localdate())

        complete_assignment(assignment, completed_by=self.zoe, today=timezone.localdate())

        successor = ChoreAssignment.objects.exclude(pk=assignment.pk).get()
        self.assertEqual(successor.member, self.ada)

    def test_skips_an_inactive_next_member(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        Member.objects.filter(pk=self.mia.pk).update(is_active=False)
        assignment = make_assignment(self.chore, self.ada, timezone.localdate())

        complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())

        successor = ChoreAssignment.objects.exclude(pk=assignment.pk).get()
        self.assertEqual(successor.member, self.zoe)

    def test_a_rotation_of_one_reassigns_to_that_member(self):
        self.build_rotation(self.ada)
        assignment = make_assignment(self.chore, self.ada, timezone.localdate())

        complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())

        successor = ChoreAssignment.objects.exclude(pk=assignment.pk).get()
        self.assertEqual(successor.member, self.ada)

    def test_successor_due_date_is_one_recurrence_period_out(self):
        self.build_rotation(self.ada, self.mia)
        today = timezone.localdate()
        assignment = make_assignment(self.chore, self.ada, today)

        complete_assignment(assignment, completed_by=self.ada, today=today)

        successor = ChoreAssignment.objects.exclude(pk=assignment.pk).get()
        self.assertEqual(successor.due_date, today + timedelta(days=1))

    def test_successor_due_date_is_relative_to_today_not_the_original_due_date(self):
        self.build_rotation(self.ada, self.mia)
        original_due_date = timezone.localdate() - timedelta(days=3)
        today = timezone.localdate()
        assignment = make_assignment(self.chore, self.ada, original_due_date)

        complete_assignment(assignment, completed_by=self.ada, today=today)

        successor = ChoreAssignment.objects.exclude(pk=assignment.pk).get()
        self.assertEqual(successor.due_date, today + timedelta(days=1))

    def test_records_the_original_due_date_and_the_actual_completion_time(self):
        self.build_rotation(self.ada, self.mia)
        original_due_date = timezone.localdate() - timedelta(days=2)
        assignment = make_assignment(self.chore, self.ada, original_due_date)

        completion = complete_assignment(
            assignment, completed_by=self.ada, today=timezone.localdate()
        )

        assignment.refresh_from_db()
        self.assertEqual(assignment.due_date, original_due_date)
        self.assertEqual(completion.completed_by, self.ada)
        self.assertAlmostEqual(
            completion.completed_at, timezone.now(), delta=timedelta(seconds=5)
        )

    def test_completing_the_same_assignment_twice_does_not_advance_the_rotation_twice(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        assignment = make_assignment(self.chore, self.ada, timezone.localdate())

        first = complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())
        second = complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ChoreAssignment.objects.count(), 2)

    def test_no_successor_is_created_when_every_other_member_is_inactive(self):
        self.build_rotation(self.ada, self.mia)
        Member.objects.filter(pk=self.mia.pk).update(is_active=False)
        Member.objects.filter(pk=self.ada.pk).update(is_active=False)
        assignment = make_assignment(self.chore, self.ada, timezone.localdate())

        complete_assignment(assignment, completed_by=self.ada, today=timezone.localdate())

        self.assertEqual(ChoreAssignment.objects.count(), 1)


class MarkDoneViewTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(self.chore, self.mia, 1)
        self.assignment = make_assignment(self.chore, self.ada, timezone.localdate())
        self.mark_done_url = reverse("chores:mark_done", args=[self.assignment.pk])
        self.dashboard_url = reverse("chores:dashboard")

    def act_as(self, member):
        self.client.post(
            reverse("chores:set_acting_member"), {"member_id": member.pk}
        )

    def test_marking_done_while_acting_as_someone_completes_it(self):
        self.act_as(self.ada)

        response = self.client.post(self.mark_done_url)

        self.assertRedirects(response, self.dashboard_url)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, ChoreAssignment.Status.DONE)

    def test_marking_done_with_no_acting_member_is_refused_without_a_500(self):
        response = self.client.post(self.mark_done_url)

        self.assertRedirects(response, self.dashboard_url)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, ChoreAssignment.Status.OPEN)
        self.assertFalse(Completion.objects.exists())

    def test_get_is_rejected(self):
        self.act_as(self.ada)

        response = self.client.get(self.mark_done_url)

        self.assertEqual(response.status_code, 405)

    def test_double_submit_from_the_dashboard_does_not_double_advance(self):
        self.act_as(self.ada)

        self.client.post(self.mark_done_url)
        self.client.post(self.mark_done_url)

        self.assertEqual(ChoreAssignment.objects.count(), 2)
        self.assertEqual(Completion.objects.count(), 1)

    def test_an_unknown_assignment_id_is_a_404(self):
        self.act_as(self.ada)
        missing_url = reverse("chores:mark_done", args=[self.assignment.pk + 999])

        response = self.client.post(missing_url)

        self.assertEqual(response.status_code, 404)

    def test_dashboard_offers_a_mark_done_control_for_an_open_assignment(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(response, self.mark_done_url)
