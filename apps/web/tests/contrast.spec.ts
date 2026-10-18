import { test, expect } from '@playwright/test';
import identity from '../../../packages/mascot/identity.json';

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

test('login mantém foco visível e desativa animações com movimento reduzido', async ({ page }) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/app/');
  const email=page.getByLabel('E-mail',{exact:true});
  await email.focus();
  const outline=await email.evaluate(element=>{
    const style=getComputedStyle(element);
    return {width:parseFloat(style.outlineWidth),style:style.outlineStyle};
  });
  expect(outline.width).toBeGreaterThanOrEqual(2);
  expect(outline.style).not.toBe('none');
  const animated=await page.locator('body *').evaluateAll(elements=>elements.filter(element=>{
    if(!element.checkVisibility())return false;
    const style=getComputedStyle(element);
    return style.animationName!=='none'&&style.animationDuration.split(',').some(value=>parseFloat(value)>.001);
  }).map(element=>element.className));
  expect(animated).toEqual([]);
});

test('cenários do mascote preservam o nome acessível e respeitam movimento reduzido', async ({ page }) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  for(const screen of ['landing','login','recuperação']){
    if(screen==='landing')await page.goto('/');
    if(screen==='login')await page.goto('/app/');
    if(screen==='recuperação')await page.getByRole('button',{name:'Esqueci minha senha',exact:true}).click();
    const mascot=page.locator('svg.mascot').filter({has:page.locator('.mascot-scene')});
    await expect(mascot).toHaveCount(1);
    await expect(mascot).toHaveAccessibleName(`${identity.name}: calmo`);
    await expect(mascot.locator('.mascot-scene')).toHaveAttribute('aria-hidden','true');
    expect(await mascot.evaluate(element=>element.getAnimations({subtree:true}).length)).toBe(0);
  }
});
