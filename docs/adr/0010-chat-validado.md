# ADR 0010 — confirmação e entrega validada no chat

## Contexto

Interpretar um lançamento pode errar valor, conta ou data. SSE pode expor um
token incorreto antes de o backend conferir a resposta. O provedor atual ainda
não está autorizado na aplicação a processar dados pessoais.

## Decisão

Usar prévia cifrada e confirmação explícita, com lançamento e atualização da
resposta na mesma transação. Reutilizar a deduplicação do ledger e os locks por
usuário. Transmitir progresso e a resposta inteira validada pelo SSE.

Manter os quatro caminhos com fallback local conservador. A interface de
classificação estruturada LLM existe, mas mantém classificação pessoal e não
contorna os bloqueios existentes. Conceitos retornam fontes citadas, sem prosa
gerada que poderia inventar números ou recomendar investimentos específicos.

## Alternativas e consequências

Inserção imediata dispensaria um clique, mas tornaria um erro de interpretação
uma alteração financeira. Streaming de tokens teria resposta visual mais rápida,
mas a validação chegaria depois da exposição. Ambos foram descartados.

A API local funciona sem chaves LLM. Em troca, entende um conjunto limitado de
frases e não oferece conversa livre por IA. Habilitar esse caminho exige revisão
de política/provedor e guardrails de saída; não será feito por reclassificação
de texto privado como público. Não há novo schema além do checkpoint aprovado.
