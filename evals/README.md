# Avaliação de recuperação — etapa 6

`make rag-eval` usa os 200 documentos e 40 perguntas de `golden.jsonl`.
Exige `TEST_DATABASE_ADMIN_URL` e `TEST_DATABASE_URL` apontando para `tato_test`
migrado. Recusa outros nomes de banco. Baixa modelos públicos na primeira execução;
usa CPU, Postgres/pgvector, FTS português, RRF e reranker reais, sem mocks ou LLM.
Cria usuários sintéticos e remove os registros de avaliação ao terminar.

O relatório completo fica em `test-results/rag-eval.json` (ignorado pelo Git),
incluindo hashes dos dados, modelo, rankings por pergunta e tempos. O baseline
versionado exige hit@5 pelo menos igual ao medido para ambos os modos.
MRR é reportado com desvio explícito contra a referência, sem exigir igualdade
entre ambientes. No mesmo SHA, dois runners tiveram RRF MRR 0,83542 e 0,81250,
mantendo hit@5 0,975. A origem ambiental da diferença não foi isolada; não houve
alteração dos valores no baseline. Este gate segue o critério hit@5 do plano original.
MRR é calculado no top-5, logo uma fonte fora dele recebe zero. `make check`
continua rápido; o CI executa a avaliação real no job de infraestrutura.

Medição inicial, 27/09/2026: RRF hit@5 0,975 / MRR 0,83542; reranker hit@5
0,925 / MRR 0,80417. Por isso `/rag/search` usa `rerank=false` por padrão.
Reranking permanece disponível para comparação, sem alegação de ganho.

Limitações: corpus e perguntas foram escritos juntos; não há conjunto externo
independente nem perguntas reais de usuários. hit@5 encontra ao menos uma fonte
aceita, não mede cobertura de todas as partes de uma pergunta. Não reduzir o
baseline para esconder regressão: revisar causa, exemplos e decisão explicitamente.
Perguntas sobre totais pessoais exigem SQL, não esse benchmark conceitual.
Faithfulness foi medida com Groq real: 71/75 afirmações sustentadas (94,67%).
Um gate de recuperação verde não é aprovação de respostas geradas.
Chaves/quota ausentes não contam como sucesso.

## Judge opt-in

Após `make rag-eval`, `make rag-judge` usa os trechos públicos efetivamente
recuperados para gerar respostas com citações e julgar cada afirmação. Precisa
da habilitação gratuita da camada LLM e de chave local configurada. São até 80
gerações lógicas para 40 perguntas, além dos retries/fallbacks limitados do router.
Sem provedor, sai com erro e registra `status=incomplete`; não usa respostas
falsas nem declara aprovação. A primeira medição completa usou somente Groq;
o resumo está em `faithfulness-measurement.json`, com falhas e consumo registrados.

Após configurar Groq, o primeiro ensaio confirmou autenticação, mas encontrou
limite de tokens por minuto e `json_validate_failed`. O teto de saída de gerador
e judge passou para 2048 tokens, dentro do limite já permitido pela camada LLM.
A repetição do caso antes inválido funcionou; isso não identifica sozinho a
causa interna do provedor. O comando espera 30 segundos entre perguntas.

Para retomar após interrupção, use `uv run --locked --env-file .env python
scripts/eval_rag_judge.py --resume` com `PYTHONPATH=apps/api`. O checkpoint exige
mesmo relatório de recuperação, código de avaliação/adapter e modelos; não
repete casos completos. `--interval` aceita de 15 a 60 segundos. Uma nova execução
sem `--resume` inicia relatório novo. Falhas continuam encerrando com erro, sem
loop ilimitado. Contagens do relatório cobrem casos completos, não todo consumo
de diagnósticos e tentativas anteriores que o provedor não informou.

`test-results/rag-judge.json` guarda vereditos e tokens, não prompts pessoais.
Faithfulness é a fração de afirmações apoiadas nos trechos citados; `answer_rate`
mede respostas consideradas corretas frente à referência dourada. Abstenções
não produzem afirmações para o denominador e reduzem answer_rate. Se nenhuma
afirmação existir, a medição falha. Resultado baixo é registrado, não mascarado
por fallback. A medição versionada é referência observada, não limiar automático
de aprovação: há quatro afirmações sem suporte, mesmo com answer_rate de 1,0.

O judge pode compartilhar modelo com o gerador e errar; não é prova formal nem
substitui revisão humana. Testes unitários validam contratos, recusa de fontes
privadas e delimitação de instruções maliciosas; não medem resistência real do LLM.
