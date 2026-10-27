import fs from 'node:fs';
import {test,expect} from '@playwright/test';

for(const role of ['guest','customer','vendor','admin']){
 test(`${role} header wishlist opens saved products without a role denial`,async({page})=>{
  if(role!=='guest'){
   test.skip(process.env.DISPOSABLE_BROWSER_AUDIT!=='1','Role checks require generated isolated accounts');
   const accounts=new Map(fs.readFileSync(process.env.DEMO_CREDENTIALS_FILE,'utf8').split(/\r?\n/).map(line=>line.match(/^NEW LOCAL ACCOUNT (\S+) password: (.+)$/)).filter(Boolean).map(match=>[match[1],match[2]]));
   await page.goto('/login');
   await page.getByLabel('Email address',{exact:true}).fill(`${role}@ecommerce.test`);
   await page.getByLabel('Password',{exact:true}).fill(accounts.get(`${role}@ecommerce.test`));
   await page.getByRole('button',{name:'Sign in',exact:true}).click();
   await expect(page.locator('.dash-sidebar')).toBeVisible();
  }
  await page.goto('/shop');
  const card=page.locator('.product-card').first();
  const name=await card.locator('.product-name').innerText();
  const save=card.getByRole('button',{name:`Wishlist ${name}`,exact:true});
  if(!(await save.getAttribute('class')).includes('selected'))await save.click();
  await expect(save).toHaveClass(/selected/);
  await page.locator('.nav-icons').getByRole('link',{name:'Wishlist',exact:true}).click();
  await expect(page).toHaveURL(role==='customer'?/\/account\/wishlist$/:/\/wishlist$/);
  await expect(page.locator('.product-card').filter({hasText:name})).toBeVisible();
  await page.reload();
  await expect(page.locator('.product-card').filter({hasText:name})).toBeVisible();
 });
}
