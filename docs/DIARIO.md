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

Validação local: 154 testes unitários/HTTP, cobertura 84,26%, lint/mypy aprovados;
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
Revisão final antecipou a checagem de logs do Postgres: perguntas também podem
ser privadas, mesmo quando a busca só retorna conteúdo público. Teste bloqueia
o envio de qualquer parâmetro antes de confirmar a configuração de logs.

## Etapa 6 — pendência de avaliação remota resolvida — 28/09/2026

Enzo adicionou Groq no `.env` e autorizou continuar. Presença da chave e flags
conferidas sem expor valores. Smoke sintético real aprovado; nenhum dado privado
foi enviado. O primeiro judge parou após dois casos; diagnósticos encontraram
HTTP 429 e JSON inválido. Aumentar teto de saída para 2048 resolveu o caso inválido
observado; intervalo de 30 s permitiu completar o conjunto sem novas interrupções.
Adicionada retomada com identidade de dados/código/modelos e teste que prova
que casos completos não são repetidos. Suíte: 155 testes, cobertura 84,26%.

Resultado Groq `openai/gpt-oss-20b`: 71 de 75 afirmações sustentadas (94,67%),
40 perguntas consideradas respondidas. Falhas em q13, q20 e q21 preservadas.
Controle separado com afirmação contraditória foi rejeitado pelo judge.
Gerador e avaliador usam o mesmo modelo; isso limita a independência da medição.
Não há garantia de segurança para números financeiros: chat continua etapa 7.

Consumo dos casos completos: 84.397 tokens de entrada, 41.122 de saída; demais
diagnósticos não estão integralmente contabilizados. Quota observada de 8000
tokens/minuto mostrou o primeiro gargalo real do provedor. Nenhuma mudança paga.
Recuperação antes/depois manteve os baselines. A pendência de chave/judge foi
resolvida; PR 10 pode sair de rascunho após CI final. Sem merge ou etapa 7 nesta sessão.

O CI final expôs variação no mesmo SHA: push com MRR RRF 0,81250 e PR com 0,83542,
sem mudança de hit@5, corpus ou pesos. Causa ambiental não isolada; hipótese de
quantização/CPU permanece aberta. Removida a exigência adicional de MRR invariável
entre runners, mantendo o gate hit@5 solicitado e o desvio MRR visível no relatório.
O baseline não foi reduzido. Portabilidade numérica precisa de validação no deploy.

## Etapa 7 — início em 28/09/2026

PR #10 integrado por autorização do Enzo, preservando os commits, após os quatro
checks verdes no SHA `1c31eaf`. Merge `8f80267`; branch `etapa-07-chat-intencao`.
Plano e proposta de tabela `chat_turns` em `07-CHAT.md`; checkpoint solicitado,
sem migration enquanto não houver aprovação.

Primeira ferramenta analítica reutiliza `expense_total`, recebe intervalo tipado
e rejeita SQL livre e proprietário no payload. Resultado leva parâmetros da fonte;
redação monetária usa somente inteiros. Nenhuma chamada externa de LLM adicionada.
Verificação: 162 testes unitários/HTTP, cobertura 84,49%, ruff e mypy aprovados;
teste de integração da ferramenta/repositório aprovado em PostgreSQL real.
Histórico, roteamento, lançamento e SSE continuam pendentes nesta etapa.

### Schema do chat aprovado — 29/09/2026

Enzo aprovou `chat_turns` e a contagem de pedidos aceitos, inclusive falhas.
Migration `0006` aplicada aos bancos locais `tato_test` e `tato`; sem drift.
Upgrade/downgrade/upgrade testado somente em `tato_test`. Isolamento de leitura
e escrita, unicidade por usuário, estados válidos e cascade cobertos em Postgres.
Verificação: 162 testes locais, cobertura 84,61%, 29 integrações aprovadas.

Reserva de mensagens implementada sob lock por usuário. Repetições não gastam
quota; pedidos antigos de outro mês não entram na contagem UTC. Histórico é
cifrado e limitado; retomada de pending antigo não repete efeitos. Testes reais
disputam a última vaga com threads, tanto com IDs iguais quanto diferentes.

### Fluxos de conversa implementados — 03/10/2026

Quatro intenções conectadas ao histórico e à API: despesas SQL com categoria,
conceitos com fontes isoladas, prévia/confirmar lançamento e conversa local.
Identidade/frases do mascote centralizadas em `packages/mascot/identity.json`.
SSE entrega status e resposta validada inteira; não transmite tokens crus.
Testes reais cobrem confirmação concorrente, rollback se a resposta não for
salva, fonte maliciosa inerte e exclusão durante processamento.

Docker estava desligado nesta retomada e foi iniciado; nenhuma alteração remota
ou contratação. Verificação local: 181 testes, cobertura 83,39%, 38 integrações.
Uma revisão encontrou que `Literal[True]` aceita `1`; corrigido antes da conversão.
Na separação de commits, o hook ocultou o registro de rotas ainda não staged e
recusou testes dependentes. Os lotes foram isolados e revalidados; nenhum hook
foi pulado. Maior commit desta retomada: 394 linhas.

Limite explícito: política pessoal permanece bloqueada e conversa livre por IA
não está habilitada. Classificador estruturado possui fallback local limitado;
conceitos mostram fontes em vez de gerar afirmações não verificadas. Detalhes
no ADR 0010. Frontend continua etapa 9. PR #11 permanece sem merge; CI remoto
será revalidado após envio final. Não avançar à etapa 8 automaticamente.

