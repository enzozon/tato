# Reconciliação de transferências e faturas

Transferir dinheiro entre contas próprias é mover uma moeda de um bolso para
outro. As duas linhas afetam cada saldo, mas não representam renda ou consumo.
Pagar uma fatura também move dinheiro: a despesa já está nas compras do cartão.
O vínculo correto é saída da conta → crédito de pagamento no cartão, não uma compra.

## Plano desta entrega

1. Validar pares e calcular o impacto com regras determinísticas e centavos exatos.
2. Persistir o vínculo e as naturezas anteriores após checkpoint do schema.
3. Sugerir candidatos limitados, sem alterar dados, por valor/sinal/conta/data.
4. Confirmar o par com versões atuais e operação atômica sob lock do usuário.
5. Exibir o vínculo e permitir desfazer, restaurando as naturezas anteriores.
6. Bloquear edição/exclusão de linhas vinculadas até desfazer a reconciliação.
7. Provar isolamento, conservação de saldos e totais SQL em Postgres; testar a UI.

## Regras e limites

Só conciliar saída negativa de conta corrente, poupança ou dinheiro com entrada
positiva em outra conta do mesmo usuário. Valores devem ser exatamente opostos,
em BRL, com até sete dias corridos entre datas. Entrada em cartão representa
pagamento de fatura; demais entradas representam transferência interna.

As duas linhas precisam existir. Não criar contrapartida, completar diferença,
parear taxas ou usar LLM para decidir. Mais de um candidato significa ambiguidade;
a pessoa escolhe. Candidatos não comprovam que o dinheiro foi transferido.
Conta/cartão sem registros compatíveis continua sem reconciliação.

Confirmar muda somente a natureza para `transfer` nas duas linhas. Valores,
datas, categorias, descrições e origens são preservados. Saldos ficam iguais;
despesas/receitas indevidas saem dos respectivos totais. Desfazer restaura a
natureza anterior e os totais. Não desfaz a transferência no banco.

Arquivos sobrepostos sem ID continuam sujeitos à limitação de deduplicação em
`19-LANCAMENTOS.md`. Reconciliação não decide que duas linhas são duplicatas.
Juros, tarifas, estornos, parcelamentos e conciliação em lote ficam fora desta versão.

## Checkpoint de schema proposto

Aprovado por Enzo em 18/10/2026 antes da migration. Tabela `reconciliations` com `id`, `user_id`,
`created_at`, `debit_transaction_id`, `credit_transaction_id`, `kind`
(`transfer`/`card_payment`), `debit_previous_kind` e `credit_previous_kind`.
Sem descrição ou valor duplicados. Adicionar UNIQUE `(user_id, id)` a
`transactions` para FKs compostas das duas pontas, restritas ao mesmo dono.

UNIQUE por dono/ponta, pontas distintas, checks das naturezas anteriores,
RLS forçada e cascata na exclusão total do usuário. A API verifica sinais e
ausência de qualquer outro vínculo nas duas posições sob o mesmo lock usado
na edição/exclusão. As linhas vinculadas ficam bloqueadas para essas operações.
Desfazer remove o vínculo na mesma transação que restaura as naturezas.

Consequência: desfazer remove este vínculo, sem criar um histórico permanente
de reconciliações. Esta versão não é um livro de auditoria imutável. Uma nova
camada de auditoria exigirá checkpoint próprio antes de persistir mais dados.

A migration `0011` foi aplicada primeiro em `tato_test`, com drift limpo. As
duas FKs incluem o dono e a API bloqueia edição/exclusão enquanto há vínculo.
Reimportar ID estável já vinculado confere a natureza anterior guardada no
vínculo, sem sobrescrever `transfer`; divergências de data/valor seguem recusadas.

`GET /reconciliations/candidates` mostra até 20 entradas e sinaliza limite;
`POST /reconciliations` confirma com versões das duas linhas e booleano explícito.
`GET /reconciliations/{id}` mostra o vínculo; `DELETE` desfaz com confirmação.
Repetir uma confirmação já ativa conserva o vínculo. Desfazer ausente é idempotente.

Sete ensaios Postgres cobrem saldos, compras, desfazer, acesso cruzado,
reimportação divergente, limite de candidatos, extremos de data/inteiro e
disputa concorrente pela mesma saída. Valores são conferidos pelos totais SQL.

## Como testar na interface

1. Importe ou registre as duas pontas em contas próprias diferentes.
2. Em **Lançamentos**, encontre a saída e clique em **Reconciliar saída**.
3. Escolha **Revisar este par** na entrada correspondente. A prévia mostra
   as duas contas, datas, valores e quanto deixará de contar como receita/despesa.
4. Confira os registros antes de **Confirmar reconciliação**. O efeito segue a
   data de cada ponta, inclusive quando pertencem a meses diferentes.
5. Abra **Ver vínculo** em qualquer ponta. **Confirmar desfazer** restaura as
   naturezas anteriores e libera edição/exclusão; não move dinheiro no banco.

Sem candidato, importe a outra ponta ou revise datas e valores. A lista mostra
até 20 entradas; não é prova de completude se o aviso de limite aparecer.
Se uma versão mudou, feche e abra novamente para revisar os dados atuais.
O app não confirma nem tenta outro par automaticamente após conflito.

As naturezas guardadas são as anteriores à reconciliação, não necessariamente
as originalmente exportadas pelo banco: correções manuais anteriores continuam
sujeitas às regras de divergência de reimportação em `19-LANCAMENTOS.md`.

## Evidência local — 18/10/2026

- `make check`: 695 testes, cobertura de 81,16%, lint/formatação/mypy aprovados.
- PostgreSQL: 119 integrações aprovadas; reversão `0011 → 0010 → 0011` no
  banco descartável e drift limpo, mais oito ensaios de schema/fluxo.
- Web: 150 testes desktop/mobile; seis exercitam prévia, confirmação,
  desfazer, ausência de candidatos, foco e conflito com nova revisão.
- Build estático, tipos e PWA offline aprovados. Capturas sintéticas em
  `test-results/reconciliacao/`, incluindo 320px sem overflow horizontal.

A exportação JSON da conta inclui vínculos ativos com as duas pontas e
naturezas anteriores, sem dados de outro usuário. Estes ensaios não comprovam
leitura bancária real, Safari/iPhone físico ou publicação em produção.
