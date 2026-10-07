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
Isso exige migration de permissões; aguarda checkpoint específico antes de
aplicar. Usar o administrador de migrations no webhook foi descartado porque
contornaria RLS. Nenhuma nova tabela ou coluna é proposta neste checkpoint.
