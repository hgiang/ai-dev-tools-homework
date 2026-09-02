"""Tests for the chore catalogue (Task 2)."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from chores.models import Chore


class ChoreModelTests(TestCase):
    def test_str_is_the_chore_name(self):
        self.assertEqual(str(Chore(name="Dishes")), "Dishes")

    def test_description_defaults_to_blank_not_null(self):
        chore = Chore.objects.create(
            name="Dishes", recurrence=Chore.Recurrence.DAILY
        )

        chore.refresh_from_db()
        self.assertEqual(chore.description, "")

    def test_description_may_be_blank(self):
        chore = Chore(
            name="Dishes", description="", recurrence=Chore.Recurrence.DAILY
        )

        chore.full_clean()  # must not raise

    def test_description_may_be_filled_in(self):
        chore = Chore.objects.create(
            name="Dishes",
            description="Empty the rack first.",
            recurrence=Chore.Recurrence.DAILY,
        )

        chore.refresh_from_db()
        self.assertEqual(chore.description, "Empty the rack first.")

    def test_every_supported_recurrence_validates(self):
        for recurrence in (
            Chore.Recurrence.DAILY,
            Chore.Recurrence.WEEKLY,
            Chore.Recurrence.MONTHLY,
        ):
            with self.subTest(recurrence=recurrence):
                Chore(name=f"Chore {recurrence}", recurrence=recurrence).full_clean()

    def test_recurrence_outside_the_choices_fails_validation(self):
        chore = Chore(name="Dishes", recurrence="yearly")

        with self.assertRaises(ValidationError):
            chore.full_clean()

    def test_recurrence_is_required(self):
        chore = Chore(name="Dishes", recurrence="")

        with self.assertRaises(ValidationError):
            chore.full_clean()

    def test_chores_are_ordered_by_name(self):
        for name in ("Vacuum", "Bins", "Dishes"):
            Chore.objects.create(name=name, recurrence=Chore.Recurrence.WEEKLY)

        self.assertEqual(
            [chore.name for chore in Chore.objects.all()],
            ["Bins", "Dishes", "Vacuum"],
        )

    def test_duplicate_name_is_rejected_by_the_database(self):
        Chore.objects.create(name="Dishes", recurrence=Chore.Recurrence.DAILY)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Chore.objects.create(name="Dishes", recurrence=Chore.Recurrence.WEEKLY)


class ChoreAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changelist_url = reverse("admin:chores_chore_changelist")
        cls.add_url = reverse("admin:chores_chore_add")

    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="housekeeper", email="", password="not-a-real-password"
        )
        self.client.force_login(user)

    def test_changelist_lists_chores_with_a_recurrence_column(self):
        Chore.objects.create(name="Dishes", recurrence=Chore.Recurrence.DAILY)

        response = self.client.get(self.changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dishes")
        self.assertContains(response, "column-recurrence")

    def test_changelist_can_be_filtered_by_recurrence(self):
        Chore.objects.create(name="Dishes", recurrence=Chore.Recurrence.DAILY)
        Chore.objects.create(name="Vacuum", recurrence=Chore.Recurrence.WEEKLY)

        response = self.client.get(
            self.changelist_url, {"recurrence__exact": Chore.Recurrence.WEEKLY}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vacuum")
        self.assertNotContains(response, "Dishes")

    def test_add_form_offers_recurrence_as_a_closed_dropdown(self):
        response = self.client.get(self.add_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="recurrence"')
