from django.db import models

MEMBER_NAME_MAX_LENGTH = 100
CHORE_NAME_MAX_LENGTH = 100
RECURRENCE_MAX_LENGTH = 10


class Member(models.Model):
    """A person in the household who chores can be assigned to."""

    name = models.CharField(max_length=MEMBER_NAME_MAX_LENGTH, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive members keep their history but are skipped in rotations.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Chore(models.Model):
    """A recurring household task, independent of who currently owes it."""

    class Recurrence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    name = models.CharField(max_length=CHORE_NAME_MAX_LENGTH, unique=True)
    description = models.TextField(blank=True)
    recurrence = models.CharField(
        max_length=RECURRENCE_MAX_LENGTH,
        choices=Recurrence.choices,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
