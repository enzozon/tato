# 0004 — Recuperação sem substituir aritmética

Status: aceito por Enzo em 19/09/2026; implementação nas etapas 5–7.

Contexto: similaridade semântica não responde totais financeiros com exatidão.
Opções: indexar transações como fonte de cálculos ou rotear por intenção.
Escolha: analítica usa queries parametrizadas permitidas; conceitos usam RAG;
lançamento usa saída estruturada validada; conversa simples não chama ferramentas.
Consequência: Pydantic sozinho não prova veracidade; valores são comparados com
resultados determinísticos antes de serem mostrados, inclusive em SSE.

RAG: seções semânticas, alvo de 400–480 tokens sujeito ao tokenizer, overlap 15%,
FTS português + cosine + RRF e reranker top-20 → top-5. FTS nativo não é BM25.
Modelo multilíngue, fastembed e consumo de RAM serão validados antes de fixação.
Documentos, memórias e sumários carregam fontes; sumários não são fonte de totais.
Evals: 40 perguntas, hit@5, MRR, judge e isolamento. Falta de quota não é aprovação.
