# Plano de conclusão — revisão de 17/10/2026

Este é o plano da retomada solicitado pelo Enzo. As etapas 1–9 têm implementação
local e CI anterior aprovado; isso não significa que todos os critérios de
produção ou todos os bancos estejam validados. A revisão percorreu fronteiras
(API, autorização, LLM, importação, cobrança, interface e empacotamento), com
regressões para problemas demonstráveis. Não equivale a auditoria de cada linha.

## Partes pequenas e dependências

| Parte | Responsável nesta retomada | Entrega e próximo passo |
|---|---|---|
| Confirmação de conta | Agente backend + revisão principal | Booleano verdadeiro explícito; regressões de coerção |
| Limites de agentes | Agente backend + revisão principal | Consultas e leitura de avisos respeitam limite por minuto |
| Conversa livre | Principal | Ampliação de regressões financeiras; filtro lexical permanece limitado |
| Sessão e concorrência web | Agente frontend + revisão principal | Respostas antigas não sobrescrevem estado novo nem encerram outra identidade |
| Preferência de e-mail | Agente frontend | Opt-in explícito; entrega real depende de configuração |
| Stripe | Agente cobrança + revisão principal | Ciclo local validado; preço sandbox consultado; falta ciclo remoto de checkout/webhook |
| Pix | Agente cobrança | Adapter exclusivamente sandbox; sem concessão de plano ou rota ativa |
| Consumo LLM | Agente cobrança + frontend | Totais mensais SQL isolados, com medições ausentes explícitas |
| Prontidão | Principal | `/ready` confere conexão, papel restrito e tabela sem ler registros |
| Imagem da API | Agente backend, worktree etapa 11 | Build e smoke locais; publicação depende de checkpoint |

## Etapa 10 — fechamento obrigatório

- [x] Aprovar papel restrito `tato_billing` e `BILLING_DATABASE_URL` antes da
  migration de permissões proposta em `12-MONETIZACAO.md`.
- [x] Aplicar a migration no banco descartável e provar RLS/negação de acesso
  a extratos. Escrita de assinaturas validada com papel efetivo restrito.
- [x] Eventos persistentes, replay/idempotência, reconciliação de estado remoto,
  expiração, reembolso/disputa e exclusão/limpeza de vínculos, em testes locais.
- [x] Portal Stripe, rotas e interface de plano; preço aprovado de R$39 em teste,
  sem aceitar valores arbitrários do navegador. Recompra preserva o cliente.
- [ ] Integração Pix: adapter sandbox consulta pedidos paginados e reconhece
  reembolso; não concede plano. Falta contrato verificável de remoção/cancelamento
  da cobrança transparente antes de ativar rotas (detalhes em `12-MONETIZACAO.md`).
  Chaves Pix ainda ausentes na conferência local de 17/10.
- [x] Configurar chave, preço, segredo de webhook e URL de retorno Stripe locais.
  Em 17/10, `make stripe-smoke ARGS=--confirm-test-mode` validou via GET o preço
  sandbox de R$ 39/mês. Não criou checkout, pagamento nem recebeu webhook.
- [ ] Validar ciclo remoto sandbox de checkout, webhook, portal e exclusão antes
  de habilitar `BILLING_ENABLED`, que permanece `false`.
- [x] Transportes Sentry/PostHog/Logfire com allowlist técnica, fila limitada,
  amostragem e testes locais; limites oficiais registrados em `09-FREE-TIER-LIMITS.md`.
- [ ] Confirmar planos gratuitos e credenciais no painel e provar recepção remota
  com dados sintéticos. Quota por processo não é garantia de limite global.
  Em 15/10, Sentry, PostHog e Logfire retornaram HTTP 200 a eventos sintéticos;
  visibilidade nos painéis e planos gratuitos ainda não conferidos.

## Etapa 11 — publicação e experimento

- [ ] Escolher hospedagem/API e aprovar deploy. Build local não escolhe provider.
- [x] Incorporar imagem revisada, build no CI, auditoria de dependências e
  detecção de segredos com ferramentas documentadas.
- [ ] Credenciais de CI, smoke HTTPS incluindo prontidão, rollback verificável.
- [ ] Medir carga/cold start/RAM de embedding e reranking, consumo observado e
  limites oficiais datados; quota-watch não deve confundir limite com saldo.
- [ ] Primeiro usuário externo: cadastro, importação, conversa e exclusão.
- [ ] Instalação física Android/iPhone e comportamento offline em HTTPS.

