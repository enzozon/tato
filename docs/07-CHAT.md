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

`chat_history.reserve_turn` aplica a quota sob `account_session`. Um identificador
repetido com conteúdo diferente retorna 409; o mesmo conteúdo recupera o estado
anterior antes de checar quota. Pending com cinco minutos de idade vira failed
na repetição, sem reexecutar ações. A finalização revalida estado e exclusão da
conta na mesma transação de eventual lançamento. O histórico carrega até dez
turnos completos e 12 mil caracteres, preservando pares inteiros.

## Limites atuais

Dados pessoais exigem autorização e confirmação de ZDR para Groq, aprovadas
pelo proprietário em 03/10/2026. Gemini/OpenRouter continuam bloqueados para
esse conteúdo. A avaliação da etapa 6 é pública; não autoriza outros destinos.
Nunca reclassificar uma pergunta pessoal como pública para contornar a política.

SSE transmite conteúdo após validação: transmitir tokens brutos e
descobrir um número inventado depois seria tarde demais. A primeira ferramenta
é `expense_total`, com intervalo `[start, end)` e centavos vindos do SQL existente.
Sua citação identifica a ferramenta e os parâmetros, sem expor SQL interno.

O classificador local reconhece despesas do mês atual/anterior, conceitos com
"o que é" e lançamentos como "gastei 42,05 no mercado ontem". Valores ambíguos
ou múltiplos lançamentos pedem esclarecimento. Datas relativas usam a data de
referência do servidor. A interface de classificação LLM usa structured output
e mantém classificação pessoal, com Groq opt-in e fallback conservador local.

Os contratos separam resposta, fonte SQL, prévia de lançamento e trechos citados.
Filtro por categoria continua no SQL. As frases da persona ficam exclusivamente
em `packages/mascot/identity.json`, inclusive orientação para confirmar a prévia.

`chat_service.respond` reserva o turno antes de processar, armazena a resposta
validada e recupera a mesma resposta em retries. Datas relativas usam São Paulo;
quota continua UTC. Conceitos retornam fontes locais com até cinco trechos,
com seleção de citações literais públicas pelo LLM, quando habilitado.
Falhas encerram o turno sem gravar a exceção.

A confirmação recebe somente `confirm: true`, nunca valores financeiros do
cliente. Reabre a prévia cifrada e revalida a conta sob lock. A identidade
`chat:<turn_id>` deduplica a transação; gravação e atualização da resposta ocorrem
na mesma transação. Confirmação repetida retorna o mesmo ID, sem nova quota.

## API e entrega

| Rota | Contrato |
|---|---|
| `POST /chat` | `request_id`, `question`, `account_id` opcional; retorna `ChatReply` |
| `POST /chat/stream` | Mesmo corpo; eventos `status`, `reply` ou `error`, `done` |
| `POST /chat/{turn_id}/confirm` | `confirm: true`; confirma a prévia daquele usuário |
| `GET /chat` | Últimos pares completos de pedido e resposta, dentro dos limites |

Todas exigem Bearer e usam `Cache-Control: no-store`. O SSE informa andamento,
executa processamento fora do event loop e entrega a resposta inteira após
validação/persistência. Não simula streaming de tokens. Falha depois dos headers
vem em evento `error` com status, sem detalhes internos. JSON escapa quebras de
linha no payload e impede injeção de eventos. Uma desconexão não cancela efeitos
já iniciados: reenviar o mesmo `request_id` recupera o resultado sem duplicação.
Antes de enviar dados, a conta é revalidada; exclusão pendente bloqueia a entrega.
O futuro frontend deve apresentar fontes como texto, nunca HTML executável.

Confirmação exige o booleano JSON `true`; `1`, `1.0` e strings são recusados.
`Literal[True]` isoladamente aceita igualdade com `1` no Pydantic, por isso a
checagem acontece antes da conversão do schema.

## Conversa por Groq e minimização de contexto

Enzo autorizou perguntas/histórico pessoal somente no Groq e confirmou ZDR
ativo na organização da chave em 03/10/2026. É confirmação do proprietário;
o navegador indisponível impediu verificação independente. As duas flags
`GROQ_PERSONAL_DATA_ENABLED` e `GROQ_ZDR_CONFIRMED` são obrigatórias.
Gemini/OpenRouter permanecem bloqueados para dados pessoais, inclusive fallback.

