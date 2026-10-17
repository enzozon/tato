# Funções e telas para avaliação local

Inventário do código em 17/10/2026. Esta matriz descreve o que testar; não é um
registro de que todos os casos manuais passaram. Use o [primeiro uso](14-PRIMEIRO-USO.md)
para subir API/web, configurar retornos do Supabase e executar as suítes.
Resultados de produção e pendências externas estão no [plano de conclusão](13-CONCLUSAO.md).

## Preparação e forma de avaliar

- Use uma identidade descartável e dados sintéticos. Não publique tokens, arquivos
  de exportação ou capturas com informações financeiras reais.
- O [CSV de exemplo](exemplos/movimentos-sinteticos.csv) tem dois débitos de
  R$ 42,00 e R$ 28,00 em **17/10/2026**. Crie uma conta de saldo zero e abertura
  nessa data. O resultado é R$ 70,00 em outubro de 2026; em outro mês, a tela
  mensal não deve mostrar esses gastos como se fossem do mês atual.
- Faça os casos de total/deduplicação antes de novos lançamentos. Depois de
  confirmar outro gasto, R$ 70,00 deixa de ser o total esperado.
- Marque cada ID com `passou`, `falhou` ou `bloqueado`, navegador/largura e o
  resultado observado. Para aparência, registre o que deseja mudar por tela.
- Avalie desktop e 320/390 px, zoom de 200%, teclado e mensagens longas.
  Emular celular não comprova instalação ou funcionamento no iPhone físico.

Legenda: **UI** = interface navegável; **API** = sem controle próprio na tela,
usar `/docs` ou testes; **externo** = exige configuração/provedor e prova adicional.
Não compartilhar o token usado em Authorize no Swagger.

## Mapa de telas e estados

| ID | Tela ou expansão | O que precisa aparecer |
|---|---|---|
| T01 | `/` landing | Mascote, proposta, como funciona, Free/Pro em preparação, FAQ, links para entrar e instalar. Preços não significam cobrança ativa. |
| T02 | `/app/` sem sessão | Login, cadastro e solicitação de recuperação alternáveis; campos, carregamento, erro e confirmação de envio. Google só com flag pública. |
| T03 | Retorno de recuperação | Nova senha, confirmação, link inválido/expirado, erro, sucesso e saída; não abre registros durante a recuperação. |
| T04 | Entrada autenticada | Preparando espaço, erro com tentar novamente e onboarding sem CPF. Navegação Resumo/Conversa/Importar/Agentes/Conta e Sair. |
| T05 | Resumo | Mascote, saldo, despesas do mês, estimativa ou histórico insuficiente, categorias, contas e expansão Adicionar conta ou cartão. |
| T06 | Conversa | Entrada padrão após login: Tato animado, sugestões, histórico vazio/preenchido, seletor de conta, compositor ao pé da tela, processamento, resposta, fonte SQL, fontes RAG expansíveis e rascunho para confirmar. |
| T07 | Importação no chat | Abrir/fechar importador dentro de Conversa; mesmos controles de T08, sem trocar de canal ou gravar sem confirmação. |
| T08 | Importar | Sem conta: orientação; com conta: formato/arquivo, mapeamento CSV expansível, prévia/tabela/aviso/confirmar, sucesso/duplicatas/erro. |
| T09 | Agentes | Cards ativo/pausado, configurar agente, seletor de meta, opt-in de e-mail, criar meta, avisos vazios/preenchidos e marcar como lido. |
| T10 | Conta | Plano, cobrança de teste desativada/configurada, uso mensal, medições IA, download/cancelamento/erro e expansão Excluir minha conta. |
| T11 | Instalação/offline | Instruções iPhone/Android, botão quando o navegador oferecer instalação, rejeição tratada e página de orientação offline. |

As expansões usam `details`; não existe uma tela separada para cada uma. O app
atual não oferece lista/editoração geral de transações, CRUD de categorias/regras,
edição/exclusão individual de contas ou gerenciador visual de documentos.

## Roteiro funcional — interface

