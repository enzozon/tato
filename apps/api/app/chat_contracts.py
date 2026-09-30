from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.chat_intent import Entry
from app.chat_tools import ExpenseResult
from app.rag.retrieval import Hit


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    account_id: UUID | None = None


class ChatReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: UUID
    intent: Literal["analytical", "entry", "conceptual", "conversation"]
    message: str = Field(max_length=4000, repr=False)
    mood: Literal["calmo", "atento", "alerta", "comemorando", "dormindo"] = "calmo"
    expense: ExpenseResult | None = None
    draft: Entry | None = None
    transaction_id: UUID | None = None
    sources: list[Hit] = Field(default_factory=list, max_length=5, repr=False)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirm: Literal[True]
