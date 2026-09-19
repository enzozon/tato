# Tato

**Seu dinheiro, em uma conversa.** Experimento de SaaS financeiro com Python,
LLM e RAG, limitado a serviços gratuitos. Em construção; use dados sintéticos.

## Executar localmente

Pré-requisitos: Git, uv e GNU Make. O uv instala o Python 3.12 indicado no projeto.

```sh
make sync
make check
make dev
```

A API responde em `http://127.0.0.1:8000/health` e documenta seu contrato em
`http://127.0.0.1:8000/docs`. O health verifica somente o processo HTTP.

No Windows, GNU Make também é necessário para os comandos acima. Como alternativa,
execute as receitas do Makefile diretamente no PowerShell, uma por vez.

## Serviços locais

Instale Docker com Compose v2. Copie `.env.example` para `.env` (no PowerShell:
`Copy-Item .env.example .env`) e ajuste a senha apenas localmente. Execute
`make infra-up` para PostgreSQL 17 com pgvector disponível e Redis 7.4.
As portas 5432 e 6379 ficam vinculadas somente a `127.0.0.1`.

`make infra-down` encerra os serviços preservando o volume do Postgres.
Redis é descartável nesta etapa. Não use `down -v` para parar o ambiente:
esse comando apagaria o banco. Alterar a senha no `.env` não muda a senha de
um banco já inicializado no volume.

A API e `make check` independem desses serviços. A extensão pgvector será
habilitada pela migration da etapa 2, após revisão do schema; não há tabelas ainda.

## Estado

Fundação: API de saúde, contrato OpenAPI testado e verificação de qualidade.
Autenticação, dados financeiros, LLM, RAG e interface ainda não existem.
Não há deploy nem necessidade de credenciais externas para testar esta etapa.

Veja [a arquitetura e o mapa do monorepo](docs/01-ARQUITETURA.md).
