import json
import re
from datetime import date, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine

from app.categorization import normalize
from app.llm import Generation, LLMUnavailable
from app.llm_service import generate


class Analytical(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: Literal["analytical"] = "analytical"
    start: date
    end: date
    category: str | None = Field(default=None, max_length=80)


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: Literal["entry"] = "entry"
    amount_cents: int = Field(gt=0, lt=2**63)
    kind: Literal["expense", "income"]
    booked_on: date
    description: str = Field(min_length=1, max_length=500, repr=False)


class Conceptual(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: Literal["conceptual"] = "conceptual"


class Conversation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: Literal["conversation"] = "conversation"
    clarify: bool = True


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    choice: Annotated[Analytical | Entry | Conceptual | Conversation, Field(discriminator="intent")]


def local_intent(question: str, today: date) -> Decision:
    text = normalize(question.strip()).rstrip("?.!")
    match = re.fullmatch(
        r"quanto gastei(?: com (.{1,80}?))? "
        r"(este mes|esse mes|neste mes|nesse mes|mes passado|no mes passado)",
        text,
    )
    if match:
        start = today.replace(day=1)
        if "passado" in match[2]:
            end, start = start, (start - timedelta(days=1)).replace(day=1)
        else:
            end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return Decision(choice=Analytical(start=start, end=end, category=match[1]))
    match = re.fullmatch(
        r"(gastei|recebi) (?:r\$\s*)?(\d{1,12})(?:,(\d{1,2}))? "
        r"(?:no|na|com|de) (.{1,500}?) (hoje|ontem)",
        question.strip(),
        re.IGNORECASE,
    )
    if match:
        amount = int(match[2]) * 100 + int((match[3] or "").ljust(2, "0"))
        if amount > 0 and not re.search(r"\b(ontem|hoje|gastei|recebi)\b", normalize(match[4])):
            return Decision(
                choice=Entry(
                    amount_cents=amount,
                    kind="expense" if match[1].lower() == "gastei" else "income",
                    booked_on=today - timedelta(days=match[5].lower() == "ontem"),
                    description=match[4],
                )
            )
    if re.fullmatch(r"(o que e|o que significa|explique) [a-z -]{2,100}", text):
        return Decision(choice=Conceptual())
    return Decision(choice=Conversation(clarify=text not in {"oi", "ola", "bom dia", "obrigado"}))


def classify(
    engine: Engine, owner: UUID, question: str, today: date, history: list[tuple[str, str]]
) -> Decision:
    local = local_intent(question, today)
    if not isinstance(local.choice, Conversation) or not local.choice.clarify:
        return local
    request = Generation(
        instruction=(
            "Classifique em analytical, entry, conceptual ou conversation. Não invente "
            "datas, valores ou categorias. Use conversation com clarify=true se ambíguo. "
            "Analytical suporta apenas total de despesas em período; não saldo ou previsão."
        ),
        data=json.dumps(
            {"question": question, "today": today.isoformat(), "history": history},
            ensure_ascii=False,
        ),
        classification="personal",
    )
    try:
        return generate(
            engine,
            owner,
            request,
            Decision,
            lambda value: (
                not isinstance(value.choice, Analytical) or value.choice.end > value.choice.start
            ),
        ).value
    except LLMUnavailable:
        return local
