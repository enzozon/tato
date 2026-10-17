import { expect, type Page } from '@playwright/test';

export async function navigate(page:Page, name:string) {
  const button=page.locator('#app-navigation').getByRole('button',{name,exact:true,includeHidden:true});
  await expect(button).toBeAttached();
  // A barra lateral vira uma navegação recolhida no celular.
  if(!await button.isVisible())await page.getByRole('button',{name:'Menu',exact:true}).click();
  await button.click();
  await expect(button).toHaveAttribute('aria-current','page');
}
