"""Importar este módulo registra os modelos para o Alembic."""

from app.models.documents import Chunk, Document
from app.models.ledger import Account, Category, Transaction, User
from app.models.planning import Goal, Insight, Rule, Subscription

__all__ = [
    "Account",
    "Category",
    "Chunk",
    "Document",
    "Goal",
    "Insight",
    "Rule",
    "Subscription",
    "Transaction",
    "User",
]
