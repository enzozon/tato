# Etapa 7 — chat com fontes verificáveis

## Plano da etapa

Uma pergunta sobre gastos é uma consulta ao livro-caixa: o modelo escolhe uma
ferramenta permitida, mas não escreve SQL nem calcula o valor apresentado.

1. Contratos de intenção e ferramentas analíticas, reutilizando os repositórios.
2. Revisão do schema abaixo; só depois, modelos, migration e testes de RLS.
3. Histórico cifrado, idempotência e quota mensal transacional no backend.
4. Classificação nas intenções analítica, conceitual, lançamento e conversa.
5. Lançamento estruturado com confirmação, conta explícita e deduplicação.
6. Recuperação conceitual com fontes; números financeiros continuam no SQL.
7. Persona importada de `packages/mascot/`, histórico limitado e entrega SSE.
8. Contratos HTTP, testes de acesso cruzado, documentação e PR da etapa.

Estimativa: 10–12 commits pequenos, cada um validado com `make check`.
Não adicionaremos dependências para os contratos e ferramentas iniciais.

## Schema aprovado em 29/09/2026

Uma tabela `chat_turns` representa pergunta e resposta juntas. Isso evita duas
tabelas para um histórico único por usuário; conversas separadas ficam fora
desta etapa. Campos:

| Campo | Propósito |
|---|---|
| `id`, `user_id`, `created_at` | UUID interno, proprietário e instante UTC |
| `request_id` | UUID enviado pelo cliente para repetição idempotente |
| `request_ciphertext` | Pergunta e parâmetros cifrados |
| `response_ciphertext` opcional | Resposta estruturada e citações cifradas |
| `status` | `pending`, `completed` ou `failed` |
| `completed_at` opcional | Término do processamento |

Restrições: unicidade `(user_id, request_id)`, FK para usuário com exclusão
em cascata, FORCE RLS por proprietário e índice `(user_id, created_at, id)`.
CHECK garante resposta e término presentes somente em estado `completed`,
término presente em `failed` e ausente em `pending`.

A quota de 200 mensagens Free conta turnos aceitos no mês UTC, inclusive
falhas após aceitação; validações recusadas antes da reserva não contam.
Repetir o mesmo `request_id` não consome novamente nem repete lançamentos.
Reserva e contagem usam o lock por usuário que já existe. Turnos pendentes
interrompidos serão finalizados como falha, sem executar gravações de novo.
Histórico recupera os últimos turnos concluídos com limite de texto; apagar
a conta remove também todos os turnos. A migration `0006` implementa esse contrato.

## Limites atuais

Os adapters de LLM recusam dados pessoais. A avaliação da etapa 6 autorizou
somente corpus público e perguntas sintéticas; não muda essa política.
Os caminhos que precisam interpretar texto pessoal serão testados com provedor
simulado enquanto a política não for revisada. Nunca reclassificar uma pergunta
pessoal como pública para contornar o bloqueio.

SSE só poderá transmitir conteúdo após validação: transmitir tokens brutos e
descobrir um número inventado depois seria tarde demais. A primeira ferramenta
é `expense_total`, com intervalo `[start, end)` e centavos vindos do SQL existente.
Sua citação identifica a ferramenta e os parâmetros, sem expor SQL interno.