## 03/10/2026 — conversa Groq e prévia bancária

Groq pessoal aprovado, ZDR confirmado por Enzo; navegador indisponível impede
verificação independente. Flags locais habilitadas, sem alterar segredos. Ensaio
real sintético de conversa e classificação passou; foi necessário adaptar schema
Pydantic ao `required` estrito do Groq. Histórico enviado exclui fontes e IDs.

Prévia assinada sem gravação, confirmação vinculada ao mesmo arquivo, conta e
usuário, expiração e deduplicação foram verificadas. Free segue com uma fonte;
Pro sintético local valida duas contas. Sem alteração de cobrança ou schema.
Layouts locais PicPay (36 movimentos) e Banestes (8) lidos sem LLM; originais
ignorados no Git. Banestes sem movimentos é recusado. Fixtures inteiramente
sintéticas, sem copiar contrapartes/valores dos PDFs fornecidos.

Validação: 205 testes unitários/HTTP, cobertura 84,58%; 40 integrações passaram
antes do cenário bancário novo, e as 10 integrações de importação passaram após
adicioná-lo. CI final e combinação com dependências serão conferidos antes do merge.
Enzo autorizou integrar PRs pendentes incluindo 11. PR 14 exige remover ignore
mypy obsoleto após atualização SQLModel, detectado no CI; não ignorar esse check.

iPhone com Windows não oferece o controle oficial de apps disponível no Mac.
MCP não fornece acesso bancário sozinho. Próximo caminho é validar disponibilidade
do histórico do cartão no Internet Banking com login manual; nenhuma conexão
bancária automática implementada, nenhuma credencial solicitada ou pagamento feito.

Consolidação: PRs 12–16 integrados após checks verdes (14 corrigido). PR 11
recebeu a base atualizada sem conflito. SQLModel 0.0.47, Uvicorn 0.54.0, Ruff
0.16.9 e Redis 8.10: make check com 205 testes/84,58% e 41 integrações locais
aprovados; PostgreSQL e Redis saudáveis. CI final do PR 11 antecede seu merge.

## 04/10/2026 — agentes com sinais verificáveis

PRs 11–16 foram integrados com CI verde; main chegou a 1c5cd4c. Enzo aprovou
o schema da etapa 8 e avançar com faturas/Sicoob explicitamente pendentes.
Migration 0007 adiciona configuração e estado de entrega; aplicada localmente,
com downgrade/upgrade no banco descartável e Alembic sem drift.

Quatro regras usam dinheiro inteiro e fatos do ledger. Configuração respeita
quota sob lock; execução revalida plano e exclusão, persiste avisos cifrados e
não duplica condições. A API permite criar metas, configurar agentes e ler avisos.
E-mail consulta identidade confirmada, manda texto genérico e persiste tentativas;
testes simulam o provedor. Cron requer ativação explícita e lote de até 25 usuários.
Redação por LLM não foi ativada: templates suficientes preservam quota e origem
dos números. Interface visual, deploy e validação externa permanecem posteriores.

Aprendizado: retenção de idempotência do provedor limita retries seguros após
timeout; estado pendente não significa que o e-mail certamente não foi entregue.
O teste detectou nomes de módulos pytest duplicados; o teste de entrega foi
renomeado. A suíte final local passou: 225 unitários/HTTP, cobertura 81,56%,
48 integrações Postgres/Redis. CI remoto será conferido no PR desta etapa.

Chat: primeira avaliação ampliada 18/20; a persona foi ajustada para evitar
quantidades em sugestões de hábitos. Nova rodada 20/20, com 13 chamadas Groq,
7.803 tokens de entrada e 2.596 de saída. Evidência sintética, não garantia universal.
Nenhum extrato enviado ao LLM, envio real de e-mail ou deploy nesta retomada.

A revisão final encontrou que pendências expiradas poderiam ocupar a janela de
seleção da entrega. O filtro passou para a consulta SQL; teste com 101 avisos
expirados comprova que uma mensagem nova ainda é entregue. CI do primeiro HEAD
05837a8 passou; a correção será revalidada no HEAD atualizado.

## 05/10/2026 — interface, PWA e validação do fluxo completo

Etapa 9 implementada em branch própria: landing, tatu autoral centralizado,
login/cadastro, onboarding, contas, dashboard SQL com projeção explícita,
importação com revisão, chat, agentes/metas/avisos e exclusão confirmada.
Google preparado sob flag; provedor real ainda não configurado. Sessão fica
em memória. PWA guarda só página offline genérica e ícones, nunca finanças.

Verificação local: 228 testes Python, 81,10% de cobertura, lint/mypy;
49 integrações Postgres/Redis passaram na etapa, com cenário de projeção
revalidado após sua inclusão. Doze fluxos de navegador desktop/mobile
passaram. Um teste completo com FastAPI/Postgres reais criou conta sintética,
importou CSV e conferiu a mesma despesa no chat e o saldo no resumo.
Lighthouse mobile: acessibilidade, boas práticas e SEO com 100 pontos.
Esses resultados não validam autenticação externa nem instalação física.

Aprendizados: valores grandes exigem centavos em string e BigInt na interface;
histórico atrasado não pode sobrescrever mensagens novas. Ambos têm testes.
O teste completo detectou ausência de TATO_ENV local; fallback de rate limit
em memória foi explicitado para desenvolvimento. URL Supabase normalizada
a partir da variável antiga com erro de nome; token interno gerado localmente.

