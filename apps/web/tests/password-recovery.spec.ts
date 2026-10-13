import { test, expect, type Page } from '@playwright/test';

const owner = '00000000-0000-4000-8000-000000000001';
const other = '00000000-0000-4000-8000-000000000002';
const user = { id: owner, email: 'teste@example.test', aud: 'authenticated', role: 'authenticated', app_metadata: {}, user_metadata: {}, created_at: '2026-10-04T00:00:00Z' };
function token(id = owner, seconds = 3600) {
  const part = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url');
  return `${part({ alg: 'HS256', typ: 'JWT' })}.${part({ sub: id, role: 'authenticated', exp: Math.floor(Date.now() / 1000) + seconds })}.c3ludGhldGlj`;
}
function link(type = 'recovery', seconds = 3600) {
  return `/app/?recovery=1#access_token=${token(owner, seconds)}&refresh_token=synthetic-refresh&expires_in=${seconds}&token_type=bearer&type=${type}`;
}
async function simulate(page: Page, options: { requestStatus?: number; updateFails?: boolean; refreshOwner?: string; expired?: boolean; updateOwner?: string; authStatus?: number } = {}) {
  let updates = 0, apiCalls = 0;
  await page.route('http://127.0.0.1:8000/**', route => { apiCalls++; return route.fulfill({ status: 503, json: {} }); });
  await page.route('https://auth.example.test/**', route => {
    const request = route.request(), url = new URL(request.url());
    if (url.pathname.endsWith('/recover')) {
      expect(url.searchParams.get('redirect_to')).toBe('http://127.0.0.1:3000/app/?recovery=1');
      expect(request.postDataJSON().email).toBe(user.email);
      return route.fulfill({ status: options.requestStatus || 200, json: options.requestStatus && options.requestStatus !== 200 ?
        { code: 'user_not_found', msg: 'synthetic private provider message' } : {} });
    }
    if (url.pathname.endsWith('/user') && request.method() === 'PUT') {
      updates++; expect(request.postDataJSON()).toEqual({ password: 'synthetic-new-password', code_challenge: null, code_challenge_method: null });
      return route.fulfill({ status: options.updateFails ? 422 : 200, json: options.updateFails ? { msg: 'synthetic private password policy' } : { ...user, id: options.updateOwner || owner } });
    }
    if (url.pathname.endsWith('/token')) {
      const id = options.refreshOwner || owner;
      return route.fulfill({ json: { access_token: token(id), refresh_token: 'synthetic-refresh', expires_in: 3600, token_type: 'bearer', user: { ...user, id } } });
    }
    if (options.expired && url.pathname.endsWith('/user')) return route.fulfill({ status: 401, json: { code: 'bad_jwt', msg: 'synthetic expired link' } });
    if (options.authStatus && url.pathname.endsWith('/user')) return route.fulfill({ status: options.authStatus, json: { msg: 'synthetic transient failure' } });
    return route.fulfill({ json: url.pathname.endsWith('/user') ? user : {} });
  });
  return { updates: () => updates, apiCalls: () => apiCalls };
}

for (const status of [200, 400, 503]) {
  test(`solicitação de recuperação trata resposta ${status} sem expor conta ou mensagem do provedor`, async ({ page }) => {
    await simulate(page, { requestStatus: status });
    await page.goto('/app/');
    await page.getByRole('button', { name: 'Esqueci minha senha' }).click();
    await expect(page.getByLabel('Senha', { exact: true })).toHaveCount(0);
    await page.getByLabel('E-mail', { exact: true }).fill(user.email);
    await page.getByRole('button', { name: 'Enviar instruções' }).click();
    await expect(page.getByRole('status')).toHaveText(status === 503 ? 'Não foi possível solicitar agora. Aguarde e tente novamente.' :
      'Se houver uma conta para este e-mail, você receberá instruções para recuperar a senha.');
    await expect(page.getByText('synthetic private provider message')).toHaveCount(0);
    await page.getByRole('button', { name: 'Voltar ao login' }).click();
    await expect(page.getByRole('heading', { name: 'Que bom te ver.' })).toBeVisible();
  });
}

