import { test, expect } from '@playwright/test';

test('interface importa no Postgres e consulta o valor pelo chat',async({page})=>{
  const today=new Date().toLocaleDateString('sv-SE',{timeZone:'America/Sao_Paulo'});
  const first=today.slice(0,8)+'01', bankDate=first.split('-').reverse().join('/');
  await page.route('https://auth.example.test/**',route=>route.fulfill({json:{access_token:'synthetic-token',refresh_token:'synthetic-refresh',expires_in:3600,token_type:'bearer',
    user:{id:'00000000-0000-4000-8000-000000000e2e',aud:'authenticated',role:'authenticated',email:'synthetic@example.test',app_metadata:{},user_metadata:{},created_at:'2026-01-01T00:00:00Z'}}}));
  await page.goto('/app/');
  await page.getByLabel('E-mail',{exact:true}).fill('synthetic@example.test');
  await page.getByLabel('Senha',{exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('button',{name:'Entendi, vamos lá'}).click();
  await page.getByLabel('Nome',{exact:true}).fill('Conta de teste completo');
  await page.getByLabel('Primeiro dia do período').fill(first);
  await page.getByLabel('Saldo de abertura (R$)').fill('100,00');
  await page.getByRole('button',{name:'Salvar conta',exact:true}).click();
  await expect(page.getByText('Conta de teste completo',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Importar',exact:true}).click();
  await page.getByLabel('Extrato ou fatura').setInputFiles({name:'synthetic.csv',mimeType:'text/csv',buffer:Buffer.from(`data;descricao;valor;id\n${bankDate};Mercado sintético;12.34;synthetic-001`)});
  await page.getByText('Mapear colunas de CSV personalizado').click();
  await page.getByLabel('Coluna da data').fill('data');
  await page.getByLabel('Coluna da descrição').fill('descricao');
  await page.getByLabel('Coluna do valor').fill('valor');
  await page.getByLabel('Coluna do identificador (opcional)').fill('id');
  await page.getByLabel('Separador decimal').selectOption('.');
  await page.getByLabel('Sinal das despesas').selectOption('true');
  await page.getByRole('button',{name:'Revisar prévia'}).click();
  await expect(page.getByText('Mercado sintético',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Confirmar importação'}).click();
  await expect(page.getByRole('status')).toContainText('1 lançamentos importados');
  await page.getByRole('button',{name:'Conversa',exact:true}).click();
  await page.getByLabel('Sua mensagem').fill('quanto gastei este mês');
  await page.getByRole('button',{name:'Enviar mensagem'}).click();
  await expect(page.locator('.answer strong')).toHaveText('R$ 12,34');
  await page.getByRole('button',{name:'Resumo',exact:true}).click();
  await expect(page.locator('.metrics article').filter({hasText:'Saldo das contas'}).getByRole('heading')).toHaveText('R$ 87,66');
});
