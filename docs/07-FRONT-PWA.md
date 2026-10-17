# Etapa 9 — interface e aplicativo instalável

Plano: base Next.js estática; identidade em packages/mascot; sessão Supabase;
onboarding, contas e resumo; prévia de importação; chat e fontes; agentes;
PWA sem cache financeiro; testes de navegador e CI. Sem novo schema previsto.
A branch parte da etapa 8. PR 17 já integrado; o PR desta etapa aponta para main.

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
Renovar o token do mesmo usuário preserva rascunhos e prévias. Trocar entre
Conversa, Importar e Resumo mantém esses formulários em memória; sair ou trocar
de usuário desmonta todo o espaço. Falhas de requisições antigas são descartadas.

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
O nome do cache incorpora também os bytes dos ícones: trocar a arte atualiza
o worker mesmo quando o manifesto e a orientação offline não mudam.
Instalação física em Android/iPhone ainda exige dispositivo e ambiente HTTPS.

`make config-check` mostra apenas presença/formato das configurações. `make
web-config` exporta uma lista fechada de três configurações públicas para
`apps/web/.env.local`, ignorado no Git. Chave JWT service_role ou sb_secret é
recusada. Login de console não substitui chave de API; presença não prova acesso.
Nesta retomada a URL local estava em SUPARABASE_PROJECT_URL; foi normalizada
para SUPABASE_URL. Token interno local gerado, sem ativar cron ou envio remoto.

Login Google só aparece com `NEXT_PUBLIC_GOOGLE_AUTH_ENABLED=true`, após ativar
o provedor e autorizar o redirect `/app/` no Supabase/Google. Cadastro envia esse
mesmo destino de confirmação. Login por senha e exclusão foram validados com
Supabase real; confirmação por e-mail e Google ainda precisam de validação própria.

O teste `playwright.integration.config.ts` sobe FastAPI em localhost:8009 e a
interface em :3001. Só Supabase é simulado: conta, prévia, importação, chat e
resumo usam SQL real em tato_test. O servidor exclusivo recusa Postgres remoto,
força LLM/e-mail desligados e restringe autenticação ao token sintético. Não é
um modo de execução da aplicação nem deve ser usado com dados pessoais.

Histórico carregado com atraso é combinado por request_id; respostas recebidas
na sessão atual prevalecem, inclusive após confirmar um lançamento.

Configuração local usa TATO_ENV=development e RATE_LIMIT_BACKEND=memory
explicitamente. Esse fallback não substitui Upstash compartilhado em produção.
Chaves Supabase e Upstash foram configuradas e validadas. O ensaio remoto usa
Upstash para limite de requisições e limpeza do cache. A chave Resend foi preenchida;
remetente/domínio e envio real continuam pendentes. Google permanece desativado.

CSV personalizado permite identificador estável, separador decimal e sinal das
despesas. Mapeamento parcial é recusado antes do upload; qualquer edição exige
nova prévia. O teste completo usa despesas positivas com ponto decimal e ID.

A conexão PostgreSQL tem timeout de cinco segundos. Um serviço local parado
gera falha limitada, permitindo diagnosticar e retomar o fluxo sem espera indefinida.

`make web-live-smoke` é opt-in e não roda no CI. Requer conta gratuita confirmada,
Postgres local `tato_dev_*`, Node/Chromium e as chaves reais no `.env`. Reutiliza
o teste de importação com Supabase e Upstash reais; LLM/e-mail ficam desligados.
Uma identidade sintética confirmada é criada administrativamente, sem e-mail.
O navegador testa senha, onboarding, CSV, chat analítico, saldo e exclusão.
O runner confirma a remoção remota e local; falhas mantêm apenas o UUID da
identidade em `test-results/live-smoke-owner.json` até confirmar a limpeza.
Senhas/tokens não são gravados em traces, relatórios ou saída do ensaio.

Após perda das chaves antigas, o banco `tato` foi preservado e o ambiente passou
para `tato_dev_20261005`, com chaves novas e corpus público indexado. Os dados
cifrados antigos continuam inacessíveis sem a chave original. Em 07/10/2026,
o fluxo remoto passou com R$ 12,34 de despesa e R$ 87,66 de saldo sintéticos;
conta de teste removida. Isso não valida instalação física ou envio de e-mail.

Respostas atrasadas de agentes não substituem alterações mais recentes nem a sessão renovada. Exclusão só encerra a sessão local se a identidade atual ainda for a dona da operação. Regressões desktop/mobile cobrem a concorrência.