| ID | Onde e ação | Resultado esperado / dependência |
|---|---|---|
| A01 | Login: cadastrar e confirmar e-mail | Sem CPF; sessão após confirmação. **Externo:** Supabase, URLs de retorno e entrega de e-mail. SMTP padrão pode restringir destinatários. |
| A02 | Entrar com senha correta e incorreta; sair | Sucesso abre o próprio espaço; falha mostra erro sem dados financeiros; Sair limpa o espaço. Reabrir o app pode exigir novo login: sessão não é persistida em armazenamento local. |
| A03 | Esqueci minha senha, link válido, senhas divergentes/curtas | Solicitação não revela existência da conta; só sessão de recuperação permite trocar senha. Após concluir, exige novo login. Link expirado não libera dashboard. |
| A04 | Continuar com Google | Só aparece com `NEXT_PUBLIC_GOOGLE_AUTH_ENABLED=true` e provider Supabase configurado; retorno permitido. OAuth real ainda depende de validação externa. |
| A05 | Concluir onboarding e entrar novamente | Aviso inicial desaparece após persistir conclusão; não solicita CPF. Falha de rede permite tentar novamente. |
| D01 | Resumo: criar conta corrente/poupança/dinheiro | Nome, abertura e saldo válidos aparecem; centavos são exatos. Criar conta não consome fonte importada até receber importação. |
| D02 | Resumo: criar cartão | Tipo disponível; saldo de cartão não entra no saldo consolidado das contas, suas despesas entram no gasto mensal. |
| D03 | Importar CSV de exemplo na conta sintética | Prévia: 2 movimentos, saídas R$ 70,00, entradas zero, datas 17/10/2026. Antes de confirmar, nenhum lançamento novo no resumo. |
| D04 | Confirmar e consultar Resumo | 2 inseridos; saldo da conta -R$ 70,00 e despesas de outubro R$ 70,00, sem outros dados. Estimativa pode indicar histórico insuficiente pela abertura no meio do mês. |
| D05 | Reimportar exatamente o mesmo CSV | 0 inseridos/2 duplicatas; total permanece igual. CSV reescrito sem ID estável não garante deduplicação entre arquivos distintos. |
| D06 | CSV personalizado: preencher mapeamento parcial e completo | Parcial bloqueia envio; completo usa colunas de data/descrição/valor, ID opcional, decimal e sinal selecionados. Alterar arquivo/campos invalida prévia antiga. |
| D07 | OFX sintético BRL com FITID estável | Prévia e confirmação; reexport com mesmos FITIDs não duplica. Múltiplas contas, moedas diferentes/correções não suportadas devem ser recusadas, sem gravação parcial. |
| D08 | PDF compatível com texto e datas completas | Extrai movimentos para prévia; não tratar total da fatura como compra. PDF cifrado/digitalizado sem texto é recusado: não há OCR. Limites/fixtures em [ingestão](04-INGESTAO.md). |
| D09 | Arquivo vazio, formato inválido ou maior que 2 MiB | Erro claro, sem persistir parte do arquivo nem expor suas linhas. Limite também de 5.000 movimentos. |
| D10 | Importar para segunda conta no Free | Backend recusa nova fonte; não libera por manipulação da tela. Pro sintético local permite múltiplas fontes, sem cobrança real. |
| C01 | Selecionar conta; perguntar despesas de outubro de 2026 | Caminho analítico: R$ 70,00 após D04/D05, ferramenta `expense_total` e período com fim exclusivo visíveis. Número vem do SQL. |
| C02 | Selecionar Todas e depois conta específica | Consulta consolidada/filtrada segue seleção. Outra conta sem movimentos não recebe total da primeira. Não há suporte genérico a toda pergunta financeira: ferramenta atual calcula despesas por período/categoria/conta. |
| C03 | Conta selecionada: “gastei 10 reais no mercado hoje” | Caminho lançamento: rascunho com descrição/data/valor, sem gravar até Confirmar lançamento. Após confirmar, um gasto a mais; repetição não duplica. **IA pessoal:** Groq elegível/ZDR. |
| C04 | Perguntar “o que é uma reserva de emergência?” | Caminho conceitual: base pública indexada/modelos disponíveis; fontes expandem texto e `chunk_id`. Sem fonte suficiente, indisponibilidade/abstenção, não prova inventada. |
| C05 | Cumprimentar e conversar sem pedir números | Caminho conversa; resposta útil sem inventar patrimônio/saldo ou recomendar ativo. IA pessoal depende da política Groq/ZDR, sem enviar extrato inteiro. |
| C06 | Usar sugestão, Enter, Shift + Enter; enviar e voltar à aba | Sugestão só preenche, sem consumir quota. Enter envia e Shift + Enter quebra linha; IME não envia enquanto compõe. Tato atento durante processamento; só depois resposta validada completa. Histórico não apaga resposta nova quando chega atrasado. |
| C07 | Falhar pedido e Repetir pedido/Descartar tentativa | Repetir conserva `request_id`: pedido já aceito não gasta quota novamente; descartar libera nova mensagem. Não há botão geral de cancelar inferência. |
| C08 | Abrir importação no chat e importar CSV | Mesma revisão/confirmar/deduplicação; depois perguntar sobre conta/período. Anexar arquivo não autoriza suas instruções como prompt. |
| G01 | Criar meta e configurar Meta | Objetivo/valor positivos; meta pertence ao usuário. Alerta só quando saldo alcança alvo, conferido na execução; não significa reserva bancária feita. |
| G02 | Configurar/pausar Vigia de assinatura, Desvio e Fôlego | Free permite um ativo, Pro três; trocar exige respeitar limite. Fôlego/Meta excluem cartões. Não esperar os quatro avisos com apenas o CSV de dois movimentos. |
| G03 | Opt-in Autorizar avisos por e-mail; pausar/reativar | Desmarcado por padrão; preferência preservada. UI explica que autorização não garante entrega. **Externo:** Resend/remetente confirmado e flags. |
| G04 | Avisos vazios/preenchidos; marcar como lido | Ausência de histórico/execução é explicada. Valores e fonte aparecem; leitura persiste. Rodar cron é operação interna, descrita abaixo. |
| M01 | Conta: uso do plano | Free: 200 mensagens/mês, 1 fonte e 1 agente; período UTC. Pedidos aceitos com falha contam. Quota contratual não equivale ao rate limit técnico. |
| M02 | Conta: medições IA | Tentativas, tokens conhecidos/desconhecidos e duração; `não informado` não vira zero. Não são saldo/limites dos provedores; falha da seção não impede exportar/excluir. |
| M03 | Baixar meus dados | JSON legível, descrições decifradas, centavos como strings, 13 coleções do próprio usuário; sem embeddings/IDs de provedores/PDF original. Limite de 64 MiB/100 mil linhas recusa arquivo inteiro, não trunca. |
| M04 | Cancelar exportação; sair/trocar aba/sessão durante download | Resposta antiga não inicia download; cancelar permite repetir. Erros 401/409/429/503 ou MIME incorreto não baixam conteúdo nem exibem corpo remoto. |
| M05 | Excluir minha conta em identidade descartável | Exige `EXCLUIR`; apaga identidade e registros/vetores, não apenas oculta. Falha externa mantém exclusão pendente bloqueada para retomada operacional. Não testar na conta que deseja conservar. |
| B01 | Conta: cobrança com configuração desligada | Botões indisponíveis; parâmetros de retorno `success` não concedem Pro. Landing continua “Pro em preparação”. |
| B02 | Sandbox Stripe checkout/portal/status | Só após preparação de [monetização](12-MONETIZACAO.md): preço fixado no backend, URL Stripe validada, UUID estável ao repetir; status/portal autenticados. Ciclo remoto completo ainda pendente; não habilitar cobrança para apenas avaliar telas. |
| U01 | Navegar/renovar token/sair durante operações | Rascunhos preservados na mesma identidade; outra identidade não recebe estado, download, redirecionamento ou resposta antiga. Após mutação salva, falha só no refresh não deve reenviar a gravação. |
| U02 | Teclado, foco, movimento reduzido, zoom e tela estreita | No celular, Menu abre as seções; selecionar fecha e devolve foco. Escape fecha. No desktop, barra lateral visível. Compositor fica acessível com rolagem das mensagens; animação para com movimento reduzido. Labels, avisos, botões e mensagens longas não causam overflow horizontal. Não substitui auditoria WCAG completa. |
| U03 | Shell offline e instalação | Testar build estático, não Next dev; offline exibe orientação, sem cache financeiro. Voltar online permite usar API. PWA física requer endereço HTTPS acessível pelo telefone. |

