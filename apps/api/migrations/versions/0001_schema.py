"""Schema inicial gerado por SQLAlchemy e revisado antes da execução."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_users PRIMARY KEY (id)
);

CREATE TABLE accounts (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	name_ciphertext BYTEA NOT NULL,
	kind VARCHAR(20) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	opening_balance_cents BIGINT NOT NULL,
	opening_date DATE NOT NULL,
	CONSTRAINT pk_accounts PRIMARY KEY (id),
	CONSTRAINT uq_accounts_user_id_id UNIQUE (user_id, id),
	CONSTRAINT ck_accounts_currency CHECK (currency = 'BRL'),
	CONSTRAINT ck_accounts_kind CHECK (kind IN ('checking', 'savings', 'credit_card', 'cash')),
	CONSTRAINT fk_accounts_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE categories (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	name VARCHAR(80) NOT NULL,
	CONSTRAINT pk_categories PRIMARY KEY (id),
	CONSTRAINT uq_categories_user_id_id UNIQUE (user_id, id),
	CONSTRAINT uq_categories_user_id_name UNIQUE (user_id, name),
	CONSTRAINT ck_categories_name CHECK (length(trim(name)) > 0),
	CONSTRAINT fk_categories_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE documents (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	name_ciphertext BYTEA NOT NULL,
	content_ciphertext BYTEA NOT NULL,
	kind VARCHAR(10) NOT NULL,
	digest VARCHAR(64) NOT NULL,
	CONSTRAINT pk_documents PRIMARY KEY (id),
	CONSTRAINT uq_documents_user_id_id UNIQUE (user_id, id),
	CONSTRAINT uq_documents_user_id_digest UNIQUE (user_id, digest),
	CONSTRAINT ck_documents_kind CHECK (kind IN ('csv', 'ofx', 'pdf', 'note', 'summary')),
	CONSTRAINT ck_documents_digest CHECK (digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT fk_documents_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE goals (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	description_ciphertext BYTEA NOT NULL,
	target_cents BIGINT NOT NULL,
	due_on DATE,
	CONSTRAINT pk_goals PRIMARY KEY (id),
	CONSTRAINT ck_goals_target CHECK (target_cents > 0),
	CONSTRAINT fk_goals_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_goals_user ON goals (user_id);

CREATE TABLE insights (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	agent_kind VARCHAR(32) NOT NULL,
	content_ciphertext BYTEA NOT NULL,
	event_key VARCHAR(128) NOT NULL,
	read_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_insights PRIMARY KEY (id),
	CONSTRAINT uq_insights_user_id_event_key UNIQUE (user_id, event_key),
	CONSTRAINT ck_insights_agent_kind CHECK (agent_kind IN ('subscription_watch', 'anomaly', 'runway', 'goal')),
	CONSTRAINT fk_insights_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE subscriptions (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	plan VARCHAR(10) NOT NULL,
	status VARCHAR(16) NOT NULL,
	CONSTRAINT pk_subscriptions PRIMARY KEY (id),
	CONSTRAINT uq_subscriptions_user_id UNIQUE (user_id),
	CONSTRAINT ck_subscriptions_plan CHECK (plan IN ('free', 'pro')),
	CONSTRAINT ck_subscriptions_status CHECK (status IN ('active', 'past_due', 'canceled')),
	CONSTRAINT fk_subscriptions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE chunks (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	document_id UUID NOT NULL,
	position INTEGER NOT NULL,
	content_ciphertext BYTEA NOT NULL,
	embedding VECTOR(384),
	CONSTRAINT pk_chunks PRIMARY KEY (id),
	CONSTRAINT fk_chunks_user_id_documents FOREIGN KEY(user_id, document_id) REFERENCES documents (user_id, id) ON DELETE CASCADE,
	CONSTRAINT uq_chunks_user_id_document_id_position UNIQUE (user_id, document_id, position),
	CONSTRAINT ck_chunks_position CHECK (position >= 0),
	CONSTRAINT fk_chunks_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE rules (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	pattern_ciphertext BYTEA NOT NULL,
	category_id UUID NOT NULL,
	priority INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	CONSTRAINT pk_rules PRIMARY KEY (id),
	CONSTRAINT fk_rules_user_id_categories FOREIGN KEY(user_id, category_id) REFERENCES categories (user_id, id),
	CONSTRAINT ck_rules_priority CHECK (priority >= 0),
	CONSTRAINT fk_rules_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_rules_user_category ON rules (user_id, category_id);

CREATE TABLE transactions (
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	user_id UUID NOT NULL,
	account_id UUID NOT NULL,
	category_id UUID,
	booked_on DATE NOT NULL,
	amount_cents BIGINT NOT NULL,
	kind VARCHAR(10) NOT NULL,
	description_ciphertext BYTEA NOT NULL,
	dedup_key VARCHAR(64) NOT NULL,
	CONSTRAINT pk_transactions PRIMARY KEY (id),
	CONSTRAINT fk_transactions_user_id_accounts FOREIGN KEY(user_id, account_id) REFERENCES accounts (user_id, id),
	CONSTRAINT fk_transactions_user_id_categories FOREIGN KEY(user_id, category_id) REFERENCES categories (user_id, id),
	CONSTRAINT uq_transactions_user_id_account_id_dedup_key UNIQUE (user_id, account_id, dedup_key),
	CONSTRAINT ck_transactions_amount_kind CHECK ((kind = 'income' AND amount_cents > 0) OR (kind = 'expense' AND amount_cents < 0) OR (kind = 'transfer' AND amount_cents <> 0)),
	CONSTRAINT ck_transactions_dedup_key CHECK (dedup_key ~ '^[0-9a-f]{64}$'),
	CONSTRAINT fk_transactions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_transactions_user_account_date ON transactions (user_id, account_id, booked_on);

CREATE INDEX ix_transactions_user_category ON transactions (user_id, category_id);

CREATE INDEX ix_transactions_user_date ON transactions (user_id, booked_on, id);
    """)


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("rules")
    op.drop_table("chunks")
    op.drop_table("subscriptions")
    op.drop_table("insights")
    op.drop_table("goals")
    op.drop_table("documents")
    op.drop_table("categories")
    op.drop_table("accounts")
    op.drop_table("users")
