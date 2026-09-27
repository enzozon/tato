# ADR 0009 — Recuperação pública e privada

Data: 27/09/2026. Schema aprovado por Enzo antes da migration 0005.

## Contexto

Precisamos explicar conceitos e recuperar contexto sem usar similaridade para
calcular dinheiro nem persistir documentos pessoais em texto claro no índice.
FTS público persistente é útil; FTS privado em claro conflita com a cifra existente.

## Decisão

Base autoral em `knowledge_chunks`, com vetor de 384 dimensões e GIN português;
runtime somente SELECT. Conteúdo privado continua cifrado em `chunks` com RLS.
Busca privada filtra dono/modelo antes de decifrar, calcular distância e FTS
transitório. Teto de 1000 chunks por usuário, com recusa explícita além disso.
CTE materializada delimita candidatos vetoriais privados; não usamos ANN global.

E5-small multilíngue quantizado local via fastembed, tokenizer real e identidade
pelo hash dos pesos. Seção/frase com alvo 480 tokens e overlap de até 15%; sem
truncamento silencioso no encoder. RRF funde cosine e FTS, que não é BM25.

MiniLM-L6 Apache-2.0 disponível para reranking, mas desativado por padrão: no
benchmark inicial reduziu hit@5 de 0,975 para 0,925. Não escolhemos automaticamente
um modelo com licença não comercial para um SaaS. Troca exige novo experimento.

## Consequências

Isolamento e cifra custam CPU/memória na busca privada. Texto transita pelo
Postgres para FTS sob parâmetros, sem persistência textual; logs de statements,
duração e parâmetros em erro devem estar desativados. Não equivale a cifra em RAM.
Escala maior exige revisar esse teto e medir alternativas, sem relaxar isolamento.

Indexação revalida exclusão e digest após inferência; IDs estáveis não preservam
versões antigas. Atualização de fonte exige invalidar respostas dependentes.
O corpus e as perguntas são autorais, portanto têm viés de construção conjunta.
Faithfulness por LLM é avaliação separada e permanece pendente sem chaves.
