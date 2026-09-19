# 0003 — Interface estática e identidade compartilhada

Status: aceito por Enzo em 19/09/2026; implementação visual na etapa 9.

Contexto: web e celular precisam compartilhar código e operar sem assinatura paga.
Opções: app nativo, Next.js com servidor, Next.js exportado como estático.
Escolha: Next.js 16, Tailwind, shadcn/ui e PWA; Cloudflare Pages como candidato.
Consequência: sem SSR/Server Actions; API faz auth/dados/chat. Vercel Hobby não
será tratada como hospedagem comercial gratuita. Telegram reutilizará o chat.

Nome, tagline, estados, arte e persona pertencem a `packages/mascot/`.
Tato, o tatu-bola, foi confirmado; arte SVG será autoral em código.
Trocar identidade básica altera um arquivo; trocar a arte inteira altera só a pasta.
