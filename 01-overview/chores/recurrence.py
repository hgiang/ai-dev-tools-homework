"""Pure date arithmetic for chore recurrence.

Every function here returns a new `date`; nothing is mutated.
"""

import calendar
from datetime import date, timedelta

from chores.models import Chore


def next_due_date(from_date, recurrence):
    """The next due date after `from_date` for the given recurrence.

    Monthly clamps to the last day of the target month (Jan 31 -> Feb 28,
    or Feb 29 in a leap year) rather than overflowing into the month after.
    """
    if recurrence == Chore.Recurrence.DAILY:
        return from_date + timedelta(days=1)
    if recurrence == Chore.Recurrence.WEEKLY:
        return from_date + timedelta(days=7)
    if recurrence == Chore.Recurrence.MONTHLY:
        return _add_one_month_clamped(from_date)
    raise ValueError(f"Unknown recurrence: {recurrence!r}")


def _add_one_month_clamped(from_date):
    year = from_date.year + from_date.month // 12
    month = from_date.month % 12 + 1
    last_day_of_target_month = calendar.monthrange(year, month)[1]
    day = min(from_date.day, last_day_of_target_month)
    return date(year, month, day)
