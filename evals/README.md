# Avaliação de recuperação — etapa 6

`make rag-eval` usa os 200 documentos e 40 perguntas de `golden.jsonl`.
Exige `TEST_DATABASE_ADMIN_URL` e `TEST_DATABASE_URL` apontando para `tato_test`
migrado. Recusa outros nomes de banco. Baixa modelos públicos na primeira execução;
usa CPU, Postgres/pgvector, FTS português, RRF e reranker reais, sem mocks ou LLM.
Cria usuários sintéticos e remove os registros de avaliação ao terminar.

O relatório completo fica em `test-results/rag-eval.json` (ignorado pelo Git),
incluindo hashes dos dados, modelo, rankings por pergunta e tempos. O baseline
versionado exige hit@5 e MRR pelo menos iguais aos medidos para ambos os modos.
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
Faithfulness ainda não foi medida por LLM; um gate de recuperação verde não é
aprovação de respostas geradas. Chaves/quota ausentes não contam como sucesso.
