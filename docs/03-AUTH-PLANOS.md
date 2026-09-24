# Autenticação e planos

Estado: etapa 3 em andamento. Os módulos de identidade, planos e limite estão
testados, mas ainda não ligados a `/me`. A API HTTP continua oferecendo somente
saúde até concluir o ciclo de onboarding e exclusão. Supabase/Upstash reais
ainda não foram provisionados ou validados nesta sessão.

Uma carteira de identidade não informa a assinatura do cliente. Da mesma forma,
o UUID validado no Supabase identifica a pessoa; somente `subscriptions` decide
o plano. `user_metadata`, query string e corpo da requisição não promovem ninguém.

`auth.current_identity` consulta o usuário no Supabase. Senhas e refresh tokens
pertencem ao provedor. HTTP 401 significa sessão inválida; 503 significa falha ou
configuração ausente do provedor, sem liberar acesso anônimo como fallback.

`plans.user_plan` lê a assinatura filtrada por usuário. Sem assinatura, cancelada
ou inadimplente, aplica Free. O papel SQL da API não pode editar assinaturas.

| Recurso | Free | Pro ativo |
| --- | --- | --- |
| Agentes ativos | 1 | 3 |
| Mensagens por mês | 200 | Sem limite comercial |
| Fontes de importação | 1 | Sem limite comercial |
| Relatórios | Não | Sim |
| Requisições técnicas por minuto | 60 | 300 |

As funções `require_capacity` e `require_reports` são verificações de backend.
As rotas de chat, importação e agentes usarão contagens autoritativas e reserva
atômica ao serem implementadas; não há contador mensal fictício nesta etapa.
O limite técnico protege a API e não substitui quota mensal nem quota de LLM.

`rate_limit.check_rate` usa script Lua atômico pelo REST do Upstash: conta por
identidade, expira a janela em 60 segundos e responde 429 com `Retry-After`.
A chave é HMAC do UUID, sem token, e-mail ou descrição financeira.
Sem configuração ou em falha do Redis, retorna 503; não reinicia o contador em RAM.
`RATE_LIMIT_BACKEND=memory` só funciona com `TATO_ENV=development`, em um processo,
para testes locais. Não serve para quota mensal, múltiplos workers ou produção.

Referência: [REST Upstash](https://upstash.com/docs/redis/features/restapi).

## Revisão pendente antes da migration

Proposta: adicionar em `users` dois campos opcionais `TIMESTAMP WITH TIME ZONE`,
ambos inicialmente `NULL`, preservando os usuários e as policies existentes.

- `onboarding_completed_at`: registra conclusão explícita, sem exigir CPF ou
  dados financeiros na entrada. `NULL` indica que ainda não terminou.
- `deletion_requested_at`: registra intenção de exclusão antes de chamar o
  Supabase. Enquanto pendente, bloquear operações e permitir retomada controlada.

Por quê: uma transação PostgreSQL não desfaz uma chamada HTTP. Se o Supabase
falhar, precisamos reconhecer a exclusão pendente após reiniciar o processo,
sem continuar usando a conta nem declarar sucesso prematuramente.

A migration não foi escrita nem aplicada: aguarda o checkpoint do Enzo.
Ainda falta implementar e testar a ordem de remoção, retomada após falha e
concorrência com requisições em andamento; estes campos sozinhos não resolvem isso.
