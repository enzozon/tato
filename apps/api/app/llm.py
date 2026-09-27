from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["groq", "gemini", "openrouter"]


class Generation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    instruction: str = Field(min_length=1, max_length=4000, repr=False)
    data: str = Field(min_length=1, max_length=16000, repr=False)
    classification: Literal["synthetic", "public", "personal"] = "personal"
    max_output_tokens: int = Field(default=512, strict=True, ge=1, le=2048)


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(max_length=64000, repr=False)
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)


class ProviderError(Exception):
    def __init__(self, reason: str, *, retryable: bool = False, cooldown: int = 60):
        super().__init__(reason)
        self.retryable = retryable
        self.cooldown = max(1, min(cooldown, 86400))


class LLMUnavailable(Exception):
    """Nenhum resultado validado: o chamador deve usar resposta determinística."""

    attempts: tuple["Attempt", ...] = ()


class LLMProvider(Protocol):
    name: ProviderName
    model: str

    def generate(self, request: Generation, schema: dict[str, object]) -> Completion: ...


@dataclass(frozen=True)
class Attempt:
    provider: ProviderName
    outcome: Literal["ok", "error", "invalid", "circuit_open", "policy"]
    input_tokens: int | None = None
    output_tokens: int | None = None
    elapsed_ms: int = 0


class MoneyAnswer(BaseModel):
    """Somente IDs e centavos; redação monetária é feita pelo código chamador."""

    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str
    amount_cents: int


def verify_money(answer: MoneyAnswer, facts: dict[str, int]) -> bool:
    return answer.source_id in facts and facts[answer.source_id] == answer.amount_cents
