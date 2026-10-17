import { defineConfig } from '@playwright/test';
import config from './playwright.config';

export default defineConfig({...config, testDir:'./gallery', outputDir:'../../test-results/gallery-traces',
  timeout:90000, retries:0, reporter:'list',
  use:{...config.use,actionTimeout:10000},
  webServer:Array.isArray(config.webServer)?config.webServer.map(server=>({...server,timeout:180000})):
    config.webServer&&{...config.webServer,timeout:180000},
});
