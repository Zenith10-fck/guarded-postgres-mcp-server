"""Pydantic v2 schemas for the write tools' inputs.

These validate *shape* -- that Claude sent a dict of values, a table name,
a confirm flag. The policy layer (policy.py) validates *authorization* --
that the table is writable and the specific columns are allowed. Both must
pass before anything reaches the database.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    values: dict[str, object] = Field(default_factory=dict)
    confirm: bool = False


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    pk_value: object
    changes: dict[str, object] = Field(default_factory=dict)
    confirm: bool = False
