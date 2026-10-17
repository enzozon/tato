# Meu Pluggy: experimento pessoal separado

Enzo aprovou este provedor apenas para suas próprias contas. Não habilita Open
Finance para usuários do SaaS. O [guia pessoal oficial](https://docs.pluggy.ai/en/docs/guides/meu-pluggy-personal-use)
permite até cinco conexões e atualização a cada 24 horas, sem uso comercial.
Não ative trial comercial, cobrança ou produtos de pagamentos para este ensaio.

## Preparação manual

1. No Meu Pluggy, conecte suas próprias instituições, conferindo o consentimento
   e o redirecionamento oficial. Não informe senha bancária ao Tato.
2. Acesse o Pluggy Dashboard com a mesma conta. Na aplicação Demo selecione o
   conector **MeuPluggy**, não o conector direto do banco nem o Sandbox.
3. No `.env` local ignorado, configure `MEU_PLUGGY_CLIENT_ID` e
   `MEU_PLUGGY_CLIENT_SECRET` com as credenciais da aplicação no Dashboard.
4. Guarde `MEU_PLUGGY_ITEM_ID` do item espelhado. `GET /v2/items` não está
   disponível para Meu Pluggy. Configure `MEU_PLUGGY_ACCOUNT_ID` com o ID da
   conta/cartão desejado no detalhe do Dashboard. Se não aparecer, consulte
   `GET /accounts?itemId=...` no API Explorer oficial; não compartilhe a resposta.

As quatro variáveis são privadas. Não cole valores na conversa, nos commits ou
em `NEXT_PUBLIC_*`. O comando verifica que a conta pertence ao item antes de
consultar movimentos; não escolhe a primeira conta por ordem de retorno.

## Executar e revisar

```powershell
make meu-pluggy ARGS="--confirm-personal-use --from 2026-10-01 --to 2026-10-15"
```

O comando não cria consentimentos nem sincroniza o ledger. Troca as credenciais
por uma chave temporária e faz apenas leitura de contas e movimentos. Produz
um CSV por conta/período em `test-results/meu-pluggy/`, ignorado pelo Git.
Os arquivos contêm dados financeiros **em claro**: mantenha-os locais, não abra
em planilha e exclua-os após a revisão. O terminal não exibe nomes, IDs,
descrições ou valores; informa apenas tipo/moeda e quantidade de pendentes.

No Tato, use Conversa → Importar, selecione a conta correta e o CSV, revise
período/totais/linhas na prévia e confirme somente se estiverem corretos.
Depois pergunte sobre o período com a mesma conta selecionada. Plano Free
continua limitado a uma fonte; testes de várias contas usam Pro sintético local.

## Limites deliberados

- Somente BRL, até 366 dias, 5.000 movimentos, 20 páginas e 2 MiB de respostas
  acumuladas; o CSV também deve caber em 2 MiB. Falha não gera CSV parcial.
  Tipos aceitos: conta corrente, poupança e cartão; empréstimos são recusados.
- `/v2/transactions` usa cursor, sem seguir URLs retornadas; 401/429/5xx,
  timeout, duplicatas, resposta incompleta e precisão maior que centavos falham.
- Datas com fuso viram `America/Sao_Paulo` usando `tzdata` já instalado no Windows.
  Datas sem horário ou timestamps sem fuso são recusados.
  A consulta amplia um dia no início e dois no fim, pois o corte UTC de `dateTo`
  não está documentado, e filtra pelo dia local solicitado. Isso cobre também
  21h–23h59 do último dia, sem incluir o dia local seguinte no CSV.
- Só `POSTED` é exportado. `PENDING`, inclusive fatura aberta/parcela futura,
  fica fora e tem contagem informada. Não é previsão completa de fatura.
- Em cartão, despesas positivas na API viram valores negativos no CSV; pagamentos
  negativos viram positivos. O tipo DEBIT/CREDIT precisa confirmar esse sinal.
- IDs são derivados de conta + ID do provedor. Correções, exclusões e IDs que
  mudam após reconexão não são reconciliados. CSV/OFX anteriores podem duplicar
  linhas porque usam outro identificador. Não sobreponha fontes/períodos.
- Não misture automaticamente compras do cartão com seu pagamento na conta:
  o importador não reconhece essa relação como transferência e pode duplicar
  despesas. Revise cada fonte separadamente; não há consolidação automática.
- Descrições com fórmula/controle são recusadas, sem alterar silenciosamente o
  dado. Não há chamadas LLM, MCP, escrita no banco nem atualização manual do item.

Contrato: [transações](https://docs.pluggy.ai/en/docs/products/transactions),
[cursor v2](https://docs.pluggy.ai/en/reference/transaction/transactions-list-by-cursor)
e [OAS oficial](https://api.pluggy.ai/oas3.json). Testes locais usam exclusivamente
MockTransport sintético e roundtrip pelo importador real. Cobertura específica
de Banestes/Sicoobcard e conexão/credenciais reais ainda não foram verificadas.
