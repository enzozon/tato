import { test, expect, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const owner='00000000-0000-4000-8000-000000000003';
const body='{ "version":1,"transactions":[{"amount_cents":"9223372036854775807","description":"Café sintético"}] }\n';
async function settings(page:Page){
  let issued=0;
  const user={id:owner,email:'teste@example.test',aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:'2026-10-04T00:00:00Z'};
  await page.route('https://auth.example.test/**',route=>route.fulfill({json:{access_token:`synthetic-token-${++issued}`,
    refresh_token:'synthetic-refresh',token_type:'bearer',expires_in:120,user}}));
  await page.route('http://127.0.0.1:8000/**',route=>{
    const path=new URL(route.request().url()).pathname;
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,POST'};
    if(route.request().method()==='OPTIONS')return route.fulfill({headers,status:200});
    if(path==='/me')return route.fulfill({headers,json:{onboarding_completed:true,plan:{name:'free',agents:1,messages_per_month:200}}});
    if(path==='/dashboard')return route.fulfill({headers,json:{as_of:'2026-10-04',balance_cents:'0',expense_cents:'0',categories:[],accounts:[]}});
    if(path==='/me/export')return route.fallback();
    return route.fulfill({headers,status:503,json:{}});
  });
  await page.goto('/app/');
  await page.getByLabel('E-mail',{exact:true}).fill(user.email);
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('button',{name:'Conta',exact:true}).click();
}

test('download preserva bytes e int64 sem depender da cobrança',async({page})=>{
  await page.route('**/me/export',route=>{
    expect(route.request().headers().authorization).toBe('Bearer synthetic-token-1');
    return route.fulfill({contentType:'application/json; charset=utf-8',body});
  });
  await settings(page);
  await page.evaluate(()=>{
    const revoked:string[]=[];(window as unknown as {revoked:string[]}).revoked=revoked;
    const revoke=URL.revokeObjectURL.bind(URL);URL.revokeObjectURL=url=>{revoked.push(url);revoke(url);};
  });
  await expect(page.getByRole('region',{name:'Exportar dados'})).toContainText('dados pessoais e financeiros legíveis');
  const pending=page.waitForEvent('download');
  await page.getByRole('button',{name:'Baixar meus dados'}).click();
  const download=await pending;
  expect(download.suggestedFilename()).toBe('tato-dados.json');
  expect(await readFile((await download.path())!)).toEqual(Buffer.from(body));
  await expect.poll(()=>page.evaluate(()=>(window as unknown as {revoked:string[]}).revoked.length)).toBe(1);
});

test('cancelar libera nova tentativa e descarta a resposta antiga',async({page})=>{
  let release!:()=>void,finished!:()=>void,calls=0;
  const gate=new Promise<void>(resolve=>{release=resolve;}),done=new Promise<void>(resolve=>{finished=resolve;});
  await page.route('**/me/export',async route=>{
    if(++calls===1){await gate;try{await route.fulfill({contentType:'application/json',body});}catch{}finally{finished();}}
    else await route.fulfill({contentType:'application/json',body});
  });
  await settings(page);
  let downloads=0;page.on('download',()=>downloads++);
  const started=page.waitForRequest('**/me/export');
  await page.getByRole('button',{name:'Baixar meus dados'}).click();await started;
  await expect(page.getByRole('button',{name:'Baixar meus dados'})).toBeDisabled();
  await page.getByRole('button',{name:'Cancelar exportação'}).click();
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:'Baixar meus dados'}).click();await download;
  release();await done;
  await expect(page.getByRole('button',{name:'Baixar meus dados'})).toBeEnabled();
  expect(downloads).toBe(1);
});

for(const leave of ['renovação','saída','troca de aba'])test(`resposta tardia não baixa após ${leave}`,async({page})=>{
  await page.clock.install();
  let release!:()=>void,finished!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;}),done=new Promise<void>(resolve=>{finished=resolve;});
  await page.route('**/me/export',async route=>{await gate;try{await route.fulfill({contentType:'application/json',body});}catch{}finally{finished();}});
  await settings(page);
  let downloads=0;page.on('download',()=>downloads++);
  const started=page.waitForRequest('**/me/export');
  await page.getByRole('button',{name:'Baixar meus dados'}).click();await started;
  if(leave==='renovação'){
    const refreshed=page.waitForRequest(r=>r.url().endsWith('/me')&&r.headers().authorization==='Bearer synthetic-token-2');
    await page.clock.runFor(31000);await refreshed;
  }else await page.getByRole('button',{name:leave==='saída'?'Sair':'Resumo',exact:true}).click();
  release();await done;await page.clock.runFor(100);
  expect(downloads).toBe(0);
});

for(const status of [401,409,429,503,200])test(`falha ${status} ou MIME incorreto não baixa nem mostra corpo remoto`,async({page})=>{
  await page.route('**/me/export',route=>route.fulfill({status,contentType:'text/html',body:'sensitive-provider-canary'}));
  await settings(page);
  let downloads=0;page.on('download',()=>downloads++);
  await page.getByRole('button',{name:'Baixar meus dados'}).click();
  await expect(page.getByRole('region',{name:'Exportar dados'}).getByRole('alert')).toHaveText('Não foi possível exportar seus dados. Aguarde e tente novamente.');
  await expect(page.getByRole('button',{name:'Baixar meus dados'})).toBeEnabled();
  await expect(page.locator('body')).not.toContainText('sensitive-provider-canary');
  expect(downloads).toBe(0);
});
