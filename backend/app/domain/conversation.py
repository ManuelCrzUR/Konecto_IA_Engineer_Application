"""Conversation contracts shared by db/sessions_repo.py, agent/ and api/.

HistoryTurn is what run_agent receives; AgentResult is what it returns.
SessionInfo / StoredMessage are what sessions_repo reads back.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import Product, ToolTrace

Role = Literal["user", "assistant"]


class HistoryTurn(BaseModel):
    """One past message passed to the agent. `part_numbers` lists the products
    shown in that turn, so follow-ups ("and its power?") can re-query them."""

    role: Role
    content: str
    part_numbers: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Output of run_agent. `products` are built by code from tool results,
    never by the LLM; `trace` has one entry per tool call."""

    answer: str
    products: list[Product] = Field(default_factory=list)
    trace: list[ToolTrace] = Field(default_factory=list)
    guard_triggered: bool = False


class SessionInfo(BaseModel):
    id: uuid.UUID
    user_id: str | None = None
    title: str
    created_at: datetime
    updated_at: datetime


class StoredMessage(BaseModel):
    id: int
    session_id: uuid.UUID
    role: Role
    content: str
    products: list[Product] = Field(default_factory=list)
    trace: list[ToolTrace] = Field(default_factory=list)
    created_at: datetime
