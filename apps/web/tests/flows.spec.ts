import { test, expect, type Page } from '@playwright/test';

const owner='00000000-0000-4000-8000-000000000001';
const account='00000000-0000-4000-8000-000000000002';
async function signIn(page:Page, expiresIn=3600, onboardingCompleted=true) {
  const user={id:owner,email:'teste@example.test',aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:'2026-10-04T00:00:00Z'};
  let issued=0;
  await page.route('https://auth.example.test/**',route=>{
    const other=route.request().url().includes('grant_type=password')&&route.request().postDataJSON().email==='outro@example.test';
    return route.fulfill({json:{access_token:`synthetic-token-${++issued}`,refresh_token:'synthetic-refresh',token_type:'bearer',expires_in:expiresIn,
      user:other?{...user,id:account,email:'outro@example.test'}:user}});
  });
  await page.route('http://127.0.0.1:8000/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,POST,PUT,DELETE'};
    if(route.request().method()==='OPTIONS')return route.fulfill({headers,status:200});
    if(path==='/me') return route.fulfill({headers,json:{onboarding_completed:onboardingCompleted,plan:{name:'free',agents:1,messages_per_month:200}}});
    if(path==='/dashboard')return route.fulfill({headers,json:{as_of:'2026-10-04',balance_cents:'1152921504606846976',expense_cents:'1234',categories:[],accounts:[{id:account,name:'Conta sintética',kind:'checking',opening_date:'2026-01-01',balance_cents:'10000'}]}});
    if(path==='/chat') return route.fulfill({headers,json:[]});
    return route.fulfill({headers,status:503,json:{detail:'indisponível'}});
  });
  await page.goto('/app/');
  await page.getByLabel('E-mail',{exact:true}).fill('teste@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Uma visão tranquila.'})).toBeVisible();
}

test('landing responsiva e login com valores exatos',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:/seu dinheiro, em uma conversa./i})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await signIn(page);
  await expect(page.getByText('R$ 11.529.215.046.068.469,76',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Que bom te ver.'})).toBeVisible();
  await expect(page.getByText('Conta sintética',{exact:true})).toHaveCount(0);
});

test('renovação e navegação preservam rascunhos, sair limpa o espaço',async({page})=>{
  await page.clock.install();
  await signIn(page,120);
  await page.route('**/import/preview',route=>route.fulfill({json:{count:1,start:'2026-10-01',end:'2026-10-01',credits_cents:0,debits_cents:1234,receipt:'signed',warning:'Prévia preservada.',truncated:false,entries:[]}}));
  await page.getByRole('button',{name:'Conversa',exact:true}).click();
  await page.getByLabel('Sua mensagem').fill('Mensagem ainda em edição');
  await page.getByRole('button',{name:'Importar',exact:true}).click();
  await page.getByLabel('Extrato ou fatura').setInputFiles({name:'synthetic.csv',mimeType:'text/csv',buffer:Buffer.from('data,descricao,valor')});
  await page.getByRole('button',{name:'Revisar prévia'}).click();
  await expect(page.getByText('Prévia preservada.',{exact:true})).toBeVisible();
  const refreshed=page.waitForRequest(r=>r.url().includes('grant_type=refresh_token'));
  await page.clock.runFor(31000);
  await refreshed;
  await expect(page.getByText('Prévia preservada.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Conversa',exact:true}).click();
  await expect(page.getByLabel('Sua mensagem')).toHaveValue('Mensagem ainda em edição');
  await page.getByRole('button',{name:'Importar',exact:true}).click();
  await expect(page.getByRole('button',{name:'Confirmar importação'})).toBeVisible();
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Que bom te ver.'})).toBeVisible();
  await expect(page.getByText('Prévia preservada.',{exact:true})).toHaveCount(0);
});

test('retornar à janela não descarta atualização da mesma sessão',async({page})=>{
  await signIn(page);
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/accounts',route=>route.fulfill({json:{}}));
  await page.route('**/dashboard',async route=>{await gate;await route.fulfill({json:{as_of:'2026-10-04',balance_cents:'4500',expense_cents:'0',categories:[],accounts:[]}});});
  await page.getByText('Adicionar conta ou cartão',{exact:true}).click();
  await page.getByLabel('Nome',{exact:true}).fill('Conta nova');
  await page.getByLabel('Primeiro dia do período').fill('2026-10-01');
  const started=page.waitForRequest('**/dashboard');
  await page.getByRole('button',{name:'Salvar conta'}).click();await started;
  await page.evaluate(()=>{document.dispatchEvent(new Event('visibilitychange'));return new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));});
  release();
  await expect(page.locator('.metrics article').filter({hasText:'Saldo das contas'}).getByRole('heading')).toHaveText('R$ 45,00');
});

