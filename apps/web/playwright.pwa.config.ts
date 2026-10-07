import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./pwa-tests',use:{baseURL:'http://127.0.0.1:4173'},
  webServer:{command:'python -m http.server 4173 --bind 127.0.0.1 --directory out',url:'http://127.0.0.1:4173',reuseExistingServer:false},
});