test('link de recuperação exige confirmação, trata erro e termina em novo login sem abrir dashboard', async ({ page }) => {
  const options = { updateFails: true }, calls = await simulate(page, options);
  await page.goto(link());
  await expect(page.getByLabel('Nova senha', { exact: true })).toBeVisible();
  await expect(page).not.toHaveURL(/access_token=/);
  await page.getByLabel('Nova senha', { exact: true }).fill('synthetic-new-password');
  await page.getByLabel('Confirmar nova senha').fill('synthetic-other-password');
  await page.getByRole('button', { name: 'Salvar nova senha' }).click();
  await expect(page.locator('main').getByRole('alert')).toHaveText('As senhas precisam ser iguais.'); expect(calls.updates()).toBe(0);
  await page.getByLabel('Confirmar nova senha').fill('synthetic-new-password');
  await page.getByRole('button', { name: 'Salvar nova senha' }).click();
  await expect(page.locator('main').getByRole('alert')).toHaveText('Não foi possível atualizar a senha. Tente novamente ou solicite outro link.');
  options.updateFails = false;
  await page.getByRole('button', { name: 'Salvar nova senha' }).click();
  await expect(page.getByRole('status')).toHaveText('Senha atualizada. Entre novamente com sua nova senha.');
  expect(calls.updates()).toBe(2); expect(calls.apiCalls()).toBe(0);
  await expect(page.getByRole('heading', { name: 'Uma visão tranquila.' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Voltar ao login' }).click();
  await expect(page.getByRole('heading', { name: 'Que bom te ver.' })).toBeVisible();
  await expect(page).toHaveURL('/app/');
});

test('renovação da mesma identidade preserva formulário de recuperação', async ({ page }) => {
  await page.clock.install(); const calls = await simulate(page);
  const renewed = page.waitForRequest(r => r.url().includes('grant_type=refresh_token'));
  await page.goto(link('recovery', 120));
  await page.getByLabel('Nova senha', { exact: true }).fill('synthetic-new-password');
  await page.clock.runFor(61000); await renewed;
  await expect(page.getByLabel('Nova senha', { exact: true })).toHaveValue('synthetic-new-password');
  expect(calls.apiCalls()).toBe(0);
  await page.getByRole('button', { name: 'Cancelar e sair' }).click();
  await expect(page.getByRole('heading', { name: 'Que bom te ver.' })).toBeVisible();
});

test('recuperação não altera senha quando a sessão passa a pertencer a outra identidade', async ({ page }) => {
  await page.clock.install(); const calls = await simulate(page, { refreshOwner: other });
  const renewed = page.waitForRequest(r => r.url().includes('grant_type=refresh_token'));
  await page.goto(link('recovery', 120));
  await page.clock.runFor(61000); await renewed;
  await expect(page.locator('main').getByRole('alert')).toHaveText('Link ausente, expirado ou de outra sessão. Solicite um novo link após sair.');
  await expect(page.getByRole('button', { name: 'Salvar nova senha' })).toHaveCount(0);
  expect(calls.updates()).toBe(0); expect(calls.apiCalls()).toBe(0);
});

test('parâmetro de recuperação sem evento PASSWORD_RECOVERY não autoriza troca', async ({ page }) => {
  const calls = await simulate(page);
  await page.goto(link('signup'));
  await expect(page.locator('main').getByRole('alert')).toHaveText('Link ausente, expirado ou de outra sessão. Solicite um novo link após sair.');
  await expect(page.getByLabel('Nova senha', { exact: true })).toHaveCount(0);
  expect(calls.updates()).toBe(0); expect(calls.apiCalls()).toBe(0);
  await page.getByRole('button', { name: 'Cancelar e sair' }).click();
  await expect(page.getByRole('heading', { name: 'Que bom te ver.' })).toBeVisible();
});

test('link expirado não permite atualizar senha nem consultar registros', async ({ page }) => {
  const calls = await simulate(page, { expired: true });
  await page.goto(link());
  await expect(page.locator('main').getByRole('alert')).toContainText('Link ausente, expirado ou de outra sessão');
  await expect(page.getByRole('button', { name: 'Salvar nova senha' })).toHaveCount(0);
  await expect(page).not.toHaveURL(/access_token=|refresh_token=/);
  expect(calls.updates()).toBe(0); expect(calls.apiCalls()).toBe(0);
});

for (const transient of [false, true]) {
  test(`callback ${transient ? 'com falha transitória' : 'malformado'} remove tokens após inicialização`, async ({ page }) => {
    const calls = await simulate(page, { authStatus: transient ? 503 : undefined });
    await page.goto(transient ? link() : link().replace('&token_type=bearer', ''));
    await expect(page.locator('main').getByRole('alert')).toContainText('Link ausente, expirado ou de outra sessão');
    await expect(page).not.toHaveURL(/access_token=|refresh_token=/);
    expect(calls.updates()).toBe(0); expect(calls.apiCalls()).toBe(0);
  });
}

test('resposta de atualização de outro usuário não libera recuperação ou dashboard', async ({ page }) => {
  const calls = await simulate(page, { updateOwner: other });
  await page.goto(link());
  await page.getByLabel('Nova senha', { exact: true }).fill('synthetic-new-password');
  await page.getByLabel('Confirmar nova senha').fill('synthetic-new-password');
  await page.getByRole('button', { name: 'Salvar nova senha' }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('Link ausente, expirado ou de outra sessão');
  await expect(page.getByText('Senha atualizada. Entre novamente com sua nova senha.')).toHaveCount(0);
  expect(calls.updates()).toBe(1); expect(calls.apiCalls()).toBe(0);
});