PicPay/Banestes: somente layouts de **conta observados**; não certificação de todos
os exports. Faturas desses bancos e conta/cartão Sicoob precisam de exemplos
compatíveis. Não existe conexão MCP com o aplicativo do iPhone nem conexão
bancária automática. Telegram, relatório PDF e Pluggy sandbox não estão disponíveis.

## Funções somente por API ou infraestrutura

| ID | Função / rota | Verificação e restrição |
|---|---|---|
| P01 | `GET /health`, `GET /ready` | Processo saudável; prontidão exige banco/schema e papel restrito. Não mostra registros. |
| P02 | `GET /me`, `POST /me/onboarding`, `DELETE /me` | Identidade da sessão; confirmar exige booleano `true`, sem coerções. Não há parâmetro para escolher outro usuário. |
| P03 | `POST /rules` | Cria categoria/regra literal do usuário (sem regex), prioridade; importação aplica regras antes da IA. Não existe formulário web de regras. Limite técnico de 1.000. |
| P04 | `POST /import`, `/import/preview`, `/import/confirm` | Rota direta existe para clientes API; web usa prévia/recibo/confirmação. Recibo precisa corresponder ao arquivo/conta/mapeamento; conflito de ID com valor/data diferente gera rollback. |
| P05 | `POST /chat`, `/chat/stream`, `GET /chat`, `POST /chat/{turn_id}/confirm` | JSON/SSE/histórico/confirmar isolados, mesmo contrato e idempotência; consulta não aceita SQL livre. |
| P06 | `POST /rag/documents/{document_id}/index`, `POST /rag/search` | Indexação privada e busca com reranking opcional; modelos locais/pgvector/configuração necessários. Busca não substitui cálculos. UI mostra fontes pelo chat, sem painel próprio de indexação. |
| P07 | `PUT /agents/{kind}`, `GET /agents`, `POST/GET /goals`, `GET /insights`, `POST /insights/{id}/read` | Tipos `subscription_watch`, `anomaly`, `runway`, `goal`; filtros da sessão, metas/contas do próprio usuário. |
| P08 | `POST /internal/agents/run` | Token operacional `AGENTS_RUN_TOKEN`, lista explícita `user_ids` (até 25); sem botão público. Reexecução não duplica aviso do mesmo sinal. Não publicar token no navegador. |
| P09 | Regras dos quatro agentes | Suíte sintética cobre recorrência/aumento, desvio com histórico de três meses, projeção de fôlego e alvo de meta. Usar testes de agentes/integração; 2 compras não cobrem todos os gatilhos. |
| P10 | `/me/usage`, `/me/llm-usage`, `/me/export`, `/dashboard` | SQL/RLS e `no-store`; cruzar sessão A com IDs B deve negar/omitir dados B, inclusive texto/vetor/cache. Prova exige Postgres real e testes A/B, não só interface vazia. |
| P11 | `/billing/status`, `/billing/stripe/checkout`, `/billing/stripe/portal`, `/billing/stripe/webhook` | Sandbox somente; webhook assinado/replay/reconciliação/limpeza testados localmente. Callback web não é prova de pagamento. Pix possui adapter sem rota ativa/concessão de plano. |
| P12 | Router LLM/cache/circuit breaker | Testes locais verificam timeout/fallback/cache cifrado e isolamento. Free tier confirmado e modelos permitidos; fallback pessoal não passa para Gemini/OpenRouter. Teste remoto é opt-in sintético. |
| P13 | Sentry/PostHog/Logfire e e-mail | Transportes têm testes/allowlist e flags; eventos sintéticos com HTTP 200 históricos não provam recepção nos painéis ou plano gratuito atual. Desligados por padrão; não enviar conteúdo financeiro para validar. |
| P14 | Segurança de armazenamento e exclusão | Testes PG verificam RLS, cifragem, concorrência, deleção/cascata e bloqueio pendente. `tato_test` descartável obrigatório; nunca apontar integrações para banco pessoal. |

