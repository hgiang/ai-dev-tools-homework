"""Tests for per-chore rotation order (Task 3)."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from chores.models import Chore, Member, RotationSlot
from chores.rotation import active_rotation, next_member, rotation_members


def make_chore(name="Dishes"):
    return Chore.objects.create(name=name, recurrence=Chore.Recurrence.DAILY)


def add_to_rotation(chore, member, position):
    return RotationSlot.objects.create(chore=chore, member=member, position=position)


class RotationSlotModelTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")

    def test_str_names_the_chore_position_and_member(self):
        slot = add_to_rotation(self.chore, self.ada, position=0)

        self.assertEqual(str(slot), "Dishes #0: Ada")

    def test_slots_are_ordered_by_position(self):
        add_to_rotation(self.chore, self.mia, position=1)
        add_to_rotation(self.chore, self.ada, position=0)

        self.assertEqual(
            [slot.member.name for slot in self.chore.rotation_slots.all()],
            ["Ada", "Mia"],
        )

    def test_a_member_cannot_hold_two_slots_in_one_chore(self):
        add_to_rotation(self.chore, self.ada, position=0)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                add_to_rotation(self.chore, self.ada, position=1)

    def test_a_member_can_be_in_the_rotation_of_several_chores(self):
        other = make_chore("Bins")
        add_to_rotation(self.chore, self.ada, position=0)
        add_to_rotation(other, self.ada, position=0)

        self.assertEqual(self.ada.rotation_slots.count(), 2)

    def test_deleting_a_member_who_is_in_a_rotation_is_refused(self):
        add_to_rotation(self.chore, self.ada, position=0)

        with self.assertRaises(ProtectedError):
            self.ada.delete()

    def test_deleting_a_chore_removes_its_slots(self):
        add_to_rotation(self.chore, self.ada, position=0)

        self.chore.delete()

        self.assertEqual(RotationSlot.objects.count(), 0)


class ActiveRotationTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        self.zoe = Member.objects.create(name="Zoe")

    def test_active_rotation_follows_slot_order_not_member_name(self):
        add_to_rotation(self.chore, self.zoe, position=0)
        add_to_rotation(self.chore, self.ada, position=1)

        self.assertEqual(active_rotation(self.chore), [self.zoe, self.ada])

    def test_active_rotation_omits_inactive_members(self):
        add_to_rotation(self.chore, self.ada, position=0)
        add_to_rotation(self.chore, self.mia, position=1)
        Member.objects.filter(pk=self.mia.pk).update(is_active=False)

        self.assertEqual(active_rotation(self.chore), [self.ada])

    def test_deactivating_a_member_keeps_their_slot_so_reactivating_restores_it(self):
        add_to_rotation(self.chore, self.ada, position=0)
        add_to_rotation(self.chore, self.mia, position=1)
        add_to_rotation(self.chore, self.zoe, position=2)

        Member.objects.filter(pk=self.mia.pk).update(is_active=False)
        self.assertEqual(active_rotation(self.chore), [self.ada, self.zoe])
        self.assertEqual(self.chore.rotation_slots.count(), 3)

        Member.objects.filter(pk=self.mia.pk).update(is_active=True)
        self.assertEqual(active_rotation(self.chore), [self.ada, self.mia, self.zoe])

    def test_active_rotation_is_empty_when_the_chore_has_no_slots(self):
        self.assertEqual(active_rotation(self.chore), [])

    def test_rotation_members_includes_inactive_members(self):
        add_to_rotation(self.chore, self.ada, position=0)
        add_to_rotation(self.chore, self.mia, position=1)
        Member.objects.filter(pk=self.mia.pk).update(is_active=False)

        self.assertEqual(rotation_members(self.chore), [self.ada, self.mia])


class NextMemberTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        self.zoe = Member.objects.create(name="Zoe")

    def build_rotation(self, *members):
        for position, member in enumerate(members):
            add_to_rotation(self.chore, member, position)

    def test_advances_one_place(self):
        self.build_rotation(self.ada, self.mia, self.zoe)

        self.assertEqual(next_member(self.chore, after=self.ada), self.mia)

    def test_wraps_from_the_last_slot_to_the_first(self):
        self.build_rotation(self.ada, self.mia, self.zoe)

        self.assertEqual(next_member(self.chore, after=self.zoe), self.ada)

    def test_skips_an_inactive_member(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        Member.objects.filter(pk=self.mia.pk).update(is_active=False)

        self.assertEqual(next_member(self.chore, after=self.ada), self.zoe)

    def test_skips_an_inactive_member_when_wrapping(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        Member.objects.filter(pk=self.ada.pk).update(is_active=False)

        self.assertEqual(next_member(self.chore, after=self.zoe), self.mia)

    def test_continues_from_the_slot_of_a_member_who_is_now_inactive(self):
        self.build_rotation(self.ada, self.mia, self.zoe)
        inactive_mia = Member.objects.get(pk=self.mia.pk)
        Member.objects.filter(pk=self.mia.pk).update(is_active=False)

        self.assertEqual(next_member(self.chore, after=inactive_mia), self.zoe)

    def test_a_single_member_rotation_returns_that_member(self):
        self.build_rotation(self.ada)

        self.assertEqual(next_member(self.chore, after=self.ada), self.ada)

    def test_is_none_for_an_empty_rotation(self):
        self.assertIsNone(next_member(self.chore, after=self.ada))

    def test_is_none_when_every_member_is_inactive(self):
        self.build_rotation(self.ada, self.mia)
        Member.objects.filter(is_active=True).update(is_active=False)

        self.assertIsNone(next_member(self.chore, after=self.ada))

    def test_starts_from_the_top_when_after_is_none(self):
        self.build_rotation(self.zoe, self.ada)

        self.assertEqual(next_member(self.chore, after=None), self.zoe)

    def test_starts_from_the_top_when_after_left_the_rotation(self):
        self.build_rotation(self.ada, self.mia)

        self.assertEqual(next_member(self.chore, after=self.zoe), self.ada)


class RotationAdminTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="housekeeper", email="", password="not-a-real-password"
        )
        self.client.force_login(user)
        self.chore = make_chore()
        self.ada = Member.objects.create(name="Ada")
        self.mia = Member.objects.create(name="Mia")
        self.change_url = reverse(
            "admin:chores_chore_change", args=[self.chore.pk]
        )

    def test_chore_page_offers_the_rotation_inline(self):
        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "rotation_slots-TOTAL_FORMS")

    def test_rotation_can_be_reordered_from_the_chore_page(self):
        ada_slot = add_to_rotation(self.chore, self.ada, position=0)
        mia_slot = add_to_rotation(self.chore, self.mia, position=1)
        self.assertEqual(active_rotation(self.chore), [self.ada, self.mia])

        response = self.client.post(
            self.change_url,
            {
                "name": self.chore.name,
                "description": "",
                "recurrence": self.chore.recurrence,
                "rotation_slots-TOTAL_FORMS": "2",
                "rotation_slots-INITIAL_FORMS": "2",
                "rotation_slots-MIN_NUM_FORMS": "0",
                "rotation_slots-MAX_NUM_FORMS": "1000",
                "rotation_slots-0-id": str(ada_slot.pk),
                "rotation_slots-0-chore": str(self.chore.pk),
                "rotation_slots-0-member": str(self.ada.pk),
                "rotation_slots-0-position": "1",
                "rotation_slots-1-id": str(mia_slot.pk),
                "rotation_slots-1-chore": str(self.chore.pk),
                "rotation_slots-1-member": str(self.mia.pk),
                "rotation_slots-1-position": "0",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(active_rotation(self.chore), [self.mia, self.ada])
