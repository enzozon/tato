import { test, expect, type Page } from '@playwright/test';

const measurement={period_start:'2026-10-01T00:00:00Z',period_end:'2026-11-01T00:00:00Z',
  attempts:2,input_tokens:null,output_tokens:0,unknown_input_attempts:2,unknown_output_attempts:1,elapsed_ms:143};

async function openSettings(page:Page) {
  let issued=0;
  const user={id:'00000000-0000-4000-8000-000000000001',email:'teste@example.test',aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:'2026-10-04T00:00:00Z'};
  await page.route('https://auth.example.test/**',route=>route.fulfill({json:{access_token:`synthetic-token-${++issued}`,
    refresh_token:'synthetic-refresh',token_type:'bearer',expires_in:120,user}}));
  await page.route('http://127.0.0.1:8000/**',route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET'};
    if(request.method()==='OPTIONS')return route.fulfill({headers,status:200});
    if(path==='/me')return route.fulfill({headers,json:{onboarding_completed:true,plan:{name:'free',agents:1,messages_per_month:200}}});
    if(path==='/dashboard')return route.fulfill({headers,json:{as_of:'2026-10-04',balance_cents:'0',expense_cents:'0',categories:[],accounts:[]}});
    if(path==='/me/usage')return route.fulfill({headers,json:{period_end:measurement.period_end,
      messages:{used:1,limit:200,remaining:199},import_sources:{used:0,limit:1,remaining:1},agents:{used:0,limit:1,remaining:1}}});
    return route.fallback();
  });
  await page.goto('/app/');
  await page.getByLabel('E-mail',{exact:true}).fill(user.email);
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('button',{name:'Conta',exact:true}).click();
}

test('medições distinguem tokens desconhecidos de zero conhecido',async({page})=>{
  await page.route('**/me/llm-usage',route=>route.fulfill({json:measurement}));
  await openSettings(page);
  const panel=page.getByRole('region',{name:'Medições da IA'});
  await expect(panel.locator('div').filter({has:page.getByText('Tokens de entrada conhecidos',{exact:true})}).locator('dd')).toHaveText('não informado');
  await expect(panel.locator('div').filter({has:page.getByText('Tokens de saída conhecidos',{exact:true})}).locator('dd')).toHaveText('0');
  await expect(panel).toContainText('2 de entrada e 1 de saída');
  await expect(panel).toContainText('143 ms');
  await expect(panel).toContainText('01/10/2026 até 01/11/2026 (fim exclusivo, UTC)');
  await expect(panel).toContainText('Não representam saldo nem quota dos provedores');
});

test('falha nas medições mantém consumo e exclusão disponíveis',async({page})=>{
  await page.route('**/me/llm-usage',route=>route.fulfill({status:503,json:{detail:'private-error'}}));
  await openSettings(page);
  await expect(page.getByRole('region',{name:'Medições da IA'}).getByRole('status')).toHaveText('Não foi possível consultar as medições da IA agora.');
  await expect(page.getByRole('region',{name:'Consumo do plano'})).toContainText('1 usados · 199 restantes de 200');
  await expect(page.getByText('Excluir minha conta',{exact:true})).toBeVisible();
  await expect(page.getByText('private-error',{exact:true})).toHaveCount(0);
});

test('resposta antiga das medições não sobrescreve a sessão renovada',async({page})=>{
  await page.clock.install();
  let release!:()=>void,completed!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const completion=new Promise<void>(resolve=>{completed=resolve;});
  await page.route('**/me/llm-usage',async route=>{
    if(route.request().headers().authorization==='Bearer synthetic-token-1'){
      await gate;await route.fulfill({json:{...measurement,attempts:99}});completed();return;
    }
    return route.fulfill({json:measurement});
  });
  await openSettings(page);
  const panel=page.getByRole('region',{name:'Medições da IA'});
  await expect(panel.getByRole('status')).toHaveText('Consultando medições…');
  const renewed=page.waitForRequest(r=>r.url().endsWith('/me/llm-usage')&&r.headers().authorization==='Bearer synthetic-token-2');
  await page.clock.runFor(31000);await renewed;
  const attempts=panel.locator('div').filter({has:page.getByText('Tentativas neste mês',{exact:true})}).locator('dd');
  await expect(attempts).toHaveText('2');
  release();await completion;await page.clock.runFor(100);
  await expect(attempts).toHaveText('2');
});