Chaves Supabase/Upstash e configuração Resend seguem pendentes. Logins de
console tentados não estabeleceram sessão; não houve envio real de e-mail,
ativação de cron, deploy ou gasto. Faturas específicas/Sicoob permanecem
indisponíveis conforme limites já aceitos. PR 17 foi confirmado como integrado;
o PR desta etapa será aberto para main, com validações externas identificadas.

Retomada: CI do PR 18 no HEAD 7cd7606 aprovado nos três jobs (execuções
37303154812 e 37303189773). Mapeamento CSV da interface ampliado com
identificador estável, separador decimal e sinal das despesas. Formulário
parcial é recusado e editar opções invalida a prévia. Quatorze testes de
interface passaram; fluxo completo com PostgreSQL confirmou despesa positiva
com ponto decimal, cálculo do saldo e consulta no chat. Make check permanece
com 228 testes e 81,10% de cobertura. Configurações externas rechecadas:
chaves Supabase/Upstash e Resend continuam ausentes; PR permanece rascunho.

## 07/10/2026 — autenticação e exclusão com provedores reais

Enzo recuperou acesso administrativo local e autorizou banco novo após perder
as chaves internas. `tato` preservado; `tato_dev_20261005` recebeu schema 0007,
novas chaves e 200 documentos públicos. Dados pessoais não foram restaurados.

O ensaio inicial encontrou containers parados, apesar do Docker Desktop aberto.
A conexão foi limitada a cinco segundos e o runner passou a testar o banco antes
de criar a identidade remota. Infraestrutura iniciada preservando volumes.
A identidade da tentativa interrompida foi removida, sem resíduos locais.

Novo ensaio passou com autenticação real Supabase e rate limit Upstash:
onboarding, conta, CSV com sinais/decimais personalizados, chat SQL, saldo e
exclusão pela interface. Remoção conferida no Supabase e no PostgreSQL.
Fluxo sintético usado no CI também passou após compartilhar o mesmo teste.
Senha temporária ficou só em memória; nenhum extrato pessoal, LLM, e-mail ou
deploy usado. Confirmação de cadastro por e-mail, Google, Resend e instalação
física permanecem sem validação. O ensaio opt-in não entra no CI automático.

## 07/10/2026 — revisão do PR 18

A revisão encontrou perda de rascunhos/prévias ao renovar o token ou alternar
abas. O espaço agora usa a identidade do usuário como chave; renovação mantém
estado, enquanto sair/trocar identidade remove os componentes. Formulários de
conversa, importação e resumo permanecem em memória durante a navegação.
Erros de requisições da sessão anterior não reaparecem após a troca.
Teste de navegador força a renovação automática Supabase com relógio simulado,
alterna abas e confirma a limpeza ao sair, em desktop e viewport de iPhone.
Outro teste segura a resposta do onboarding, troca o usuário e comprova que
o callback antigo não consulta dados com o token anterior. Validação local:
20 testes de interface, fluxo API/PostgreSQL, offline, build e TypeScript
aprovados; make check permanece com 228 testes e cobertura de 81,10%.
Voltar à janela emite SIGNED_IN novamente com o mesmo token; esse evento não
invalida uma atualização em andamento. Teste segura o dashboard durante o
retorno à janela e comprova a chegada do novo saldo.

O cache PWA usava hash do manifesto/orientação, ignorando mudanças isoladas na
arte. Agora os ícones 192/512 participam da versão. Teste Node sem dependências
verifica build estável e atualização quando só um ícone muda; faz parte do
check web/CI. A lista de recursos offline continua sem dados financeiros.
Build, TypeScript, teste Node e offline aprovados. Ensaio com Supabase/Upstash
reais repetido após a revisão: login, onboarding, import, chat SQL, dashboard
e exclusão passaram; identidade temporária removida. Sem envio de e-mail,
dados pessoais ou deploy. Config-check ainda identifica RESEND_FROM ausente.

## 07/10/2026 — início da etapa 10

PR 18 integrado após revalidar os seis checks do commit 5e0d363 e ausência de
conflitos; merge 8423cb1. Só havia esse PR aberto. A sequência de etapas permanece
linear, com nova branch codex/etapa-10-monetizacao-observabilidade em main.
Schema/cobrança de teste propostos em docs/12-MONETIZACAO.md aguardam checkpoint.
Enquanto isso, consumo pessoal usa SQL/RLS existentes: pedidos aceitos no mês
UTC, fontes distintas e agentes ativos. Não mede quotas globais de provedores.
Endpoint aprovado em 231 testes Python/HTTP (81,13%) e 50 integrações
PostgreSQL/Redis, incluindo isolamento, falhas aceitas, prazo mensal, Pro e
exclusão pendente. Nenhuma migration gerada nesta parte.
A tela Conta passa a mostrar consumo e saldo de quotas, inclusive plano sem
limite e falha de consulta. Dados não ficam no armazenamento do navegador.
TypeScript/build e 22 testes desktop/mobile aprovados. O fluxo completo com
PostgreSQL confere uma fonte usada e um pedido contado após CSV/chat, sem mocks
para o consumo. Schema e cobrança continuam aguardando aprovação.
Verificadores Stripe/AbacatePay acrescentados sem SDK, usando stdlib. Testes
apresentam corpo adulterado, assinatura expirada/futura, rotação e secret errado.
A chave HMAC pública AbacatePay não substitui o secret privado. Nenhuma rota de
cobrança ativada; replay persistente depende do ledger aprovado.
Make check aprovado com 244 testes e 81,38% de cobertura. Verificação é somente
criptográfica; idempotência, consulta remota e mudança de plano não foram
declaradas prontas sem a aprovação do schema.
Observabilidade começa pelo fallback de logging padrão opt-in: lista fixa de
métricas técnicas, sem dados/identidade/erro bruto, e falha de logging isolada.
Testes comprovam exclusão desses dados, configuração desligada e tolerância à
indisponibilidade. Não foi conectado serviço externo de telemetria.
Make check final desta parte: 246 testes Python/HTTP e 81,45% de cobertura,
com ruff/mypy aprovados. Checkout/migration ainda aguardam o checkpoint enviado.

