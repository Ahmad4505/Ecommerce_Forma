import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const passwords=JSON.parse(fs.readFileSync('.setup/backend-smoke-credentials.json','utf8'));
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const context=await browser.newContext({baseURL:'http://localhost:5175'});
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
async function login(email,password){await page.goto('/login');await page.getByLabel('Email address',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click()}
try{
 await page.goto('/');await page.getByRole('heading',{name:/good|considered|everyday|thoughtful/i}).first().waitFor();
 await page.goto('/shop');await page.locator('.product-card').first().waitFor();
 const image=page.locator('.product-card img').first();await image.waitFor();assert(await image.evaluate(el=>el.complete&&el.naturalWidth>0));
 await login('pending.vendor@ecommerce.test',passwords.PENDING);await page.waitForURL('**/vendor-pending');
 await page.goto('/login');await login('admin@ecommerce.test',passwords.ADMIN);await page.waitForURL('**/admin');await page.goto('/admin/vendors');await page.getByRole('heading',{name:'Vendor applications.'}).waitFor();
 const pendingRow=page.getByRole('row').filter({hasText:'pending.vendor@ecommerce.test'});await pendingRow.getByRole('button',{name:'Approve',exact:true}).click();await pendingRow.getByText('APPROVED',{exact:true}).waitFor();
 await login('vendor@ecommerce.test',passwords.VENDOR);await page.waitForURL('**/vendor');await page.goto('/vendor/products');await page.getByRole('heading',{name:'Your products.'}).waitFor();
 await login('customer@ecommerce.test',passwords.CUSTOMER);await page.waitForURL('**/account');await page.goto('/shop');
 await page.locator('.product-card').first().getByRole('button',{name:/add/i}).click();
 await page.goto('/checkout');await page.getByLabel('Full name',{exact:true}).fill('Browser Buyer');await page.getByLabel('Email address',{exact:true}).fill('customer@ecommerce.test');await page.getByLabel('Street address',{exact:true}).fill('10 Main Street');await page.getByLabel('City',{exact:true}).fill('Portland');await page.getByLabel('Postal code',{exact:true}).fill('97201');await page.getByRole('button',{name:/Place demo order/}).click();await page.waitForURL('**/account/orders/**');
 for(const status of [400,401,403,404,405,408,409,413,422,429,500,502,503]){await page.goto('/errors/'+status);await page.getByText(`FORMA · ${status}`,{exact:true}).waitFor()}
 await page.goto('/does-not-exist');await page.getByText('FORMA · 404',{exact:true}).waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: catalog/image, four account roles, approval, vendor products, cart/mock checkout/order, all error routes; no page errors.');
}finally{await browser.close()}