O histórico enviado contém somente pergunta/resposta textual; IDs, rascunhos
e conteúdo de anexos/fontes são removidos. Conversa livre usa os últimos dois
pares, valida saída e cai na frase local se o provedor/guardrail falhar.
O filtro lexical de números e recomendações é conservador e não prova ausência
de toda paráfrase indevida. Cálculos continuam exclusivamente nas ferramentas SQL.
Para conceitos, a geração só pode selecionar trechos literais de fontes públicas
com IDs válidos; fontes privadas não são enviadas ao modelo.

Groq exige todas as propriedades no `required`, inclusive campos anuláveis.
O adapter transforma uma cópia do schema, remove defaults e usa `anyOf` na união;
a validação Pydantic original continua obrigatória depois da resposta.
Ensaio sintético real: conversa 351/206 tokens e 718 ms; classificação após
correção do schema 635/161 tokens e 578 ms. Não é avaliação exaustiva do modelo.

## Importação no contexto da conversa

Prioridades aprovadas: movimentações de conta e faturas de cartão de PicPay,
Banestes e Sicoob/Sicoobcard, sempre com revisão da prévia. Layouts específicos
ainda dependem de amostras anonimizadas; não assumir compatibilidade por marca.
O limite Free continua em uma fonte enquanto não houver decisão de alteração.

Lançamentos importados já alimentam o mesmo ledger consultado pelo chat.
`account_id` também filtra consultas analíticas e é validado contra o dono da
sessão. Para períodos históricos, use `quanto gastei de 2026-01-01 a 2026-01-31?`:
as duas datas da pergunta são inclusivas; o SQL recebe fim exclusivo no dia seguinte.

O cliente do chat usa `POST /import/preview` com multipart (`account_id`, `kind`,
`file`, `mapping` opcional). A resposta traz período, contagem, créditos/débitos
em centavos, até 50 linhas e `receipt` assinado, válido por 15 minutos. Nada é
gravado. Para confirmar, reenvia o mesmo arquivo/campos e `receipt` para
`POST /import/confirm`. A assinatura vincula usuário, conta, bytes, mapeamento
e resultado do parser; mudança ou expiração exige nova prévia. A confirmação
revalida autorização, plano e deduplicação na transação de persistência.
Totais da prévia são brutos, antes da deduplicação. O endpoint legado `/import`
continua disponível para clientes existentes; o fluxo novo exige revisão.

PDF de conta não pode passar pelo parser genérico de fatura: sinais diferentes
inverteriam receitas/despesas. Layout não suportado é recusado explicitamente.
Os exemplos locais ficam ignorados no Git, sem cópias em fixtures ou envio ao LLM.
Free permanece com uma fonte; múltiplas contas usam Pro sintético em testes locais.

## Avaliação ampliada e fechamento

`make chat-eval` executa 20 casos sintéticos de `evals/chat.jsonl`, usando o mesmo
classificador e gerador da aplicação. Compara intenção, datas e valores esperados;
conversa precisa passar o guardrail sem cair silenciosamente em fallback. Falta de
provedor/quota não conta como aprovação. O relatório em `test-results/chat-eval.json`
registra tentativas, tokens e respostas sintéticas; `--resume` exige fingerprint
compatível de dataset, código e modelo. Chamadas remotas são opt-in, fora do CI.
Não é prova universal de segurança nem avaliação humana independente.

Em 04/10/2026 Enzo autorizou avançar à etapa 8 mantendo pendentes os layouts de
faturas PicPay/Banestes e conta/cartão Sicoob. Não há novos exemplos nem acesso
bancário utilizável no Windows. Essa pendência não é contada como implementada.

Primeira medição ampliada: 18/20. Em s02, sugestão numérica de duração foi
rejeitada; s03 encontrou o circuito aberto resultante. O guardrail impediu a
entrega, mas fallback não contou como sucesso. Instrução da persona foi ajustada
para hábitos sem quantidades e sem repetir alegações do usuário. A medição inicial
está preservada em evals/chat-measurement.json; nova rodada será registrada.