## Dependências que podem bloquear casos

- **Auth:** Supabase URL/chave publicável/segredo só na API; configuração pública
  gerada pelo comando do primeiro uso. Confirmar e-mail, recuperação e Google
  exigem serviços externos configurados, não fixtures de Playwright.
- **Core:** Postgres/pgvector/Redis locais, migrations, URLs com papéis corretos,
  `DATA_ENCRYPTION_KEY` e `DEDUP_HMAC_KEY`; não regenerar chaves com dados existentes.
  `RATE_LIMIT_BACKEND=memory` é opção de desenvolvimento de um único processo.
- **IA:** `LLM_ENABLED`, `LLM_FREE_TIER_CONFIRMED`; para dados pessoais,
  `GROQ_PERSONAL_DATA_ENABLED`, `GROQ_ZDR_CONFIRMED` e chave da organização
  autorizada. Não ligar flags sem cumprir as condições. Corpus/modelos RAG são
  locais; download inicial/cache e índice público precisam estar preparados.
- **E-mail:** `AGENT_EMAIL_ENABLED`, `RESEND_FREE_TIER_CONFIRMED`, chave,
  `RESEND_FROM` e destinatário confirmado. Sem configuração, avaliar opt-in e
  avisos in-app; entrega real continua bloqueada.
- **Cobrança:** `BILLING_ENABLED` permanece desligada até ensaio aprovado;
  configuração Stripe/API/listener de teste em `12-MONETIZACAO.md`.
  Nunca usar cartão/chave live. Pix fica indisponível até resolver seu contrato.
- **Telemetria:** flags `SENTRY_ENABLED`, `POSTHOG_ENABLED`, `LOGFIRE_ENABLED`
  independentes e opt-in; não necessárias para navegar no app.

## Como fechar a avaliação

O [primeiro uso](14-PRIMEIRO-USO.md#testes-e-pwa) contém comandos de qualidade,
Playwright e PWA. `make check` não executa todas as integrações/RAG/serviços
remotos: `make integration` e `make rag-eval` exigem ambiente descartável e
modelos preparados. Playwright normalmente usa API/auth simulados; seus passes
não comprovam login remoto, pagamento, e-mail ou instalação física.

Registre os IDs bloqueados e a dependência faltante. Deploy, rollback, usuário
externo, medição de quotas/carga e iPhone físico continuam ensaios separados;
não são aprovados pelo simples fato de o servidor local abrir.
