# Base pública autoral

`base.jsonl` contém 200 documentos curtos independentes, identificados por slug.
Os parágrafos são autorais: conceitos introdutórios e situações de organização
financeira, sem recomendação de ativos, taxas atuais ou dados de usuários.
Os textos sobre o Tato descrevem regras de interpretação; não anunciam funções
futuras como se já estivessem disponíveis. Revisão inicial: 27/09/2026.

Não alongamos documentos para atingir 400 tokens: o chunker preserva uma seção
curta inteira. Seus limites/overlap são exercitados também com textos longos nos
testes. Um corpus de parágrafos curtos não mede sozinho qualidade em contratos.

Referências primárias consultadas para conferir os conceitos correspondentes:

- CET: [Banco Central](https://www.bcb.gov.br/pre/pef/port/caderno_cidadania_financeira.pdf).
- Liquidez: [Portal do Investidor/CVM](https://www.gov.br/investidor/pt-br/investir/antes-de-investir/entenda-as-caracteristicas-dos-investimentos/liquidez).
- Riscos: [Portal do Investidor/CVM](https://www.gov.br/investidor/pt-br/investir/antes-de-investir/entenda-as-caracteristicas-dos-investimentos/risco-e-a-relacao-risco-x-retorno).
- Perfil: [Portal do Investidor/CVM](https://www.gov.br/investidor/pt-br/investir/antes-de-investir/respeite-o-seu-perfil-de-investidor).
- Títulos bancários: [Portal do Investidor/CVM](https://www.gov.br/investidor/pt-br/investir/tipos-de-investimentos/titulos-bancarios/titulos-bancarios).
- IPCA: [IBGE](https://www.ibge.gov.br/explica/inflacao.php).
- IOF: [Receita Federal](https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/tributos/IOF).

Essas fontes não endossam o corpus nem substituem revisão editorial independente.
Os documentos não são um manual tributário ou jurídico. Atualizações devem manter
slugs estáveis, revisar perguntas afetadas e medir recuperação antes/depois.
