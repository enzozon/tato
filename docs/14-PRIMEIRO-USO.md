# Rodar, testar e publicar o Tato

## Rodar no Windows

Use `D:\financiaAi`, preserve o `.env` existente e abra Docker Desktop.
Pré-requisitos: uv/Python 3.12, GNU Make e Node 24. Não copie o exemplo por cima
das suas chaves nem recrie o banco já preparado neste computador.

No primeiro terminal PowerShell:

```powershell
cd D:\financiaAi
make sync
make infra-up
make config-check
make migrate
make web-config
make dev
```

`make migrate` aplica migrations pendentes; `make web-config` exporta somente
URLs e chave publicável para `apps/web/.env.local`. Nunca enviar tokens secretos
ou chave administrativa ao navegador. API: `http://127.0.0.1:8000`.

No segundo terminal:

```powershell
cd D:\financiaAi
npm.cmd ci
npm.cmd run dev --workspace=tato-web
```

Abra a landing em `http://127.0.0.1:3000/` e o app em
`http://127.0.0.1:3000/app/`. Deixe os dois terminais abertos.
`http://127.0.0.1:8000/health` verifica o processo; `/ready` confere banco, papel
e schema mínimo; `/docs` documenta a API e não substitui a interface.

Neste teste, `WEB_API_URL=http://127.0.0.1:8000` no `.env` e `WEB_ORIGINS` inclui
`http://127.0.0.1:3000`. Mudanças de ambiente exigem reiniciar a API; mudanças
públicas exigem repetir `make web-config` e reiniciar a interface.

No Supabase, Authentication → URL Configuration: Site URL
`http://127.0.0.1:3000` e Redirect URLs `http://127.0.0.1:3000/**` para uso local.
Não misturar `localhost` e `127.0.0.1`. Confirmação e recuperação precisam de
entrega de e-mail; o SMTP padrão restringe destinatários. Google exige provider
e flag pública próprios. [Referência](https://supabase.com/docs/guides/auth/redirect-urls).

## O que testar primeiro

1. Criar conta, confirmar e-mail, entrar e concluir onboarding sem CPF.
2. No Resumo, adicionar uma conta sintética com saldo inicial zero e primeiro
   dia do período em 17/10/2026.
3. Importar [movimentos-sinteticos.csv](exemplos/movimentos-sinteticos.csv) nessa
   conta. Esperar dois débitos e total R$ 70,00; revisar antes de confirmar.
4. Reimportar o mesmo arquivo: zero inseridos e duas duplicatas.
5. Perguntar quanto gastou nessa conta em outubro de 2026: esperar R$ 70,00
   e fonte SQL. A expectativa vem do arquivo, não de texto inventado pela IA.
6. Fazer um lançamento pelo chat, revisar/confirmar e conferir o novo total.
7. Testar conversa livre e pergunta conceitual. Para a base pública, executar
   `make rag-index` uma vez no banco local preparado: usa conexão administrativa
   e indexa somente o corpus público, não seus uploads privados.
8. Ativar um agente Free e conferir limites; alertas exigem dados suficientes.
9. Conferir consumo, saída/login e recuperação de senha. Quando a exportação
   estiver integrada, baixar o JSON e conferir valores e descrições.
10. Excluir somente uma conta descartável; a exclusão remove seus registros.

O Free permite uma fonte importada e um agente. Várias instituições exigem o
Pro sintético local aprovado; não ativar cobrança para contornar esse limite.
IA pessoal exige as flags Groq/ZDR existentes. Sem provider elegível, algumas
respostas ficam indisponíveis. Bancos/faturas sem exemplo validado não estão
cobertos por este roteiro. Use dados sintéticos antes de dados pessoais.

## Testes e PWA

`make check` executa lint, tipagem e testes Python. Para a interface:

```powershell
npm.cmd run check:web
npm.cmd exec --workspace=tato-web -- playwright install chromium
npm.cmd test --workspace=tato-web
```

Instale o Chromium na primeira execução ou após atualizar o Playwright.
Pare o servidor web manual antes do Playwright: a suíte cria seu próprio
servidor na porta 3000 com fixtures sintéticas. Não executar duas suítes com o
mesmo diretório de resultados. PG/RLS exigem URLs de teste para `tato_test`,
nunca URLs de um banco com dados reais.

Para testar o build estático e o shell offline, pare o Next dev e execute:

```powershell
npm.cmd run build
uv run --locked python -m http.server 3000 --bind 127.0.0.1 --directory apps/web/out
```

Mantenha a API no primeiro terminal. No celular, `127.0.0.1` aponta para o próprio
celular. Instalação física da PWA deve ser testada por um endereço HTTPS
acessível no Safari/Chrome; a prova local não confirma funcionamento no iPhone.

## Publicar na internet — proposta ainda sem deploy

Frontend, API e banco são serviços distintos. Publicar somente o frontend
disponibiliza a landing; não torna uma API local acessível a outras pessoas.

Cloudflare Pages é uma opção do plano B existente para o frontend estático:
Workers & Pages → Create application → Pages → importar `enzozon/tato`.
Monorepo: raiz do repositório, branch `main`, build `npm run build`, saída
`apps/web/out`, variável de build `NODE_VERSION=24`. Configurar apenas
`NEXT_PUBLIC_API_URL` (HTTPS da API),
`NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Nunca copiar
o `.env` inteiro. Validar um preview antes de promover a publicação.
[Guia oficial](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/).

A API ainda precisa de host aprovado e medido. Em 17/10/2026, a documentação do
[HF Spaces](https://huggingface.co/docs/hub/spaces-overview) exige plano pago para
criar Docker Spaces. O RAG local chegou a 864,99 MiB no Windows; não assumir que
512 MiB suportam o produto, nem que essa medição prova memória em Linux.
[Vercel Hobby](https://vercel.com/docs/plans/hobby) restringe uso a projetos
pessoais não comerciais; não garante operação comercial gratuita.

Uma VM [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
é candidata a investigar, não uma escolha aprovada: capacidade regional,
recuperação de máquinas ociosas e compatibilidade ARM precisam de prova.
Não contratar recursos pagos ou Pay-as-you-go para resolver falta de capacidade.
API temporária no PC depende dele ligado e de túnel HTTPS aprovado; não é um
servidor independente disponível 24 horas.

Depois da decisão: preparar Postgres/pgvector/RLS e papéis restritos; aplicar
migrations administrativamente; indexar corpus público; configurar secrets da
API; publicar a imagem Docker; validar saúde/prontidão, auth, importação, SQL,
RAG e exclusão. Não entregar `DATABASE_MIGRATION_URL` ao processo da API pública.
Com URLs finais, ajustar `WEB_ORIGINS`, variáveis públicas do build, Site URL e
redirects exatos do Supabase. E-mail e Stripe sandbox têm configuração própria.
Finalizar com usuário externo, PWA física, rollback, carga e quotas observadas.

## Próxima implementação

Concluir exportação e download; validar auth/e-mails e sandbox Stripe; aprovar
host compatível com R$ 0; implementar deploy/smoke/rollback/quotas; validar
bancos pendentes e iPhone. Pix aguarda contrato de cleanup. Telegram, relatório
PDF e Pluggy sandbox vêm depois do MVP.
