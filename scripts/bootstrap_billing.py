"""Habilita login restrito de cobrança somente no banco local aprovado."""

import os

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def main() -> None:
    admin = make_url(os.environ["DATABASE_MIGRATION_URL"])
    runtime = make_url(os.environ["BILLING_DATABASE_URL"])
    if (
        admin.host not in {"localhost", "127.0.0.1"}
        or not ((admin.database or "").startswith("tato_dev_") or admin.database == "tato_test")
        or runtime.username != "tato_billing"
        or len(runtime.password or "") < 32
        or (admin.host, admin.port, admin.database)
        != (runtime.host, runtime.port, runtime.database)
    ):
        raise ValueError("Bootstrap exige banco local novo e papel tato_billing.")
    with psycopg.connect(
        admin.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as connection:
        role = connection.execute(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolinherit "
            "FROM pg_roles WHERE rolname = 'tato_billing'"
        ).fetchone()
        membership = connection.execute(
            "SELECT count(*) FROM pg_auth_members WHERE member = "
            "(SELECT oid FROM pg_roles WHERE rolname = 'tato_billing') OR roleid = "
            "(SELECT oid FROM pg_roles WHERE rolname = 'tato_billing')"
        ).fetchone()
        if role is None or any(role) or membership is None or membership[0]:
            raise ValueError("Execute a migration e revise os privilégios do papel de cobrança.")
        connection.execute(
            sql.SQL("ALTER ROLE tato_billing LOGIN PASSWORD {}").format(
                sql.Literal(runtime.password)
            )
        )
    print("Login local de cobrança configurado sem privilégios administrativos.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, psycopg.Error):
        raise SystemExit("Não foi possível configurar o papel local de cobrança.") from None
