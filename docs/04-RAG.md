# RAG — etapa 6

Status: início; proposta de schema abaixo aguarda aprovação antes de migration.

## Plano da etapa

1. Separar conhecimento público de conteúdo privado e revisar o schema.
2. Validar fastembed multilíngue, tokenizer real, modelo de 384 dimensões e RAM.
3. Implementar chunking por seção/frase, alvo 400–480 tokens e overlap de 15%.
4. Indexar documentos com origem, modelo e conteúdo rastreáveis.
5. Recuperar por cosine e FTS português, combinar com RRF e reranquear top-20 → top-5.
6. Provar isolamento no Postgres, inclusive antes de ranking/reranking.
7. Construir base autoral de 200 textos e dataset dourado de 40 perguntas.
8. Medir hit@5/MRR, comparação com reranking e faithfulness; integrar checks ao CI.

Não usar recuperação vetorial para somas, saldos ou valores financeiros exatos.
Modelo de embedding é um mapa: textos parecidos ficam próximos, mas proximidade
não prova igualdade nem autoriza calcular dinheiro. As 384 coordenadas são o
formato do modelo escolhido, não 384 categorias financeiras interpretáveis.

## Checkpoint de schema proposto

Criar `knowledge_chunks` exclusivamente para material público autoral do repositório:

| Coluna | Tipo e regra |
| --- | --- |
| id | UUID, chave primária estável por slug/posição |
| slug | varchar(160), identificador do documento |
| position | inteiro >= 0; único com slug |
| section | varchar(200), título usado na citação |
| content | text público, não cifrado |
| content_digest | varchar(64), SHA-256 do texto |
| embedding | vector(384), obrigatório |
| embedding_model | varchar(120), identificador/versionamento do encoder |
| search_vector | tsvector gerado com configuração portuguese; índice GIN |

O papel runtime terá somente SELECT nessa tabela. Atualização da base pública é
comando administrativo explícito; uploads não podem escrever nela. Não adicionar
ANN inicialmente: cosine exato evita candidatos de outro usuário antes do filtro.

Adicionar a `chunks` somente `embedding_model`, varchar(120), opcional. Chunks
antigos com embedding sem identificação não entram na nova busca até reindexar.
Manter ciphertext, vínculo com documento, usuário e RLS existentes. Nenhuma nova
coluna privada de texto/tsvector em claro será persistida.

Trade-off: um índice FTS privado persistente revelaria lexemas apesar da cifragem
do texto. A proposta é FTS privado transitório sobre o conjunto autorizado e
limitado, após decifrar; isso exige controlar logs de parâmetros e medir o custo.
Não apresentar essa busca como indexada em disco nem varrer usuários alheios.
A busca pública usa seu índice GIN; a privada preserva a fronteira de usuário.

Este checkpoint não autoriza migration por silêncio. Chunking, fusão e métricas
podem avançar enquanto a decisão de schema está pendente.

## Chunking iniciado

`chunk_markdown` mantém seções e usa frases como unidades. Frases maiores que a
janela são repartidas por palavras, sem cortar caracteres. Cada chunk tem no
máximo 480 tokens contados pelo tokenizer recebido, sem truncamento/padding.
Os 32 tokens restantes da janela E5 de 512 ficam disponíveis para prefixo e tokens
especiais; o encoder ainda deverá conferir o limite final.

Overlap é uma cauda de palavras de até 15% do alvo, dentro da mesma seção. Pode
ser menor quando uma frase inteira precisa caber; não duplicamos metade de um
documento só para atingir uma porcentagem exata. Últimos chunks podem ser curtos.
Textos vazios não geram chunks, palavras indivisíveis grandes demais são recusadas.

`fastembed` substitui código próprio de inferência ONNX; `tokenizers` fornece a
contagem real usada no chunking. Ambos estão fixados no lockfile. A versão 0.8.1
do fastembed não lista E5-small diretamente; será necessário registrar o modelo
ONNX oficial, sem usar código remoto de Python. Reranker leve em inglês precisa
ser medido em português; não assumir ganho. Jina v2 multilíngue tem licença não
comercial e não será escolhido automaticamente para o SaaS.

Referências: [modelo E5-small e licença MIT](https://huggingface.co/intfloat/multilingual-e5-small),
[modelos fastembed](https://qdrant.github.io/fastembed/examples/Supported_Models/).
