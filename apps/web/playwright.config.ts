import { defineConfig, devices } from '@playwright/test';

const port=Number(process.env.PLAYWRIGHT_PORT||3000);
if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('PLAYWRIGHT_PORT inválida');
const baseURL=`http://127.0.0.1:${port}`;

export default defineConfig({
  testDir:'./tests', fullyParallel:false, workers:1,
  use:{baseURL, trace:'retain-on-failure'},
  projects:[{name:'desktop',use:{...devices['Desktop Chrome']}},
    {name:'mobile',use:{...devices['iPhone 13'],defaultBrowserType:'chromium'}}],
  webServer:{command:`npm run dev -- --port ${port}`,url:baseURL,reuseExistingServer:false,
    env:{NEXT_TELEMETRY_DISABLED:'1',NEXT_PUBLIC_SUPABASE_URL:'https://auth.example.test',
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:'synthetic-public-key',NEXT_PUBLIC_GOOGLE_AUTH_ENABLED:'true',NEXT_PUBLIC_API_URL:'http://127.0.0.1:8000'}},
});
