"""The domain vocabulary: lanes, and the card as the server holds it.

Kept free of FastAPI, Pydantic and any storage concern so the repository
implementations and the API layer can both depend on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum


class LaneId(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


LANE_ORDER: tuple[LaneId, ...] = (LaneId.TODO, LaneId.DOING, LaneId.DONE)

LANE_NAMES: dict[LaneId, str] = {
    LaneId.TODO: "To Do",
    LaneId.DOING: "In Progress",
    LaneId.DONE: "Done",
}

TITLE_MAX = 200
DESCRIPTION_MAX = 2000
LABEL_MAX = 30
LABELS_MAX = 10


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Card:
    id: str
    title: str
    description: str = ""
    labels: list[str] = field(default_factory=list)
    due_date: date | None = None
    lane: LaneId = LaneId.TODO
    position: int = 0
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


class CardNotFound(LookupError):
    """Raised by a repository when no card carries the given id."""

    def __init__(self, card_id: str) -> None:
        super().__init__(f"Card {card_id} not found")
        self.card_id = card_id
