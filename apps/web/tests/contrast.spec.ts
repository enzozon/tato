import { test, expect } from '@playwright/test';

test('campos vazios de login têm limites distinguíveis das superfícies adjacentes', async ({ page }) => {
  await page.goto('/app/');
  for (const label of ['E-mail', 'Senha']) {
    const field = page.getByLabel(label, { exact: true });
    await expect(field).toBeVisible();
    await expect(field).toHaveValue('');
    const ratios = await field.evaluate(element => {
      const luminance = (color: string) => {
        const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {
          const channel = value / 255;
          return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
        });
        return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
      };
      const contrast = (first: string, second: string) => {
        const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
        return (values[0] + .05) / (values[1] + .05);
      };
      const style = getComputedStyle(element);
      let ancestor = element.parentElement!;
      while (getComputedStyle(ancestor).backgroundColor === 'rgba(0, 0, 0, 0)') {
        ancestor = ancestor.parentElement!;
      }
      return {
        borderWidth: parseFloat(style.borderTopWidth),
        inside: contrast(style.borderTopColor, style.backgroundColor),
        outside: contrast(style.borderTopColor, getComputedStyle(ancestor).backgroundColor),
      };
    });
    expect(ratios.borderWidth).toBeGreaterThan(0);
    expect(ratios.inside).toBeGreaterThanOrEqual(3);
    expect(ratios.outside).toBeGreaterThanOrEqual(3);
  }
});
