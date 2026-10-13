import { test, expect } from '@playwright/test';

for (const failure of ['prompt', 'choice']) {
  test(`instalação trata rejeição de ${failure} sem erro não capturado`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.getByText('Usar como aplicativo', { exact: true }).click();
    await page.evaluate(which => {
      const event = new Event('beforeinstallprompt', { cancelable: true });
      Object.defineProperties(event, {
        prompt: { value: () => which === 'prompt' ? Promise.reject(new Error('synthetic')) : Promise.resolve() },
        userChoice: { get: () => which === 'choice' ? Promise.reject(new Error('synthetic')) : Promise.resolve({ outcome: 'dismissed' }) },
      });
      window.dispatchEvent(event);
    }, failure);
    await page.getByRole('button', { name: 'Instalar aplicativo', exact: true }).click();
    await expect(page.getByRole('status')).toHaveText('Não foi possível abrir a instalação. Use as instruções do seu navegador.');
    await expect(page.getByRole('button', { name: 'Instalar aplicativo', exact: true })).toHaveCount(0);
    await expect(page.getByText(/No iPhone, abra no Safari/)).toBeVisible();
    expect(errors).toEqual([]);
  });
}
