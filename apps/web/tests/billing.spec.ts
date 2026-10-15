import { test, expect, type Page } from '@playwright/test';

const pending = '00000000-0000-4000-8000-000000000003';
const enabled = { enabled: true, mode: 'test', can_checkout: true, can_portal: true, pending_request_id: null };
async function settings(page: Page) {
  let issued = 0;
  const user = { id: pending, email: 'teste@example.test', aud: 'authenticated', role: 'authenticated', app_metadata: {}, user_metadata: {}, created_at: '2026-10-04T00:00:00Z' };
  await page.route('https://auth.example.test/**', route => route.fulfill({ json: { access_token: `synthetic-token-${++issued}`,
    refresh_token: 'synthetic-refresh', token_type: 'bearer', expires_in: 120, user } }));
  await page.route('http://127.0.0.1:8000/**', route => {
    const path = new URL(route.request().url()).pathname;
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization,content-type', 'Access-Control-Allow-Methods': 'GET,POST' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ headers, status: 200 });
    if (path === '/me') return route.fulfill({ headers, json: { onboarding_completed: true, plan: { name: 'free', agents: 1, messages_per_month: 200 } } });
    if (path === '/dashboard') return route.fulfill({ headers, json: { as_of: '2026-10-04', balance_cents: '0', expense_cents: '0', categories: [], accounts: [] } });
    if (path.startsWith('/billing/')) return route.fallback();
    return route.fulfill({ headers, status: 503, json: {} });
  });
  await page.goto('/app/?checkout=success&plan=pro');
  await page.getByLabel('E-mail', { exact: true }).fill(user.email);
  await page.getByLabel('Senha', { exact: true }).fill('synthetic-password');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await page.getByRole('button', { name: 'Conta', exact: true }).click();
}

