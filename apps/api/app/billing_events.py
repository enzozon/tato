from datetime import UTC, datetime
from re import fullmatch
from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.billing_database import billing_account_session
from app.billing_resolution import (
    SubscriptionReference,
    find_reserved_checkout,
    object_by_id,
    resolve_subscription,
)
from app.billing_stripe import BillingUnavailable, StripeSandbox
from app.models import BillingCheckout, BillingEvent, Subscription, User


def apply_checkout(
    session: Session,
    provider: StripeSandbox,
    row: BillingCheckout,
    reference: SubscriptionReference | None = None,
) -> bool:
    remote = (
        provider.retrieve_checkout(row.external_id, row.user_id, row.request_id)
        if row.external_id
        else find_reserved_checkout(provider, row.user_id, row.request_id, row.created_at)
    )
    if remote is None:
        raise BillingUnavailable("Reserva remota não localizada; reconciliação pendente.")
    if row.provider != "stripe" or row.amount_cents != 3900:
        raise BillingUnavailable("Reserva local divergente.")
    if reference is not None and (
        reference.checkout_id not in {None, remote.id}
        or reference.subscription_id != remote.subscription
        or reference.customer_id != remote.customer
    ):
        raise BillingUnavailable("Vínculo remoto/local divergente.")
    row.external_id = remote.id
    if remote.status != "complete":
        if remote.status == "expired":
            row.status, row.completed_at = "canceled", datetime.now(UTC)
        session.add(row)
        return True
    current = session.exec(select(Subscription).where(Subscription.user_id == row.user_id)).first()
    if current is not None and current.billing_provider not in {None, "stripe"}:
        raise BillingUnavailable("Assinatura vinculada a outro provedor.")
    if (
        current is not None
        and current.billing_provider == "stripe"
        and (
            not isinstance(current.external_id, str)
            or not fullmatch(r"sub_[A-Za-z0-9_]+", current.external_id)
            or not isinstance(current.external_customer_id, str)
            or not fullmatch(r"cus_[A-Za-z0-9_]+", current.external_customer_id)
            or current.external_customer_id != remote.customer
        )
    ):
        raise BillingUnavailable("Cliente de assinatura local divergente ou incompleto.")
    if current is not None and current.external_id not in {None, remote.subscription}:
        if (
            row.status != "pending"
            or remote.status != "complete"
            or remote.payment_status != "paid"
        ):
            return False  # Evento de assinatura anterior não substitui o vínculo atual.
        old = object_by_id(provider, "subscriptions", current.external_id, "sub")
        if (
            old.get("status") not in {"canceled", "incomplete_expired"}
            or old.get("customer") != remote.customer
        ):
            raise BillingUnavailable("Assinatura anterior ainda não encerrada.")
    if remote.status == "complete":
        if remote.customer is None or remote.subscription is None:
            raise BillingUnavailable("Checkout concluído sem assinatura vinculada.")
        state = provider.subscription_state(
            remote.subscription, row.user_id, row.request_id, remote.customer
        )
        current = current or Subscription(user_id=row.user_id)
        current.billing_provider, current.external_id = "stripe", state.id
        current.external_customer_id, current.valid_until = state.customer, state.valid_until
        current.plan, current.status = "pro", state.status
        session.add(current)
        row.status, row.completed_at = "paid", row.completed_at or datetime.now(UTC)
    session.add(row)
    return True


def process_event(
    engine: Engine, provider: StripeSandbox, event_id: str, kind: str, object_id: str
) -> bool:
    if not fullmatch(r"evt_[A-Za-z0-9_]+", event_id):
        raise BillingUnavailable("Identificador de evento inválido.")
    reference = resolve_subscription(provider, kind, object_id)
    with billing_account_session(engine, reference.owner) as session:
        user = session.get(User, reference.owner)
        if user is None or user.deletion_requested_at is not None:
            return False
        previous = session.exec(
            select(BillingEvent).where(
                BillingEvent.user_id == reference.owner,
                BillingEvent.provider == "stripe",
                BillingEvent.event_id == event_id,
            )
        ).first()
        if previous is not None:
            return False
        row = session.exec(
            select(BillingCheckout).where(
                BillingCheckout.user_id == reference.owner,
                BillingCheckout.request_id == reference.request_id,
                BillingCheckout.provider == "stripe",
            )
        ).first()
        if row is None:
            return False
        applied = apply_checkout(session, provider, row, reference)
        session.add(BillingEvent(user_id=reference.owner, provider="stripe", event_id=event_id))
        return applied


def reconcile(engine: Engine, provider: StripeSandbox, owner: UUID, request_id: UUID) -> bool:
    with billing_account_session(engine, owner) as session:
        user = session.get(User, owner)
        if user is None or user.deletion_requested_at is not None:
            raise BillingUnavailable("Conta indisponível para reconciliação.")
        row = session.exec(
            select(BillingCheckout).where(
                BillingCheckout.user_id == owner,
                BillingCheckout.request_id == request_id,
                BillingCheckout.provider == "stripe",
            )
        ).first()
        if row is None:
            raise BillingUnavailable("Reserva local não encontrada.")
        return apply_checkout(session, provider, row)
