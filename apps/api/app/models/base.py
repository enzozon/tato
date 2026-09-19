from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData
from sqlmodel import Field, SQLModel

SQLModel.metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Record(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # SQLModel aceita a instância do tipo em runtime; seu overload só declara classes.
    created_at: datetime = Field(  # type: ignore[call-overload]
        default_factory=lambda: datetime.now(UTC), sa_type=DateTime(timezone=True)
    )


class TenantRecord(Record):
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
