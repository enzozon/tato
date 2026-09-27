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

## 23/09/2026 — Etapa 3 iniciada com autorização do Enzo

O Enzo autorizou seguir para auth/planos e informou Docker aberto. Revalidamos:
Docker 29.8.0 acessível; Compose saudável; papel local, migrations até `0002` e
seed sintético aplicados. Banco de teste `tato_test` criado separadamente: nove
testes PostgreSQL/pgvector/RLS aprovados e `alembic check` sem divergências.

Branch `etapa-03-auth-planos` baseada na etapa 2, pois PR 6 continua aberto.
Implementados módulos de identidade remota Supabase, plano derivado da assinatura
e limite atômico via REST/Lua Upstash, com memória somente em desenvolvimento.
`httpx` foi promovido de teste a execução, sem adicionar SDK. `make check` passou
com 49 testes, cobertura 94,67%; nove testes de integração passaram separadamente.
O script Lua também foi exercitado no Redis local: primeira chamada aceita,
segunda negada, expiração presente. Serviços hospedados não foram provisionados.

Etapa **incompleta**: módulos ainda não ligados a rotas de negócio. Checkpoint
solicitado para `users.onboarding_completed_at` e `users.deletion_requested_at`;
nenhuma migration nova gerada enquanto aguarda resposta. Depois implementar
`/me`, onboarding, exclusão recuperável, testes de concorrência/isolamento e CI.
Interfaces de login e Google dependem da configuração Supabase e da etapa 9.

## 26/09/2026 — Backend da etapa 3 entregue

O checkpoint foi respondido: ambos os campos aprovados, serviços externos ainda
não criados por escolha do Enzo. A migration `0003` foi gerada após aprovação e
aplicada no banco local. Esta entrada substitui as pendências de schema acima.

Entregues `/me`, onboarding explícito sem CPF, planos derivados do banco e limite
por identidade. Exclusão confirma intenção antes de chamar Supabase, bloqueia
operações enquanto pendente e remove dados/vetores por cascata. Um comando
operacional retoma falhas mesmo quando a identidade externa já foi apagada.
Revalidação sob lock impede que uma requisição antiga recrie a conta.

Validação: 63 testes locais, ruff e mypy aprovados; cobertura 94,03%. Quatorze
testes PostgreSQL/pgvector/RLS aprovados, incluindo concorrência, isolamento,
falhas antes/depois do provedor e cascata completa. Smoke HTTP real: saúde 200
e perfil anônimo 401. CI do código `9a0f50f` aprovado no push `36275070828` e no
PR `36275071998`; migrations aplicadas/revertidas e sem drift no runner.

PR 6 foi mesclado pelo usuário. Incorporadas atualizações aprovadas de main
(mypy 2.3.1, Redis 8.0, Actions), preservando httpx em execução. PR 7 agora usa main.
Nenhum segredo publicado, nenhum deploy e nenhum custo contratado.

Limites reais: Supabase/Upstash hospedados e login e-mail/Google não foram testados;
HTTP externo foi simulado, banco/Redis foram reais. Não há frontend ainda. Quotas
mensais de chat e quantidade de agentes serão conectadas aos fluxos futuros;
o limite técnico já protege conta/onboarding/exclusão. Retomada de exclusão após
queda externa é operacional, não um worker automático. Parar antes da etapa 4.

## 27/09/2026 — Ingestão local da etapa 4

Enzo autorizou a etapa 4 e aprovou os vínculos opcionais de origem antes da
migration 0004. PR 7 já mesclado pelo usuário; branch parte de main atualizado.
CSV/OFX usam centavos exatos e identidade bancária quando disponível. Sem ID,
hash do arquivo e linha preservam compras iguais; reexports exigem revisão de
sobreposição. PDF aceita texto com data completa, sem OCR nem inferência de ano.

Implementados upload autenticado com limite de corpo, persistência atômica cifrada,
regras literais por usuário e cadastro de contas/regras pela API. Fonte Free é
reservada na primeira importação; lock impede ultrapassar o limite em concorrência.
As migrations estão aplicadas localmente e alembic check não encontrou divergência.

Aprendizado: deduplicar por descrição/valor apagaria compras legítimas. Reexport
com ID e valor divergente precisa falhar integralmente, preservando o histórico.
O PDF roda em subprocesso sem segredos, mas isso não constitui sandbox do SO.

Validação local: make check com 107 testes unitários/HTTP, cobertura 86,84%, ruff
e mypy aprovados. Os 22 testes de integração exercitam PostgreSQL/pgvector/RLS, importações
concorrentes, rollback, quotas, origem cifrada e fluxo HTTP completo. Testes usam
dados sintéticos; não há comprovação de compatibilidade com extratos reais dos bancos.

