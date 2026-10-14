# Etapa 10 — monetização e observabilidade

O pagamento de teste funciona como um ingresso de demonstração: altera o plano
no backend, mas não movimenta dinheiro. Stripe fica restrito a `sk_test_` e
objetos `livemode=false`. Pix AbacatePay exige resposta `devMode=true`. Ausência
de configuração mantém cobrança desligada; nunca fazer fallback para produção.

## Plano da etapa

1. Integrar PR 18 após conferir o commit e todos os checks.
2. Expor consumo autoritativo de mensagens, fontes importadas e agentes ativos.
3. Aprovar schema e regras de demonstração antes de gerar migration.
4. Implementar checkout Stripe teste, portal e Pix sandbox com HTTPX existente.
5. Validar assinaturas de webhook, repetição, ordem e vínculos do mesmo usuário.
6. Acrescentar contadores LLM sem prompts, respostas ou descrições financeiras.
7. Ligar observabilidade opt-in com eventos permitidos e telemetria sanitizada.
8. Testar isolamento, expiração, falhas e retorno da interface; abrir PR da etapa.

Cada commit contém uma ideia e no máximo 400 linhas. Não provisionar deploy ou
enviar notificações como parte desta etapa. Dados de teste são sintéticos.

## Schema aprovado em 07/10/2026

`subscriptions` conserva os campos atuais. Acrescentar campos opcionais
`billing_provider` (stripe/abacatepay), `external_id`, `external_customer_id` e
`valid_until` (UTC). Referências externas são únicas por provedor; campos internos
não entram no schema público. Pro de teste concedido por pagamento exige prazo
vigente; assinaturas sintéticas locais existentes continuam compatíveis.
`user_plan` exige `valid_until` futuro e com fuso para assinaturas de pagamento.
Na igualdade do prazo, o plano já é Free; não depende de cron para expirar.

`billing_checkouts`: usuário, provedor, request_id, referência externa, valor
inteiro em centavos, estado pending/paid/canceled e datas. Request_id único por
usuário permite repetir um pedido sem criar outra cobrança. Referência externa
única por provedor; não persistir URL de checkout, CPF, cartão ou QR code.

`billing_events`: usuário, provedor, event_id único por provedor e data. Registra
apenas processamento idempotente, nunca o corpo do webhook. Webhook confirma
estado atual no provedor e vínculo com checkout/assinatura conhecido antes de
conceder acesso; retorno do navegador sozinho não muda plano.

`llm_usage`: usuário, provedor, resultado, tokens de entrada/saída opcionais,
latência inteira e data. Tokens ausentes significam desconhecidos, não zero.
Sem prompts, respostas, documentos ou histórico pessoal.

Novas tabelas têm RLS e exclusão em cascata com o usuário. Índices de usuário/data
servem às consultas mensais; referências externas e eventos têm unicidade.
Migration `0008` aplicada no banco local novo e no descartável `tato_test`.
Upgrade/downgrade e ausência de drift conferidos; o banco histórico foi preservado.
O papel comum da API continua somente leitura em `subscriptions`.
Exclusão pendente bloqueia checkout e atualização do plano. Eventos antigos
não recriam usuário removido. Testes PostgreSQL devem provar esses limites.
O fluxo de exclusão também deverá cancelar a assinatura de teste e limpar
referências pessoais no provedor antes de remover os vínculos locais. Falha
remota conserva deletion_requested_at e os dados necessários para repetir.

Regra aprovada: Pro demonstrativo R$ 39/mês no Stripe teste; Pix sandbox libera
30 dias, sem renovação automática. Um provedor de cobrança por vez; Free segue
com uma fonte, um agente e 200 pedidos de chat por mês. Cobrança real permanece
indisponível. Valor de teste não é compromisso com preço comercial futuro.

## Consumo e privacidade

O painel pessoal conta pedidos aceitos de chat, incluindo falhas, fontes já
importadas (contas/cartões distintos) e agentes habilitados. São consultas SQL
filtradas pela identidade autenticada; não representam quota global de Groq,
Neon, Upstash ou Vercel. Quotas globais dependem do experimento da etapa 11.
`GET /me/usage` usa a mesma janela mensal UTC da reserva de chat. Limite nulo
significa sem limite contratual; exceder um limite após downgrade mostra zero
restante, sem ocultar o consumo existente. A rota não descriptografa documentos
ou conversas e retorna Cache-Control: no-store.
A tela Conta mostra usados/restantes, reinício UTC das mensagens e o significado
de limite nulo. Falha de consulta fica explícita e não esconde a exclusão da conta.

