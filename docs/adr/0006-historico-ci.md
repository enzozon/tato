# 0006 — Histórico como material de aprendizado

Status: aceito por Enzo em 19/09/2026.

Contexto: commits extensos tornam a revisão didática difícil; checks distintos
entre máquinas escondem falhas. Opções: entrega única ou pequenos passos executáveis.
Escolha: uma ideia por commit, teto de 400 linhas exceto lockfiles/migrations
autogeradas, corpo com justificativa e `make check` antes de cada commit.
Consequência: documentação e testes entram no orçamento de diff, sem commits WIP.

Uma branch/PR por etapa, resumo e parada ao final. Repositório público autorizado.
Um commit executável inicial em main permite abrir o primeiro PR com base real.
Pre-commit e CI compartilham Makefile; checks entram quando há implementação.
Dependabot mensal, Actions fixadas por SHA e proteção do main com checks exigidos.
Merge e deploy não são consequências automáticas de CI verde.
