# Visão do Tato

Tato transforma registros financeiros em uma conversa compreensível. A referência
de produto é o Pierre: organizar dados e avisar o que merece atenção, sem exigir
que a pessoa mantenha categorias e dashboards manualmente. Não copiamos arte,
código ou identidade do produto de referência.

## Prioridades

1. Aprender LLM e RAG numa aplicação real, com avaliação e isolamento de usuários.
2. Medir até onde serviços gratuitos sustentam o produto, sem habilitar cobrança.
3. Entregar um portfólio utilizável: landing, aplicação e PWA instalável.

CSV/OFX e PDF substituem conexão bancária real. Telegram será o segundo canal;
Pluggy sandbox será uma experiência posterior, exclusivamente com dados sintéticos.
Open Finance real e publicação em lojas não fazem parte do compromisso de custo zero.

O tatu-bola foi escolhido por Enzo em 19/09/2026: proteção, identidade brasileira
e delicadeza ao falar de dinheiro. Seus estados não substituem informações objetivas.

## O que uma conversa poderá fazer

- Analítica: consultar valores calculados por SQL, com filtros explícitos.
- Conceitual: recuperar conteúdo financeiro e citar trechos da base de conhecimento.
- Lançamento: transformar texto em proposta estruturada, validada antes de gravar.
- Conversa: responder com a persona, sem ferramentas quando não forem necessárias.

Sumários semânticos ajudam a localizar contexto, mas não são fonte de totais.
O produto explica conceitos; não recomenda a compra de investimentos específicos.

## Entrega incremental

| Etapa | Resultado esperado | Commits estimados |
| --- | --- | --- |
| 1 | Fundação, CI, ambiente e regras de trabalho | 8–10 |
| 2 | Domínio e dados; schema revisado antes da migration | 10–12 |
| 3 | Auth, planos, quotas e exclusão de conta | 8–10 |
| 4 | Ingestão e categorização por regras | 12–15 |
| 5 | Router LLM e categorização restante | 12–15 |
| 6 | RAG híbrido, 200 documentos, 40 perguntas douradas | 16–22 |
| 7 | Chat, ferramentas, streaming seguro e exportação | 12–15 |
| 8 | Agentes, cron e notificações | 10–12 |
| 9 | Landing, aplicação, PWA e SVGs do mascote | 16–22 |
| 10 | Pagamentos sandbox e observabilidade | 10–12 |
| 11 | Deploy autorizado e medições controladas | 10–14 |
| 12 | Telegram, Pluggy sandbox e relatórios | 8–12 |

O MVP utilizável termina na etapa 9. As estimativas não substituem o limite de diff.
Nenhuma etapa autoriza iniciar a seguinte sem o resumo e checkpoint de Enzo.

## Critérios finais, ainda não atingidos

- Uma pessoa cadastra, importa e conversa sem assistência do desenvolvedor.
- PWA instalável em Android/iOS; troca de mascote restrita ao seu pacote.
- Números rastreáveis ao banco, fontes RAG visíveis e teste bloqueante de isolamento.
- CI completo, documentação didática e histórico de commits pequenos.
- Custos efetivamente nulos e consumo medido, com limites e indisponibilidades claros.

A etapa 1 não trata dados pessoais e não tem aplicação publicada.
