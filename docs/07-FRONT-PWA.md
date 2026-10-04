# Etapa 9 — interface e aplicativo instalável

Plano: base Next.js estática; identidade em packages/mascot; sessão Supabase;
onboarding, contas e resumo; prévia de importação; chat e fontes; agentes;
PWA sem cache financeiro; testes de navegador e CI. Sem novo schema previsto.
A branch parte da etapa 8 e mantém seu PR separado enquanto o PR 17 está aberto.

Direção visual: papel claro, verde profundo e terracota, tipografia de leitura,
mascote geométrico autoral. Formulários usam HTML semântico e foco visível.
Next/React substituem roteamento e renderização próprios; Supabase JS cuida da
sessão; Playwright valida comportamento real no navegador. CSS local nesta
primeira entrega evita gerar uma biblioteca de componentes sem usos definidos.

Build por exportação estática, conforme a [documentação Next](https://nextjs.org/docs/app/getting-started/deploying).
Credenciais administrativas nunca entram no bundle. Configuração pública usa
somente URL da API, URL Supabase e chave explicitamente publicável.

`GET /dashboard` retorna contas e agregados SQL do mês até a data local atual.
Centavos nessa API são strings decimais para preservar inteiros além de 2^53 no
JavaScript. Saldo consolidado exclui cartões; despesas incluem cartões. CORS
usa origens explícitas de `WEB_ORIGINS`, sem cookies ou wildcard.
