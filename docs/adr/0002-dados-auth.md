# 0002 — Postgres e autenticação gerenciada

Status: direção aceita em 19/09/2026; schema pendente de checkpoint.

Contexto: SQL e vetores devem compartilhar armazenamento sem construir auth próprio.
Opções: Neon + Supabase Auth, tudo em Supabase, SQLite local.
Escolha: Neon Postgres + pgvector, SQLModel/Alembic e Supabase Auth; localmente,
Compose com Postgres/pgvector e Redis. SQLite não valida vetores nem RLS.
Consequência: exclusão precisa coordenar Auth e banco com retomada/idempotência.

Isolamento usará RLS e consultas sobre o conjunto autorizado, com teste cruzado.
Começar com busca vetorial exata evita prometer pré-filtro físico que HNSW não oferece.
Criptografia de descrições e cópias pesquisáveis exigem decisão explícita no schema.
Dinheiro será armazenado/calculado sem ponto flutuante; modelo ainda não definido.
