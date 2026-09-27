---
name: tato-rag-change
description: Alterar chunking, embeddings, busca ou reranking do Tato com avaliação real antes/depois e registro das métricas.
---

# Mudanças no RAG do Tato

- Consulte `docs/04-RAG.md` e `evals/README.md` somente para o trecho afetado.
- Antes de mudar comportamento, execute `make rag-eval` contra `tato_test` migrado
  e preserve o relatório ignorado em `test-results/` como comparação local.
- Depois da mudança, repita a avaliação real; registre hit@5/MRR de RRF e reranker
  antes/depois em `docs/04-RAG.md`, incluindo modelo, corpus e limitação relevante.
- Não reduza `evals/baseline.json` apenas para passar CI. Explique a regressão e
  decida com evidências se a mudança deve ser mantida. Preserve perguntas que falham.
- Alterações em escopo privado exigem testes Postgres/RLS antes de ranking e
  reranking; SQLite e filtros posteriores não substituem essa evidência.
- Alterações em geração/citação exigem validar fontes permitidas. `make rag-judge`
  é opt-in público com provedores gratuitos configurados; ausência de chave/quota
  deve ser registrada como indisponível, nunca como faithfulness aprovada.
- Atualização de schema segue o checkpoint do `AGENTS.md`; esta skill não concede
  autorização para deploy, merge, novos provedores ou envio de dados pessoais.
