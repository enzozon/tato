# Interface web — etapa 9

Destino do Next.js 16 com App Router, Tailwind e shadcn/ui.
Landing e aplicação serão exportadas como arquivos estáticos para Cloudflare Pages;
auth, dados e chat serão acessados pela API. Não haverá Server Actions nem SSR.

Implementados landing, login, onboarding, resumo, contas, importação com prévia,
chat, agentes e exclusão. Comandos npm são executados na raiz do monorepo:

- `npm ci`: dependências reproduzíveis.
- `npm run dev --workspace=tato-web`: interface na porta 3000.
- `npm run build`: exportação estática e service worker.
- `npm test --workspace=tato-web`: fluxos sintéticos desktop/mobile.
- `npm exec --workspace=tato-web -- playwright test --config=playwright.pwa.config.ts`:
  verifica o build real offline, após npm run build.

Configuração pública em `.env.local`, gerada por `make web-config`; nunca inserir
chave administrativa. Sessão fica em memória. Cache offline contém só orientação
e ícones; instalação física em Android/iOS permanece pendente de dispositivo/HTTPS.
