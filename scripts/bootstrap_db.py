"""Cria o papel restrito apenas em banco local; não imprime credenciais."""

import os

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

admin = make_url(os.environ["DATABASE_MIGRATION_URL"])
runtime = make_url(os.environ["DATABASE_URL"])
if (
    admin.host not in {"localhost", "127.0.0.1"}
    or not (admin.database or "").startswith("tato")
    or runtime.username != "tato_app"
    or not runtime.password
    or (admin.host, admin.port, admin.database) != (runtime.host, runtime.port, runtime.database)
):
    raise SystemExit("Bootstrap restrito ao banco local tato e papel tato_app.")

with psycopg.connect(
    admin.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
) as connection:
    role = connection.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'tato_app'"
    ).fetchone()
    if role is None:
        connection.execute(
            sql.SQL("CREATE ROLE tato_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Literal(runtime.password)
            )
        )
    elif any(role):
        raise SystemExit(
            "Papel existente tem privilégios incompatíveis; revise antes de continuar."
        )
print("Papel local conferido. Execute a migration para conceder permissões nas tabelas.")
