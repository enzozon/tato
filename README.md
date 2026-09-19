# Tato

**Seu dinheiro, em uma conversa.** Experimento de SaaS financeiro com Python,
LLM e RAG, limitado a serviços gratuitos. Em construção; use dados sintéticos.

## Executar localmente

Pré-requisitos: Git, uv e GNU Make. O uv instala o Python 3.12 indicado no projeto.

```sh
make sync
make check
make dev
```

A API responde em `http://127.0.0.1:8000/health` e documenta seu contrato em
`http://127.0.0.1:8000/docs`. O health verifica somente o processo HTTP.

No Windows, GNU Make também é necessário para os comandos acima. Como alternativa,
execute as receitas do Makefile diretamente no PowerShell, uma por vez.

## Estado

Fundação: API de saúde, contrato OpenAPI testado e verificação de qualidade.
Autenticação, dados financeiros, LLM, RAG e interface ainda não existem.
Não há deploy nem necessidade de credenciais externas para testar esta etapa.
