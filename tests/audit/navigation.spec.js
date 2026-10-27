import fs from 'node:fs';
import {test,expect} from '@playwright/test';
const credentials=new Map(fs.readFileSync(process.env.DEMO_CREDENTIALS_FILE||'.setup/postgresql-demo-accounts-created.txt','utf8').split(/\r?\n/).map(line=>line.match(/^NEW LOCAL ACCOUNT (\S+) password: (.+)$/)).filter(Boolean).map(m=>[m[1],m[2]]));
function monitor(page){const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('Browser runtime error:',e.message)});page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=500)errors.push(`API ${r.status()}`)});return errors}
async function login(page,role){await page.goto('/login');await page.getByLabel('Email address',{exact:true}).fill(`${role}@ecommerce.test`);await page.getByLabel('Password',{exact:true}).fill(credentials.get(`${role}@ecommerce.test`));await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(new RegExp(role==='customer'?'/account$':role==='pending.vendor'?'/vendor-pending$':`/${role}$`))}
for(const [role,base] of [['customer','/account'],['vendor','/vendor'],['admin','/admin']])test(`${role} sidebar navigation, refresh and role boundary`,async({page})=>{const errors=monitor(page);await login(page,role);const links=await page.locator('.dash-sidebar nav a').evaluateAll(elements=>elements.map(e=>({href:e.getAttribute('href'),text:e.textContent})));for(const link of links){await page.locator(`.dash-sidebar nav a[href="${link.href}"]`).click();await expect(page).toHaveURL(new RegExp(`${link.href}$`));await expect(page.locator('main h1, main h2').first()).toBeVisible();await expect(page.getByText('Something went wrong',{exact:true})).toHaveCount(0)}await page.reload();await expect(page.locator('.dash-sidebar')).toBeVisible();await page.getByRole('button',{name:'Notifications',exact:true}).click();await expect(page.locator('.dropdown h4')).toBeVisible();await page.getByRole('button',{name:'Notifications',exact:true}).click();await expect(page.locator('.dropdown h4')).toHaveCount(0);await page.locator('.profile-trigger').click();await page.getByRole('link',{name:'Manage your account',exact:true}).click();await expect(page).toHaveURL(new RegExp(`${base}/${role==='vendor'?'store':role==='admin'?'settings':'profile'}$`));await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Open sidebar',exact:true}).click();await expect(page.locator('.dash-sidebar')).toHaveClass(/open/);await page.getByRole('button',{name:'Close sidebar',exact:true}).click();await expect(page.locator('.dash-sidebar')).not.toHaveClass(/open/);await page.setViewportSize({width:1280,height:720});if(role!=='admin'){await page.goto('/admin');await expect(page.getByRole('heading',{name:'This door is closed.'})).toBeVisible()}await page.goto(base);await page.locator('.sidebar-bottom').getByRole('button',{name:'Sign out'}).click();await expect(page).toHaveURL(/\/$/);await page.goto(base);await expect(page).toHaveURL(/\/login$/);expect(errors).toEqual([])});
test('public routes, search, product details, guest bag and protected checkout',async({page})=>{const errors=monitor(page);for(const route of ['/','/shop','/categories','/vendors','/offers','/wishlist','/cart','/about','/contact','/faq','/privacy','/terms','/register','/forgot-password','/reset-password','/vendor-register']){await page.goto(route);await expect(page.locator('main h1, main h2').first()).toBeVisible()}await page.goto('/shop');await expect(page.locator('.product-card').first()).toBeVisible();const product=page.locator('.product-card').first();await product.getByRole('button',{name:/add/i}).click();await page.goto('/cart');await expect(page.locator('main')).toContainText('1');await page.goto('/checkout');await expect(page).toHaveURL(/\/login$/);for(const code of [400,401,403,404,409,422,429,500,503]){await page.goto(`/errors/${code}`);await expect(page.locator('main .eyebrow')).toContainText(String(code))}await page.goto('/route-that-does-not-exist');await expect(page.locator('main .eyebrow')).toContainText('404');expect(errors).toEqual([])});
test('pending vendor cannot enter management',async({page})=>{await login(page,'pending.vendor');await page.goto('/vendor/products');await expect(page).toHaveURL(/\/vendor-pending$/)});
test('public catalog search, filters, details, quick view and mobile navigation',async({page})=>{await page.goto('/shop');await page.getByLabel('Search collection').fill('Arc Lounge Chair');await expect(page.locator('.product-card').first()).toBeVisible();await page.getByLabel('Sort products').selectOption('price-asc');await page.getByLabel('Minimum rating').selectOption('0');await page.locator('.product-card').first().getByRole('button',{name:/Quick view/}).click();await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);await page.locator('.product-card').first().locator('.product-name').click();await expect(page.locator('main h1')).toContainText('Arc Lounge Chair');await page.getByRole('button',{name:'Add to bag',exact:true}).click();await expect(page.getByText('A good choice. Added to your bag.',{exact:true})).toBeVisible();await page.goto('/categories');await page.locator('.category-card').first().click();await expect(page).toHaveURL(/\/category\//);await page.goto('/vendors');await page.locator('.vendor-card').first().click();await expect(page).toHaveURL(/\/vendor\//);await page.setViewportSize({width:390,height:844});await page.goto('/');await page.getByLabel('Toggle navigation').click();await expect(page.getByRole('link',{name:'Shop all',exact:true}).first()).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)});
test('Vite refuses development credentials, backend files and logs',async({request})=>{
 for(const path of ['/.setup/postgresql-demo-accounts-created.txt','/backend/.env','/backend/config/settings.py','/forma-dev.log']){
  const response=await request.get(path);expect([403,404]).toContain(response.status());
 }
});

test('header search, category menu and shopping bag buttons perform their actions',async({page})=>{
 const errors=monitor(page);
 await page.goto('/');
 await page.getByRole('button',{name:'Search products',exact:true}).click();
 const search=page.getByRole('dialog',{name:'Find your next favorite'});
 await expect(search).toBeVisible();
 await search.getByRole('textbox').fill('Arc Lounge Chair');
 await search.getByRole('button',{name:'Search',exact:true}).click();
 await expect(page).toHaveURL(/\/search\?q=Arc%20Lounge%20Chair$/);
 await expect(search).toHaveCount(0);
 await expect(page.locator('.product-card').first()).toBeVisible();
 await page.getByRole('button',{name:'Categories',exact:true}).click();
 await expect(page.locator('.mega')).toBeVisible();
 await page.locator('.mega-links a').first().click();
 await expect(page).toHaveURL(/\/category\//);
 await expect(page.locator('.mega')).toHaveCount(0);
 await page.goto('/shop');
 await page.locator('.product-card').first().getByRole('button',{name:/Add .* to bag/}).click();
 await expect(page.getByText('A good choice. Added to your bag.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Open shopping bag',exact:true}).click();
 const bag=page.getByRole('dialog',{name:'Shopping bag',exact:true});
 await expect(bag).toBeVisible();
 await bag.getByRole('button',{name:/^Increase /}).click();
 await expect(bag.locator('.quantity span')).toHaveText('2');
 await bag.getByRole('button',{name:/^Decrease /}).click();
 await expect(bag.locator('.quantity span')).toHaveText('1');
 await bag.getByRole('link',{name:'View shopping bag',exact:true}).click();
 await expect(page).toHaveURL(/\/cart$/);
 await expect(bag).toHaveCount(0);
 await page.getByRole('button',{name:'Open shopping bag',exact:true}).click();
 await bag.getByRole('button',{name:/^Remove /}).click();
 await expect(bag.getByRole('heading',{name:'Your next favorite is waiting.',exact:true})).toBeVisible();
 await bag.getByRole('button',{name:'Close bag',exact:true}).click();
 await expect(bag).toHaveCount(0);
 await page.getByRole('button',{name:'Search products',exact:true}).click();
 await search.getByRole('button',{name:'Close dialog',exact:true}).click();
 await expect(search).toHaveCount(0);
 expect(errors).toEqual([]);
});
