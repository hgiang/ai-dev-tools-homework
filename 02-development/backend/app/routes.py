"""HTTP surface. Every handler delegates to the repository."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_repository
from app.domain import LANE_NAMES, LANE_ORDER, Card, utcnow
from app.repository import CardRepository, new_card_id
from app.schemas import (
    BoardOut,
    CardCreate,
    CardMove,
    CardOut,
    CardUpdate,
    Health,
    LaneOut,
)

router = APIRouter(prefix="/api")

Repo = Depends(get_repository)


@router.get("/health", response_model=Health, tags=["health"])
def get_health() -> Health:
    return Health()


@router.get("/board", response_model=BoardOut, tags=["board"])
def get_board(repository: CardRepository = Repo) -> BoardOut:
    return BoardOut(
        lanes=[
            LaneOut(
                id=lane,
                name=LANE_NAMES[lane],
                cards=[
                    CardOut.model_validate(card)
                    for card in repository.list_by_lane(lane)
                ],
            )
            for lane in LANE_ORDER
        ]
    )


@router.post(
    "/cards",
    response_model=CardOut,
    status_code=status.HTTP_201_CREATED,
    tags=["cards"],
)
def create_card(
    payload: CardCreate, repository: CardRepository = Repo
) -> CardOut:
    now = utcnow()
    card = repository.add(
        Card(
            id=new_card_id(),
            title=payload.title,
            description=payload.description,
            labels=payload.labels,
            due_date=payload.due_date,
            lane=payload.lane,
            created_at=now,
            updated_at=now,
        )
    )
    return CardOut.model_validate(card)


@router.get("/cards/{card_id}", response_model=CardOut, tags=["cards"])
def get_card(card_id: str, repository: CardRepository = Repo) -> CardOut:
    return CardOut.model_validate(repository.get(card_id))


@router.patch("/cards/{card_id}", response_model=CardOut, tags=["cards"])
def update_card(
    card_id: str, payload: CardUpdate, repository: CardRepository = Repo
) -> CardOut:
    card = repository.get(card_id)

    # exclude_unset is what separates "field absent" from "field set to null" —
    # the difference between leaving a due date alone and clearing it.
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, name, value)
    card.updated_at = utcnow()

    return CardOut.model_validate(repository.replace(card))


@router.post("/cards/{card_id}/move", response_model=CardOut, tags=["cards"])
def move_card(
    card_id: str, payload: CardMove, repository: CardRepository = Repo
) -> CardOut:
    card = repository.move(card_id, payload.lane, payload.position)
    return CardOut.model_validate(card)


@router.delete(
    "/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["cards"]
)
def delete_card(card_id: str, repository: CardRepository = Repo) -> Response:
    repository.delete(card_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
