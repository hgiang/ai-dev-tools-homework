"""The SQLAlchemy-backed CardRepository.

Same contract as InMemoryCardRepository, same ordering rules — the API layer
cannot tell them apart, which is what the shared test suite checks.
"""

from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import CardRow
from app.domain import Card, CardNotFound, LaneId, utcnow


def _to_domain(row: CardRow) -> Card:
    return Card(
        id=row.id,
        title=row.title,
        description=row.description,
        labels=list(row.labels),
        due_date=row.due_date,
        lane=LaneId(row.lane),
        position=row.position,
        # SQLite drops the offset on the way in, so a naive value read back is
        # still the UTC instant that was written.
        created_at=_as_utc(row.created_at),
        updated_at=_as_utc(row.updated_at),
    )


def _as_utc(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _apply(row: CardRow, card: Card) -> None:
    row.title = card.title
    row.description = card.description
    row.labels = list(card.labels)
    row.due_date = card.due_date
    row.lane = card.lane.value
    row.position = card.position
    row.updated_at = card.updated_at


class SqlCardRepository:
    """Opens one short transaction per operation."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    # ---------- reads ----------

    def list_by_lane(self, lane: LaneId) -> list[Card]:
        with self._session_factory() as session:
            return [_to_domain(row) for row in self._rows_in(session, lane)]

    def get(self, card_id: str) -> Card:
        with self._session_factory() as session:
            return _to_domain(self._row(session, card_id))

    # ---------- writes ----------

    def add(self, card: Card) -> Card:
        with self._session_factory() as session:
            card.position = len(self._rows_in(session, card.lane))
            row = CardRow(
                id=card.id,
                title=card.title,
                description=card.description,
                labels=list(card.labels),
                due_date=card.due_date,
                lane=card.lane.value,
                position=card.position,
                created_at=card.created_at,
                updated_at=card.updated_at,
            )
            session.add(row)
            session.commit()
            return _to_domain(row)

    def replace(self, card: Card) -> Card:
        with self._session_factory() as session:
            row = self._row(session, card.id)
            # Lane and position are the move operation's business, not this one's.
            card.lane = LaneId(row.lane)
            card.position = row.position
            _apply(row, card)
            session.commit()
            return _to_domain(row)

    def move(self, card_id: str, lane: LaneId, position: int) -> Card:
        with self._session_factory() as session:
            row = self._row(session, card_id)
            source = LaneId(row.lane)

            target = [
                other
                for other in self._rows_in(session, lane)
                if other.id != card_id
            ]
            index = max(0, min(position, len(target)))

            row.lane = lane.value
            row.updated_at = utcnow()
            target.insert(index, row)
            self._renumber(target)

            if source != lane:
                self._renumber(self._rows_in(session, source))

            session.commit()
            return _to_domain(row)

    def delete(self, card_id: str) -> None:
        with self._session_factory() as session:
            row = self._row(session, card_id)
            lane = LaneId(row.lane)
            session.delete(row)
            session.flush()
            self._renumber(self._rows_in(session, lane))
            session.commit()

    # ---------- internals ----------

    @staticmethod
    def _rows_in(session: Session, lane: LaneId) -> list[CardRow]:
        return list(
            session.scalars(
                select(CardRow)
                .where(CardRow.lane == lane.value)
                .order_by(CardRow.position)
            )
        )

    @staticmethod
    def _row(session: Session, card_id: str) -> CardRow:
        row = session.get(CardRow, card_id)
        if row is None:
            raise CardNotFound(card_id)
        return row

    @staticmethod
    def _renumber(rows: list[CardRow]) -> None:
        for index, row in enumerate(rows):
            row.position = index
