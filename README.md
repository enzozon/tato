# Tato

**Seu dinheiro, em uma conversa.** Experimento de SaaS financeiro com Python,
LLM e RAG, limitado a serviços gratuitos. Em construção; use dados sintéticos.

## Executar localmente

Pré-requisitos: Git, uv e GNU Make. O uv instala o Python 3.12 indicado no projeto.
Antes de `make dev`, prepare `.env` conforme abaixo; preserve um arquivo já existente.

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
`make infra-up` para PostgreSQL 17 com pgvector disponível e Redis 8.0.
As portas 5432 e 6379 ficam vinculadas somente a `127.0.0.1`.

`make infra-down` encerra os serviços preservando o volume do Postgres.
Redis é descartável nesta etapa. Não use `down -v` para parar o ambiente:
esse comando apagaria o banco. Alterar a senha no `.env` não muda a senha de
um banco já inicializado no volume.

A API de saúde e `make check` independem desses serviços. A camada de dados
tem dez tabelas e três migrations revisadas, incluindo pgvector e RLS.

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

`db-init` provisiona apenas o papel local; `migrate` aplica as revisions até `0003`;
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

Etapa 7: chat autenticado com `POST /chat`, `POST /chat/stream`, `GET /chat` e
`POST /chat/{turn_id}/confirm`. Despesas vêm de SQL, lançamentos exigem prévia
e confirmação, fontes conceituais vêm da busca isolada. Histórico cifrado,
quota mensal e retries idempotentes estão implementados. SSE entrega eventos
de progresso e resposta validada inteira. Veja [contratos e exemplos](docs/07-CHAT.md).
O reconhecimento local é limitado aos formatos documentados; LLM pessoal segue
bloqueado. Ainda não há conversa livre por IA, frontend ou deploy de produção.

Etapa 6: indexação local E5-small (384 dimensões), busca híbrida Postgres/FTS/RRF,
citações e reranking opcional. Base pública com 200 documentos e 40 perguntas:
hit@5 RRF 0,975; reranker 0,925, portanto desativado por padrão. Rotas autenticadas
`POST /rag/documents/{id}/index` e `POST /rag/search` retornam fontes autorizadas.
Veja [RAG, medições e limites](docs/04-RAG.md). `make rag-index` carrega a base pública;
`make rag-eval` exige banco descartável. Judge Groq real mediu 71/75 afirmações
sustentadas (94,67%); quatro falhas permanecem documentadas. O judge é opt-in,
enquanto o CI exige recuperação real. A etapa 7 integra as fontes ao chat local.

Etapa 5: camada LLM com adapters Groq/Gemini/OpenRouter, fallback limitado,
circuit breaker, validação Pydantic/semântica e cache Redis cifrado por usuário.
Desativada por padrão; dados pessoais bloqueados. `make llm-smoke` permite ensaio
sintético após configuração de contas gratuitas. Veja [operação e limites](docs/03-LLM.md).
O chat da etapa 7 respeita esse bloqueio e usa fallback local.

Etapa 4: ingestão local CSV/OFX/PDF com centavos exatos, deduplicação, regras
determinísticas e documento cifrado. Após `GET /me`, crie a origem com
`POST /accounts`, regras opcionais com `POST /rules` e envie `POST /import`.
Veja [formatos, contrato e limitações](docs/04-INGESTAO.md). Fallback LLM em uploads
pessoais permanece bloqueado; fixtures sintéticas ainda exigem exports bancários reais.

Backend de sessão, perfil, onboarding, planos e exclusão recuperável da etapa 3:
`GET /me`, `POST /me/onboarding` e `DELETE /me` exigem bearer Supabase; saúde
continua pública. Supabase e Upstash são simulados nos testes locais; PostgreSQL
e Redis são reais. Não há login visual, contas externas provisionadas nem deploy.
Veja [configuração e limites da etapa](docs/03-AUTH-PLANOS.md).

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
(Compose, migrations, pgvector, RLS, seeds, Redis e avaliação RAG real).
Testes de integração são separados dos unitários, mas obrigatórios no CI.
Dependabot roda mensalmente.
Build do frontend/API Docker e auditorias adicionais entram com as etapas
correspondentes; não há jobs vazios que simulem essas verificações.
