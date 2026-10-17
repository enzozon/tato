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
e o gerador conceitual aceita apenas citações literais de fontes públicas.
Conversa livre passa por filtro lexical conservador e fallback; esse filtro não
prova segurança semântica de toda frase. Groq pessoal exige duas flags e ZDR
confirmado pelo proprietário; Gemini/OpenRouter continuam bloqueados. A interface futura precisa escapar
fontes como texto e não as inserir como HTML.


## Revisão de 12/10/2026

Confirmações de onboarding e exclusão exigem o booleano JSON `true`: o número
`1` não é consentimento, mesmo quando `Literal[True]` o aceita. Testes rejeitam
números, texto, falso e nulo antes de qualquer operação.

O filtro de conversa passou a reconhecer centenas, bilhões, patrimônio e sugestões de aquisição. As regressões mostram falhas concretas corrigidas; a lista lexical continua sem provar ausência de toda afirmação financeira.

## Exportação pessoal autenticada

`GET /me/export` entrega `tato-dados.json` sem armazenar uma cópia no servidor.
Exige sessão válida, aplica RLS e limite por minuto, e bloqueia contas ausentes
ou com exclusão pendente. O JSON inclui perfil, contas, categorias, transações,
regras, metas, documentos, chunks textuais, conversas, agentes, avisos,
assinatura, compras e medições individuais de IA. Textos cifrados são
restaurados apenas para o titular; valores em centavos são strings decimais,
sem arredondamento por JavaScript. O arquivo contém dados pessoais em claro.

O formato tem `version=1`, `exported_at`, `user` e uma lista por tipo de registro.
UUIDs locais preservam vínculos; datas usam ISO. Conversas e avisos mantêm o
texto armazenado, sem nova geração por IA. Documentos contêm o texto extraído:
o Tato não armazena nem recupera o PDF original. Não inclui o cadastro externo
do Supabase ou registros mantidos pelos provedores de cobrança.

Campos cifrados, hashes de deduplicação, embeddings, cache, eventos técnicos,
IDs internos dos provedores e a base pública de conhecimento ficam fora do
arquivo. A exportação não altera dados, assinaturas nem preferências.

A leitura mantém o mesmo lock por usuário usado pelas escritas do app; o
arquivo é materializado e o lock liberado antes de transmitir a resposta.
Consultas percorrem lotes de 128 registros. O limite técnico é 64 MiB de JSON
UTF-8 e 100 mil registros: excedê-lo retorna 409, sem arquivo parcial nem
truncamento. Contas acima desse limite exigem exportação operacional. O JSON
em memória pode ocupar temporariamente mais que o tamanho final; não há job
assíncrono nem paginação que misture momentos diferentes da conta.

Respostas usam `Cache-Control: no-store` e nome fixo de download. Falhas de
chave ou integridade retornam erro genérico, sem texto privado ou exportação
parcial. A fronteira tem testes HTTP e integração PostgreSQL A/B, incluindo
exclusão pendente e concorrência com o lock de exportação.
