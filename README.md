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

A API de saúde e `make check` independem desses serviços. A camada de dados
tem dez tabelas e duas migrations revisadas, incluindo pgvector e RLS.

## Preparar o banco de desenvolvimento

No `.env`, mantenha `DATABASE_MIGRATION_URL` para o administrador local e
`DATABASE_URL` para `tato_app`, com senhas diferentes. Para o seed, preencha
`DATA_ENCRYPTION_KEY` e `DEDUP_HMAC_KEY` com duas chaves aleatórias independentes
de 32 bytes codificadas em base64. Não reutilize JWT, senhas ou chaves de produção.

```sh
make infra-up
make db-init
make migrate
make seed
```

`db-init` provisiona apenas o papel local; `migrate` aplica as revisions até `0002`;
`seed` insere exemplos sintéticos sem sobrescrever registros. Não existe migração
automática no startup da API. Guarde as chaves: sem elas, os textos não são recuperáveis.

Nesta máquina, Docker Desktop e WSL estão operacionais. As migrations até `0002`
e o seed sintético foram aplicados localmente em 23/09/2026. Os nove testes de
integração passaram no banco descartável `tato_test`, incluindo RLS e pgvector.
O `.env` local mantém as credenciais fora do Git.

`make integration` exige as variáveis `TEST_DATABASE_ADMIN_URL` e `TEST_DATABASE_URL`
apontando para o banco descartável `tato_test`, com migrations aplicadas e papel
restrito. Não use esse comando em dados reais. O CI prepara esse banco sozinho.

## Estado

Etapa 2: domínio, criptografia de textos, deduplicação, repositórios, seeds e
migrations verificadas. A API pública ainda oferece somente saúde e OpenAPI;
auth HTTP, imports, LLM, RAG e interface entram nas próximas etapas. Não há deploy
nem necessidade de contas externas para testes locais.

Veja [a arquitetura e o mapa do monorepo](docs/01-ARQUITETURA.md).
O [diário](docs/DIARIO.md) registra evidências e limitações, e o
[experimento de quotas](docs/09-FREE-TIER-LIMITS.md) separa medição de estimativa.
O [modelo de dados](docs/02-DADOS.md) explica dinheiro, índices, isolamento e migrations.

## Contribuir

Execute `make hooks` uma vez após clonar. O pre-commit executa `make check`,
sem formatar ou modificar arquivos automaticamente. O mesmo comando roda no CI.
Não pule o hook para contornar falhas; corrija a causa e rode a verificação novamente.
O pre-commit substitui a manutenção de um hook Git manual específico de cada sistema.

Commits seguem [AGENTS.md](AGENTS.md): uma ideia, corpo explicando o porquê e
até 400 linhas de adições + remoções, exceto lockfiles e migrations autogeradas.

O CI possui dois jobs: qualidade Python (via pre-commit) e infraestrutura local
(Compose, migrations, pgvector, RLS, seeds e Redis em ambiente descartável).
Testes de integração são separados dos unitários, mas obrigatórios no CI.
Dependabot roda mensalmente.
Build do frontend/API Docker, evals RAG e auditorias adicionais entram com as etapas
correspondentes; não há jobs vazios que simulem essas verificações.