test('operação antiga não recarrega dados depois de outro login',async({page})=>{
  await signIn(page,3600,false);
  let release!:()=>void, staleRequests=0;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/me/onboarding',async route=>{await gate;await route.fulfill({json:{}});});
  const started=page.waitForRequest('**/me/onboarding');
  await page.getByRole('button',{name:'Entendi, vamos lá'}).click();
  await started;
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await page.getByLabel('E-mail',{exact:true}).fill('outro@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Uma visão tranquila.'})).toBeVisible();
  page.on('request',r=>{if(r.url().includes('127.0.0.1:8000')&&r.headers().authorization==='Bearer synthetic-token-1')staleRequests++;});
  const finished=page.waitForResponse('**/me/onboarding');
  release();await (await finished).finished();
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  expect(staleRequests).toBe(0);
  await expect(page.locator('main').getByRole('alert')).toHaveCount(0);
});

test('arquivo exige prévia e confirmação',async({page})=>{
  await signIn(page);let confirmed=0;
  await page.route('**/import/preview',route=>route.fulfill({json:{count:1,start:'2026-10-01',end:'2026-10-01',credits_cents:0,debits_cents:1234,receipt:'signed',warning:'Revise os sinais.',truncated:false,entries:[{booked_on:'2026-10-01',description:'<script>alert(1)</script>',amount_cents:-1234}]}}));
  await page.route('**/import/confirm',route=>{confirmed++;return route.fulfill({json:{inserted:1,duplicates:0}});});
  await page.getByRole('button',{name:'Importar',exact:true}).click();
  await page.getByLabel('Extrato ou fatura').setInputFiles({name:'synthetic.csv',mimeType:'text/csv',buffer:Buffer.from('data,descricao,valor\n01/10/2026,Teste,"-12,34"')});
  await page.getByRole('button',{name:'Revisar prévia'}).click();
  await expect(page.getByText('<script>alert(1)</script>',{exact:true})).toBeVisible();
  expect(confirmed).toBe(0);
  await page.getByRole('button',{name:'Confirmar importação'}).click();
  await expect(page.getByRole('status')).toContainText('1 lançamentos importados');
  expect(confirmed).toBe(1);
});

