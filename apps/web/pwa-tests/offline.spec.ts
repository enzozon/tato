import { test, expect } from '@playwright/test';

test('manifesto válido e offline sem dados financeiros em cache',async({page,context})=>{
  await page.goto('/');
  const manifest=await (await page.request.get('/manifest.webmanifest')).json();
  expect(manifest.display).toBe('standalone');
  expect(manifest.icons.map((i:{sizes:string})=>i.sizes)).toEqual(['192x192','512x512']);
  for(const size of [180,192,512])expect((await page.request.get(`/icons/${size}.png`)).ok()).toBe(true);
  await page.evaluate(async()=>{await navigator.serviceWorker.ready;});
  await page.waitForFunction(()=>!!navigator.serviceWorker.controller);
  const cached=await page.evaluate(async()=>{
    const keys=await caches.keys();return (await Promise.all(keys.map(async key=>(await(await caches.open(key)).keys()).map(r=>new URL(r.url).pathname)))).flat();
  });
  expect(cached.sort()).toEqual(['/icons/192.png','/icons/512.png','/offline.html']);
  await context.setOffline(true);
  await page.goto('/app/');
  await expect(page.getByRole('heading',{name:'Vamos retomar quando a conexão voltar.'})).toBeVisible();
  await expect(page.getByText('Seus dados financeiros não ficam salvos neste dispositivo para uso offline.')).toBeVisible();
});
