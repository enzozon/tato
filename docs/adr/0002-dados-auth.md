# 0002 — Postgres e autenticação gerenciada

Status: direção aceita em 19/09/2026; Enzo autorizou a revisão e migration na etapa 2.

Contexto: SQL e vetores devem compartilhar armazenamento sem construir auth próprio.
Opções: Neon + Supabase Auth, tudo em Supabase, SQLite local.
Escolha: Neon Postgres + pgvector, SQLModel/Alembic e Supabase Auth; localmente,
Compose com Postgres/pgvector e Redis. SQLite não valida vetores nem RLS.
Consequência: exclusão precisa coordenar Auth e banco com retomada/idempotência.

Isolamento usará RLS e consultas sobre o conjunto autorizado, com teste cruzado.
Começar com busca vetorial exata evita prometer pré-filtro físico que HNSW não oferece.
Criptografia de descrições e cópias pesquisáveis exigem decisão explícita no schema.
Revisão detalhada em `../02-DADOS.md`: centavos BIGINT em BRL, UUIDs, FKs compostas,
textos cifrados com AES-GCM e RLS forçada. O schema precede a migration.
