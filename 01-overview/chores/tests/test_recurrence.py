"""Tests for pure recurrence date arithmetic (Task 4)."""

from datetime import date

from django.test import SimpleTestCase

from chores.models import Chore
from chores.recurrence import next_due_date


class NextDueDateTests(SimpleTestCase):
    def test_daily_adds_one_day(self):
        self.assertEqual(
            next_due_date(date(2026, 3, 10), Chore.Recurrence.DAILY),
            date(2026, 3, 11),
        )

    def test_weekly_adds_seven_days(self):
        self.assertEqual(
            next_due_date(date(2026, 3, 10), Chore.Recurrence.WEEKLY),
            date(2026, 3, 17),
        )

    def test_monthly_adds_one_month(self):
        self.assertEqual(
            next_due_date(date(2026, 3, 15), Chore.Recurrence.MONTHLY),
            date(2026, 4, 15),
        )

    def test_monthly_wraps_into_the_next_year(self):
        self.assertEqual(
            next_due_date(date(2025, 12, 15), Chore.Recurrence.MONTHLY),
            date(2026, 1, 15),
        )

    def test_monthly_clamps_to_month_end_in_a_non_leap_year(self):
        self.assertEqual(
            next_due_date(date(2025, 1, 31), Chore.Recurrence.MONTHLY),
            date(2025, 2, 28),
        )

    def test_monthly_clamps_to_month_end_in_a_leap_year(self):
        self.assertEqual(
            next_due_date(date(2024, 1, 31), Chore.Recurrence.MONTHLY),
            date(2024, 2, 29),
        )

    def test_from_date_is_not_mutated(self):
        original = date(2026, 3, 10)

        next_due_date(original, Chore.Recurrence.DAILY)

        self.assertEqual(original, date(2026, 3, 10))

    def test_unknown_recurrence_raises_value_error(self):
        with self.assertRaises(ValueError):
            next_due_date(date(2026, 3, 10), "yearly")
