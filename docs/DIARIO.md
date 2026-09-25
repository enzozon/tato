# Diário do projeto

## Etapa 0 — alinhamento (19/09/2026)

Enzo confirmou Tato, o tatu-bola, e aprovou os ajustes de stack: Next.js 16 estático
com Cloudflare Pages, Render condicionado à prova de RAM, dados sintéticos até
revisar provedores, chunks compatíveis com o modelo e FTS sem chamar isso de BM25.
O roteiro e as consequências estão na visão, arquitetura e ADRs.

## Etapa 1 — fundação (19/09/2026)

### O que foi entregue

- API FastAPI/Pydantic com `/health`, OpenAPI e dois testes.
- Python 3.12 via uv, lockfile, ruff, mypy estrito e cobertura mínima de 80%.
- Monorepo com fronteiras documentadas, identidade central e destinos de web/evals.
- Compose local com Postgres 17/pgvector e Redis 7.4; `.env.example` sem chaves reais.
- Makefile, pre-commit, CI com qualidade e serviços reais, Dependabot mensal.
- Regras locais curtas, skill `tato-commit`, seis ADRs e primeiras medições de CI.

Repositório público autorizado: https://github.com/enzozon/tato.
O primeiro commit executável ficou em `main`, como base para o PR da etapa;
o restante está em `etapa-01-fundacao`. Oito commits planejados/produzidos na etapa,
todos com checks antes de gravar; documentação e testes contam no teto de 400 linhas.
Main exige PR e os checks `Qualidade Python` e `Infraestrutura local`, inclusive
para administradores. Não há merge nem deploy automático nesta entrega.

### Verificação e evidências

- Windows local: `make check` aprovado, dois testes, cobertura de 100% das nove
  instruções da API atual. Essa cobertura não representa funcionalidades futuras.
- Smoke test com processo Uvicorn real: HTTP 200 e status ok no `/health`.
- Skill validada com `quick_validate.py`; pre-commit instalado e executado nos commits.
- [CI dos dois jobs](https://github.com/enzozon/tato/actions/runs/35466039585):
  qualidade e infraestrutura aprovadas; pgvector criado/testado apenas no banco
  descartável do runner, Redis respondeu PONG. Nenhuma migration de domínio criada.
- [CI inicial do main](https://github.com/enzozon/tato/actions/runs/35465820555): aprovado.
- Histórico conferido: commits abaixo de 400 linhas excluindo `uv.lock`;
  `AGENTS.md` abaixo de 150 linhas. O PR exige novamente CI no seu estado final.

### O que travou e o que aprendemos

O Python encontrado no PATH era 3.13, apesar da instalação histórica de 3.14.
O uv existente estava fora do PATH. Instalamos Python 3.12.14 via uv e GNU Make
3.81 via winget; incluímos uv/Make no PATH do usuário sem substituir entradas.
Novos terminais recebem os caminhos; shells já abertos podem precisar reiniciar.
O uv copiou arquivos entre discos em vez de hardlinks; isso não é falha de instalação.

Docker não está instalado nesta máquina. Não simulamos um teste local aprovado:
a verificação dos serviços foi feita no runner Linux do GitHub. Para usar
`make infra-up` aqui ainda é necessário instalar/iniciar Docker com Compose v2.

As dependências atuais emitem dois avisos de depreciação no TestClient:
integração httpx e alias BlockingPortal. Os testes passam; mantemos o httpx previsto
no projeto e registramos a migração futura, sem ocultar os avisos.

Um health verde significa somente processo HTTP vivo. Não comprova banco disponível,
RAG correto, tratamento de dados pessoais aprovado ou capacidade de produção.
As primeiras durações medidas de jobs estão em `09-FREE-TIER-LIMITS.md`.

### Próximo checkpoint

Parar para o resumo da etapa. A etapa 2 começa com proposta do schema e revisão
com Enzo antes de gerar qualquer migration. Nenhum provedor externo de dados/LLM,
frontend, SVG final, conta bancária real ou pagamento foi ativado nesta etapa.

## Etapa 2 — domínio e dados (19–23/09/2026)

Enzo autorizou revisão do schema, instalação das dependências e execução das
migrations após a revisão. O PR #1 já estava mesclado ao retomar; a etapa usa
`etapa-02-dominio-dados`, baseada no main atualizado, sem alterar PRs do Dependabot.

Entregues os dez modelos, centavos BIGINT, FKs compostas, constraints e índices;
criptografia AES-GCM com contexto de usuário/finalidade e HMAC de idempotência;
repositórios de transação/total/chunks; seeds sintéticos; Alembic com duas revisions.
A migration `0001` congela DDL gerado pelo SQLAlchemy; `0002` força RLS e restringe
o papel da API. Assinaturas são somente leitura para impedir elevação de plano.

### Evidências

- `make check` local: 18 testes aprovados, cobertura de 91,35%, mypy estrito e ruff.
  Nove testes de integração não rodam nesse comando; não são contabilizados como aprovados.
- [CI 35926485225](https://github.com/enzozon/tato/actions/runs/35926485225): nove
  testes de integração aprovados em Postgres 17/pgvector real; seed executado duas
  vezes; migration sobe, reverte e sobe novamente; `alembic check` sem drift.
- Testes cobrem centavos, sinais inválidos, FKs entre donos, unicidade, adulteração
  de ciphertext, acesso cruzado nas dez tabelas, consulta vetorial sem WHERE,
  reset do contexto de conexão, bloqueio de Pro e cascatas sem afetar outro usuário.
- Alterações permanecem em commits pequenos e PR da etapa; sem deploy ou merge automático.

### Instalação e limites locais

A falha de 19/09 foi cancelamento da confirmação UAC, conforme log do instalador.
Em 23/09, Docker Desktop 4.91.0 e WSL 2.7.13 foram instalados. Os recursos
VirtualMachinePlatform/WSL foram habilitados com `NoRestart`; Windows retornou
`RestartNeeded: True`. Não reiniciamos o computador. Até reiniciar e abrir Docker,
o engine local não funciona; a migration foi executada no CI, não no banco local.

`.env` local foi criado com senhas aleatórias e duas chaves independentes, sem
exibição dos valores; arquivo ignorado pelo Git. Após reiniciar: `make infra-up`,
`make db-init`, `make migrate` e `make seed`. Nenhuma conexão Neon/Supabase foi criada.

### Aprendizado e próximo passo

DDL gerado também precisa de revisão: a convenção inicial repetia nomes de UNIQUE
com o mesmo primeiro campo. Incluímos todas as colunas no nome e um teste de colisão.
RLS depende de papel sem bypass; testar como superuser esconderia a falha que importa.
FTS privado persistido exporia palavras dos textos cifrados; essa cópia não foi criada.

A etapa 3 acrescentará Auth e autorização HTTP; as migrations não substituem JWT.
Parar após o resumo desta etapa. Reaplicar localmente depois da reinicialização não
autoriza avançar para auth, deploy ou dados financeiros reais.
