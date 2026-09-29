# Experimento de serviços gratuitos

## Como ler

Limite publicado é uma regra do fornecedor; medição é uma observação do nosso uso.
Projeção depende de taxa medida. Sem taxa, dias até esgotar são **não calculáveis**.
Não interpretar campos sem medição como consumo zero comprovado no painel.

Referências consultadas no alinhamento de 19/09/2026; revalidar antes de provisionar.
Nenhum serviço financeiro/LLM foi provisionado nesta etapa. Não habilitar plano
pago, recarga automática nem modelo pago como fallback.

| Serviço | Limite/condição publicada | Consumo do projeto | Ao atingir o limite |
| --- | --- | --- | --- |
| [Neon](https://neon.com/docs/introduction/plans) | Referência de 0,5 GB por projeto; conferir compute/egress no painel | Não provisionado | Bloquear novas ingestões; exportar/limpar conforme política |
| [Upstash](https://upstash.com/pricing/redis) | 256 MB e 500 mil comandos/mês | Não provisionado | Cache em memória; quotas não podem perder consistência |
| [Groq](https://console.groq.com/docs/rate-limits) | Limites por modelo e janela; não há taxa universal | Não provisionado | Provider elegível seguinte ou resposta determinística |
| [Gemini](https://ai.google.dev/gemini-api/terms) | Gratuito não recebe informação pessoal/confidencial | Não provisionado | Dados públicos/sintéticos apenas; sem fallback pessoal |
| [OpenRouter](https://openrouter.ai/docs/api_reference/limits) | Modelos gratuitos têm quotas por conta/modelo | Não provisionado | Parar chamadas quando não houver opção permitida |
| [Render](https://render.com/docs/free) | API Free suspende após 15 min sem tráfego; recursos limitados | Não provisionado | Medir cold start/RAM antes de aceitar como destino |
| [HF Spaces](https://huggingface.co/docs/hub/spaces-overview) | Documentação consultada exige plano pago para criar Docker Space | Não contratado | Excluído como garantia de custo zero |
| [Cloudflare Pages](https://developers.cloudflare.com/pages/platform/limits/) | Candidato para exportação estática; conferir limites antes do deploy | Não provisionado | Suspender builds excedentes; reavaliar hospedagem |
| [Vercel Hobby](https://vercel.com/docs/plans/hobby) | Restrito a uso pessoal não comercial | Não provisionado | Não usar para operação comercial gratuita |
| [Supabase Auth](https://supabase.com/docs/guides/auth/auth-smtp) | SMTP padrão limitado a destinatários da equipe | Não provisionado | Google OAuth; SMTP próprio com domínio verificado |
| [Resend](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain) | Domínio de teste não envia livremente para terceiros | Não provisionado | Avisos in-app; domínio próprio para envio público |
| Sentry, PostHog, Logfire | Conferir planos e limites na etapa 10 | Não provisionados | Amostragem/limite de eventos e logs locais sem dados pessoais |
| GitHub Actions | Repositório público, runner Ubuntu padrão; conferir política antes de alterar recursos | Tempos abaixo | Cache, reduzir builds redundantes, nunca pular checks obrigatórios |

## Medição inicial: 19/09/2026

Fonte: timestamps de jobs da API do GitHub, não estimativa do tempo de CPU.

| Execução | Job | Início UTC | Fim UTC | Duração observada |
| --- | --- | --- | --- | --- |
| [35465820555](https://github.com/enzozon/tato/actions/runs/35465820555) | Qualidade Python (bootstrap) | 19:55:32 | 19:55:42 | 10 s |
| [35466039585](https://github.com/enzozon/tato/actions/runs/35466039585) | Qualidade Python | 20:00:15 | 20:00:26 | 11 s |
| mesma execução | Infraestrutura local | 20:00:15 | 20:00:39 | 24 s |

Essas amostras não são consumo mensal, minutos faturados, benchmark de produção ou
prova de capacidade para usuários. Banco hospedado, cold start e tokens ainda não
foram medidos. Custo contratado por esta execução: R$ 0,00; nenhum plano pago ativado.

Na etapa 11, `quota-watch` registrará medição, data e origem, usando API quando
disponível ou contador próprio/registro manual explicitamente identificado.
Não fingiremos coleta automática de um provedor que não expõe esses dados.

## Atualização local — 27/09/2026

Camada LLM implementada sem chamadas remotas: chaves Groq/Gemini/OpenRouter ausentes.
Não há taxa real de tokens nem estimativa confiável de dias até esgotar. Adapters
reportam contagens recebidas; falhas sem contagem retornam uso desconhecido.
`make llm-smoke` permitirá medir com dados sintéticos quando contas gratuitas
estiverem conferidas. Modelo pago OpenRouter é recusado antes de fazer HTTP.

O cache foi exercitado no Redis local: TTL de uma hora, até 64 respostas por usuário,
remoção na exclusão e fallback sem cache quando indisponível. Isso comprova lógica,
não capacidade ou latência do Upstash hospedado. Sem nova contratação.

Amostra CI da etapa 4: [execução 36295671630](https://github.com/enzozon/tato/actions/runs/36295671630),
qualidade Python 33 s e infraestrutura 32 s (início UTC 04:54:41 de 27/09/2026).
São durações observadas dos jobs, não minutos mensais faturados.

## Medição da etapa 2: 23/09/2026

[Execução 35926485225](https://github.com/enzozon/tato/actions/runs/35926485225),
SHA `c705b14`: qualidade Python de 22:06:58 a 22:07:19 UTC (21 s);
infraestrutura de 22:06:56 a 22:07:22 UTC (26 s). O job de infraestrutura aplicou
e reverteu migrations e executou nove testes de integração em 0,35 s.
São tempos de uma execução, não extrapolação de capacidade nem faturamento mensal.
Docker Desktop/WSL foram instalados para desenvolvimento local; nenhum plano pago,
provedor LLM ou banco hospedado foi ativado. Custo contratado nesta etapa: R$ 0,00.

## Medição da etapa 3: 26/09/2026

[CI do PR 36275071998](https://github.com/enzozon/tato/actions/runs/36275071998),
SHA `9a0f50f`: qualidade Python 20 s, infraestrutura 30 s. Os dois jobs passaram,
incluindo quatorze testes de integração PostgreSQL. Tempos de execução não são
minutos faturados nem medida de capacidade do SaaS. Supabase/Upstash continuam
sem provisionamento; seus adapters HTTP foram testados com respostas simuladas.
Nenhum serviço pago foi ativado nesta etapa; custo contratado R$ 0,00.

## Medição local da etapa 6: 27/09/2026

`make rag-measure`, Windows 10 build 19045, CPU, threads=2, modelos já baixados:

| Medida | Resultado observado |
| --- | --- |
| Carregar E5-small quantizado + primeira consulta | 2,092 s |
| Pico de memória do processo com encoder | 770,07 MiB |
| Carregar reranker + primeiro lote de 20 | 0,682 s |
| Pico com ambos os modelos | 865,45 MiB |
| Consulta aquecida, média de 5 | 0,005 s |
| Reranking de 20 aquecido, média de 5 | 0,279 s |

Pico de working set inclui Python, bibliotecas, tokenizer, buffers e pesos; não
é apenas tamanho do ONNX. Um processo limitado a 512 MiB não foi validado por
esse ensaio. Compatibilidade com hospedagem e concorrência precisa de medição
no ambiente escolhido antes do deploy; não extrapolar usuários suportados.

Downloads públicos iniciais e inferência real foram executados sem API LLM.
O primeiro ensaio do encoder levou cerca de 12 s com download; o do reranker,
8,25 s. Esses tempos não são cold starts de um serviço hospedado.
Corpus de 200 textos indexado em 6,772 s; 40 buscas SQL em 0,367 s; 40 rerankings
incluindo carga em 14,098 s. Detalhes de qualidade em `04-RAG.md`.
Judge remoto indisponível: três chaves LLM ausentes; consumo remoto não medido.
Custo contratado nesta etapa: R$ 0,00. Não houve deploy nem contratação.

## Groq real — retomada em 28/09/2026

Enzo configurou a chave local e confirmou o uso gratuito. O smoke sintético
consumiu 287 tokens de entrada e 120 de saída, com 483 ms medidos na chamada.
A primeira sequência de RAG encontrou HTTP 429: limite retornado de 8000 tokens
por minuto para `openai/gpt-oss-20b` nessa conta. É observação do ensaio, não
promessa universal de quota. Nenhum upgrade ou faturamento foi habilitado.

Com intervalo de 30 s entre perguntas, concluímos 40 casos (80 gerações lógicas):
84.397 tokens de entrada e 41.122 de saída nos casos completos. Controle negativo
separado: 497 de entrada e 200 de saída. Diagnósticos e chamadas interrompidas
também podem consumir quota; esses totais não representam o consumo integral da
conta. Não houve medição de saldo diário de quota ou confirmação de fatura.

Aprendizado operacional: respeitar tokens/minuto exige espaçamento mesmo quando
requisições/dia parecem abundantes. Checkpoint evita repetir casos concluídos;
falhas de quota não ativam modelo pago nem tornam a avaliação aprovada.
