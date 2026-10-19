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

Ainda não aprovado nem migrado. Tabela `reconciliations` com `id`, `user_id`,
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
