import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir:'./tests', fullyParallel:false, workers:1,
  use:{baseURL:'http://127.0.0.1:3000', trace:'retain-on-failure'},
  projects:[{name:'desktop',use:{...devices['Desktop Chrome']}},
    {name:'mobile',use:{...devices['iPhone 13'],defaultBrowserType:'chromium'}}],
  webServer:{command:'npm run dev',url:'http://127.0.0.1:3000',reuseExistingServer:false,
    env:{NEXT_TELEMETRY_DISABLED:'1',NEXT_PUBLIC_SUPABASE_URL:'https://auth.example.test',
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:'synthetic-public-key',NEXT_PUBLIC_GOOGLE_AUTH_ENABLED:'true',NEXT_PUBLIC_API_URL:'http://127.0.0.1:8000'}},
});
