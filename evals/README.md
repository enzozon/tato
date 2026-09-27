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

## Judge opt-in

Após `make rag-eval`, `make rag-judge` usa os trechos públicos efetivamente
recuperados para gerar respostas com citações e julgar cada afirmação. Precisa
da habilitação gratuita da camada LLM e de chave local configurada. São até 80
gerações lógicas para 40 perguntas, além dos retries/fallbacks limitados do router.
Sem provedor, sai com erro e registra `status=incomplete`; não usa respostas
falsas nem declara aprovação. Em 27/09/2026, as três chaves estavam ausentes.

`test-results/rag-judge.json` guarda vereditos e tokens, não prompts pessoais.
Faithfulness é a fração de afirmações apoiadas nos trechos citados; `answer_rate`
mede respostas consideradas corretas frente à referência dourada. Abstenções
não produzem afirmações para o denominador e reduzem answer_rate. Se nenhuma
afirmação existir, a medição falha. Resultado baixo é registrado, não mascarado
por fallback. Não existe baseline de judge até executar uma medição real.

O judge pode compartilhar modelo com o gerador e errar; não é prova formal nem
substitui revisão humana. Testes unitários validam contratos, recusa de fontes
privadas e delimitação de instruções maliciosas; não medem resistência real do LLM.