Enzo aprovou o schema e as regras sandbox em 07/10. Migration 0008 acrescenta
vínculos de cobrança, ledger de eventos e métricas LLM sem conteúdo pessoal.
52 integrações PostgreSQL/Redis aprovadas, incluindo RLS de leitura/escrita,
unicidade, valores inválidos e exclusão em cascata. Alembic sem drift e ciclo
down/up aprovado no banco descartável; banco histórico tato preservado.
Assinaturas continuam somente leitura para o papel comum da API; nenhuma
cobrança ou concessão de Pro foi ativada nesta parte.
Plano pago agora exige prazo futuro UTC em cada consulta; ausência, igualdade,
expiração ou data sem fuso não concedem Pro. Assinaturas sintéticas locais
continuam compatíveis. Testes cobrem os dois provedores e o limite exato.
Tentativas LLM passam a ser persistidas sem conteúdo, inclusive erros que levam
ao fallback. Tokens ausentes permanecem nulos e cache não simula uso remoto.
Testes verificam falha do armazenamento e bloqueio de exclusão pendente.
Adapter Stripe inicial usa HTTPX existente, chave teste, preço mensal exato e
metadata do dono/request_id. Testes simulados comprovam idempotency key estável,
recusa de produção/preço alterado/destino indevido e erros sanitizados.
Checkout ainda não está exposto por rota nem concede plano; integração remota
aguarda configuração, e processamento de webhook/portal/Pix continua pendente.
Retomada: rota de checkout sandbox reserva pedido antes da chamada remota,
reutiliza UUID/vínculo, bloqueia pedidos paralelos e exclusão pendente. Nenhum
retorno do navegador concede Pro. Configuração fica desligada até fechamento.
Escrita de assinaturas pelo webhook exige papel restrito separado; proposta em
docs/12-MONETIZACAO.md evita usar administrador ou liberar a API comum.
Adapter consulta assinatura/fatura atuais e confere vínculo, quantidade e
pagamento; estados trial/past_due/canceled não concedem acesso. Make check
passou com 282 testes e 81,42% de cobertura. Docker local falhou ao iniciar;
integrações desta retomada serão comprovadas no CI, não contadas como locais.


## 12/10/2026 — revisão paralela e conclusão em partes

Três agentes revisaram backend, frontend e cobrança. O consumo LLM mensal
agora vem de agregação SQL por usuário, sem transformar tokens ausentes em zero.
57 integrações locais PostgreSQL/Redis passaram nesta retomada, incluindo a
prova nova de isolamento/mês/ausência. Não houve chamada de cobrança real.

Prontidão do banco separada de liveness: /ready recusa papel privilegiado e confere acesso à tabela sem linhas. Testes HTTP sanitizados e integração com os dois papéis aprovados.

Confirmações de onboarding/exclusão rejeitam números e texto; somente true explícito chega à operação.

Limite por minuto cobre leituras de agentes/metas/avisos e marcação de leitura. O bloqueio de exclusão continua anterior ao rate limit.

Conversa livre ganhou regressões para centenas/bilhões e recomendações de aquisição. A limitação lexical está explícita na documentação.

Exportação de configuração pública rejeita espaços/controles, credenciais vazias e portas inválidas; a lista de variáveis permitidas foi preservada.

Stripe sandbox recebeu validação estrita de URL e identificadores completos. Nenhuma cobrança real ou concessão de Pro foi ativada.

Regressões web corrigem respostas atrasadas de agentes e exclusão após troca de identidade. A remoção experimental da guarda fez a regressão falhar, confirmando que o teste detecta o problema.

Opt-in de e-mail disponível na interface, com preservação e revogação testadas em desktop/mobile. Nenhuma mensagem real enviada.

Painel de IA concluído com seis testes desktop/mobile para null/zero, falha isolada e resposta antiga após renovação. Não apresenta saldo dos provedores.

Adapter Pix exclusivamente sandbox revisado por outro agente, com vinte testes simulados. Ainda não expõe checkout nem concede plano.

Plano de conclusão documenta responsáveis, dependências e pendências das etapas 10–12. Avaliação real de recuperação manteve baseline; judge remoto não foi executado.

CI detectou dependência oculta do .env no teste HTTP de agentes: leituras novas
usavam o padrão Upstash sem credenciais no runner. O teste agora escolhe
explicitamente limitador em memória de desenvolvimento; integração repetida
com ambiente padrão do CI, sem depender da configuração privada local.

Etapa 11 iniciada em worktree separado: imagem da API sem ferramentas de build, UID1000, raiz somente leitura e contexto restrito. Build/smoke locais passaram; /ready retorna503 sem banco. Sem deploy ou escolha de provider.

