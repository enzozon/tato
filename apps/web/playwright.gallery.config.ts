import { defineConfig } from '@playwright/test';
import config from './playwright.config';

export default defineConfig({...config, testDir:'./gallery', outputDir:'../../test-results/gallery-traces',
  projects:[{name:'desktop',use:{viewport:{width:1440,height:1000}}},
    {name:'mobile',use:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}},
    {name:'narrow',use:{viewport:{width:320,height:844},isMobile:true,hasTouch:true}}],
  timeout:90000, retries:0, reporter:'list',
  use:{...config.use,actionTimeout:10000},
  webServer:Array.isArray(config.webServer)?config.webServer.map(server=>({...server,timeout:180000})):
    config.webServer&&{...config.webServer,timeout:180000},
});
