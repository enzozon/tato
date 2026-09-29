from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from sqlmodel import Session

from app.repositories import expense_total


class ExpenseQuery(BaseModel):
    """A ferramenta aceita parâmetros tipados, nunca SQL ou identidade do cliente."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    tool: Literal["expense_total"]
    start: date
    end: date

    @model_validator(mode="after")
    def valid_period(self) -> Self:
        if self.end <= self.start:
            raise ValueError("O fim deve ser posterior ao início.")
        return self


class ExpenseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source: ExpenseQuery
    amount_cents: int


def run_expense_query(session: Session, owner: UUID, query: ExpenseQuery) -> ExpenseResult:
    """O chamador fornece a sessão RLS e o proprietário autenticado."""
    return ExpenseResult(
        source=query,
        amount_cents=expense_total(session, owner, query.start, query.end),
    )


def render_expense(result: ExpenseResult) -> str:
    # Inteiros preservam os centavos mesmo além da precisão de float.
    whole, fraction = divmod(result.amount_cents, 100)
    amount = f"{whole:,}".replace(",", ".") + f",{fraction:02d}"
    return (
        f"Despesas de {result.source.start:%d/%m/%Y} até "
        f"{result.source.end:%d/%m/%Y} (fim exclusivo): R$ {amount}."
    )