Sentry/PostHog/Logfire ficam opt-in. Não enviar identidade, e-mail, URL com IDs,
headers, corpos, variáveis locais, captura automática ou gravação de sessão.
Somente eventos técnicos previamente permitidos; indisponibilidade remota não
impede operações financeiras. Limites gratuitos ainda precisam de registro
antes de adicionar qualquer serviço/SDK.
O fallback local já existe no router: `LLM_LOG_USAGE=true` permite registros
JSON no logger `tato.llm_usage`, quando o nível INFO estiver configurado.
A lista fixa contém apenas evento, provedor, resultado, contagens e latência.
Não inclui modelo, dono, instrução, erro bruto ou resposta. Logging falho não
impede geração; desligado por padrão. Não cria armazenamento nem chama serviço
remoto. `llm_service.generate` agora persiste tentativas técnicas em `llm_usage`,
inclusive fallback por indisponibilidade, sob o usuário autenticado. Cache hit
não inventa consumo. A gravação revalida exclusão pendente; falha de métricas
não interrompe geração. Integração externa permanece pendente.

## Referências oficiais verificadas em 07/10/2026

- [Stripe: ambientes de teste](https://docs.stripe.com/testing).
- [Stripe: assinatura e entrega de webhooks](https://docs.stripe.com/webhooks).
- [Stripe: ciclo de assinatura](https://docs.stripe.com/billing/subscriptions/webhooks).
- [AbacatePay: modo de desenvolvimento](https://www.abacatepay.com/blog/como-testar-gateway-sandbox-abacatepay).
- [AbacatePay: webhooks](https://docs.abacatepay.com/pages/webhooks).

Documentação do provedor muda; confirmar contratos usados antes de implementar
os adapters. Teste com servidor simulado não comprova integração remota.

`billing_stripe.py` inicia o adapter com HTTPX já instalado. Ele recusa chave
de produção, preço fora de BRL 3.900 centavos/mês e objetos fora do modo teste.
Checkout usa idempotency key derivada de usuário/request_id, metadata em sessão
e assinatura e URL hospedada validada. Retorno fixo não concede Pro.
API fixada em `2026-09-30.endive`.
Contratos: [checkout](https://docs.stripe.com/api/checkout/sessions/create),
[preço](https://docs.stripe.com/api/prices/object) e
[versionamento](https://docs.stripe.com/api/versioning), conferidos em 07/10.

## Verificação antecipada de webhooks

`billing_signatures.py` verifica Stripe sobre bytes originais, com HMAC-SHA256,
janela de 300 segundos e múltiplas assinaturas para rotação. AbacatePay usa chave
HMAC pública: isso não basta para autenticar. Também exige secret privado forte
com comparação constante. A chave pública deve vir da documentação oficial.
Não há rota de pagamento ativa nesta parte, nem processamento do evento.
Idempotência persistente e consulta do estado atual ainda dependem do schema.
Secret na query string exige suprimir acesso bruto nos logs do futuro endpoint;
não ativar webhook antes dessa proteção. Testes cobrem adulteração e replay.

## Reserva do checkout

`POST /billing/stripe/checkout` recebe somente `request_id` UUID. A identidade
vem da sessão; o preço vem do backend. Exige `BILLING_ENABLED=true`, chave/price
de teste e `BILLING_RETURN_URL` fixa, sem credenciais ou parâmetros.
A configuração permanece desligada até completar webhooks e limpeza remota.
A reserva local confirma antes da chamada Stripe; falha remota permite repetir
o UUID. Checkout conhecido é consultado, nunca recriado. Um pedido pendente ou
assinatura existente impede novo checkout. URL não é persistida e resposta é
`no-store`. Expiração remota cancela a reserva; pagamento aguarda webhook.
Sem vínculo após 23 horas, exige reconciliação operacional: não arriscar uma
segunda sessão depois da janela de idempotência do provedor. O lock por conta
serializa chamadas; limite atual é timeout HTTP de 10 segundos por chamada.

O adapter consulta assinatura e última fatura novamente antes de produzir o
estado para o futuro webhook. Confere dono/request_id, cliente, uma única
unidade do preço mensal aprovado, fuso UTC e vínculo da fatura à assinatura.
`active` remoto só produz estado ativo com fatura `paid` de 3.900 centavos;
trial, dívida e cancelamento não concedem Pro. Nenhum payload bruto é persistido.
Esse estado ainda não escreve em `subscriptions`. Contratos oficiais:
[assinatura](https://docs.stripe.com/api/subscriptions/object) e
[fatura](https://docs.stripe.com/api/invoices/object), conferidos em 07/10.
Refunds/disputas e limpeza remota precisam de tratamento antes de ativar cobrança.

## Checkpoint adicional de privilégio do webhook

Proposta: papel `tato_billing`, sem superuser/BYPASSRLS, conexão separada
`BILLING_DATABASE_URL`, sem acesso a transações, documentos ou chats.
Ele lê usuários e pode escrever somente assinaturas, checkouts e eventos, sob
RLS pelo mesmo `app.user_id`. A API comum `tato_app` continua sem escrita em
assinaturas. Rotas de usuário não recebem a conexão de cobrança; webhook
valida assinatura e vínculo remoto/local antes de usá-la.
Checkpoint aprovado por Enzo em 12/10/2026; migration `0009` aplicada nos bancos
locais de desenvolvimento e teste. Usar o administrador no webhook foi descartado porque
contornaria RLS. Nenhuma nova tabela ou coluna é proposta neste checkpoint.

O papel nasce sem login. `scripts/bootstrap_billing.py` habilita a credencial
de desenvolvimento via `BILLING_DATABASE_URL`, exclusivamente em banco local
novo ou `tato_test`, após verificar privilégios e ausência de vínculos entre papéis.
Nove testes PostgreSQL provam o escopo de escrita, isolamento por usuário e
bloqueio de dados financeiros privados. Cobrança continua desativada até
fechar webhooks, reconciliação e limpeza remota.


## Consumo LLM por usuário

`GET /me/llm-usage` agrega tentativas persistidas no mês UTC pela conexão RLS.
Soma somente tokens conhecidos; ausência completa permanece nula, e contadores
indicam medições parciais. Zero é uma medição válida. Tempo total inclui erros.
Não retorna conteúdo pessoal nem estima saldo/limite das contas dos provedores.
Testes cobrem identidade, `no-store`, exclusão pendente, fronteiras do mês,
usuários distintos e valores ausentes no PostgreSQL.

O adapter Stripe também recusa controles, userinfo vazio e portas inválidas no retorno. IDs de checkout, cliente e assinatura precisam ter formato completo antes de qualquer uso remoto; regressões cobrem respostas adulteradas.

A tela Conta mostra métricas LLM em painel independente: null aparece como não informado, zero permanece zero e contagens ausentes explicam somas parciais. Erro não oculta exclusão/consumo e resposta de token antigo é descartada.

### Adapter Pix sandbox

`billing_abacate.py` exige chave `dev_` antes da requisição e recusa produção.
Usa PIX v2 com valor fixo aprovado de 3.900 centavos, validade de uma hora e
vínculos de dono/request_id; resposta exige devMode booleano verdadeiro.
QR não aparece em repr. Não há retry automático: timeout exige reconciliação,
pois externalId não possui garantia documentada de idempotência neste contrato.
Vinte testes MockTransport cobrem a fronteira. Nenhuma chamada real foi feita.
Sem rota, escrita de assinatura ou concessão de Pro; integração depende do
fechamento do ledger/webhook. Contrato oficial conferido em 12/10/2026:
https://docs.abacatepay.com/pages/transparents/create e
https://www.abacatepay.com/blog/como-testar-gateway-sandbox-abacatepay.

### Portal Stripe de teste

O adapter cria sessão temporária somente para cliente Stripe validado, com
retorno fixo e idempotência por cliente/request_id. Recusa modo real,
redirecionamentos e URLs fora de `https://billing.stripe.com/p/session`.
A URL não deve ser persistida nem registrada. O serviço autenticado ainda
precisa obter o cliente do vínculo local; não aceitar esse ID da interface.
Contrato: https://docs.stripe.com/api/customer_portal/sessions/create.

### Confirmação do pagamento atual

Fatura `paid` não prova ausência de reembolso. Antes de produzir estado ativo,
o adapter expande `payments` e exige um pagamento de fatura completo, vinculado
ao PaymentIntent e à cobrança atual, no cliente esperado, em BRL e modo teste.
Valores são inteiros de 3.900 centavos. Reembolso parcial/total ou disputa
produz `past_due`; contrato ausente ou divergente falha sem expor payload.
Isso ainda precisa ser acionado pelos webhooks de reembolso/disputa.
Contrato: https://docs.stripe.com/invoicing/partial-payments.

## Webhook sandbox ? resolu??o de refer?ncias

Listas Stripe n?o possuem livemode no envelope: cada item ? validado.
Eventos de disputa/reembolso resolvem Charge ? PaymentIntent ? InvoicePayment
? fatura ? assinatura atual, sem persistir corpos remotos. Ambiguidade de
pagamento ou pagina??o incompleta impede conceder Pro. Checkout expirado sem
assinatura continua identific?vel pela metadata e pelo client_reference_id.
Refer?ncia: https://docs.stripe.com/api/invoice-payment/list.

A factory billing_engine exige BILLING_DATABASE_URL e papel efetivo
tato_billing sem eleva??o ou heran?a. N?o reutiliza DATABASE_URL nem URL
administrativa; cada transa??o de cobran?a revalida o papel antes de operar.

Reservas sem ID remoto s?o pesquisadas por per?odo com pagina??o e v?nculo
exato, nunca por nova cria??o. A busca tem teto expl?cito de 2.000 sess?es:
exceder, duplicidade e cursor repetido exigem reconcilia??o operacional.
N?o encontrar uma reserva pendente n?o comprova aus?ncia de efeito remoto.
