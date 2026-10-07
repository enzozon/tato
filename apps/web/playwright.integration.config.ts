import { defineConfig } from '@playwright/test';
const live=process.env.TATO_LIVE_WEB==='true';
export default defineConfig({testDir:'./integration-tests',workers:1,timeout:live?90000:30000,use:{baseURL:'http://127.0.0.1:3001'},
  webServer:[
    {command:live?'uv run --project ../.. uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port 8009 --no-access-log':
      'uv run --project ../.. python ../../scripts/web_integration_server.py',url:'http://127.0.0.1:8009/health',reuseExistingServer:false,
      env:{LLM_ENABLED:'false',AGENT_EMAIL_ENABLED:'false',LLM_CACHE:'off',WEB_ORIGINS:'http://127.0.0.1:3001',RATE_LIMIT_BACKEND:live?'upstash':'memory'}},
    {command:'npm run dev -- --port 3001',url:'http://127.0.0.1:3001',reuseExistingServer:false,
      env:{NEXT_TELEMETRY_DISABLED:'1',NEXT_PUBLIC_SUPABASE_URL:live?process.env.SUPABASE_URL!:'https://auth.example.test',
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:live?process.env.SUPABASE_PUBLISHABLE_KEY!:'synthetic-public-key',NEXT_PUBLIC_API_URL:'http://127.0.0.1:8009'}},
  ],
});