CI acrescenta pip-audit2.10.1 e Gitleaks8.30.1 com checksum. Auditorias locais Windows53/Linux50 dependências e histórico Git sem achados conhecidos; jobs remotos serão verificados antes de afirmar aprovação.

Retomada de 12/10: PRs #19 e #20 integradas após CI verde, sem deploy.
Checkpoint de `tato_billing` aprovado; migration 0009 aplicada localmente e
66 integrações PostgreSQL/Redis passaram, incluindo nove provas do papel
restrito. Bootstrap preserva bancos anteriores e não concede privilégios
administrativos. Webhook e limpeza remota continuam pendentes.

Adapter do portal sandbox validado com URLs restritas, retorno fixo e
idempotência. Testes simulados incluem cliente divergente, modo real,
redirecionamento e URLs adulteradas; nenhuma sessão remota foi criada.

Revisão paralela identificou que fatura paga permanece paga após reembolso.
A concessão de estado ativo agora verifica a cadeia até a cobrança atual;
regressões simuladas cobrem reembolso parcial/total, disputa e contrato ausente.

Interface de cobrança usa disponibilidade do backend, conserva pedidos em
falhas e só libera novo UUID após reconciliação de cancelamento. Revisão cruzada
encontrou e corrigiu o loop de checkout encerrado; regressões desktop/mobile verdes.

Revisão de UI reproduziu criação duplicada após POST bem-sucedido e GET falho.
Conta e importação agora distinguem gravação de atualização do resumo; quatro
regressões desktop/mobile impedem reenviar operações já confirmadas.

Instalação PWA trata rejeições do navegador e mantém instruções manuais.
Quatro cenários desktop/mobile verificam ausência de erro não capturado e
consumo único do evento; isso não prova instalação física em Android/iPhone.

Validação de 13/10: 389 testes Python/HTTP (81,97% de cobertura), 80 integrações
PostgreSQL/Redis/RLS sem skips, 58 Playwright desktop/mobile, build estático e
TypeScript/SW aprovados. RAG real em cache offline preservou hit@5=0,975 e
MRR=0,835417. Os 14 testes novos de acesso à cobrança provam identidade,
retomada, portal e bloqueio de exclusão sem chamadas externas.

### 14/10 — resolução segura dos eventos Stripe

Iniciada continuação isolada de webhooks/limpeza, sem ativar cobrança.
Resolvidos vínculos remotos por IDs validados; listas verificam modo teste por
item. Testes HTTP simulados incluem disputa, lista ambígua/live e expiração.
Nenhuma chamada real, nova migration ou alteração de credenciais.

Revisão independente do resolver apontou vínculos de cliente não comparados
na passagem fatura→assinatura, parent.type permissivo e UUID recebendo tipo
inválido. Corrigidos com três regressões simuladas; erros são sanitizados.

Factory do papel de cobrança comprovada com PostgreSQL real em tato_test,
SET ROLE em conexão própria de teste e nenhuma rotação global de senha.
Papel comum tato_app é rejeitado, assim como roles efetivos elevados.

Busca de reserva remota perdida implementada somente com GET paginado;
provas simuladas de duplicidade, paginação repetida, cliente divergente e live.
O processo conserva a reserva local quando a ausência remota é inconclusiva.

Processador comprovado em tato_test: replay concorrente, isolamento, rollback,
retry, snapshot antigo, vínculo divergente e exclusão pendente. Revisão
identificou renovação expirada presa em pending; corrigida antes do commit.

Endpoint Stripe autenticado pelos bytes originais comprovado por HTTP local:
assinatura, replay vencido, live, versão, JSON, tamanho e falha recuperável.
As provas persistentes de replay/isolamento/rollback usam PostgreSQL real.

Comando administrativo de reconciliação implementado com opt-in antes de
qualquer rede/banco; testes locais comprovam recusa sem confirmação e erro
sanitizado. Não foi executado contra Stripe real.
### 14/10 — helpers de limpeza Stripe

Helpers isolados validam cliente vivo/tombstone e corrida ao expirar checkout;
testes MockTransport recusam modo real, referência divergente e erro privado.
Nenhuma chamada remota real ou alteração de referências SQL.

Limpeza de conta recebe Session existente, consulta vínculos apenas do dono,
expira checkout aberto e deduplica clientes completos antes de removê-los.
Reserva inconclusiva e vínculo remoto divergente bloqueiam a exclusão sem
apagar referências locais. Testes simulam webhook ausente e retry tombstone;
isolamento real de PostgreSQL continua coberto pela suíte específica, sem SQLite.
Validação local: make check aprovado, 435 testes, cobertura 82,64%; 30 cenários
de limpeza simulados. Integrações PostgreSQL não executadas nesta frente.
Revisão incluiu clientes deixados por confirmação incompleta em checkout
expirado; regressões cobrem sessão já expirada e sessão aberta expirada na limpeza,
mantendo referências locais e sem criação remota.
make check aprovado após correção: 437 testes, 82,66% de cobertura; 32 cenários
simulados de limpeza, sem chamadas remotas reais.

Limpeza integrada antes Supabase/cascade, reutilizando sessão existente.
Provas PG/MockTransport: falha após remoção remota retoma por tombstone e
webhook aguardando exclusão não recria usuário. Configuração comum extraída
para reutilização real entre endpoint, CLI e limpeza, sem SDK novo.

