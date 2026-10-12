# Plano de conclusão — revisão de 12/10/2026

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
| Stripe | Agente cobrança + revisão principal | Validação de destinos e identificadores; falta fechar processamento de eventos |
| Pix | Agente cobrança | Adapter exclusivamente sandbox; sem concessão de plano ou rota ativa |
| Consumo LLM | Agente cobrança + frontend | Totais mensais SQL isolados, com medições ausentes explícitas |
| Prontidão | Principal | `/ready` confere conexão, papel restrito e tabela sem ler registros |
| Imagem da API | Agente backend, worktree etapa 11 | Build e smoke locais; publicação depende de checkpoint |

## Etapa 10 — fechamento obrigatório

- [ ] Aprovar papel restrito `tato_billing` e `BILLING_DATABASE_URL` antes da
  migration de permissões proposta em `12-MONETIZACAO.md`.
- [ ] Aplicar essa migration no banco descartável e provar RLS/negação de acesso
  a extratos; somente então conectar escrita de assinaturas ao webhook.
- [ ] Eventos persistentes, replay/idempotência, reconciliação de estado remoto,
  expiração, reembolso/disputa e exclusão/limpeza de vínculos remotos.
- [ ] Portal Stripe, integração Pix, rotas e interface de plano; preservar preço
  aprovado de R$39 em teste, sem aceitar valores arbitrários do navegador.
- [ ] Configurar chaves sandbox localmente, validar ensaios opt-in sem cobrança
  real e só depois habilitar `BILLING_ENABLED`.
- [ ] Sentry/PostHog/Logfire: revisar limites oficiais e política de dados antes
  de conectar. Logging técnico local existente não é integração desses serviços.

## Etapa 11 — publicação e experimento

- [ ] Escolher hospedagem/API e aprovar deploy. Build local não escolhe provider.
- [ ] Incorporar imagem revisada, build no CI, auditoria de dependências e
  detecção de segredos com ferramentas documentadas.
- [ ] Credenciais de CI, smoke HTTPS incluindo prontidão, rollback verificável.
- [ ] Medir carga/cold start/RAM de embedding e reranking, consumo observado e
  limites oficiais datados; quota-watch não deve confundir limite com saldo.
- [ ] Primeiro usuário externo: cadastro, importação, conversa e exclusão.
- [ ] Instalação física Android/iPhone e comportamento offline em HTTPS.

## Pendências funcionais e externas

- Categorização atual é por regras; fallback LLM para itens restantes ainda falta.
- Faturas PicPay/Banestes e conta/cartão Sicoob dependem de exemplos compatíveis;
  não afirmar suporte sem fixture e comparação. Sicoobcard visto apenas no app
  do iPhone não oferece, por si só, uma API/MCP acessível pelo Windows.
- RESEND_FROM e entrega real precisam ser validados; opt-in na tela não envia.
- Google real, confirmação de e-mail e recuperação de senha precisam de
  configuração/fluxo e prova externa apropriados.
- Exportação completa, Telegram, relatório PDF e Pluggy sandbox são etapa 12;
  não são pré-requisitos para iniciar ensaios controlados do MVP.

## Evidência e regra de merge

Antes de cada commit: `make check`, diff de até 400 linhas e documentação da
parte. Antes de merge: CI do SHA exato, integrações Postgres/Redis, avaliação
RAG e testes web pertinentes. Nenhum teste ignorado conta como aprovado.
PR19 continua rascunho enquanto o fechamento da etapa 10 estiver incompleto.
Não houve migração adicional de permissões, deploy ou cobrança nesta revisão.

Validação local desta revisão: 341 testes Python/HTTP, cobertura 82,02%, 57 integrações PostgreSQL/Redis, 34 Playwright desktop/mobile, TypeScript/build estático e avaliação RAG com baseline preservado. Verificações externas/produção e judge remoto continuam distintos desta prova local.
