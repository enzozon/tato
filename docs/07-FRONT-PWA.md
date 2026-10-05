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

Projeção do dashboard: saldo das contas menos despesas diárias médias projetadas
até o fim do mês, sem cartões ou receitas futuras. Exige contas abertas desde o
início do mês; a hipótese de histórico completo depende dos imports do usuário.
Centavos arredondados para cima nas despesas futuras; cálculo inteiro no backend.
O pet se enrola quando esse saldo projetado fica negativo; sem contas, dorme.

Sessão Supabase permanece em memória; atualizar a página exige novo login.
Isso evita persistir tokens no armazenamento local. A criação de `/me` antecede
o resumo, para que a primeira visita não concorra com a inicialização da conta.
Respostas de uma sessão anterior são descartadas após troca de identidade.

Importação mantém arquivo e recibo apenas em memória; qualquer edição invalida
a prévia. O chat usa SSE e só apresenta a resposta validada pela API; repetir
uma tentativa reutiliza request_id. React trata descrições e fontes como texto,
sem HTML/Markdown executável. Confirmação de lançamento chama a rota própria.

Agentes permitem configurar, pausar, criar metas e marcar avisos como lidos.
Quota permanece no backend. E-mail não é oferecido como ativo sem configuração
externa validada. Exclusão exige digitar EXCLUIR; o backend conserva a proteção
de exclusão pendente se a remoção no provedor falhar.

O manifesto e PNGs 192/512 tornam a instalação possível em navegadores compatíveis;
sharp rasteriza apenas o SVG autoral do pacote, sem API de imagem. O service worker
guarda somente a página genérica offline e ícones. Nenhuma resposta de API, HTML
autenticado ou transação entra em CacheStorage. Não é possível consultar finanças
sem rede. HTTPS é necessário fora do localhost, conforme [MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).
Instalação física em Android/iPhone ainda exige dispositivo e ambiente HTTPS.

`make config-check` mostra apenas presença/formato das configurações. `make
web-config` exporta uma lista fechada de três configurações públicas para
`apps/web/.env.local`, ignorado no Git. Chave JWT service_role ou sb_secret é
recusada. Login de console não substitui chave de API; presença não prova acesso.
Nesta retomada a URL local estava em SUPARABASE_PROJECT_URL; foi normalizada
para SUPABASE_URL. Token interno local gerado, sem ativar cron ou envio remoto.