Conta inclui cobrança exclusivamente de teste. A disponibilidade vem de
`/billing/status`; retorno do navegador não concede plano. Checkout pendente
reutiliza UUID mesmo após falha/renovação; UUID cancelado só é descartado depois
de confirmar ausência de pendente. Portal recebe apenas UUID e aceita destino
Stripe validado. URLs temporárias não são persistidas pela interface.

Após salvar conta/importação, falha ao atualizar o resumo não apaga a confirmação.
A conta limpa o formulário já salvo e oferece repetir somente a leitura;
a importação remove a prévia confirmada e informa que os registros foram salvos.

Instalação consome o evento `beforeinstallprompt` uma única vez. Rejeições do
prompt ou da escolha do navegador apresentam orientação, sem erro não capturado.

Campos de formulário usam `--muted` na borda: contraste de 6,21:1 sobre branco,
acima do mínimo 3:1 do [WCAG 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).
A borda anterior atingia 2,10:1 e não distinguia campos vazios do painel branco.
Playwright calcula o contraste das cores computadas dos campos de login contra
as superfícies interna e externa em desktop/mobile; isso não é auditoria completa.

## Recuperação de senha

`Login` solicita `resetPasswordForEmail` com retorno fixo no mesmo site,
`/app/?recovery=1`. A resposta da interface é igual para sucesso e conta ausente;
limite de frequência e indisponibilidade mostram erro genérico, sem texto bruto
do provedor. Isso não comprova proteção contra enumeração na API do Supabase.

O parâmetro apenas abre a tela de recuperação: não autoriza trocar a senha.
Somente `PASSWORD_RECOVERY`, emitido pelo SDK após validar a sessão, vincula o
formulário a um usuário, removendo o fragmento de autenticação da URL após a
validação. O observador em `lib/client.ts` registra esse evento
antes da hidratação; sem ele, o componente pode receber só `INITIAL_SESSION`.
Enquanto recupera, a interface não chama `/me` nem `/dashboard`. O formulário
confere confirmação e identidade atual antes de `updateUser`, rejeita respostas
de outro usuário e preserva rascunho na renovação da mesma sessão. Sucesso pede
novo login; cancelar encerra a sessão local e remove o parâmetro de retorno.

Após `auth.initialize()` concluir, callbacks inválidos, expirados ou com falha
transitória também têm credenciais removidas da URL. A limpeza aguarda o SDK
consumir o retorno, não altera outra navegação e não libera a recuperação.
Falha ao sair também aparece para links inválidos, mantém o dashboard fechado
e permite repetir o cancelamento.
O SDK pode remover a sessão local antes de devolver erro remoto; nesse caso,
o gate preserva o aviso, sem afirmar que a revogação remota foi confirmada.

Para validar externamente, o responsável precisa autorizar a URL exata de
retorno em Supabase → Authentication → URL Configuration e configurar envio
de e-mail/SMTP e limites gratuitos. Em desenvolvimento, a URL usada nos testes
é `http://127.0.0.1:3000/app/?recovery=1`; produção depende do domínio HTTPS
aprovado. Nenhuma allowlist, configuração remota ou serviço de e-mail foi alterado.
Os testes desktop/mobile usam somente respostas e tokens sintéticos; não provam
entrega, validade de link real ou revogação de outras sessões.

Na conversa, perguntas também permitem quebra de palavras longas, como já
acontece nas respostas. Sem isso, uma mensagem válida de 500 caracteres sem
espaços alargava a página no computador e no celular. O teste de regressão
envia essa mensagem sintética e verifica a largura real do documento.

Referências oficiais consultadas em 13/10/2026:
[solicitar recuperação](https://supabase.com/docs/reference/javascript/auth-resetpasswordforemail),
[alterar senha](https://supabase.com/docs/reference/javascript/auth-updateuser),
[eventos de autenticação](https://supabase.com/docs/reference/javascript/auth-onauthstatechange) e
[URLs permitidas](https://supabase.com/docs/guides/auth/redirect-urls).

## Exportação pessoal

Configurações oferece download de tato-dados.json por GET /me/export autenticado.
O navegador preserva bytes do JSON e centavos int64 em strings. Cancelamento,
renovação/saída e desmontagem abortam o pedido; a identidade é conferida novamente
antes do download. O Blob não entra no service worker e sua URL é revogada.
A tela informa que o arquivo contém dados pessoais legíveis. A prova Playwright
é Chromium desktop/mobile; Safari e iPhone físico ainda precisam de validação.
