import { navigate } from './navigation';
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const owner='00000000-0000-4000-8000-000000000001';
const account='00000000-0000-4000-8000-000000000002';
async function signIn(page:Page, expiresIn=3600, onboardingCompleted=true, history:Promise<unknown[]>=Promise.resolve([]), longContent=false) {
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
    if(path==='/dashboard')return route.fulfill({headers,json:{as_of:'2026-10-04',balance_cents:'1152921504606846976',expense_cents:'1234',categories:longContent?[{name:'Categoria'.repeat(10),amount_cents:'1234'}]:[],accounts:[{id:account,name:longContent?'C'.repeat(80):'Conta sintética',kind:'checking',opening_date:'2026-01-01',balance_cents:'10000'}]}});
    if(path==='/chat') return route.fulfill({headers,json:await history});
    return route.fulfill({headers,status:503,json:{detail:'indisponível'}});
  });
  await page.goto('/app/');
  await page.getByLabel('E-mail',{exact:true}).fill('teste@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Vamos conversar.'})).toBeVisible();
  await navigate(page,'Resumo');
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

test('resumo acomoda nomes longos de conta e categoria em 320px',async({page})=>{
  await page.setViewportSize({width:320,height:844});
  await signIn(page,3600,true,Promise.resolve([]),true);
  await expect(page.getByText('C'.repeat(80),{exact:true}).filter({visible:true})).toBeVisible();
  await expect(page.locator('.category-list p')).toContainText('Categoria'.repeat(10));
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('estados vazios orientam o primeiro passo e abrem o cadastro com foco',async({page},info)=>{
  await signIn(page);
  const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,OPTIONS'};
  await page.route('**/dashboard',route=>route.fulfill({headers,json:{as_of:'2026-10-18',balance_cents:'0',expense_cents:'0',categories:[],accounts:[]}}));
  for(const endpoint of ['agents','goals','insights'])await page.route(`**/${endpoint}`,route=>route.fulfill({headers,json:[]}));
  await page.reload();
  await page.getByLabel('E-mail',{exact:true}).fill('teste@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Vamos conversar.',exact:true})).toBeVisible();
  const directory=path.resolve(__dirname,'../../../test-results/obsidiana-empty');
  await mkdir(directory,{recursive:true});
  for(const width of info.project.name==='desktop'?[1440]:[390,320]){
    await page.setViewportSize({width,height:844});
    await navigate(page,'Conversa');await navigate(page,'Resumo');
    await expect(page.getByRole('heading',{name:'Um primeiro passo, no seu ritmo.',exact:true})).toBeVisible();
    await expect(page.locator('.metrics')).toHaveCount(0);
    await expect(page.locator('.screen-heading').getByRole('img')).toHaveAccessibleName(/: dormindo$/);
    const firstAccount=page.getByRole('button',{name:'Adicionar minha primeira conta',exact:true});
    const box=await firstAccount.boundingBox();
    expect(box).not.toBeNull();expect(box!.y).toBeGreaterThanOrEqual(0);expect(box!.y+box!.height).toBeLessThanOrEqual(844);
    await expect(page.getByLabel('Nome',{exact:true})).toBeVisible();
    await page.getByText('Adicionar conta ou cartão',{exact:true}).click();
    await expect(page.getByLabel('Nome',{exact:true})).not.toBeVisible();
    await firstAccount.click();
    await expect(page.getByLabel('Nome',{exact:true})).toBeFocused();
    for(const [screen,heading] of [['Resumo','Um primeiro passo, no seu ritmo.'],['Importar','Vamos dar um lugar aos seus registros.'],['Agentes','Você escolhe o que acompanhar.']]){
      if(screen!=='Resumo')await navigate(page,screen);
      await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${screen} ${width}px`).toBe(true);
      await page.screenshot({path:path.join(directory,`${width}-${screen}.png`),fullPage:true,animations:'disabled',style:'nextjs-portal{display:none!important}'});
    }
  }
});

test('lançamentos filtram e corrigem valores exatos sem trocar a origem',async({page},info)=>{
  await signIn(page);
  const item={id:owner,account_id:account,booked_on:'2026-10-01',amount_cents:'-1152921504606846976',kind:'expense',description:'Mercado sintético',category:null,revision:'a'.repeat(64)};
  let query='',saved:Record<string,unknown>|undefined;
  const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,PUT,OPTIONS'};
  await page.route('**/transactions**',route=>{
    if(route.request().method()==='OPTIONS')return route.fulfill({headers,status:200});
    if(route.request().method()==='PUT'){saved=route.request().postDataJSON();return route.fulfill({headers,json:{...item,...saved,revision:'b'.repeat(64)}});}
    query=new URL(route.request().url()).search;
    return route.fulfill({headers,json:{items:[saved?{...item,...saved}:item],next_cursor:null}});
  });
  await navigate(page,'Lançamentos');
  if(info.project.name==='mobile')await page.setViewportSize({width:320,height:844});
  await expect(page.getByText('Mercado sintético',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Editar lançamento',exact:true}).click();
  await expect(page.getByLabel('Valor em reais',{exact:true})).toHaveValue('-11529215046068469,76');
  const screenshots=path.resolve(__dirname,'../../../test-results/lancamentos');
  await mkdir(screenshots,{recursive:true});
  await page.screenshot({path:path.join(screenshots,`${info.project.name}-editar.png`),fullPage:true,animations:'disabled',style:'nextjs-portal{display:none!important}'});
  await page.getByLabel('Descrição',{exact:true}).fill('Mercado revisado');
  await page.getByLabel('Valor em reais',{exact:true}).fill('-45,00');
  await page.getByRole('combobox',{name:'Natureza',exact:true}).selectOption('transfer');
  await page.getByRole('button',{name:'Confirmar correção',exact:true}).click();
  await expect(page.getByText('Lançamento corrigido.',{exact:true})).toBeVisible();
  expect(saved).toMatchObject({amount_cents:'-4500',kind:'transfer',description:'Mercado revisado',revision:'a'.repeat(64)});
  expect(saved).not.toHaveProperty('account_id');expect(saved).not.toHaveProperty('user_id');
  await page.getByLabel('De',{exact:true}).fill('2026-10-01');
  await page.getByRole('button',{name:'Filtrar lançamentos',exact:true}).click();
  await expect.poll(()=>query).toContain('start=2026-10-01');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('exclusão de lançamento exige confirmação e não repete após falha de atualização',async({page})=>{
  await signIn(page);let deleted=0;
  const item={id:owner,account_id:account,booked_on:'2026-10-01',amount_cents:'-4500',kind:'expense',description:'Registro sintético',category:null,revision:'a'.repeat(64)};
  const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,DELETE,OPTIONS'};
  await page.route('**/transactions**',route=>{
    if(route.request().method()==='OPTIONS')return route.fulfill({headers,status:200});
    if(route.request().method()==='DELETE'){
      expect(route.request().postDataJSON()).toEqual({confirm:true,revision:item.revision});deleted++;
      return route.fulfill({headers,status:204});
    }
    return route.fulfill({headers,json:{items:deleted?[]:[item],next_cursor:null}});
  });
  await navigate(page,'Lançamentos');
  await page.getByRole('button',{name:'Excluir lançamento',exact:true}).click();
  expect(deleted).toBe(0);
  await page.getByRole('button',{name:'Cancelar exclusão',exact:true}).click();
  expect(deleted).toBe(0);
  await page.getByRole('button',{name:'Excluir lançamento',exact:true}).click();
  await page.route('**/dashboard',route=>route.fulfill({headers,status:503,json:{detail:'Sintético'}}));
  await page.getByRole('button',{name:'Confirmar exclusão',exact:true}).click();
  await expect(page.getByText('Lançamento excluído. Atualize o Resumo para conferir os totais.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Confirmar exclusão',exact:true})).toHaveCount(0);
  expect(deleted).toBe(1);
});

test('paginação de lançamentos volta e reinicia ao filtrar',async({page})=>{
  await signIn(page);
  const item={id:owner,account_id:account,booked_on:'2026-10-01',amount_cents:'-4500',kind:'expense',category:null,revision:'a'.repeat(64)};
  const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type'};
  await page.route('**/transactions**',route=>{
    const query=new URL(route.request().url()).searchParams;
    return route.fulfill({headers,json:{items:[{...item,description:query.has('cursor')?'Página seguinte sintética':'Página inicial sintética'}],next_cursor:query.has('cursor')?null:'2026-10-01:'+owner}});
  });
  await navigate(page,'Lançamentos');
  await expect(page.getByText('Página inicial sintética',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Página anterior',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Próxima página',exact:true}).click();
  await expect(page.getByText('Página seguinte sintética',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Página anterior',exact:true}).click();
  await expect(page.getByText('Página inicial sintética',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Próxima página',exact:true}).click();
  await expect(page.getByText('Página seguinte sintética',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Filtrar lançamentos',exact:true}).click();
  await expect(page.getByText('Página inicial sintética',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Página anterior',exact:true})).toBeDisabled();
});

test('mensagem sem espaços cabe na conversa sem rolagem horizontal',async({page})=>{
  await signIn(page);
  const question='x'.repeat(500);
  await page.route('**/chat/stream',route=>route.fulfill({contentType:'text/event-stream',body:`event: reply\ndata: ${JSON.stringify({turn_id:owner,message:'Resposta sintética.',mood:'calmo',sources:[]})}\n\n`}));
  await navigate(page,'Conversa');
  await page.getByLabel('Sua mensagem').fill(question);
  await page.getByRole('button',{name:'Enviar mensagem'}).click();
  await expect(page.locator('.question')).toHaveText(question);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('sugestões preenchem sem enviar e teclado respeita quebra de linha e IME',async({page})=>{
  await signIn(page);let requests=0;
  await page.route('**/chat/stream',route=>{requests++;return route.fulfill({contentType:'text/event-stream',body:`event: reply\ndata: ${JSON.stringify({turn_id:owner,message:'Resposta sintética.',mood:'calmo',sources:[]})}\n\n`});});
  await navigate(page,'Conversa');
  await page.getByRole('button',{name:'Quanto gastei este mês?',exact:true}).click();
  const input=page.getByLabel('Sua mensagem');
  await expect(input).toHaveValue('Quanto gastei este mês?');await expect(input).toBeFocused();
  expect(requests).toBe(0);
  await input.press('Shift+Enter');await input.press('a');
  await expect(input).toHaveValue('Quanto gastei este mês?\na');
  await input.dispatchEvent('keydown',{key:'Enter',code:'Enter',isComposing:true});
  expect(requests).toBe(0);
  await input.press('Enter');
  await expect(page.getByText('Resposta sintética.',{exact:true})).toBeVisible();
  expect(requests).toBe(1);await expect(input).toHaveValue('');
  const composer=await page.locator('.chat-composer').boundingBox();
  expect(composer!.y+composer!.height).toBeLessThanOrEqual(await page.evaluate(()=>innerHeight));
});

test('erro mantém o mesmo pedido para repetição e permite descartá-lo',async({page})=>{
  await signIn(page);const requests:{request_id:string;question:string}[]=[];
  await page.route('**/chat/stream',route=>{requests.push(route.request().postDataJSON());return route.fulfill({status:503,json:{detail:'private'}});});
  await navigate(page,'Conversa');
  await page.getByLabel('Sua mensagem').fill('Pedido sintético');await page.getByLabel('Sua mensagem').press('Enter');
  await expect(page.getByRole('button',{name:'Repetir pedido'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Enviar mensagem'})).toBeDisabled();
  await page.getByRole('button',{name:'Repetir pedido'}).click();
  await expect(page.getByRole('button',{name:'Repetir pedido'})).toBeEnabled();
  expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);
  await page.getByRole('button',{name:'Descartar tentativa'}).click();
  await expect(page.getByRole('button',{name:'Enviar mensagem'})).toBeEnabled();
  await expect(page.getByText('Pedido sintético',{exact:true})).toHaveCount(0);
});

for(const viewport of [{width:320,height:480},{width:390,height:400}])test(`conversa cabe em ${viewport.width}×${viewport.height} e respeita movimento reduzido`,async({page})=>{
  await page.setViewportSize(viewport);await page.emulateMedia({reducedMotion:'reduce'});
  await signIn(page);await navigate(page,'Conversa');
  const menu=page.getByRole('button',{name:'Menu',exact:true});
  await menu.click();await expect(menu).toHaveAttribute('aria-expanded','true');
  await page.locator('#app-navigation').getByRole('button',{name:'Conversa',exact:true}).focus();
  await page.keyboard.press('Escape');await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute('aria-expanded','false');
  expect(await page.locator('.chat-welcome .breath').evaluate(node=>getComputedStyle(node).animationName)).toBe('none');
  await page.getByLabel('Sua mensagem').fill('Mensagem sintética');
  const composer=await page.locator('.chat-composer').boundingBox();
  expect(composer!.y+composer!.height).toBeLessThanOrEqual(viewport.height);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Importar um extrato no chat'}).focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('region',{name:'Importação no chat'})).toBeFocused();
  await page.getByRole('button',{name:'Fechar importação'}).focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('region',{name:'Importação no chat'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Importar um extrato no chat'})).toBeFocused();
});

test('renovação e navegação preservam rascunhos, sair limpa o espaço',async({page})=>{
  await page.clock.install();
  await signIn(page,120);
  await page.route('**/import/preview',route=>route.fulfill({json:{count:1,start:'2026-10-01',end:'2026-10-01',credits_cents:0,debits_cents:1234,receipt:'signed',warning:'Prévia preservada.',truncated:false,entries:[]}}));
  await navigate(page,'Conversa');
  await page.getByLabel('Sua mensagem').fill('Mensagem ainda em edição');
  await navigate(page,'Importar');
  await page.getByLabel('Extrato ou fatura').setInputFiles({name:'synthetic.csv',mimeType:'text/csv',buffer:Buffer.from('data,descricao,valor')});
  await page.getByRole('button',{name:'Revisar prévia'}).click();
  await expect(page.getByText('Prévia preservada.',{exact:true})).toBeVisible();
  const refreshed=page.waitForRequest(r=>r.url().includes('grant_type=refresh_token'));
  await page.clock.runFor(31000);
  await refreshed;
  await expect(page.getByText('Prévia preservada.',{exact:true})).toBeVisible();
  await navigate(page,'Conversa');
  await expect(page.getByLabel('Sua mensagem')).toHaveValue('Mensagem ainda em edição');
  await navigate(page,'Importar');
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
  await page.route('**/dashboard',async route=>{await gate;await route.fulfill({json:{as_of:'2026-10-04',balance_cents:'4500',expense_cents:'0',categories:[],accounts:[{id:account,name:'Conta nova',kind:'checking',balance_cents:'4500'}]}});});
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
  await navigate(page,'Resumo');
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
  await navigate(page,'Importar');
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
  await navigate(page,'Conversa');
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
  await navigate(page,'Agentes');
  await page.getByRole('button',{name:'Pausar',exact:true}).click();
  await expect(page.getByText('Pausado',{exact:true})).toBeVisible();
  await page.route('**/me',route=>{
    if(route.request().method()==='DELETE'){deleted++;expect(route.request().postDataJSON()).toEqual({confirm:true});return route.fulfill({status:204});}
    return route.fallback();
  });
  await navigate(page,'Conta');
  await page.getByText('Excluir minha conta',{exact:true}).click();
  await expect(page.getByRole('button',{name:'Excluir permanentemente'})).toBeDisabled();expect(deleted).toBe(0);
  await page.getByLabel('Digite EXCLUIR para confirmar').fill('EXCLUIR');
  await page.getByRole('button',{name:'Excluir permanentemente'}).click();
  await expect(page.getByRole('heading',{name:'Que bom te ver.'})).toBeVisible();expect(deleted).toBe(1);
});

test('conta mostra consumo e admite falha sem ocultar exclusão',async({page})=>{
  await signIn(page);
  await page.route('**/me/usage',route=>route.fulfill({json:{period_end:'2026-11-01T00:00:00Z',
    messages:{used:200,limit:200,remaining:0},import_sources:{used:7,limit:null,remaining:null},agents:{used:1,limit:3,remaining:2}}}));
  await navigate(page,'Conta');
  const panel=page.getByRole('region',{name:'Consumo do plano'});
  await expect(panel.getByText('200 usados · 0 restantes de 200')).toBeVisible();
  await expect(panel.getByText('7 usados · sem limite contratual')).toBeVisible();
  await expect(panel).toContainText('01/11/2026 (UTC)');
  await navigate(page,'Resumo');
  await page.route('**/me/usage',route=>route.fulfill({status:503,json:{detail:'private'}}));
  await navigate(page,'Conta');
  await expect(panel.getByRole('status')).toHaveText('Não foi possível consultar o consumo agora.');
  await expect(page.getByText('Excluir minha conta',{exact:true})).toBeVisible();
  await expect(panel.getByText('200 usados · 0 restantes de 200')).toHaveCount(0);
});

test('renovar sessão recarrega agentes sem sobrescrever uma alteração recente',async({page})=>{
  await page.clock.install();await signIn(page,120);
  let enabled=true,blocked=false,release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/agents',route=>route.fulfill({json:[{kind:'runway',account_id:account,goal_id:null,enabled,email_enabled:false}]}));
  await page.route('**/goals',async route=>{
    if(route.request().headers().authorization==='Bearer synthetic-token-2'&&!blocked){blocked=true;await gate;}
    await route.fulfill({json:[]});
  });
  await page.route('**/insights',route=>route.fulfill({json:[]}));
  await page.route('**/agents/runway',route=>{enabled=route.request().postDataJSON().enabled;return route.fulfill({json:{}});});
  await navigate(page,'Agentes');
  await expect(page.getByRole('button',{name:'Pausar',exact:true})).toBeVisible();
  const renewed=page.waitForRequest(r=>r.url().endsWith('/goals')&&r.headers().authorization==='Bearer synthetic-token-2');
  await page.clock.runFor(31000);await renewed;
  await page.getByRole('button',{name:'Pausar',exact:true}).click();
  await expect(page.getByText('Pausado',{exact:true})).toBeVisible();
  const finished=page.waitForResponse('**/goals');release();await (await finished).finished();await page.clock.runFor(100);
  await expect(page.getByText('Pausado',{exact:true})).toBeVisible();
});

test('exclusão atrasada não encerra a sessão de outra identidade',async({page})=>{
  await signIn(page);let release!:()=>void,completed!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const completion=new Promise<void>(resolve=>{completed=resolve;});
  await page.route('**/me',async route=>{
    if(route.request().method()!=='DELETE')return route.fallback();
    await gate;await route.fulfill({status:204});completed();
  });
  await navigate(page,'Conta');
  await page.getByText('Excluir minha conta',{exact:true}).click();
  await page.getByLabel('Digite EXCLUIR para confirmar').fill('EXCLUIR');
  const started=page.waitForRequest(r=>r.url().endsWith('/me')&&r.method()==='DELETE');
  await page.getByRole('button',{name:'Excluir permanentemente'}).click();await started;
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await page.getByLabel('E-mail',{exact:true}).fill('outro@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await navigate(page,'Resumo');
  await expect(page.getByRole('heading',{name:'Uma visão tranquila.'})).toBeVisible();
  let signedOut=false;
  page.on('request',request=>{if(request.url().includes('/auth/v1/logout'))signedOut=true;});
  release();await completion;
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  expect(signedOut).toBe(false);
  await expect(page.getByRole('heading',{name:'Uma visão tranquila.'})).toBeVisible();
});

test('cadastro aguarda confirmação e Google usa o retorno permitido',async({page})=>{
  await page.route('https://auth.example.test/auth/v1/signup**',route=>{
    expect(new URL(route.request().url()).searchParams.get('redirect_to')).toBe(`${new URL(page.url()).origin}/app/`);
    return route.fulfill({json:{id:owner,email:'teste@example.test',identities:[]}});
  });
  await page.route('https://auth.example.test/auth/v1/authorize**',route=>{
    const url=new URL(route.request().url());
    expect(url.searchParams.get('provider')).toBe('google');
    expect(url.searchParams.get('redirect_to')).toBe(`${new URL(page.url()).origin}/app/`);
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
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const history=gate.then(()=>[{request:{request_id:owner,question:'Pergunta anterior',account_id:null},
    response:{turn_id:owner,message:'Resposta anterior',mood:'calmo',sources:[]}}]);
  await signIn(page,3600,true,history);
  await page.route('**/chat/stream',route=>route.fulfill({contentType:'text/event-stream',
    body:'event: reply\ndata: '+JSON.stringify({turn_id:account,message:'Resposta nova',mood:'calmo',sources:[]})+'\n\n'}));
  await navigate(page,'Conversa');
  await page.getByLabel('Sua mensagem').fill('Olá');
  await page.getByRole('button',{name:'Enviar mensagem'}).click();
  await expect(page.getByText('Resposta nova',{exact:true})).toBeVisible();
  release();
  await expect(page.getByText('Resposta anterior',{exact:true})).toBeVisible();
  await expect(page.getByText('Resposta nova',{exact:true})).toBeVisible();
});

test('histórico recebido fora da aba mostra o fim sem perder leitura anterior',async({page})=>{
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const history=gate.then(()=>Array.from({length:20},(_,i)=>({request:{request_id:`request-${i}`,question:`Pergunta sintética ${i}`,account_id:null},response:{turn_id:`turn-${i}`,message:'Resposta sintética para revisar com cuidado. '.repeat(8),mood:'calmo',sources:[]}})));
  await signIn(page,3600,true,history);release();
  await expect(page.locator('.conversation article')).toHaveCount(20);await navigate(page,'Conversa');
  const list=page.getByRole('region',{name:'Mensagens da conversa'});
  await expect.poll(()=>list.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight)).toBeLessThan(2);
  await list.evaluate(node=>new Promise<void>(resolve=>{node.addEventListener('scroll',()=>resolve(),{once:true});node.scrollTop=0;}));
  await navigate(page,'Resumo');await navigate(page,'Conversa');
  await expect.poll(()=>list.evaluate(node=>node.scrollTop)).toBe(0);
});

test('mapeamento parcial bloqueia envio e editar sinais invalida a prévia',async({page})=>{
  await signIn(page);let previews=0;
  await page.route('**/import/preview',route=>{
    previews++;
    return route.fulfill({json:{count:1,start:'2026-10-01',end:'2026-10-01',
      credits_cents:0,debits_cents:1234,receipt:'signed',warning:'Revise.',truncated:false,entries:[]}});
  });
  await navigate(page,'Importar');
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
