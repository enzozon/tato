import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./integration-tests',workers:1,use:{baseURL:'http://127.0.0.1:3001'},
  webServer:[
    {command:'uv run --project ../.. python ../../scripts/web_integration_server.py',url:'http://127.0.0.1:8009/health',reuseExistingServer:false},
    {command:'npm run dev -- --port 3001',url:'http://127.0.0.1:3001',reuseExistingServer:false,
      env:{NEXT_TELEMETRY_DISABLED:'1',NEXT_PUBLIC_SUPABASE_URL:'https://auth.example.test',
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:'synthetic-public-key',NEXT_PUBLIC_API_URL:'http://127.0.0.1:8009'}},
  ],
});
