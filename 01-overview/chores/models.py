from django.db import models

MEMBER_NAME_MAX_LENGTH = 100


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
