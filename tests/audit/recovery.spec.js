import {test,expect} from '@playwright/test';

test('malformed URL encoding keeps the not-found page and home navigation working',async({page})=>{
 const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');
 await expect(page.locator('main h1').first()).toBeVisible();
 await page.evaluate(()=>{
  history.pushState({},'', '/%E0%A4%A');
  dispatchEvent(new PopStateEvent('popstate'));
 });
 await expect(page.getByRole('link',{name:'Return to homepage',exact:true})).toBeVisible();
 await expect(page.locator('main .eyebrow').first()).toContainText('404');
 await page.getByRole('link',{name:'Return to homepage',exact:true}).click();
 await expect(page).toHaveURL(/\/$/);
 await expect(page.locator('main h1').first()).toBeVisible();
 expect(errors).toEqual([]);
});