## Pendências funcionais e externas

- Gestão individual entregue na etapa de lançamentos: consultar por conta/período/
  tipo, corrigir com versão conferida e excluir com confirmação. A migration 0010
  conserva identidades removidas com RLS, impedindo recriação da mesma origem.
  Arquivos diferentes sem ID estável continuam exigindo revisão de sobreposição.
  Reconciliação manual de transferências e pagamentos de faturas entregue em
  `20-RECONCILIACAO.md`: prévia, confirmação e desfazer, sem alterar saldos.
  As duas pontas precisam existir; não se cria uma contrapartida automaticamente.

- Categorização usa regras e sugestão LLM limitada na confirmação, quando a política
  pessoal Groq/ZDR está habilitada; prova remota com dados bancários não foi realizada.
- Faturas PicPay/Banestes e conta/cartão Sicoob dependem de exemplos compatíveis;
  não afirmar suporte sem fixture e comparação. Sicoobcard visto apenas no app
  do iPhone não oferece, por si só, uma API/MCP acessível pelo Windows.
- `RESEND_FROM` ausente na conferência de 17/10; entrega real ainda precisa ser
  configurada e validada. Opt-in na tela não comprova envio.
- Fluxo local de recuperação de senha entregue e testado com Supabase simulado.
  Allowlist/SMTP e entrega real ainda precisam de configuração e prova externa.
  Google real e confirmação de e-mail também permanecem sem validação externa.
- Exportação pessoal JSON implementada em `GET /me/export` e na tela Conta:
  dados decifrados, valores em centavos como strings, sem vetores ou IDs externos.
  O arquivo é completo ou recusado pelos limites, nunca truncado; PDFs originais
  não são armazenados pelo Tato e não fazem parte da exportação.
- Telegram, relatório PDF e Pluggy sandbox continuam como extensões da etapa 12;
  não são pré-requisitos para iniciar ensaios controlados do MVP.

## Evidência e regra de merge

Antes de cada commit: `make check`, diff de até 400 linhas e documentação da
parte. Antes de merge: CI do SHA exato, integrações Postgres/Redis, avaliação
RAG e testes web pertinentes. Nenhum teste ignorado conta como aprovado.
PR19 e PR20 foram integradas com os checks dos respectivos SHAs aprovados,
no escopo de preparação de monetização e empacotamento. A continuação da
etapa 10 usa `codex/etapa-10-telemetria-pix`. Migration 0009 aplicada somente
localmente; nenhuma cobrança ou publicação foi realizada.

### Status e portal autenticados

`GET /billing/status` informa disponibilidade de teste, ações possíveis e UUID
de checkout Stripe pendente, sem identificadores do cliente/provedor.
`POST /billing/stripe/portal` aceita somente `request_id`; cliente vem da
assinatura local sob RLS. Ambas as rotas usam `no-store`, limite por minuto
e bloqueio de exclusão pendente. Configuração desativada/inválida não libera
botões; preços e concessão de plano continuam sendo decisões do backend.
O fluxo de pagamento permanece desativado até concluir seu ciclo de vida.

Validação da PR25 em 15/10: 520 testes Python/HTTP, cobertura 82,43%,
100 integrações PostgreSQL/Redis/RLS sem skips; 98 Playwright desktop/mobile,
build estático, TypeScript/SW e um teste PWA offline aprovados.
A última avaliação RAG real
preservou o baseline (RRF hit@5=0,975/MRR=0,835417); esta mudança não altera RAG.
Revisão anterior em 320px não encontrou overflow nos
fluxos inspecionados. Verificações externas/produção, instalação física,
auditoria WCAG completa e judge remoto não foram realizados nesta retomada.

O webhook só confirma após transação, reconsulta a assinatura atual e não cria
usuários. Eventos antigos não substituem uma assinatura nova; reembolso antigo
não derruba o mês atual quitado. Limpeza precede Supabase na mesma sessão de
exclusão; falhas conservam referências para retomar. Reserva sem ID cuja ausência
remota seja inconclusiva exige intervenção operacional, sem recriação automática.

Telemetria externa permanece desativada. PostHog conta operações agregadas,
Sentry recebe um evento fixo de armazenamento e Logfire recebe tentativas LLM
sem contexto pessoal. Eventos pendentes podem ser perdidos ao encerrar a API;
contadores SQL continuam sendo a fonte confiável de consumo individual.
