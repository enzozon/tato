# 0005 — Custo zero limita capacidade, não só preço

Status: aceito por Enzo em 19/09/2026; provedores serão revalidados antes do uso.

Contexto: fallback e planos comerciais não podem prometer recursos infinitos.
Opções: contratar capacidade, degradar dentro das quotas ou encerrar chamadas.
Escolha: Groq → Gemini → OpenRouter somente entre destinos elegíveis para os dados.
Gemini gratuito não recebe dados pessoais; inicialmente tudo será sintético.
Consequência: se não houver destino permitido, responder deterministicamente ou
informar indisponibilidade. Ollama local é alternativa, não capacidade grátis remota.

Render é candidato à API após prova de RAM; HF Docker não é garantia gratuita.
Upstash cobre cache/rate limit; fallback em memória não pode reiniciar quotas de plano.
Actions cron precisa de idempotência; não garante horário exato nem execução contínua.
Stripe teste e AbacatePay sandbox não cobram usuários; Pro terá limites explícitos.
Resend depende de domínio para público; avisos in-app continuam disponíveis.
Sentry/PostHog/Logfire entram sem payload financeiro; Portkey é opcional.
Limites, medições e planos B ficam em `../09-FREE-TIER-LIMITS.md`.
