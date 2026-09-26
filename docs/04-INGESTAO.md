# Ingestão — etapa 4 em andamento

Plano: parsers CSV/OFX, extração PDF, regras determinísticas, persistência atômica,
rotas autenticadas, testes e limites. Alterações de schema aguardam revisão;
nenhuma migration nova foi aplicada nesta etapa.

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