Recompra cancelada usa cliente existente, UUID novo e confirmação terminal
remota, sem apagar histórico. O retorno do checkout continua sem conceder Pro.
Docker retomado sem reset; oito integrações de exclusão, histórico e reembolsos
passaram após a indisponibilidade inicial. Nenhuma chamada Stripe real.
### 13/10/2026 — contraste dos campos

Revisão de acessibilidade identificou bordas com contraste 2,10:1 sobre branco.
Reutilizamos `--muted` (6,21:1) para distinguir campos vazios sem criar outro token.
A regressão mede cores computadas no login real, em desktop/mobile, sem alterar o DOM.

Recuperação de senha em worktree isolado: solicitação genérica, retorno fixo,
evento PASSWORD_RECOVERY observado antes da hidratação e formulário vinculado
ao usuário da recuperação. Dashboard bloqueado até sair; sucesso exige novo
login. Testes sintéticos cobrem confirmação, falha, renovação, troca de identidade
e parâmetro sem autorização. Nenhum e-mail real ou ajuste remoto foi realizado.
Validação local: 52 Playwright desktop/mobile (18 de recuperação), TypeScript,
build estático e 341 testes Python/HTTP com cobertura de 82,02%. A confirmação
de e-mail real e o funcionamento da allowlist continuam sem prova externa.

Revisão de recuperação: credenciais do callback também são removidas após
inicialização do SDK falhar, sem impedir que ele consuma o link primeiro.
Regressões verificam link expirado, retorno malformado e falha transitória;
nenhuma falha libera o formulário ou consulta registros financeiros.
Na base main integrada: 80 Playwright desktop/mobile (22 de recuperação),
389 testes Python/HTTP com 81,97% de cobertura e checks estáticos aprovados.

Reproduzida falha de logout ocultada quando o link de recuperação era inválido.
O erro de saída agora independe da validade do link; a interface continua
bloqueada e permite repetir a saída até voltar ao login, sem consultar dados.
O SDK emite SIGNED_OUT mesmo após erro remoto; durante o cancelamento, esse
evento não desmonta o formulário antes de ele apresentar o erro. Não se presume
revogação remota a partir da remoção da sessão local.

Após integrar a recuperação de senha da main em 14/10, os 84 testes Playwright
desktop/mobile passaram, incluindo os dois cenários de contraste computado.
`make check` manteve 389 testes Python/HTTP e 81,97% de cobertura; os históricos
das duas correções foram preservados na resolução dos conflitos de documentação.
Validação independente do transporte do webhook: cinco testes ASGI locais
comprovam interrupção de upload chunked acima de 64 KiB, sem Content-Length,
antes da assinatura ou acesso ao banco. Falhas de permissão e SQL no bootstrap
ou processamento retornam 503 genérico com no-store, sem detalhes privados.

Recompra na interface: checkout pago deixava seu UUID preso após cancelamento
da assinatura. O UUID terminal agora é descartado apenas após o backend
confirmar ausência de pendente; falha ou estado desconhecido conserva o pedido.
A regressão desktop/mobile cobre pagamento, cancelamento e renovação de token.
Os 30 testes de cobrança também comprovam preservação do UUID após 503 ou
pendência ausente e adoção do pedido pendente informado pelo serviço.

### 15/10/2026 — consolidação do ciclo local de cobrança

Integração da base com recuperação de senha e contraste preservou os históricos.
Corrigida a interface que conservava UUID pago após cancelamento da assinatura.
Provas finais: 460 testes Python/HTTP, 81,55% de cobertura, 100 integrações
PostgreSQL/Redis/RLS e 98 Playwright desktop/mobile, todos sem skips. Build,
TypeScript/SW e PWA offline também passaram. Docker foi retomado sem reset.
Revisadas falhas, concorrência, recompra, replay, reembolso/disputa e exclusão.
Chaves Stripe/Pix e RESEND_FROM continuam ausentes; cobrança permanece desligada.
Sem chamadas Stripe reais, envio de e-mail, judge remoto ou deploy nesta parte.

### 15/10/2026 — fronteira verificável do Pix

Pesquisa oficial confirmou listagem PIX por referência com metadata e paginação,
mas não encontrou cancelamento/remoção de cobrança transparente. Implementada
consulta restrita do adapter com validação de dono, valor, modo dev, fuso,
duplicidades e paginação; reembolso é reconhecido sem concessão de plano.
Testes sintéticos cobrem falhas e ausência inconclusiva sem repetir POST.
Pix continua indisponível para ativação; nenhuma API remota ou migration usada.

Revisão da paginação evitou pressupor prefixo PIX no cursor: o publicId retornado
é opaco e passa por query params do HTTPX, com limite e rejeição de controles.
### 15/10/2026 — observabilidade técnica sem captura pessoal

HTTPX existente atende Sentry e PostHog sem SDK de captura automática. Contratos
aceitam apenas nomes fixos, provedor, resultado, tokens e latência; não recebem
requisições, exceções brutas, IDs de usuário ou conteúdo financeiro. Fila limitada,
amostragem e orçamento por tipo descartam excessos sem bloquear o negócio.
Planos gratuitos revalidados; limites locais reiniciáveis não garantem quota global.
MockTransport cobre privacidade, hosts, falha de rede, amostra, fila e orçamento.
Nenhum envio remoto/ativação de conta nesta implementação.

Logfire foi concluído localmente com o pacote de tipos Protobuf oficiais, evitando
os recursos automáticos do SDK. O transporte HTTPX permanece explícito e limitado;
testes decodificam o payload e demonstram ausência de metadados do host/ambiente.