test('chat confirma lançamento validado e mostra fontes como texto',async({page})=>{
  await signIn(page);let confirmed=0;
  const reply={turn_id:owner,message:'Revise a prévia.',mood:'atento',sources:[{chunk_id:owner,section:'Teste',content:'<img src=x onerror=alert(1)>'}],draft:{description:'Mercado',booked_on:'2026-10-04',amount_cents:4200,kind:'expense'}};
  await page.route('**/chat/stream',route=>route.fulfill({contentType:'text/event-stream',body:`event: status\ndata: {}\n\nevent: reply\ndata: ${JSON.stringify(reply)}\n\nevent: done\ndata: {}\n\n`}));
  await page.route(`**/chat/${owner}/confirm`,route=>{confirmed++;return route.fulfill({json:{...reply,transaction_id:account,message:'Registrado.'}});});
  await page.getByRole('button',{name:'Conversa',exact:true}).click();
  await page.getByLabel('Sua mensagem').fill('gastei 42 no mercado ontem');
  await page.getByRole('button',{name:'Enviar mensagem'}).click();
  await expect(page.getByText('Revise a prévia.',{exact:true})).toBeVisible();expect(confirmed).toBe(0);
  await page.getByRole('button',{name:'Confirmar lançamento'}).click();
  await expect(page.getByText('Registrado.',{exact:true})).toBeVisible();expect(confirmed).toBe(1);
  await page.getByText('Fonte: Teste').click();
  await expect(page.getByText('<img src=x onerror=alert(1)>',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('agentes respeitam contrato e exclusão exige confirmação',async({page})=>{
  await signIn(page);let enabled=true,deleted=0;
  await page.route('**/agents',route=>route.fulfill({json:[{id:owner,kind:'runway',account_id:account,goal_id:null,enabled,email_enabled:false}]}));
  await page.route('**/goals',route=>route.fulfill({json:[]}));
  await page.route('**/insights',route=>route.fulfill({json:[]}));
  await page.route('**/agents/runway',route=>{
    const body=route.request().postDataJSON();
    expect(Object.keys(body).sort()).toEqual(['account_id','email_enabled','enabled','goal_id']);
    enabled=body.enabled;return route.fulfill({json:{...body,id:owner,kind:'runway'}});
  });
  await page.getByRole('button',{name:'Agentes',exact:true}).click();
  await page.getByRole('button',{name:'Pausar',exact:true}).click();
  await expect(page.getByText('Pausado',{exact:true})).toBeVisible();
  await page.route('**/me',route=>{
    if(route.request().method()==='DELETE'){deleted++;expect(route.request().postDataJSON()).toEqual({confirm:true});return route.fulfill({status:204});}
    return route.fallback();
  });
  await page.getByRole('button',{name:'Conta',exact:true}).click();
  await page.getByText('Excluir minha conta',{exact:true}).click();
  await expect(page.getByRole('button',{name:'Excluir permanentemente'})).toBeDisabled();expect(deleted).toBe(0);
  await page.getByLabel('Digite EXCLUIR para confirmar').fill('EXCLUIR');
  await page.getByRole('button',{name:'Excluir permanentemente'}).click();
  await expect(page.getByRole('heading',{name:'Que bom te ver.'})).toBeVisible();expect(deleted).toBe(1);
});

test('cadastro aguarda confirmação e Google usa o retorno permitido',async({page})=>{
  await page.route('https://auth.example.test/auth/v1/signup**',route=>{
    expect(new URL(route.request().url()).searchParams.get('redirect_to')).toBe('http://127.0.0.1:3000/app/');
    return route.fulfill({json:{id:owner,email:'teste@example.test',identities:[]}});
  });
  await page.route('https://auth.example.test/auth/v1/authorize**',route=>{
    const url=new URL(route.request().url());
    expect(url.searchParams.get('provider')).toBe('google');
    expect(url.searchParams.get('redirect_to')).toBe('http://127.0.0.1:3000/app/');
    return route.fulfill({contentType:'text/html; charset=utf-8',body:'<h1>Continuação OAuth simulada</h1>'});
  });
  await page.goto('/app/');
  await page.getByRole('button',{name:'Criar conta gratuitamente'}).click();
  await page.getByLabel('E-mail',{exact:true}).fill('teste@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Criar conta',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Confira seu e-mail');
  await page.getByRole('button',{name:'Continuar com Google'}).click();
  await expect(page.getByRole('heading',{name:'Continuação OAuth simulada'})).toBeVisible();
});

test('histórico atrasado preserva a resposta recém-recebida',async({page})=>{
  await signIn(page);
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/chat',async route=>{
    if(route.request().method()!=='GET')return route.fallback();
    await gate;
    return route.fulfill({json:[{request:{request_id:owner,question:'Pergunta anterior',account_id:null},
      response:{turn_id:owner,message:'Resposta anterior',mood:'calmo',sources:[]}}]});
  });
  await page.route('**/chat/stream',route=>route.fulfill({contentType:'text/event-stream',
    body:'event: reply\ndata: '+JSON.stringify({turn_id:account,message:'Resposta nova',mood:'calmo',sources:[]})+'\n\n'}));
  await page.getByRole('button',{name:'Conversa',exact:true}).click();
  await page.getByLabel('Sua mensagem').fill('Olá');
  await page.getByRole('button',{name:'Enviar mensagem'}).click();
  await expect(page.getByText('Resposta nova',{exact:true})).toBeVisible();
  release();
  await expect(page.getByText('Resposta anterior',{exact:true})).toBeVisible();
  await expect(page.getByText('Resposta nova',{exact:true})).toBeVisible();
});

test('mapeamento parcial bloqueia envio e editar sinais invalida a prévia',async({page})=>{
  await signIn(page);let previews=0;
  await page.route('**/import/preview',route=>{
    previews++;
    return route.fulfill({json:{count:1,start:'2026-10-01',end:'2026-10-01',
      credits_cents:0,debits_cents:1234,receipt:'signed',warning:'Revise.',truncated:false,entries:[]}});
  });
  await page.getByRole('button',{name:'Importar',exact:true}).click();
  await page.getByLabel('Extrato ou fatura').setInputFiles({name:'synthetic.csv',mimeType:'text/csv',buffer:Buffer.from('data,descricao,valor')});
  await page.getByText('Mapear colunas de CSV personalizado').click();
  await page.getByLabel('Coluna da data').fill('data');
  await page.getByRole('button',{name:'Revisar prévia'}).click();
  await expect(page.getByRole('status')).toContainText('Preencha as colunas');
  expect(previews).toBe(0);
  await page.getByLabel('Coluna da descrição').fill('descricao');
  await page.getByLabel('Coluna do valor').fill('valor');
  await page.getByRole('button',{name:'Revisar prévia'}).click();
  await expect(page.getByRole('button',{name:'Confirmar importação'})).toBeVisible();
  await page.getByLabel('Sinal das despesas').selectOption('true');
  await expect(page.getByRole('button',{name:'Confirmar importação'})).toHaveCount(0);
  expect(previews).toBe(1);
});
