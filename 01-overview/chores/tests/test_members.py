"""Tests for the household roster (Task 1)."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from chores.models import Member


class MemberModelTests(TestCase):
    def test_str_is_the_member_name(self):
        self.assertEqual(str(Member(name="Ada")), "Ada")

    def test_new_member_is_active_by_default(self):
        member = Member.objects.create(name="Ada")

        self.assertTrue(member.is_active)

    def test_members_are_ordered_by_name(self):
        for name in ("Zoe", "Ada", "Mia"):
            Member.objects.create(name=name)

        self.assertEqual(
            [member.name for member in Member.objects.all()],
            ["Ada", "Mia", "Zoe"],
        )

    def test_duplicate_name_is_rejected_by_the_database(self):
        Member.objects.create(name="Ada")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Member.objects.create(name="Ada")

    def test_duplicate_name_fails_validation(self):
        Member.objects.create(name="Ada")

        with self.assertRaises(ValidationError):
            Member(name="Ada").full_clean()

    def test_blank_name_fails_validation(self):
        with self.assertRaises(ValidationError):
            Member(name="").full_clean()


class MemberAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changelist_url = reverse("admin:chores_member_changelist")

    def setUp(self):
        get_user_model().objects.create_superuser(
            username="housekeeper", email="", password="not-a-real-password"
        )
        self.client.force_login(get_user_model().objects.get(username="housekeeper"))

    def test_changelist_lists_members_with_an_active_flag_column(self):
        Member.objects.create(name="Ada")

        response = self.client.get(self.changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada")
        self.assertContains(response, "column-is_active")

    def test_changelist_can_be_filtered_to_inactive_members(self):
        Member.objects.create(name="Ada", is_active=True)
        Member.objects.create(name="Mia", is_active=False)

        response = self.client.get(self.changelist_url, {"is_active__exact": "0"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mia")
        self.assertNotContains(response, "Ada")
