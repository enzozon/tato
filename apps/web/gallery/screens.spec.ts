import { test, expect } from '@playwright/test';
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const output=path.resolve(__dirname,'../../../test-results/ui-gallery');
const owner='00000000-0000-4000-8000-000000000001';
const account='00000000-0000-4000-8000-000000000002';
const user={id:owner,email:'teste@example.test',aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:'2026-10-17T00:00:00Z'};

test.afterAll(async()=>{
  const files=(await readdir(output)).filter(file=>/^(desktop|mobile)-\d{2}-[a-z-]+\.png$/.test(file)).sort();
  await writeFile(path.join(output,'index.html'),`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Tato — avaliação visual</title>
    <style>body{font:18px system-ui;max-width:1200px;margin:32px auto;padding:16px;background:#faf8f1;color:#153e35}nav{display:flex;flex-wrap:wrap;gap:12px}img{max-width:100%;height:auto;border:1px solid #668579}figure{margin:40px 0}a{color:#175f46}</style>
    <h1>Tato — telas para avaliação</h1><p>Somente dados sintéticos. Capturas da aplicação real com respostas simuladas; não comprovam funcionamento dos provedores nem instalação física no iPhone. O catálogo só está completo se o comando terminou com 2 testes aprovados.</p>
    <nav>${files.map((file,i)=>`<a href="#screen-${i}">${file.replace('.png','')}</a>`).join('')}</nav>
    ${files.map((file,i)=>`<figure id="screen-${i}"><figcaption><h2>${file.replace('.png','')}</h2><a href="${file}">Abrir imagem completa</a></figcaption><img src="${file}" loading="lazy" alt="${file.replace('.png','')} — dados sintéticos"></figure>`).join('')}</html>`);
});