Pendências explícitas: fallback LLM aguarda provedores da etapa 5; PDF não usa
structured output de LLM. Navegador conectado não apareceu na sessão, portanto
login/configuração real de Supabase e Upstash continua sem validação. Credenciais
de painel não equivalem às chaves de API necessárias. Sem deploy nem plano pago.

## 27/09/2026 — Camada LLM local da etapa 5

Enzo pediu continuidade pelo plano após o resumo da etapa 4. Branch
`etapa-05-camada-llm` baseada em `etapa-04-ingestao`, pois PR 8 ainda está aberto.
A camada reutiliza httpx/Pydantic/Redis; nenhuma dependência adicionada ou migration.

Implementados protocolo e contratos, três adapters HTTP, fallback na ordem aprovada,
retry transitório limitado, circuit breaker, métricas sem payload e validação de
centavos por fonte. Cache Redis cifrado usa HMAC do pedido e contexto por usuário;
hit também exige validação. Exclusão concorrente é revalidada após geração; falha
ao remover cache mantém marcador e pode ser retomada operacionalmente.

Validação: make check aprovado com 137 testes unitários/HTTP, cobertura 87,50%;
23 testes de integração PostgreSQL/pgvector/Redis aprovados. Lua, TTL/capacidade,
exclusão após falha de Redis e isolamento foram exercitados em serviços reais.
Provedores LLM foram simulados, incluindo 429, timeout, falhas, JSON inválido,
valor inventado, saída incompleta e modelo pago. Chaves LLM ausentes no .env;
nenhum ensaio remoto executado nem consumo remoto apresentado como medido.

Aprendizado: validar JSON não valida dinheiro; conferir fonte e valor é uma etapa
separada. Timeout por leitura não limita fluxo lento contínuo, por isso existe
prazo adicional entre chunks. Cache precisa participar da exclusão e revalidar
guardrails, não apenas reaproveitar uma resposta que já foi válida no passado.

Limites: circuitos/serialização são por processo; geração pessoal segue bloqueada.
`LLM_FREE_TIER_CONFIRMED` é declaração operacional, não detecção de billing.
Etapa 4 ainda não chama LLM em uploads pessoais; PDF structured output e fixtures
bancárias reais continuam pendentes. Supabase/Upstash hospedados não validados.
Próxima etapa planejada é RAG (6), sem iniciá-la nesta entrega.

## Etapa 6 — engine RAG e experimento de recuperação — 27/09/2026

PRs 8 e 9 revisados e mesclados após CI verde, preservando commits pequenos.
Enzo aprovou o schema público/privado antes da migration 0005, aplicada localmente
e no banco descartável. Branch `etapa-06-rag-engine`; etapa 7 não iniciada.

Implementados chunking por seção/frase com tokenizer real, E5-small quantizado
multilíngue local, cosine + FTS português + RRF, reindexação atômica e rotas
autenticadas com fontes. Busca privada filtra antes de decifrar/rankear; exclusão
concorrente bloqueia nova indexação e entrega da resposta. Público é somente
leitura para runtime. Inferência real exercitada na CPU, sem provedores externos.

Corpus autoral: 200 documentos; conjunto dourado: 40 perguntas. RRF hit@5 0,975
e MRR 0,83542; reranker hit@5 0,925 e MRR 0,80417. Aprendizado: o modelo adicional
piorou esta amostra em português, portanto ficou opcional. A falha RRF foi q05
(renda irregular); reranker falhou em q02, q34 e q40. Casos não foram reescritos
para aumentar a métrica. O CI passa a exigir ambos os baselines reais.

Validação local: 153 testes unitários/HTTP, cobertura 83,99%, lint/mypy aprovados;
27 integrações Postgres reais aprovadas; avaliação neural/SQL das 40 perguntas
aprovada separadamente. Pico local de 770 MiB com encoder e 865 MiB com ambos
os modelos: peso quantizado pequeno não implica processo pequeno.

Judge público e contrato de citações implementados/testados, mas a fidelidade
remota não foi medida: chaves ausentes, comando termina incompleto/erro.
Testes simulados de delimitação de instruções não provam resistência real de LLM.
Corpus/perguntas ainda precisam de revisão independente. A etapa permanece com
essa pendência; PR deve ficar em rascunho, sem declarar conclusão integral.
Supabase/Upstash hospedados e pendências pessoais da ingestão não foram resolvidos
por este RAG. Nenhum gasto, deploy ou acesso a dados reais de usuários.
