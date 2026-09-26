# Ingestão — etapa 4 em andamento

Plano: parsers CSV/OFX, extração PDF, regras determinísticas, persistência atômica,
rotas autenticadas, testes e limites. Enzo aprovou `Document.account_id` e
`Transaction.document_id`, opcionais e vinculados ao mesmo usuário, antes da
migration `0004`. Uma fonte do plano equivale a uma conta/cartão importado.
Índices por usuário/origem permitem contar fontes e rastrear arquivos. Nenhuma
policy é relaxada. A exclusão isolada de documento com lançamentos é restringida;
a exclusão total da conta continua removendo o conjunto em cascata.

## CSV e dinheiro

Valores viram centavos usando Decimal, sem float. Separador decimal pertence ao
mapeamento; datas aceitas são ISO ou DD/MM/AAAA. Arquivos têm limite de 2 MiB e
5.000 lançamentos. Erros não reproduzem descrições ou linhas privadas.

Os cabeçalhos `date,title,amount` são tratados como fatura (débito positivo no
arquivo, negativo no ledger); `Data,Valor,Identificador,Descrição` como conta.
Outros cabeçalhos exigem mapeamento explícito. Não afirmamos compatibilidade com
todos os exports atuais de um banco: fixtures desta etapa são sintéticas, não
extratos reais anonimizados fornecidos pelo usuário.

Identificador bancário permite deduplicar reexports. Sem identificador, a origem
é hash do arquivo + linha: reimportar o mesmo arquivo não duplica, e duas compras
iguais em linhas distintas são preservadas. Arquivos diferentes/reescritos sem ID
exigem revisão de sobreposição; igualdade de valor e descrição não prova duplicata.

## OFX

Suporte restrito a um extrato bancário/cartão em BRL, com blocos `STMTTRN` e
`FITID`, tanto folhas SGML sem fechamento quanto XML com fechamento. A origem
usa FITID: reexportar o mesmo lançamento mantém sua identidade. Correções OFX,
moedas diferentes, múltiplas contas e entidades XML são recusadas explicitamente.
A data contábil preserva os oito primeiros dígitos de DTPOSTED, sem converter o
dia para UTC. Os testes são sintéticos e não afirmam certificação OFX completa.

Referência: [OFX Banking 2.3](https://financialdataexchange.org/common/Uploaded%20files/OFX%20files/OFX%20Banking%20Specification%20v2.3.pdf).

## PDF

`pypdf` substitui implementar estruturas/streams PDF; `python-multipart` permite
upload padrão no FastAPI. Extração em subprocesso sem credenciais, timeout de
10 segundos, até 40 páginas e 200 mil caracteres. Streams descomprimidos têm
limites próprios; processo separado não equivale a sandbox de segurança do SO.
PDF digitalizado sem texto e PDF cifrado são recusados; não há OCR nesta etapa.

Conteúdo extraído continua sendo dado não confiável. O teste com instruções
maliciosas comprova extração literal, sem execução ou envio a provedor LLM.
Referência: [segurança pypdf](https://pypdf.readthedocs.io/en/6.6.1/user/security.html).
