import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.categorization import normalize

AgentKind = Literal["subscription_watch", "anomaly", "runway", "goal"]


@dataclass(frozen=True)
class Movement:
    booked_on: date
    amount_cents: int
    kind: str
    category_id: UUID | None = None
    description: str = field(default="", repr=False)


@dataclass(frozen=True)
class Snapshot:
    account_id: UUID
    as_of: date
    opening_date: date
    balance_cents: int
    movements: list[Movement] = field(repr=False)


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: AgentKind
    subject: str = Field(repr=False)
    message: str = Field(repr=False)
    facts: dict[str, int]
    account_id: UUID
    as_of: date
    source: Literal["ledger_snapshot_v1"] = "ledger_snapshot_v1"


def month_start(day: date, offset: int = 0) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 + offset, 12)
    return date(year, month + 1, 1)


def evaluate(kind: AgentKind, snapshot: Snapshot, target_cents: int | None = None) -> list[Signal]:
    today = snapshot.as_of
    current = month_start(today)
    expenses = [
        row
        for row in snapshot.movements
        if row.kind == "expense" and row.amount_cents < 0 and row.booked_on <= today
    ]
    signals: list[Signal] = []

    def emit(subject: str, message: str, facts: dict[str, int]) -> None:
        signals.append(
            Signal(
                kind=kind,
                subject=subject,
                message=message,
                facts=facts,
                account_id=snapshot.account_id,
                as_of=today,
            )
        )

    if kind == "goal":
        if target_cents is not None and target_cents > 0 and snapshot.balance_cents >= target_cents:
            emit(
                "goal",
                "O saldo registrado alcançou o alvo da meta; confirme o valor reservado.",
                {"balance_cents": snapshot.balance_cents, "target_cents": target_cents},
            )
    elif kind == "runway":
        spent = -sum(row.amount_cents for row in expenses if row.booked_on >= current)
        # Sem período completo desde o início do mês, a média diária seria enganosa.
        if snapshot.opening_date > current:
            return []
        remaining = calendar.monthrange(today.year, today.month)[1] - today.day
        projected = (spent * remaining + today.day - 1) // today.day
        if projected > snapshot.balance_cents:
            emit(
                "runway",
                "A projeção linear de despesas supera o saldo registrado. Revise o mês.",
                {
                    "balance_cents": snapshot.balance_cents,
                    "spent_cents": spent,
                    "projected_expense_cents": projected,
                    "remaining_days": remaining,
                },
            )
    elif kind == "anomaly":
        start = month_start(today, -3)
        if snapshot.opening_date > start:
            return []
        totals: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
        for row in expenses:
            if row.booked_on >= start and row.category_id is not None:
                totals[str(row.category_id)][month_start(row.booked_on)] -= row.amount_cents
        for category, months in sorted(totals.items()):
            history = [months[month_start(today, -n)] for n in (1, 2, 3)]
            total, actual = sum(history), months[current]
            variance_scaled = 3 * sum(value * value for value in history) - total * total
            delta = 3 * actual - total
            if total > 0 and delta > 0 and delta * delta > 4 * variance_scaled:
                emit(
                    category,
                    "A despesa da categoria superou o padrão dos meses completos anteriores.",
                    {
                        "spent_cents": actual,
                        "history_total_cents": total,
                        "history_months": 3,
                        "mean_cents_floor": total // 3,
                    },
                )
    else:
        groups: dict[str, dict[date, list[Movement]]] = defaultdict(lambda: defaultdict(list))
        for row in expenses:
            if row.description.strip() and row.booked_on >= month_start(today, -2):
                groups[normalize(row.description)][month_start(row.booked_on)].append(row)
        for description, recurring_months in sorted(groups.items()):
            recurring_history = [recurring_months[month_start(today, -n)] for n in (2, 1, 0)]
            if not all(len(rows) == 1 for rows in recurring_history):
                continue
            charges = [rows[0] for rows in recurring_history]
            if (
                max(row.booked_on.day for row in charges)
                - min(row.booked_on.day for row in charges)
                > 7
            ):
                continue
            previous, actual = -charges[-2].amount_cents, -charges[-1].amount_cents
            message = (
                "Uma possível cobrança recorrente aumentou; confira o serviço."
                if actual > previous
                else "Identifiquei uma possível cobrança recorrente; revise se ainda é útil."
            )
            emit(description, message, {"previous_cents": previous, "current_cents": actual})
    return signals
