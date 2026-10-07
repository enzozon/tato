import calendar
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import Engine, func
from sqlmodel import col, select

from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.agent_routes import handled
from app.agent_rules import month_start
from app.crypto import decrypt_text, load_key
from app.llm_service import require_active
from app.models import Account, Category, Transaction
from app.plans import user_plan
from app.rate_limit import check_rate

router = APIRouter(tags=["resumo financeiro"])


class AccountView(BaseModel):
    id: UUID
    name: str
    kind: str
    opening_date: date
    balance_cents: str


class CategoryTotal(BaseModel):
    name: str
    amount_cents: str


class Dashboard(BaseModel):
    as_of: date
    month_start: date
    accounts: list[AccountView]
    balance_cents: str
    expense_cents: str
    categories: list[CategoryTotal]
    projected_balance_cents: str | None = None
    source: str = "ledger_summary_v1"


def summary(engine: Engine, owner: UUID, today: date) -> Dashboard:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        accounts = session.exec(
            select(Account).where(Account.user_id == owner).order_by(col(Account.created_at))
        ).all()
        views = []
        balance = 0
        cash_expenses = 0
        complete_history = bool(accounts)
        for account in accounts:
            total = session.exec(
                select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                    Transaction.user_id == owner,
                    Transaction.account_id == account.id,
                    Transaction.booked_on >= account.opening_date,
                    Transaction.booked_on <= today,
                )
            ).one()
            amount = account.opening_balance_cents + int(total)
            if account.kind != "credit_card" and account.opening_date <= today:
                balance += amount
                spent = session.exec(
                    select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                        Transaction.user_id == owner,
                        Transaction.account_id == account.id,
                        Transaction.kind == "expense",
                        Transaction.booked_on >= month_start(today),
                        Transaction.booked_on <= today,
                    )
                ).one()
                cash_expenses -= int(spent)
                complete_history &= account.opening_date <= month_start(today)
            elif account.kind != "credit_card":
                complete_history = False
            views.append(
                AccountView(
                    id=account.id,
                    kind=account.kind,
                    name=decrypt_text(account.name_ciphertext, key, owner, "account"),
                    opening_date=account.opening_date,
                    balance_cents=str(amount),
                )
            )
        rows = session.exec(
            select(Category.name, func.sum(Transaction.amount_cents))
            .select_from(Transaction)
            .outerjoin(
                Category,
                (col(Category.id) == col(Transaction.category_id))
                & (col(Category.user_id) == col(Transaction.user_id)),
            )
            .where(
                Transaction.user_id == owner,
                Transaction.kind == "expense",
                Transaction.booked_on >= month_start(today),
                Transaction.booked_on <= today,
            )
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount_cents))
        ).all()
        categories = [
            CategoryTotal(name=name or "Sem categoria", amount_cents=str(-int(total)))
            for name, total in rows
        ]
        return Dashboard(
            as_of=today,
            month_start=month_start(today),
            accounts=views,
            balance_cents=str(balance),
            expense_cents=str(sum(int(row.amount_cents) for row in categories)),
            categories=categories[:5],
            projected_balance_cents=(
                str(
                    balance
                    - (
                        cash_expenses
                        * (calendar.monthrange(today.year, today.month)[1] - today.day)
                        + today.day
                        - 1
                    )
                    // today.day
                )
                if complete_history and any(a.kind != "credit_card" for a in accounts)
                else None
            ),
        )


@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(identity: IdentityDep, engine: EngineDep, response: Response) -> Dashboard:
    response.headers["Cache-Control"] = "no-store"
    with handled():
        return summary(engine, identity.id, datetime.now(ZoneInfo("America/Sao_Paulo")).date())
