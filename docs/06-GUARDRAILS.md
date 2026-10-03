# Guardrails do chat

O modelo pode ajudar a interpretar uma pergunta; não recebe autorização para
executar SQL livre nem para registrar uma compra sem confirmação do usuário.

| Proteção | Erro ou ataque evitado | Evidência executável |
|---|---|---|
| Ferramenta tipada e soma SQL | Número plausível inventado | `test_chat_tools.py` |
| Centavos inteiros | Arredondamento acima da precisão de float | `test_chat_tools.py` |
| Prévia cifrada + booleano true | Cliente troca valor ao confirmar | `test_chat_contracts.py`, `test_chat_flow.py` |
| Gravação e resposta na mesma transação | Retry duplica compra ou falha deixa gravação parcial | `test_chat_flow.py` |
| RLS + identidade da sessão | Usuário confirma prévia ou lê fontes alheias | `test_chat_schema.py`, `test_chat_flow.py` |
| Reserva sob lock | Duas requisições excedem a última vaga Free | `test_chat_history.py` |
| Classificação pessoal mantida | Pergunta privada enviada como corpus público | `test_chat_intent.py` |
| Fonte tratada como texto citado | Instrução importada vira ação no sistema | `test_chat_flow.py` |
| Resposta validada antes do SSE | Token incorreto sai antes da verificação | `test_chat_routes.py` |
| Revalidação após processamento | Exclusão pendente ainda permite entrega | `test_chat_flow.py` |

Testes de fluxo, histórico e schema estão em `apps/api/tests/integration/` e
exigem Postgres real. Os demais estão em `apps/api/tests/`. Execute `make check`
e `make integration` com as URLs do banco descartável `tato_test` configuradas.

Não há garantia de fidelidade para prosa financeira gerada livremente: a etapa 6
mediu falhas reais. Por isso a resposta conceitual atual entrega trechos citados,
e a conversa usa frases locais. Isso não substitui revisão de política/provedores
antes de habilitar LLM com dados pessoais. A interface futura precisa escapar
fontes como texto e não as inserir como HTML.
