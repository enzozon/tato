# Lançamentos e preparação para uso diário

Uma lista de extrato precisa permitir conferir e corrigir registros sem perder
a identidade de origem. A conta e a chave de deduplicação permanecem fixas ao
editar: reimportar o arquivo não deve desfazer uma correção manual.
Se um arquivo sobreposto trouxer data, valor ou tipo diferentes dos já corrigidos,
a validação existente recusa a importação com conflito; não sobrescreve a edição.

## Entrega em partes pequenas

1. Consultar lançamentos com conta, período, tipo e paginação limitada no servidor.
2. Corrigir data, descrição, valor, tipo e categoria com confirmação explícita.
3. Excluir somente após preservar a identidade removida contra reimportação.
4. Revisar reconciliação de transferências/faturas com proposta própria.
5. Validar configurações externas e preparar publicação, sem fazer deploy agora.

Consultas usam `account_session`, dono autenticado, RLS, quota e `no-store`.
Descrições são decifradas apenas na página autorizada; não há busca textual
persistente em claro. Valores da resposta são strings de centavos, sem float.
Intervalos incluem as duas datas. A paginação usa data/UUID como cursor para
não repetir linhas quando chegam registros mais recentes.

A edição mantém conta, documento e identidade de origem. Um token derivado do
registro impede sobrescrever outra edição com uma tela antiga. O usuário revisa
o impacto nos saldos antes de confirmar. Transferência não entra em despesas;
marcar uma linha como transferência não cria nem pareia a contrapartida.

## Checkpoint de schema proposto — exclusão

Aprovado por Enzo em 18/10/2026, antes da migration. Tabela `deleted_transactions` com
`id`, `user_id`, `created_at`, `account_id` e `dedup_key`. Sem descrição, data ou
valor financeiro. FK de conta restrita ao mesmo usuário, UNIQUE
`(user_id, account_id, dedup_key)`, RLS forçada e cascata na exclusão do usuário.

Na exclusão de um lançamento, gravar essa identidade e remover a linha na mesma
transação. O ponto único `add_transaction` consulta as identidades removidas
antes da inserção. Isso impede uma reimportação de ressuscitar o lançamento.
O custo é conservar o hash de origem enquanto existir a conta do usuário.
Sem essa tabela, apagar uma linha permitiria sua recriação por arquivo sobreposto.
O marcador usa o UUID do lançamento para permitir repetir a exclusão após uma
resposta perdida. A migration foi aplicada primeiro em `tato_test`, com drift
verificado. Downgrade descarta a proteção e fica restrito ao banco descartável;
em ambiente publicado, corrigir migrations com uma nova revisão.

Limite: CSV/PDF sem ID estável usam identidade do arquivo/linha. O mesmo arquivo
continua bloqueado, mas outro arquivo sobreposto pode conter a mesma movimentação
com outra identidade. O marcador não resolve essa ambiguidade; preservar o aviso
de sobreposição e revisar períodos. A prova entre arquivos distintos usa ID bancário.

Reconciliação automática, alteração de conta/origem e exclusão em lote ficam
fora desta primeira entrega: exigem regras próprias de rastreabilidade.

## Como conferir no aplicativo

No menu, abra **Lançamentos** depois de cadastrar uma conta e importar dados
sintéticos. Filtre conta/período/tipo e navegue pelas páginas. Em **Editar**,
revise data, descrição, valor assinado, natureza e categoria; confirme a correção
e confira o Resumo. Para excluir, use a confirmação separada. Cancele primeiro
para verificar que nada muda. A exclusão não pode ser desfeita nesta versão.

Se outra edição ocorrer, recarregue a lista antes de confirmar novamente. Se
a gravação funcionar mas o Resumo falhar, a tela informa o sucesso e pede somente
a atualização dos totais. Os testes cobrem esse caso sem repetir a exclusão.

Provas locais: `make check` com 674 testes/82,53%; ciclo de downgrade/upgrade
no banco descartável e 111 integrações Postgres/RLS aprovados. A suíte web inicial
aprovou 140 casos e falhou em dois por seletor do novo campo Natureza. Após usar
o papel acessível do campo e ajustar o espaçamento, seis casos focados passaram.
Capturas sintéticas de desktop e 320px em `test-results/lancamentos/`.
Build estático, checagem de tipos e PWA offline também passaram após o ajuste.
