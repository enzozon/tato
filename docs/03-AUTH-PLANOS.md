# Autenticação e planos

Estado: `/me` retorna identidade, onboarding e plano; `POST /me/onboarding`
aceita somente `{"completed": true}`, sem CPF ou campos internos. Respostas não
podem ser cacheadas. Supabase/Upstash hospedados ainda não foram provisionados:
o Enzo escolheu implementar e testar localmente primeiro.

As operações da conta usam lock transacional por UUID e papel SQL restrito.
Na criação inicial, a identidade é revalidada sob o lock: uma requisição
autenticada antes de uma exclusão não pode recriar o usuário depois dela.

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

## Revisão aprovada antes da migration

Proposta: adicionar em `users` dois campos opcionais `TIMESTAMP WITH TIME ZONE`,
ambos inicialmente `NULL`, preservando os usuários e as policies existentes.

- `onboarding_completed_at`: registra conclusão explícita, sem exigir CPF ou
  dados financeiros na entrada. `NULL` indica que ainda não terminou.
- `deletion_requested_at`: registra intenção de exclusão antes de chamar o
  Supabase. Enquanto pendente, bloquear operações e permitir retomada controlada.

Por quê: uma transação PostgreSQL não desfaz uma chamada HTTP. Se o Supabase
falhar, precisamos reconhecer a exclusão pendente após reiniciar o processo,
sem continuar usando a conta nem declarar sucesso prematuramente.

O Enzo aprovou os dois campos em 23/09/2026. A revision `0003` adiciona somente
essas colunas; downgrade remove os marcadores, portanto não usar em exclusões
pendentes. O ambiente local usa dados sintéticos e não altera serviços hospedados.

## Exclusão recuperável

`DELETE /me` exige bearer e `{"confirm": true}`. Primeiro confirma no banco o
marcador de exclusão; depois remove identidade Supabase, chave de limite e usuário
PostgreSQL, cuja cascata inclui documentos/vetores. Só retorna 204 após o commit.
Falha externa mantém o marcador e bloqueia perfil/onboarding com 409.

Se o login já foi removido, a retomada operacional usa o papel restrito e somente
uma conta que já pediu exclusão: `uv run --locked --env-file .env python
scripts/retry_deletion.py UUID`, com `PYTHONPATH=apps/api`. Não aceita iniciar
exclusão arbitrária. Repita após corrigir indisponibilidade; não há worker automático
nesta etapa. Isso evita exigir um token que deixou de existir para terminar a remoção.