test('catálogo das telas principais com dados sintéticos',async({page},info)=>{
  await mkdir(output,{recursive:true});
  const errors:string[]=[];
  page.on('pageerror',error=>errors.push(error.message));
  // Impede que uma alteração de URL envie credenciais sintéticas a serviços reais.
  await page.route('**/*',route=>new URL(route.request().url()).origin==='http://127.0.0.1:3000'
    ?route.continue():route.abort());
  let completed=false, billing=false;
  await page.route('https://auth.example.test/**',route=>route.fulfill({json:route.request().url().endsWith('/user')?user:
    {access_token:'synthetic-token',refresh_token:'synthetic-refresh',token_type:'bearer',expires_in:3600,user}}));
  await page.route('http://127.0.0.1:8000/**',route=>{
    const endpoint=new URL(route.request().url()).pathname;
    const headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'GET,POST,PUT,DELETE'};
    if(route.request().method()==='OPTIONS')return route.fulfill({headers,status:200});
    const responses:Record<string,unknown>={
      '/me':{onboarding_completed:completed,plan:{name:'free',agents:1,messages_per_month:200}},
      '/dashboard':{as_of:'2026-10-17',balance_cents:'93000',expense_cents:'7000',categories:[{name:'Alimentação',amount_cents:'7000'}],accounts:[{id:account,name:'Conta sintética',kind:'checking',opening_date:'2026-10-01',balance_cents:'93000'}]},
      '/chat':[], '/goals':[{id:owner,description:'Reserva sintética',target_cents:500000}],
      '/agents':[{kind:'runway',account_id:account,goal_id:null,enabled:true,email_enabled:false}],
      '/insights':[{id:owner,read_at:null,signal:{message:'Seu saldo registrado cobre a projeção sintética.',kind:'runway',as_of:'2026-10-17',facts:{balance_cents:93000,projected_expense_cents:12000,remaining_days:14}}}],
      '/me/usage':{period_end:'2026-11-01T00:00:00Z',messages:{used:4,limit:200,remaining:196},import_sources:{used:1,limit:1,remaining:0},agents:{used:1,limit:1,remaining:0}},
      '/me/llm-usage':{period_start:'2026-10-01',period_end:'2026-11-01',attempts:4,input_tokens:600,output_tokens:120,elapsed_ms:1200,unknown_input_attempts:0,unknown_output_attempts:0},
      '/billing/status':{enabled:billing,mode:'test',can_checkout:billing,can_portal:billing,pending_request_id:null},
      '/import/preview':{count:2,start:'2026-10-17',end:'2026-10-17',credits_cents:0,debits_cents:7000,receipt:'synthetic',warning:'Confira a conta e os sinais antes de confirmar.',truncated:false,entries:[{booked_on:'2026-10-17',description:'Mercado sintético',amount_cents:-4200},{booked_on:'2026-10-17',description:'Delivery sintético',amount_cents:-2800}]},
      '/import/confirm':{inserted:2,duplicates:0},
    };
    if(endpoint==='/me/onboarding'){completed=true;return route.fulfill({headers,json:{}});}
    return route.fulfill({headers,status:endpoint in responses?200:503,json:responses[endpoint]||{}});
  });
  async function capture(label:string){
    await expect(page.locator('body')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),label).toBe(true);
    await page.screenshot({path:path.join(output,`${info.project.name}-${label}.png`),fullPage:true,animations:'disabled',style:'nextjs-portal{display:none!important}'});
  }
  async function tab(name:string){await page.getByRole('button',{name,exact:true}).click();}
  await page.goto('/');
  await expect(page.getByRole('heading',{name:/seu dinheiro, em uma conversa./i})).toBeVisible();
  await capture('01-landing');
  await page.getByText('Usar como aplicativo',{exact:true}).click();
  await expect(page.getByText(/No iPhone, abra no Safari/)).toBeVisible();
  await capture('02-instalacao-pwa');
  await page.goto('/app/');
  await expect(page.getByRole('heading',{name:'Que bom te ver.'})).toBeVisible();await capture('03-login');
  await tab('Criar conta gratuitamente');await capture('04-cadastro');await tab('Já tenho conta');
  await tab('Esqueci minha senha');await capture('05-recuperar-senha');await tab('Voltar ao login');
  await page.getByLabel('E-mail',{exact:true}).fill(user.email);await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');await tab('Entrar');
  await expect(page.getByRole('button',{name:'Entendi, vamos lá'})).toBeVisible();await capture('06-onboarding');await tab('Entendi, vamos lá');
  await expect(page.getByRole('heading',{name:'Uma visão tranquila.'})).toBeVisible();await capture('07-resumo');
  await page.getByText('Adicionar conta ou cartão',{exact:true}).click();await capture('08-criar-conta-cartao');
  await tab('Conversa');await expect(page.getByRole('heading',{name:'Vamos conversar.'})).toBeVisible();await capture('09-conversa');
  let reply:Record<string,unknown>={turn_id:owner,message:'Revise o lançamento sintético antes de salvar.',mood:'atento',sources:[],draft:{description:'Mercado sintético',booked_on:'2026-10-17',amount_cents:4200,kind:'expense'}};
  await page.route('**/chat/stream',route=>route.fulfill({contentType:'text/event-stream',body:`event: reply\ndata: ${JSON.stringify(reply)}\n\n`}));
  await page.getByRole('combobox',{name:/^Conta para consulta ou lançamento/}).selectOption(account);
  await page.getByLabel('Sua mensagem').fill('Gastei 42 no mercado hoje');await tab('Enviar mensagem');
  await expect(page.getByRole('button',{name:'Confirmar lançamento'})).toBeVisible();await capture('10-chat-confirmacao');
  reply={turn_id:account,message:'Uma reserva ajuda com despesas inesperadas. Exemplo sintético.',mood:'calmo',sources:[{chunk_id:owner,section:'Reserva de emergência',content:'Uma reserva ajuda a lidar com despesas inesperadas. Exemplo de conteúdo público sintético.'}]};
  await page.getByLabel('Sua mensagem').fill('O que é reserva de emergência?');await tab('Enviar mensagem');
  await page.getByText('Fonte: Reserva de emergência').click();await capture('21-chat-fonte-rag');
  reply={turn_id:owner,message:'Consulta sintética de despesas.',mood:'calmo',sources:[],expense:{amount_cents:7000,source:{start:'2026-10-01',end:'2026-11-01',tool:'expense_total'}}};
  await page.getByLabel('Sua mensagem').fill('Quanto gastei em outubro?');await tab('Enviar mensagem');
  await expect(page.getByText('Consulta sintética de despesas.',{exact:true})).toBeVisible();await capture('22-chat-fonte-sql');
  reply={turn_id:account,message:'Podemos organizar seus registros juntos. Resposta conversacional sintética.',mood:'calmo',sources:[]};
  await page.getByLabel('Sua mensagem').fill('Olá, Tato');await tab('Enviar mensagem');
  await expect(page.getByText('Podemos organizar seus registros juntos. Resposta conversacional sintética.',{exact:true})).toBeVisible();await capture('23-chat-conversa-livre');
  await tab('Importar um extrato no chat');await capture('11-importar-no-chat');
  await tab('Importar');await capture('12-importacao');
  await page.getByText('Mapear colunas de CSV personalizado',{exact:true}).filter({visible:true}).click();await capture('13-mapeamento-csv');
  await page.getByText('Mapear colunas de CSV personalizado',{exact:true}).filter({visible:true}).click();
  await page.getByLabel('Extrato ou fatura').filter({visible:true}).setInputFiles({name:'movimentos-sinteticos.csv',mimeType:'text/csv',buffer:Buffer.from('date,title,amount\n2026-10-17,Mercado sintetico,42.00\n2026-10-17,Delivery sintetico,28.00')});
  await tab('Revisar prévia');await expect(page.getByRole('heading',{name:'Confira antes de salvar'})).toBeVisible();await capture('14-previa-importacao');
  await tab('Confirmar importação');await expect(page.getByRole('status')).toContainText('2 lançamentos importados');await capture('15-importacao-concluida');
  await tab('Agentes');await expect(page.getByRole('heading',{name:'Seu saldo registrado cobre a projeção sintética.'})).toBeVisible();await capture('16-agentes-avisos');
  await page.getByText('Configurar um agente',{exact:true}).click();await page.getByRole('combobox',{name:/^Agente/}).selectOption('goal');await page.getByText('Criar uma meta',{exact:true}).click();await capture('17-agente-meta-email');
  await tab('Conta');await expect(page.getByText('4 usados · 196 restantes de 200')).toBeVisible();await capture('18-conta-exportacao-cobranca-desligada');
  await page.getByText('Excluir minha conta',{exact:true}).click();await capture('19-exclusao-confirmacao');
  billing=true;await tab('Resumo');await tab('Conta');await expect(page.getByRole('button',{name:'Simular assinatura Pro'})).toBeEnabled();await capture('20-cobranca-sandbox');
  await tab('Sair');
  const part=(value:object)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  const token=`${part({alg:'HS256',typ:'JWT'})}.${part({sub:owner,role:'authenticated',exp:Math.floor(Date.now()/1000)+3600})}.c3ludGhldGlj`;
  await page.goto(`/app/?recovery=1#access_token=${token}&refresh_token=synthetic-refresh&expires_in=3600&token_type=bearer&type=recovery`);
  await expect(page.getByLabel('Nova senha',{exact:true})).toBeVisible();await capture('24-nova-senha');
  await page.goto('/offline.html');
  await expect(page.getByRole('heading',{name:'Vamos retomar quando a conexão voltar.'})).toBeVisible();await capture('25-orientacao-offline');
  expect(errors).toEqual([]);
});
