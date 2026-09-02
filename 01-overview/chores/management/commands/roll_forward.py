from django.core.management.base import BaseCommand
from django.utils import timezone

from chores.services import roll_forward


class Command(BaseCommand):
    help = "Advance chores whose open assignment has fallen past due."

    def handle(self, *args, **options):
        created = roll_forward(timezone.localdate())
        self.stdout.write(f"Created {created} successor assignment(s).")
