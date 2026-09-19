---
name: tato-commit
description: Preparar commits do Tato com diff pequeno, checks aprovados e justificativa em português; usar ao commitar uma etapa deste repositório.
---

# Commit do Tato

- Consulte `AGENTS.md` e a documentação da etapa afetada.
- Inspecione `git status --short` e o diff. Adicione caminhos explícitos, sem incluir
  alterações alheias, `.env`, extratos ou credenciais.
- Conte adições + remoções de `git diff --cached --numstat`: teto de 400 linhas.
  Exclua apenas lockfiles e migrations comprovadamente autogeradas; confira binários
  separadamente. Acima do teto, separe ideias em commits que funcionem isoladamente.
- Execute `git diff --cached --check` e `make check` antes de cada commit.
  Falha bloqueia o commit. Hooks não substituem essa verificação explícita.
- Mantenha docs atualizadas no commit relacionado; registre conclusão no diário.
- Use Conventional Commits em pt-BR com escopo e corpo explicando o motivo.
  Uma mensagem que precisa juntar duas ideias indica que o diff deve ser dividido.
- Não adicione atribuição de IA, Co-Authored-By ou links de sessão.
- Confira o commit gerado. Não reescreva histórico publicado para esconder falhas.
- Push/PR devem respeitar o escopo autorizado; esta skill não autoriza deploy nem merge.
