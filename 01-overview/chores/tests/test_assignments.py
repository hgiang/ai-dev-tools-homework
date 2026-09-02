"""Tests for chore assignments, seeding, and their admin (Task 4)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreAssignment, Member, RotationSlot
from chores.services import EmptyRotationError, open_assignment_for, seed_first_assignment


def make_chore(name="Dishes"):
    return Chore.objects.create(name=name, recurrence=Chore.Recurrence.DAILY)


def add_to_rotation(chore, member, position):
    return RotationSlot.objects.create(chore=chore, member=member, position=position)


class ChoreAssignmentModelTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")

    def make_assignment(self, **overrides):
        fields = {
            "chore": self.chore,
            "member": self.ada,
            "due_date": timezone.localdate(),
        }
        fields.update(overrides)
        return ChoreAssignment.objects.create(**fields)

    def test_str_names_the_chore_member_and_due_date(self):
        assignment = self.make_assignment(due_date=timezone.datetime(2026, 3, 10).date())

        self.assertEqual(str(assignment), "Dishes for Ada, due 2026-03-10")

    def test_status_defaults_to_open(self):
        assignment = self.make_assignment()

        self.assertEqual(assignment.status, ChoreAssignment.Status.OPEN)

    def test_ordering_is_by_due_date(self):
        today = timezone.localdate()
        later = self.make_assignment(due_date=today + timedelta(days=5))
        sooner = self.make_assignment(due_date=today + timedelta(days=1))

        self.assertEqual(list(ChoreAssignment.objects.all()), [sooner, later])

    def test_is_indexed_on_status_and_due_date(self):
        indexed_field_groups = [
            tuple(index.fields) for index in ChoreAssignment._meta.indexes
        ]

        self.assertIn(("status", "due_date"), indexed_field_groups)

    def test_deleting_the_chore_cascades_its_assignments(self):
        self.make_assignment()

        self.chore.delete()

        self.assertEqual(ChoreAssignment.objects.count(), 0)

    def test_deleting_an_assigned_member_is_refused(self):
        self.make_assignment()

        with self.assertRaises(ProtectedError):
            self.ada.delete()


class OpenAssignmentForTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")

    def test_returns_the_open_assignment(self):
        assignment = ChoreAssignment.objects.create(
            chore=self.chore, member=self.ada, due_date=timezone.localdate()
        )

        self.assertEqual(open_assignment_for(self.chore), assignment)

    def test_is_none_when_the_only_assignment_is_done(self):
        ChoreAssignment.objects.create(
            chore=self.chore,
            member=self.ada,
            due_date=timezone.localdate(),
            status=ChoreAssignment.Status.DONE,
        )

        self.assertIsNone(open_assignment_for(self.chore))

    def test_is_none_for_a_chore_with_no_assignments(self):
        self.assertIsNone(open_assignment_for(self.chore))


class SeedFirstAssignmentTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")

    def test_assigns_the_first_rotation_member(self):
        add_to_rotation(self.chore, self.ada, position=0)
        add_to_rotation(self.chore, self.mia, position=1)

        assignment = seed_first_assignment(self.chore)

        self.assertEqual(assignment.member, self.ada)
        self.assertEqual(assignment.status, ChoreAssignment.Status.OPEN)

    def test_due_date_is_today(self):
        add_to_rotation(self.chore, self.ada, position=0)

        assignment = seed_first_assignment(self.chore)

        self.assertEqual(assignment.due_date, timezone.localdate())

    def test_skips_an_inactive_first_slot(self):
        add_to_rotation(self.chore, self.ada, position=0)
        add_to_rotation(self.chore, self.mia, position=1)
        Member.objects.filter(pk=self.ada.pk).update(is_active=False)

        assignment = seed_first_assignment(self.chore)

        self.assertEqual(assignment.member, self.mia)

    def test_seeding_twice_does_not_create_a_second_open_assignment(self):
        add_to_rotation(self.chore, self.ada, position=0)

        first = seed_first_assignment(self.chore)
        second = seed_first_assignment(self.chore)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ChoreAssignment.objects.count(), 1)

    def test_raises_a_clear_error_for_a_chore_with_no_rotation(self):
        with self.assertRaisesMessage(
            EmptyRotationError, "Dishes has no active rotation members to seed."
        ):
            seed_first_assignment(self.chore)

    def test_raises_a_clear_error_when_every_rotation_member_is_inactive(self):
        add_to_rotation(self.chore, self.ada, position=0)
        Member.objects.filter(pk=self.ada.pk).update(is_active=False)

        with self.assertRaises(EmptyRotationError):
            seed_first_assignment(self.chore)


class ChoreAssignmentAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changelist_url = reverse("admin:chores_choreassignment_changelist")

    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="housekeeper", email="", password="not-a-real-password"
        )
        self.client.force_login(user)
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")

    def test_changelist_lists_assignments_sorted_by_due_date(self):
        today = timezone.localdate()
        ChoreAssignment.objects.create(
            chore=self.chore, member=self.ada, due_date=today + timedelta(days=5)
        )
        ChoreAssignment.objects.create(
            chore=self.chore, member=self.ada, due_date=today + timedelta(days=1)
        )

        response = self.client.get(self.changelist_url)

        self.assertEqual(response.status_code, 200)
        first, second = response.context["cl"].result_list
        self.assertEqual(first.due_date, today + timedelta(days=1))
        self.assertEqual(second.due_date, today + timedelta(days=5))

    def test_changelist_can_be_filtered_by_status(self):
        ChoreAssignment.objects.create(
            chore=self.chore,
            member=self.ada,
            due_date=timezone.localdate(),
            status=ChoreAssignment.Status.DONE,
        )
        open_one = ChoreAssignment.objects.create(
            chore=self.chore, member=self.ada, due_date=timezone.localdate()
        )

        response = self.client.get(
            self.changelist_url, {"status__exact": ChoreAssignment.Status.OPEN}
        )

        self.assertEqual(list(response.context["cl"].result_list), [open_one])

    def test_changelist_can_be_filtered_by_member(self):
        mia = Member.objects.create(name="Mia")
        ada_assignment = ChoreAssignment.objects.create(
            chore=self.chore, member=self.ada, due_date=timezone.localdate()
        )
        ChoreAssignment.objects.create(
            chore=self.chore, member=mia, due_date=timezone.localdate()
        )

        response = self.client.get(self.changelist_url, {"member__id__exact": self.ada.pk})

        self.assertEqual(list(response.context["cl"].result_list), [ada_assignment])


class SeedRotationAssignmentActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changelist_url = reverse("admin:chores_chore_changelist")

    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="housekeeper", email="", password="not-a-real-password"
        )
        self.client.force_login(user)

    def post_action(self, chore_ids):
        return self.client.post(
            self.changelist_url,
            {
                "action": "seed_rotation_assignment",
                "_selected_action": [str(pk) for pk in chore_ids],
            },
            follow=True,
        )

    def test_creates_an_open_assignment_for_a_seedable_chore(self):
        chore = make_chore()
        ada = Member.objects.create(name="Ada")
        add_to_rotation(chore, ada, position=0)

        response = self.post_action([chore.pk])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChoreAssignment.objects.filter(chore=chore).count(), 1)

    def test_reports_an_error_instead_of_a_server_error_for_an_empty_rotation(self):
        chore = make_chore()

        response = self.post_action([chore.pk])

        self.assertEqual(response.status_code, 200)
        error_messages = [
            str(message)
            for message in response.context["messages"]
            if message.level == messages.ERROR
        ]
        self.assertTrue(
            any("no active rotation members" in message for message in error_messages)
        )
        self.assertEqual(ChoreAssignment.objects.filter(chore=chore).count(), 0)
