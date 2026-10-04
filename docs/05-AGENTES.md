# Etapa 8 — agentes financeiros

Um agente é um alarme com três partes: gatilho, condição verificável e aviso.
O cron dispara a avaliação; SQL fornece fatos; regras determinísticas decidem
se existe um sinal. Nesta entrega, a redação também usa templates determinísticos.
Personalização por LLM permanece uma extensão opcional: não há ganho demonstrado
que justifique enviar contexto financeiro ou consumir quota para esses avisos.

## Plano e fronteiras

1. Fechar documentação e avaliação sintética reproduzível do chat da etapa 7.
2. Registrar acesso/layouts bancários ainda indisponíveis sem inventar integração.
3. Revisar schema antes da migration: configuração dos agentes e entrega de avisos.
4. Implementar regras de recorrência, desvio, fôlego e meta com dinheiro inteiro.
5. Persistir insights cifrados com idempotência e isolamento por usuário.
6. Expor configuração, leitura/confirmação de insights e execução interna protegida.
7. Integrar cron opt-in e e-mail opt-in, sem habilitar envio ou deploy automaticamente.
8. Validar quotas, acesso cruzado, concorrência, falhas e documentar resultados.

## Schema aprovado em 04/10/2026

`agents`: UUID, user_id, created_at, kind, enabled, account_id obrigatório,
goal_id opcional, email_enabled (false). Um registro por (user_id, kind),
permitindo configurar os quatro tipos e ativar apenas 1 no Free ou 3 no Pro.
Vínculos compostos garantem conta/meta do mesmo usuário. Apenas o agente Meta
aceita/exige goal_id. RLS forçada e exclusão em cascata via usuário.

`goals`: acrescentar unicidade (user_id, id) para a FK composta; sem novo campo.
A meta acompanha saldo da conta indicada, não um valor inventado ou inferido
da descrição. Contas de cartão não são aceitas como reserva da meta.

`insights`: acrescentar email_status (off/pending/sent), email_attempts (0),
email_last_attempt_at e email_sent_at opcionais. Conteúdo continua cifrado;
event_key já fornece idempotência. O destinatário será o e-mail confirmado no
Supabase, consultado no envio; não haverá campo livre para disparar a terceiros.
Avisos externos serão genéricos, sem valores ou extratos. Envio desligado por padrão.

## Operação inicial

O endpoint interno recebe uma lista limitada de usuários autorizada por token
operacional. O cron lê essa lista de um secret do GitHub: a API não usa conexão
administrativa para varrer usuários e não relaxa RLS. É uma limitação operacional
para a primeira implantação; descoberta automática de usuários exigirá outra revisão.
Nenhum secret, URL remota ou cron ativo será provisionado nesta implementação local.

Rebaixar Pro para Free não pode executar três agentes: em cada execução, ordenar
agentes ativos por criação/ID e aplicar o limite atual. A configuração bloqueia
novas ativações acima da quota sob o mesmo lock de usuário usado pelo chat.

## Regras propostas

- Assinaturas: mesma descrição normalizada, três cobranças em meses consecutivos;
  avisar aumento sobre a anterior ou sugerir revisão da recorrência. Não afirmar
  que um serviço está esquecido sem evidência de uso.
- Desvio: gastos do mês por categoria contra três meses completos, com média e
  variância em centavos. Exigir histórico e gasto acima de média + 2 desvios.
- Fôlego: saldo de abertura + movimentos, despesas médias diárias do mês e dias
  restantes. Projeção linear explicitamente identificada, sem promessa de precisão.
- Meta: saldo da conta versus alvo registrado, com aviso ao atingir o alvo.
  Saldo pertence à conta, não comprova que o usuário reservou todo esse dinheiro.

As regras em `agent_rules.py` usam centavos inteiros. Desvio compara quadrados
com variância escalada, sem arredondar raiz quadrada. Fôlego arredonda projeção
para cima e exige conta aberta desde o início do mês. Histórico insuficiente
não gera alarme; padrão de cobrança é hipótese, nunca prova de serviço esquecido.

Configuração usa lock por usuário e quota do plano atual. Concorrência na última
vaga Free é testada no Postgres; alterar configuração e desativar não cria outro
agente. Metas são cifradas, limitadas tecnicamente a 100 por usuário; conta de
cartão não pode sustentar agente de fôlego ou meta. Schemas de saída omitem user_id.

Runtime lê somente o ledger da conta autorizada, ignora movimentos futuros e
recusa mais de 5.000 linhas no recorte antes de gerar resultados parciais. Saldo
é calculado por SUM desde a abertura. Insights são cifrados; HMAC identifica a
condição sem revelar descrição. Avisos são limitados a uma ocorrência por condição
e mês; meta usa alvo como identidade para não repetir a comemoração todo mês.
Downgrade de plano e exclusão pendente são revalidados a cada execução.

API autenticada: `PUT /agents/{kind}`, `GET /agents`, `POST /goals`, `GET /goals`,
`GET /insights?limit=50` (máximo 100 recentes) e `POST /insights/{id}/read`.
Respostas usam no-store. `POST /internal/agents/run` exige token operacional de
pelo menos 32 caracteres e lista de até 25 UUIDs; data vem do servidor São Paulo.
Não aceita data, valor financeiro ou destinatário de e-mail do chamador.

E-mail exige as flags `AGENT_EMAIL_ENABLED` e `RESEND_FREE_TIER_CONFIRMED`, além
da opção individual do agente. O destinatário vem do usuário confirmado no
Supabase; assunto e corpo são genéricos, sem valores ou descrições financeiras.
Cada tentativa é persistida antes da rede, com intervalo mínimo de dois minutos,
até três tentativas e cinco mensagens por usuário/lote. O plano é revalidado.
Retries usam o mesmo ID de insight; após 23 horas da criação, uma tentativa
anterior impede novo envio automático. Isso evita duplicação depois da
[retenção de 24 horas da chave Resend](https://resend.com/docs/dashboard/emails/idempotency-keys).
Uma entrega incerta permanece pendente para revisão, sem promessa de exactly-once.
Testes usam transporte simulado e Postgres real; envio remoto ainda não validado.

O workflow `agents-cron.yml` só executa com a variável de repositório
`AGENTS_CRON_ENABLED=true`. Após o deploy autorizado, configurar os secrets
`TATO_API_URL` (HTTPS), `AGENTS_RUN_TOKEN` e `AGENT_USER_IDS` (lista JSON de
até 25 UUIDs autorizados). A agenda é horária, sem garantia de pontualidade.
O cliente recusa redirects e imprime apenas totais; nenhuma credencial passa
por interpolação de shell. Não há descoberta automática de usuários nesta fase.
O lote retorna `processed`, `inserted` e `sent`; falha de execução interrompe
o lote e resulta em erro HTTP. A próxima tentativa reaproveita a idempotência
dos usuários já processados. E-mail desabilitado não impede avisos internos.

## Evidência e limites da entrega

Migration 0007 aplicada nos bancos locais; ida e volta testada no `tato_test`,
sem divergência detectada pelo Alembic. Suíte combinada: 225 testes unitários/HTTP,
47 integrações Postgres/Redis e cobertura de 81,56%. A integração verifica quota
concorrente Free, downgrade Pro, acesso cruzado, exclusão pendente, execução
idempotente e tentativas de entrega persistidas. Não houve envio real de e-mail.
Cron remoto aguarda deploy e configuração; interface de agentes entra na etapa 9.
Não há detecção de serviços efetivamente esquecidos, reserva segregada para metas
nem previsão financeira probabilística. Os avisos descrevem limites e hipóteses.
