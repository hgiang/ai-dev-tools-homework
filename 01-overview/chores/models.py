from django.db import models

MEMBER_NAME_MAX_LENGTH = 100
CHORE_NAME_MAX_LENGTH = 100
RECURRENCE_MAX_LENGTH = 10
STATUS_MAX_LENGTH = 10


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


class RotationSlot(models.Model):
    """One member's place in a chore's rotation order.

    A slot survives its member going inactive, so deactivating and later
    reactivating someone restores their original place in the rotation.
    """

    chore = models.ForeignKey(
        Chore, on_delete=models.CASCADE, related_name="rotation_slots"
    )
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="rotation_slots"
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        # Ties broken by id so the order is deterministic even while two slots
        # transiently share a position, which is what reordering a formset does.
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["chore", "member"],
                name="unique_member_per_chore_rotation",
            ),
        ]

    def __str__(self):
        return f"{self.chore.name} #{self.position}: {self.member.name}"


class ChoreAssignment(models.Model):
    """One occurrence of a chore, owed by one member on one due date."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    chore = models.ForeignKey(
        Chore, on_delete=models.CASCADE, related_name="assignments"
    )
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="assignments"
    )
    due_date = models.DateField()
    status = models.CharField(
        max_length=STATUS_MAX_LENGTH,
        choices=Status.choices,
        default=Status.OPEN,
    )

    class Meta:
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["status", "due_date"], name="assignment_status_due_idx"),
        ]

    def __str__(self):
        return f"{self.chore.name} for {self.member.name}, due {self.due_date}"


class Completion(models.Model):
    """Append-only record that a member completed an assignment.

    One-to-one with the assignment, so the database itself rules out
    completing the same occurrence twice.
    """

    assignment = models.OneToOneField(
        ChoreAssignment, on_delete=models.CASCADE, related_name="completion"
    )
    completed_by = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="completions"
    )
    completed_at = models.DateTimeField()

    class Meta:
        ordering = ["-completed_at"]

    def __str__(self):
        return (
            f"{self.assignment.chore.name} completed by {self.completed_by.name} "
            f"on {self.completed_at:%Y-%m-%d}"
        )
