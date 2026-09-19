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
