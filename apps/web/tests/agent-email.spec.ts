import { test, expect } from '@playwright/test';

test('e-mail exige opt-in explícito e preserva preferência ao renovar ou pausar',async({page})=>{
  const owner='00000000-0000-4000-8000-000000000001';
  const account='00000000-0000-4000-8000-000000000002';
  let issued=0;
  const user={id:owner,email:'teste@example.test',aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:'2026-10-04T00:00:00Z'};
  let agent={id:owner,kind:'runway',account_id:account,goal_id:null,enabled:true,email_enabled:false};
  const changes:{enabled:boolean;email_enabled:boolean}[]=[];
  await page.clock.install();
  await page.route('https://auth.example.test/**',route=>route.fulfill({json:{access_token:`synthetic-token-${++issued}`,
    refresh_token:'synthetic-refresh',token_type:'bearer',expires_in:120,user}}));
  await page.route('http://127.0.0.1:8000/**',route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,PUT'};
    if(request.method()==='OPTIONS')return route.fulfill({headers,status:200});
    if(path==='/me')return route.fulfill({headers,json:{onboarding_completed:true,plan:{name:'free',agents:1,messages_per_month:200}}});
    if(path==='/dashboard')return route.fulfill({headers,json:{as_of:'2026-10-04',balance_cents:'0',expense_cents:'0',categories:[],
      accounts:[{id:account,name:'Conta sintética',kind:'checking',opening_date:'2026-01-01',balance_cents:'0'}]}});
    if(path==='/agents')return route.fulfill({headers,json:[agent]});
    if(path==='/goals'||path==='/insights')return route.fulfill({headers,json:[]});
    if(path==='/agents/runway'){
      const body=request.postDataJSON();
      expect(typeof body.email_enabled).toBe('boolean');
      expect(Object.keys(body).sort()).toEqual(['account_id','email_enabled','enabled','goal_id']);
      changes.push({enabled:body.enabled,email_enabled:body.email_enabled});agent={...agent,...body};
      return route.fulfill({headers,json:agent});
    }
    return route.fulfill({headers,status:503,json:{detail:'indisponível'}});
  });
  await page.goto('/app/');
  await page.getByLabel('E-mail',{exact:true}).fill(user.email);
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('button',{name:'Agentes',exact:true}).click();
  await expect(page.getByText('E-mail: desligado',{exact:true})).toBeVisible();
  await page.getByText('Configurar um agente',{exact:true}).click();
  const checkbox=page.getByRole('checkbox',{name:'Autorizar avisos por e-mail'});
  await expect(checkbox).not.toBeChecked();
  await page.getByRole('button',{name:'Salvar agente'}).click();
  await expect.poll(()=>changes.length).toBe(1);
  expect(changes[0]).toEqual({enabled:true,email_enabled:false});
  await checkbox.check();
  const renewed=page.waitForRequest(r=>r.url().endsWith('/agents')&&r.headers().authorization==='Bearer synthetic-token-2');
  await page.clock.runFor(31000);await renewed;
  await expect(checkbox).toBeChecked();
  await page.getByRole('button',{name:'Salvar agente'}).click();
  await expect(page.getByText('E-mail: autorizado',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Pausar',exact:true}).click();
  await expect(page.getByText('Pausado',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Ativar',exact:true}).click();
  await expect(page.getByText('Ativo',{exact:true})).toBeVisible();
  expect(changes.slice(1)).toEqual([{enabled:true,email_enabled:true},{enabled:false,email_enabled:true},{enabled:true,email_enabled:true}]);
  await checkbox.uncheck();
  await page.getByRole('button',{name:'Salvar agente'}).click();
  await expect(page.getByText('E-mail: desligado',{exact:true})).toBeVisible();
  expect(changes.at(-1)).toEqual({enabled:true,email_enabled:false});
  await expect(page.getByText(/autorizar não garante a entrega/)).toBeVisible();
});
