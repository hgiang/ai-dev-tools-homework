"""Wire format. Mirrors openapi.yaml, which is the contract of record."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import DESCRIPTION_MAX, LABEL_MAX, LABELS_MAX, TITLE_MAX, LaneId

Title = Annotated[str, Field(min_length=1, max_length=TITLE_MAX)]
Description = Annotated[str, Field(max_length=DESCRIPTION_MAX)]

# No per-item constraint here: blank entries are dropped rather than rejected,
# so the length limit is enforced in _clean_labels, after trimming. Input is
# lenient, output is strict — an empty label can never reach a response.
Labels = Annotated[list[str], Field(max_length=LABELS_MAX)]


def _clean_title(value: str) -> str:
    title = value.strip()
    if not title:
        raise ValueError("Title must not be blank")
    return title


def _clean_labels(values: list[str]) -> list[str]:
    """Trim, drop blanks, and de-duplicate case-insensitively, keeping order."""
    seen: set[str] = set()
    labels: list[str] = []
    for value in values:
        label = value.strip()
        if not label:
            continue
        if len(label) > LABEL_MAX:
            raise ValueError(f"Each label must be at most {LABEL_MAX} characters")
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    labels: list[str]
    due_date: date | None
    lane: LaneId
    position: int
    created_at: datetime
    updated_at: datetime


class CardCreate(BaseModel):
    title: Title
    description: Description = ""
    labels: Labels = Field(default_factory=list)
    due_date: date | None = None
    lane: LaneId = LaneId.TODO

    _title = field_validator("title")(_clean_title)
    _labels = field_validator("labels")(_clean_labels)

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return value.strip()


class CardUpdate(BaseModel):
    """Absent fields are left untouched; `due_date: null` clears the date."""

    title: Title | None = None
    description: Description | None = None
    labels: Labels | None = None
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return None if value is None else _clean_title(value)

    @field_validator("labels")
    @classmethod
    def _dedupe(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_labels(value)

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()


class CardMove(BaseModel):
    lane: LaneId
    position: int = Field(ge=0)


class LaneOut(BaseModel):
    id: LaneId
    name: str
    cards: list[CardOut]


class BoardOut(BaseModel):
    lanes: list[LaneOut]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
