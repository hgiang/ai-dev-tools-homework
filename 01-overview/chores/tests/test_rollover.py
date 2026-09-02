"""Tests for overdue rollover (Task 7)."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, Member, RotationSlot
from chores.services import roll_forward


def make_chore(recurrence=Chore.Recurrence.DAILY, name="Dishes"):
    return Chore.objects.create(name=name, recurrence=recurrence)


def add_to_rotation(chore, member, position):
    return RotationSlot.objects.create(chore=chore, member=member, position=position)


def make_assignment(chore, member, due_date, status=ChoreAssignment.Status.OPEN):
    return ChoreAssignment.objects.create(
        chore=chore, member=member, due_date=due_date, status=status
    )


class RollForwardTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")

    def test_an_overdue_assignment_produces_exactly_one_successor(self):
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(self.chore, self.mia, 1)
        make_assignment(self.chore, self.ada, self.today - timedelta(days=1))

        created = roll_forward(self.today)

        self.assertEqual(created, 1)
        self.assertEqual(ChoreAssignment.objects.count(), 2)

    def test_the_successor_goes_to_the_next_member_due_one_period_from_today(self):
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(self.chore, self.mia, 1)
        overdue = make_assignment(self.chore, self.ada, self.today - timedelta(days=3))

        roll_forward(self.today)

        successor = ChoreAssignment.objects.exclude(pk=overdue.pk).get()
        self.assertEqual(successor.member, self.mia)
        self.assertEqual(successor.due_date, self.today + timedelta(days=1))

    def test_the_overdue_assignment_stays_open_and_attributed_to_the_original_member(self):
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(self.chore, self.mia, 1)
        overdue = make_assignment(self.chore, self.ada, self.today - timedelta(days=1))

        roll_forward(self.today)

        overdue.refresh_from_db()
        self.assertEqual(overdue.status, ChoreAssignment.Status.OPEN)
        self.assertEqual(overdue.member, self.ada)

    def test_running_twice_in_a_row_creates_nothing_the_second_time(self):
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(self.chore, self.mia, 1)
        make_assignment(self.chore, self.ada, self.today - timedelta(days=1))

        roll_forward(self.today)
        second_run_created = roll_forward(self.today)

        self.assertEqual(second_run_created, 0)
        self.assertEqual(ChoreAssignment.objects.count(), 2)

    def test_a_chore_due_today_produces_nothing(self):
        add_to_rotation(self.chore, self.ada, 0)
        make_assignment(self.chore, self.ada, self.today)

        created = roll_forward(self.today)

        self.assertEqual(created, 0)
        self.assertEqual(ChoreAssignment.objects.count(), 1)

    def test_a_chore_due_in_the_future_produces_nothing(self):
        add_to_rotation(self.chore, self.ada, 0)
        make_assignment(self.chore, self.ada, self.today + timedelta(days=2))

        created = roll_forward(self.today)

        self.assertEqual(created, 0)

    def test_a_chore_with_a_newer_open_assignment_already_produces_nothing(self):
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(self.chore, self.mia, 1)
        make_assignment(self.chore, self.ada, self.today - timedelta(days=5))
        make_assignment(self.chore, self.mia, self.today + timedelta(days=1))

        created = roll_forward(self.today)

        self.assertEqual(created, 0)
        self.assertEqual(ChoreAssignment.objects.count(), 2)

    def test_skips_a_chore_that_has_never_been_seeded(self):
        add_to_rotation(self.chore, self.ada, 0)

        created = roll_forward(self.today)

        self.assertEqual(created, 0)
        self.assertEqual(ChoreAssignment.objects.count(), 0)

    def test_a_done_assignment_is_not_treated_as_overdue(self):
        add_to_rotation(self.chore, self.ada, 0)
        make_assignment(
            self.chore,
            self.ada,
            self.today - timedelta(days=1),
            status=ChoreAssignment.Status.DONE,
        )

        created = roll_forward(self.today)

        self.assertEqual(created, 0)

    def test_a_rotation_of_one_still_gets_a_successor(self):
        add_to_rotation(self.chore, self.ada, 0)
        make_assignment(self.chore, self.ada, self.today - timedelta(days=1))

        created = roll_forward(self.today)

        self.assertEqual(created, 1)
        self.assertEqual(ChoreAssignment.objects.count(), 2)

    def test_no_successor_is_created_when_every_member_is_inactive(self):
        add_to_rotation(self.chore, self.ada, 0)
        make_assignment(self.chore, self.ada, self.today - timedelta(days=1))
        Member.objects.filter(pk=self.ada.pk).update(is_active=False)

        created = roll_forward(self.today)

        self.assertEqual(created, 0)
        self.assertEqual(ChoreAssignment.objects.count(), 1)

    def test_the_return_count_is_accurate_across_several_chores(self):
        other_chore = make_chore(name="Vacuum")
        add_to_rotation(self.chore, self.ada, 0)
        add_to_rotation(other_chore, self.mia, 0)
        make_assignment(self.chore, self.ada, self.today - timedelta(days=1))
        make_assignment(other_chore, self.mia, self.today - timedelta(days=1))

        created = roll_forward(self.today)

        self.assertEqual(created, 2)


class RollForwardCommandTests(TestCase):
    def test_the_command_calls_roll_forward_and_reports_the_count(self):
        chore = make_chore()
        ada = Member.objects.create(name="Ada")
        add_to_rotation(chore, ada, 0)
        make_assignment(chore, ada, timezone.localdate() - timedelta(days=1))

        out = StringIO()
        call_command("roll_forward", stdout=out)

        self.assertIn("1", out.getvalue())
        self.assertEqual(ChoreAssignment.objects.count(), 2)
