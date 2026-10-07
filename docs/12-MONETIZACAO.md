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

## Checkpoint proposto — ainda sem migration

`subscriptions` conserva os campos atuais. Acrescentar campos opcionais
`billing_provider` (stripe/abacatepay), `external_id`, `external_customer_id` e
`valid_until` (UTC). Referências externas são únicas por provedor; campos internos
não entram no schema público. Pro de teste concedido por pagamento exige prazo
vigente; assinaturas sintéticas locais existentes continuam compatíveis.

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
Exclusão pendente bloqueia checkout e atualização do plano. Eventos antigos
não recriam usuário removido. Testes PostgreSQL devem provar esses limites.

Regra proposta: Pro demonstrativo R$ 39/mês no Stripe teste; Pix sandbox libera
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

Sentry/PostHog/Logfire ficam opt-in. Não enviar identidade, e-mail, URL com IDs,
headers, corpos, variáveis locais, captura automática ou gravação de sessão.
Somente eventos técnicos previamente permitidos; indisponibilidade remota não
impede operações financeiras. Limites gratuitos ainda precisam de registro
antes de adicionar qualquer serviço/SDK.

## Referências oficiais verificadas em 07/10/2026

- [Stripe: ambientes de teste](https://docs.stripe.com/testing).
- [Stripe: assinatura e entrega de webhooks](https://docs.stripe.com/webhooks).
- [Stripe: ciclo de assinatura](https://docs.stripe.com/billing/subscriptions/webhooks).
- [AbacatePay: modo de desenvolvimento](https://www.abacatepay.com/blog/como-testar-gateway-sandbox-abacatepay).
- [AbacatePay: webhooks](https://docs.abacatepay.com/pages/webhooks).

Documentação do provedor muda; confirmar contratos usados antes de implementar
os adapters. Teste com servidor simulado não comprova integração remota.