test('cobrança desligada não permite ações nem concede plano pelo retorno', async ({ page }) => {
  await page.route('**/billing/status', route => route.fulfill({ json: { ...enabled, enabled: false, can_checkout: false, can_portal: false } }));
  await settings(page);
  const panel = page.getByRole('region', { name: 'Cobrança de teste' });
  await expect(panel).toContainText('desativada neste ambiente');
  await expect(panel.getByRole('button', { name: 'Simular assinatura Pro' })).toBeDisabled();
  await expect(panel.getByRole('button', { name: 'Gerenciar assinatura de teste' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Plano free' })).toBeVisible();
  await expect(page.getByText('Excluir minha conta', { exact: true })).toBeVisible();
});

test('repetição do checkout conserva UUID durante renovação e valida destino', async ({ page }) => {
  await page.clock.install();
  const ids: string[] = [];
  await page.route('**/billing/status', route => route.fulfill({ json: enabled }));
  await page.route('**/billing/stripe/checkout', route => {
    const body = route.request().postDataJSON();
    expect(Object.keys(body)).toEqual(['request_id']); ids.push(body.request_id);
    return route.fulfill({ json: { request_id: body.request_id, status: 'pending', checkout_url: 'https://evil.example.test/c/pay/session' } });
  });
  await settings(page);
  const panel = page.getByRole('region', { name: 'Cobrança de teste' });
  await panel.getByRole('button', { name: 'Simular assinatura Pro' }).click();
  await expect(panel.getByRole('alert')).toContainText('mesmo pedido');
  const renewed = page.waitForRequest(r => r.url().endsWith('/billing/status') && r.headers().authorization === 'Bearer synthetic-token-2');
  await page.clock.runFor(31000); await renewed;
  await panel.getByRole('button', { name: 'Simular assinatura Pro' }).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  expect(ids).toHaveLength(2); expect(ids[1]).toBe(ids[0]);
  expect(ids[0]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  await expect(page).toHaveURL(/127\.0\.0\.1:3000\/app\//);
});

test('checkout existente reutiliza pedido do serviço e navega somente para Stripe', async ({ page }) => {
  await page.route('**/billing/status', route => route.fulfill({ json: { ...enabled, pending_request_id: pending } }));
  await page.route('**/billing/stripe/checkout', route => {
    expect(route.request().postDataJSON()).toEqual({ request_id: pending });
    return route.fulfill({ json: { request_id: pending, status: 'pending', checkout_url: 'https://checkout.stripe.com/c/pay/synthetic#return' } });
  });
  await page.route('https://checkout.stripe.com/**', route => route.fulfill({ contentType: 'text/html', body: '<h1>Checkout simulado</h1>' }));
  await settings(page);
  await page.getByRole('button', { name: 'Simular assinatura Pro' }).click();
  await expect(page.getByRole('heading', { name: 'Checkout simulado' })).toBeVisible();
});

test('portal envia somente UUID e abre sessão hospedada do Stripe', async ({ page }) => {
  await page.route('**/billing/status', route => route.fulfill({ json: { ...enabled, can_checkout: false } }));
  await page.route('**/billing/stripe/portal', route => {
    const body = route.request().postDataJSON();
    expect(Object.keys(body)).toEqual(['request_id']); expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);
    return route.fulfill({ json: { portal_url: 'https://billing.stripe.com/p/session?token=synthetic' } });
  });
  await page.route('https://billing.stripe.com/**', route => route.fulfill({ contentType: 'text/html', body: '<h1>Portal simulado</h1>' }));
  await settings(page);
  await page.getByRole('button', { name: 'Gerenciar assinatura de teste' }).click();
  await expect(page.getByRole('heading', { name: 'Portal simulado' })).toBeVisible();
});

test('resposta de checkout do token anterior não navega após renovação', async ({ page }) => {
  await page.clock.install();
  let release!: () => void, completed!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const completion = new Promise<void>(resolve => { completed = resolve; });
  await page.route('**/billing/status', route => route.fulfill({ json: enabled }));
  await page.route('**/billing/stripe/checkout', async route => {
    const body = route.request().postDataJSON();
    await gate; await route.fulfill({ json: { request_id: body.request_id, status: 'pending', checkout_url: 'https://checkout.stripe.com/c/pay/synthetic' } });
    completed();
  });
  let navigated = false;
  await page.route('https://checkout.stripe.com/**', route => { navigated = true; return route.fulfill({ body: 'Checkout simulado' }); });
  await settings(page);
  const started = page.waitForRequest('**/billing/stripe/checkout');
  await page.getByRole('button', { name: 'Simular assinatura Pro' }).click(); await started;
  const renewed = page.waitForRequest(r => r.url().endsWith('/billing/status') && r.headers().authorization === 'Bearer synthetic-token-2');
  await page.clock.runFor(31000); await renewed;
  release(); await completion; await page.clock.runFor(100);
  expect(navigated).toBe(false);
  await expect(page.getByRole('heading', { name: 'Sua conta.' })).toBeVisible();
});

test('checkout sem URL atualiza disponibilidade sem ativar Pro na interface', async ({ page }) => {
  let paid = false;
  await page.route('**/billing/status', route => route.fulfill({ json: { ...enabled, can_checkout: !paid } }));
  await page.route('**/billing/stripe/checkout', route => {
    paid = true;
    return route.fulfill({ json: { request_id: route.request().postDataJSON().request_id, status: 'paid', checkout_url: null } });
  });
  await settings(page);
  await page.getByRole('button', { name: 'Simular assinatura Pro' }).click();
  await expect(page.getByText(/o retorno do navegador não ativa o Pro/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Simular assinatura Pro' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Plano free' })).toBeVisible();
});

test('checkout pago libera novo UUID após cancelar assinatura e confirmar ausência de pendente', async ({ page }) => {
  await page.clock.install();
  const ids: string[] = [];
  let canceled = false;
  await page.route('**/billing/status', route => route.fulfill({ json: { ...enabled,
    can_checkout: ids.length === 0 || canceled } }));
  await page.route('**/billing/stripe/checkout', route => {
    const id = route.request().postDataJSON().request_id; ids.push(id);
    return route.fulfill({ json: { request_id: id, status: 'paid', checkout_url: null } });
  });
  await settings(page);
  const button = page.getByRole('button', { name: 'Simular assinatura Pro' });
  await button.click();
  await expect(page.getByText('Preparando ambiente de teste…')).not.toBeVisible();
  await expect(button).toBeDisabled();
  canceled = true;
  const renewed = page.waitForRequest(r => r.url().endsWith('/billing/status') && r.headers().authorization === 'Bearer synthetic-token-2');
  await page.clock.runFor(31000); await renewed;
  await expect(button).toBeEnabled();
  await button.click();
  await expect.poll(() => ids.length).toBe(2);
  expect(ids[1]).not.toBe(ids[0]);
  expect(ids[1]).toMatch(/^[0-9a-f-]{36}$/);
});

for (const terminal of ['canceled', 'paid']) {
for (const replacement of [null, pending]) {
  test(`checkout ${terminal} usa ${replacement ? 'o novo pedido pendente' : 'um novo UUID'} após reconciliação`, async ({ page }) => {
    const ids: string[] = [];
    await page.route('**/billing/status', route => route.fulfill({ json: { ...enabled,
      pending_request_id: ids.length ? replacement : null } }));
    await page.route('**/billing/stripe/checkout', route => {
      const id = route.request().postDataJSON().request_id; ids.push(id);
      return route.fulfill({ json: { request_id: id, status: terminal, checkout_url: null } });
    });
    await settings(page);
    const button = page.getByRole('button', { name: 'Simular assinatura Pro' });
    await button.click();
    await expect(button).toBeEnabled();
    await button.click();
    await expect.poll(() => ids.length).toBe(2);
    expect(ids[1]).not.toBe(ids[0]);
    if (replacement) expect(ids[1]).toBe(replacement);
    else expect(ids[1]).toMatch(/^[0-9a-f-]{36}$/);
  });
}
for (const failed of [true, false]) {
  test(`checkout ${terminal} conserva UUID se estado ${failed ? 'falhar' : 'omitir pendência'}`, async ({ page }) => {
    const ids: string[] = [];
    await page.route('**/billing/status', route => route.fulfill(ids.length
      ? failed ? { status: 503, json: {} } : { json: { ...enabled, pending_request_id: undefined } }
      : { json: enabled }));
    await page.route('**/billing/stripe/checkout', route => {
      const id = route.request().postDataJSON().request_id; ids.push(id);
      return route.fulfill({ json: { request_id: id, status: terminal, checkout_url: null } });
    });
    await settings(page);
    const button = page.getByRole('button', { name: 'Simular assinatura Pro' });
    await button.click();
    if (failed) await expect(page.getByRole('region', { name: 'Cobrança de teste' }).getByRole('alert')).toContainText('mesmo pedido');
    await expect(page.getByText('Preparando ambiente de teste…')).not.toBeVisible();
    await expect(button).toBeEnabled(); await button.click();
    await expect.poll(() => ids.length).toBe(2);
    expect(ids[1]).toBe(ids[0]);
  });
}
}