Consolidação: auditoria de configuração distingue desativação, formato inválido
e formato válido sem imprimir credenciais ou fingir teste remoto. O exportador
web permanece restrito às três variáveis públicas da sessão/API.
Validação local: 520 testes Python/HTTP, 82,43% de cobertura e 100 integrações
PostgreSQL/Redis/RLS sem skips. Nenhum código web foi alterado; CI verifica os
fluxos web/PWA e o baseline RAG. Pix segue preparatório por falta de contrato
verificável de remoção/cancelamento; nenhum plano foi concedido por esse canal.

### 15/10/2026 — prova HTTP da telemetria

PostHog e Logfire aceitaram um evento sintético cada com HTTP 200; nenhum dado
pessoal ou pedido LLM foi enviado. Sentry ficou bloqueado antes da rede porque
o valor informado não era um DSN HTTPS completo. A orientação foi copiar o DSN
do projeto, sem compartilhar seu valor na conversa. As flags não foram ativadas.

O novo ensaio opt-in reutiliza os transportes existentes e informa somente
aceitação HTTP. Não confundir essa evidência com confirmação de ingestão no
painel ou garantia de plano gratuito; essas verificações continuam separadas.

### 15/10/2026 — validação de sugestões de categoria

Helper isolado limita sugestões ao usuário e libera o lock antes da IA; preflight reutiliza validação de espaço e identidade. Exclusão concorrente impede inferência. Integração com confirmação será entregue no próximo commit.

### 15/10/2026 — categorização na confirmação

A confirmação da prévia agora tenta um lote limitado por IA para itens sem regra.
Regras e categorias atuais prevalecem na gravação; valores e datas são dos parsers.
Preflight e persistência compartilham as validações de espaço e identidade.
104 integrações PostgreSQL/Redis/RLS passaram, incluindo exclusão durante inferência,
renomeação de categoria, nova regra e reimportação sem nova chamada. O provedor foi
simulado: não houve envio de descrições reais. O limite é por pedido, não mensal.

### 15/10/2026 — Sentry aceito e preço sandbox verificável

DSN corrigido pelo Enzo: Sentry respondeu HTTP 200 ao evento sintético. O CI de
main após a PR27 também passou. Painel/ingestão e plano contratado não foram
conferidos; flags de telemetria permanecem desativadas.

Stripe ainda não está configurado. Preparado um ensaio opt-in somente leitura
do preço, reutilizando as mesmas validações do checkout e HTTPX existente.
O motivo é validar chave/preço antes de criar objetos de demonstração; esse teste
não comprova pagamento ou webhook. Nenhuma dependência, migration ou cobrança.
Validação: 573 testes Python/HTTP, cobertura de 82,81%, lint e tipagem aprovados;
58 testes focados cobrem adapter e ensaio. Stripe CLI 1.53.1 instalada globalmente,
sem login, configuração de conta ou inclusão de dependência no app.

### 16/10/2026 — revisão da interface e quebra de mensagens longas

Revisados login, recuperação, conversa, importação, agentes, conta e cobrança
com respostas sintéticas. Uma pergunta de 500 caracteres sem espaços causava
rolagem horizontal no desktop e no celular; uma declaração CSS resolveu a
quebra, preservando o conteúdo. A regressão falhou nos dois projetos antes da
correção e passou depois. Build, tipagem e teste de versão do service worker
passaram, assim como 100 testes Playwright desktop/mobile; o ensaio PWA
confirmou shell offline sem dados financeiros no cache.
Não houve acesso a extratos, contas reais ou alteração de configuração remota.

### 16/10/2026 — listener Stripe na versão instalada

A CLI1.53.1 exige seleção explícita de eventos ao encaminhar. O comando foi
corrigido com --all-snapshot após conferir o help local; a referência web ainda
mostrava o exemplo legado. Sem listener ou pagamento real nesta correção.

### 16/10/2026 — exportação pessoal em validação

Implementado endpoint isolado com JSON completo, campos permitidos e centavos
como strings; sem migration ou serviços novos. make check passou com601testes
(83,24%). A fixture PostgreSQL repetia um IDStripe entre usuários sintéticos;
foi corrigida com sufixo do titular e os4testesnovos passaram. Ainda falta repetir
make check após essa correção, executar108integrações juntas e integrar o download
na interface. Código segue no worktree de segurança, semcommit/PRdeexport.

### 17/10/2026 — endpoint de exportação

A rota autenticada materializa o JSON sob lock, preserva RLS e bloqueia exclusão
pendente. Campos explícitos evitam vazamentos; limites recusam o arquivo inteiro,
sem truncamento. Testes HTTP cobrem download, erros sanitizados e limites.

### 17/10/2026 — download pessoal na interface

Reutilizado o transporte autenticado para baixar JSON sem converter centavos
int64 para Number. Cancelamento e trocas de sessão descartam respostas antigas;
URLs Blob são liberadas e erros remotos não aparecem na tela. 120 testes web,
check/build e PWA offline passaram com fixtures; falta a prova física no iPhone.

### 17/10/2026 — exportação integrada ao fluxo completo

Consolidados backend e interface após revisão independente sem P1/P2 encontrado.
601 testes Python/HTTP (83,24%) e 108 integrações Postgres/Redis/RLS passaram.
O navegador importou CSV, consultou o gasto e baixou o JSON pela API real local;
o teste confere conta, vínculo e centavos exportados. A identidade é sintética,
sem login remoto ou dados bancários reais. Safari/iPhone continua pendente.

