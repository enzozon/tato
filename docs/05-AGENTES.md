# Etapa 8 — agentes financeiros

Um agente é um alarme com três partes: gatilho, condição verificável e aviso.
O cron dispara a avaliação; SQL fornece fatos; regras determinísticas decidem
se existe um sinal. O LLM pode escolher uma redação aprovada, nunca recalcular.

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
