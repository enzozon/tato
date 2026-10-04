"""Importar este módulo registra os modelos para o Alembic."""

from app.models.agents import Agent
from app.models.chat import ChatTurn
from app.models.documents import Chunk, Document
from app.models.knowledge import KnowledgeChunk
from app.models.ledger import Account, Category, Transaction, User
from app.models.planning import Goal, Insight, Rule, Subscription

__all__ = [
    "Account",
    "Agent",
    "Category",
    "ChatTurn",
    "Chunk",
    "Document",
    "Goal",
    "Insight",
    "KnowledgeChunk",
    "Rule",
    "Subscription",
    "Transaction",
    "User",
]
