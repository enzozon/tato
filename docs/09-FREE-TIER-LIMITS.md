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

## Medição da etapa 2: 23/09/2026

[Execução 35926485225](https://github.com/enzozon/tato/actions/runs/35926485225),
SHA `c705b14`: qualidade Python de 22:06:58 a 22:07:19 UTC (21 s);
infraestrutura de 22:06:56 a 22:07:22 UTC (26 s). O job de infraestrutura aplicou
e reverteu migrations e executou nove testes de integração em 0,35 s.
São tempos de uma execução, não extrapolação de capacidade nem faturamento mensal.
Docker Desktop/WSL foram instalados para desenvolvimento local; nenhum plano pago,
provedor LLM ou banco hospedado foi ativado. Custo contratado nesta etapa: R$ 0,00.
