"""Persistence, behind an interface.

Route handlers depend on `CardRepository` only. Phase 1 backs it with a dict;
phase 2 will back it with SQLAlchemy, and nothing above this line changes.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain import Card, CardNotFound, LaneId, utcnow


class CardRepository(Protocol):
    def list_by_lane(self, lane: LaneId) -> list[Card]:
        """Cards in that lane, ordered by position ascending."""

    def get(self, card_id: str) -> Card:
        """Raises CardNotFound if the id is unknown."""

    def add(self, card: Card) -> Card:
        """Appends the card to the end of its lane."""

    def replace(self, card: Card) -> Card:
        """Persists edits to an existing card's content."""

    def move(self, card_id: str, lane: LaneId, position: int) -> Card:
        """Re-lanes and re-ranks, renormalizing both lanes involved."""

    def delete(self, card_id: str) -> None:
        """Removes the card and closes the gap it leaves behind."""


def new_card_id() -> str:
    return str(uuid.uuid4())


class InMemoryCardRepository:
    """A dict-backed store. Its contents live only as long as the process."""

    def __init__(self) -> None:
        self._cards: dict[str, Card] = {}

    # ---------- reads ----------

    def list_by_lane(self, lane: LaneId) -> list[Card]:
        return sorted(
            (card for card in self._cards.values() if card.lane == lane),
            key=lambda card: card.position,
        )

    def get(self, card_id: str) -> Card:
        try:
            return self._cards[card_id]
        except KeyError:
            raise CardNotFound(card_id) from None

    # ---------- writes ----------

    def add(self, card: Card) -> Card:
        card.position = len(self.list_by_lane(card.lane))
        self._cards[card.id] = card
        return card

    def replace(self, card: Card) -> Card:
        self.get(card.id)  # 404 rather than a silent insert
        self._cards[card.id] = card
        return card

    def move(self, card_id: str, lane: LaneId, position: int) -> Card:
        card = self.get(card_id)
        source = card.lane

        # `position` is read against the target lane with the card taken out,
        # which is what makes "drop onto the card at index n" land at n.
        target = [other for other in self.list_by_lane(lane) if other.id != card_id]
        index = max(0, min(position, len(target)))

        card.lane = lane
        card.updated_at = utcnow()
        target.insert(index, card)
        self._renumber(target)

        if source != lane:
            self._renumber(self.list_by_lane(source))

        return card

    def delete(self, card_id: str) -> None:
        card = self.get(card_id)
        del self._cards[card_id]
        self._renumber(self.list_by_lane(card.lane))

    # ---------- internals ----------

    @staticmethod
    def _renumber(cards: list[Card]) -> None:
        for index, card in enumerate(cards):
            card.position = index