### 17/10/2026 — roteiro de uso e publicação

Documentados comandos reais do monorepo, duas janelas de execução e roteiro
manual com CSV sintético de R$ 70. Publicar frontend não publica API local.
Host continua pendente: RAG medido em 865 MiB e HF Docker exige plano pago;
nenhum serviço foi contratado ou publicado para contornar essa limitação.

Revisão do roteiro explicita a instalação do Chromium para o Playwright, a
data obrigatória da conta sintética e a seleção de Node 24 no build do Pages.

### 17/10/2026 — exportação disponível e conferência sandbox

PR32 integrada: roteiro agora inclui o download pessoal na tela Conta.
O ensaio Stripe somente leitura validou preço sandbox de R$ 39/mês via GET;
não houve checkout, pagamento ou webhook. Chave, preço, segredo de webhook e
URL de retorno estão presentes localmente. `BILLING_ENABLED=false`, flags de
telemetria desligadas, `RESEND_FROM` pendente e chaves Pix ausentes.
O ciclo remoto de cobrança e a entrega de e-mails continuam sem comprovação.

### 17/10/2026 — diagnóstico de deadlock no CI

No SHA b8822b1, 108 integrações e avaliação RAG passaram, mas o downgrade
falhou com deadlock em `DROP INDEX ix_knowledge_search` (migration 0005).
O job paralelo de infraestrutura passou no mesmo SHA. Sem logs do servidor,
a contraparte do lock e a causa não são identificáveis; não atribuir ao teardown.
O CI agora preserva logs do Postgres sintético antes de apagar o ambiente em
caso de falha, sem alterar migrations, inserir retry ou ocultar o erro.

## Avaliação funcional local — 17/10/2026

Inventário de telas, expansões, estados e rotas em `15-TESTES-LOCAIS.md`, com
casos identificados e expectativas monetárias do CSV sintético de 17/10/2026.
A matriz distingue UI, API e dependências externas; não equivale a execução
manual completa nem declara suporte a bancos sem exemplos ou PWA física.
Sem alteração de schema, provider, dados ou configuração de cobrança.

### 17/10/2026 — Galeria local para avaliação de todas as telas

- Criado comando Playwright dedicado que percorre a interface real com mocks
  exclusivamente sintéticos e bloqueio de rede externa, sem modo demo no produto.
- Foram aprovados os dois percursos: 25 estados em desktop e 25 em celular,
  com checagem de conteúdo, erros JavaScript e largura do documento.
- O índice HTML e imagens ficam ignorados, separados dos traces. Execuções
  parciais são identificadas e a próxima geração remove a galeria anterior.
- Recuperação de senha inclui solicitação e formulário de nova senha. As quatro
  intenções do chat aparecem separadas, respeitando o roteamento da aplicação.
- A página de orientação offline aparece por visita direta; entrega sem rede,
  provedores reais e iPhone físico não fazem parte desta galeria.

A revisão do catálogo corrigiu o aviso sintético de Fôlego: o runtime emite
alerta quando a projeção supera o saldo, sem emitir mensagem de cobertura positiva.
A captura agora usa a mensagem real e fatos compatíveis com essa condição.

### 17/10/2026 — Pesquisa de conexões bancárias e MCP

- Consultadas fontes oficiais do Pierre, Banco Central, Pluggy, Belvo e MCP.
  Os termos do Pierre citam REST/MCP, sem documentação pública suficiente para
  validar endpoint e autenticação; não atribuímos um agregador ao seu backend.
- Diferenciadas leitura de movimentações Pix, iniciação de pagamento e uso de
  MCP. O protocolo não cria autorização bancária nem acesso ao app do iPhone.
- Identificada oferta Meu Pluggy gratuita para uso pessoal limitado, distinta
  do SaaS comercial. Cobertura genérica de PicPay/Sicoob não comprova o cartão
  exato; Banestes permanece sem cobertura de fornecedor validada.
- Nenhuma conta foi conectada, credencial lida, dependência instalada ou mudança
  de provedor/schema executada. Experimento pessoal ainda depende de checkpoint.

### Conversa com compositor (17/10/2026)

- Interface de conversa mantém importação com prévia, conta selecionada, fontes
  SQL/RAG, repetição do mesmo pedido e confirmação explícita antes de gravar.
- Sugestões preenchem o campo sem chamada à IA; Enter envia e Shift + Enter
  quebra a linha. Cores e movimentos continuam no pacote do mascote.
- Validação: 601 testes Python/HTTP (83,24%), 128 testes web, quatro verificações
  extras de viewport/importação/fontes, 56 capturas, build estático e PWA offline.
  Foco do importador e região acessível tiveram regressões posteriores específicas.
- Integração real passou no banco descartável: importar, consultar por SQL, atualizar
  resumo/quota e baixar JSON. Não comprova login remoto, bancos ou iPhone físico.

## Experimento pessoal Meu Pluggy — 17/10/2026

Após checkpoint do provedor, adicionamos leitura local separada do SaaS: conta
explicitamente vinculada ao item, CSV revisável e nenhuma escrita automática.
O cursor v2 substitui o endpoint de páginas legado; valores usam Decimal antes
da normalização e datas usam São Paulo. Testes sintéticos cobrem sinais de
cartão/conta, paginação, limites, isolamento do item e falhas sem CSV parcial.
Não houve conexão real, consentimento bancário, gasto ou habilitação comercial.
