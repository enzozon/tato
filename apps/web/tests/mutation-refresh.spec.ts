import { test, expect, type Page } from '@playwright/test';

async function signIn(page: Page, dashboardFailed: () => boolean) {
  const id = '00000000-0000-4000-8000-000000000001';
  const user = { id, email: 'teste@example.test', aud: 'authenticated', role: 'authenticated', app_metadata: {}, user_metadata: {}, created_at: '2026-10-04T00:00:00Z' };
  await page.route('https://auth.example.test/**', route => route.fulfill({ json: { access_token: 'synthetic-token', refresh_token: 'synthetic-refresh', token_type: 'bearer', expires_in: 3600, user } }));
  await page.route('http://127.0.0.1:8000/**', route => {
    const path = new URL(route.request().url()).pathname;
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization,content-type', 'Access-Control-Allow-Methods': 'GET,POST' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ headers, status: 200 });
    if (path === '/me') return route.fulfill({ headers, json: { onboarding_completed: true, plan: { name: 'free', agents: 1, messages_per_month: 200 } } });
    if (path === '/dashboard') return dashboardFailed() ? route.fulfill({ headers, status: 503, json: {} }) :
      route.fulfill({ headers, json: { as_of: '2026-10-04', balance_cents: '0', expense_cents: '0', categories: [],
        accounts: [{ id, name: 'Conta sintética', kind: 'checking', opening_date: '2026-10-01', balance_cents: '0' }] } });
    return route.fulfill({ headers, status: 503, json: {} });
  });
  await page.goto('/app/');
  await page.getByLabel('E-mail', { exact: true }).fill(user.email);
  await page.getByLabel('Senha', { exact: true }).fill('synthetic-password');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Uma visão tranquila.' })).toBeVisible();
}

test('conta salva não é reenviada quando somente a atualização do resumo falha', async ({ page }) => {
  let failed = false, created = 0;
  await signIn(page, () => failed);
  await page.route('**/accounts', route => { created++; failed = true; return route.fulfill({ json: {} }); });
  await page.getByText('Adicionar conta ou cartão', { exact: true }).click();
  await page.getByLabel('Nome', { exact: true }).fill('Conta nova');
  await page.getByLabel('Primeiro dia do período').fill('2026-10-01');
  await page.getByRole('button', { name: 'Salvar conta' }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('Conta criada. Não foi possível atualizar o resumo');
  await expect(page.getByLabel('Nome', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Salvar conta' }).click();
  expect(created).toBe(1);
  failed = false;
  await page.getByRole('button', { name: 'Atualizar resumo', exact: true }).click();
  await expect(page.locator('main').getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Atualizar resumo', exact: true })).toHaveCount(0);
  expect(created).toBe(1);
});

test('importação salva preserva confirmação quando o resumo fica indisponível', async ({ page }) => {
  let failed = false, confirmed = 0;
  await signIn(page, () => failed);
  await page.route('**/import/preview', route => route.fulfill({ json: { count: 1, start: '2026-10-01', end: '2026-10-01', credits_cents: 0, debits_cents: 1234,
    receipt: 'signed', warning: 'Prévia sintética.', truncated: false, entries: [] } }));
  await page.route('**/import/confirm', route => { confirmed++; failed = true; return route.fulfill({ json: { inserted: 1, duplicates: 0 } }); });
  await page.getByRole('button', { name: 'Importar', exact: true }).click();
  await page.getByLabel('Extrato ou fatura').setInputFiles({ name: 'synthetic.csv', mimeType: 'text/csv', buffer: Buffer.from('data,descricao,valor') });
  await page.getByRole('button', { name: 'Revisar prévia' }).click();
  await page.getByRole('button', { name: 'Confirmar importação' }).click();
  await expect(page.getByRole('status')).toContainText('1 lançamentos importados; 0 duplicados ignorados.');
  await expect(page.getByRole('status')).toContainText('a importação já foi salva');
  await expect(page.getByRole('button', { name: 'Confirmar importação' })).toHaveCount(0);
  expect(confirmed).toBe(1);
});
