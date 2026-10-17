# ADR 0011 — Leitura pessoal separada com Meu Pluggy

- Estado: aprovado por Enzo em 17/10/2026; credenciais reais ainda não exercitadas.
- Contexto: o SaaS precisa continuar sem gasto; o plano pessoal Meu Pluggy não
  autoriza uso comercial. MCP não concede acesso a um aplicativo bancário.
- Escolha: CLI local opt-in, somente contas próprias, host HTTPS fixo,
  conta vinculada explicitamente ao item, CSV de uma fonte com revisão no Tato.
  Reutiliza httpx/Decimal/importador existentes; sem schema, dependência ou API nova.
- Alternativas: importação manual CSV/OFX/PDF continua disponível; agregação
  comercial e servidor MCP financeiro ficam fora deste experimento.
- Consequência: sem cron, reconciliação de alterações, pagamento Pix ou garantia
  de cobertura bancária. Dado pessoal permanece em CSV local ignorado, em claro;
  a integração comercial exigiria outro checkpoint e condições contratuais.
