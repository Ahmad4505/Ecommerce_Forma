import fs from 'node:fs';
import {test,expect} from '@playwright/test';

test.use({viewport:{width:390,height:844}});
test.skip(process.env.DISPOSABLE_BROWSER_AUDIT!=='1','Mobile mutations require the isolated PostgreSQL harness');
const unavailable='The service is temporarily unavailable. Please try again.';
async function login(page,role){
 const credentials=new Map(fs.readFileSync(process.env.DEMO_CREDENTIALS_FILE,'utf8').split(/\r?\n/).map(line=>line.match(/^NEW LOCAL ACCOUNT (\S+) password: (.+)$/)).filter(Boolean).map(match=>[match[1],match[2]]));
 await page.goto('/login');
 await page.getByLabel('Email address',{exact:true}).fill(`${role}@ecommerce.test`);
 await page.getByLabel('Password',{exact:true}).fill(credentials.get(`${role}@ecommerce.test`));
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page).toHaveURL(role==='customer'?/\/account$/:new RegExp(`/${role}$`));
}
async function navigate(page,label,path){
 await page.getByRole('button',{name:'Open sidebar',exact:true}).click();
 await page.locator('.dash-sidebar nav').getByRole('link',{name:label,exact:true}).click();
 await expect(page).toHaveURL(new RegExp(`${path}$`));
 await expect(page.locator('.dash-sidebar')).not.toHaveClass(/open/);
}
async function fit(page){expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true)}
async function failWrites(page,pattern,method){
 const handler=route=>route.request().method()===method?route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{status:503,details:'Injected test-only service failure'}})}):route.continue();
 await page.route(pattern,handler);
 return ()=>page.unroute(pattern,handler);
}

test('mobile customer profile failure retains edits; retry and address save persist',async({page})=>{
 await login(page,'customer');
 await navigate(page,'My profile','/account/profile');
 const name=page.getByLabel('Full name',{exact:true});
 const original=await name.inputValue();
 await name.fill('Mobile Audit Buyer');
 const restore=await failWrites(page,'**/api/auth/profile/','PATCH');
 await page.getByRole('button',{name:'Save your details'}).click();
 await expect(page.getByText(unavailable,{exact:true})).toBeVisible();
 await expect(name).toHaveValue('Mobile Audit Buyer');
 await expect(page.getByText('Your profile is up to date.',{exact:true})).toHaveCount(0);
 const session=await page.request.get(process.env.BACKEND_TEST_URL+'/api/auth/session/');
 expect((await session.json()).user.name).toBe(original);
 await restore();
 await page.getByRole('button',{name:'Save your details'}).click();
 await expect(page.getByText('Your profile is up to date.',{exact:true})).toBeVisible();
 await page.reload();
 await expect(name).toHaveValue('Mobile Audit Buyer');
 await fit(page);
 await name.fill(original);
 const saved=page.waitForResponse(response=>response.url().endsWith('/api/auth/profile/')&&response.request().method()==='PATCH'&&response.ok());
 await page.getByRole('button',{name:'Save your details'}).click();await saved;
 await navigate(page,'My addresses','/account/addresses');
 await page.getByRole('button',{name:'Add an address'}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByLabel(/^Label/).fill('Mobile Home');
 for(const [label,value] of [['Full name','Mobile Buyer'],['Street address','45 Mobile Avenue'],['City','Portland'],['Postal code','97201'],['Country','United States']])await dialog.getByLabel(label,{exact:true}).fill(value);
 await dialog.getByRole('button',{name:'Save address'}).click();
 await expect(dialog).toHaveCount(0);
 await page.reload();
 await expect(page.getByRole('heading',{name:'Mobile Home',exact:true})).toBeVisible();
 await fit(page);
});

test('mobile vendor product failure preserves form; real create and edit persist',async({page})=>{
 await login(page,'vendor');
 await navigate(page,'Add product','/vendor/products/new');
 await page.getByLabel('Product name',{exact:true}).fill('Mobile Audit Stool');
 await page.getByLabel('Description',{exact:true}).fill('A stool created through the real mobile vendor product workflow.');
 await page.getByLabel('Regular price ($)',{exact:true}).fill('95');
 await page.getByLabel('Stock quantity',{exact:true}).fill('5');
 await page.getByLabel('Or upload a product photo').setInputFiles(process.env.AUDIT_IMAGE);
 const restore=await failWrites(page,'**/api/products/','POST');
 await page.getByRole('button',{name:'Save product',exact:true}).click();
 await expect(page.getByRole('alert')).toHaveText(unavailable);
 await expect(page).toHaveURL(/\/vendor\/products\/new$/);
 await expect(page.getByLabel('Product name',{exact:true})).toHaveValue('Mobile Audit Stool');
 const absent=await page.request.get(process.env.BACKEND_TEST_URL+'/api/products/?search=Mobile%20Audit%20Stool');
 expect((await absent.json()).count).toBe(0);
 await fit(page);await restore();
 await page.getByRole('button',{name:'Save product',exact:true}).click();
 await expect(page).toHaveURL(/\/vendor\/products$/);
 await page.getByLabel('Search products').fill('Mobile Audit Stool');
 await page.getByRole('link',{name:'Edit Mobile Audit Stool',exact:true}).click();
 await page.getByLabel('Regular price ($)',{exact:true}).fill('99');
 await page.getByRole('button',{name:'Save product',exact:true}).click();
 await expect(page).toHaveURL(/\/vendor\/products$/);
 await page.reload();await page.getByLabel('Search products').fill('Mobile Audit Stool');
 await expect(page.getByRole('row').filter({hasText:'Mobile Audit Stool'})).toContainText('$99.00');
 await fit(page);
});

test('mobile vendor application and admin decision recover from a failed approval',async({page})=>{
 await page.goto('/vendor-register');
 for(const [label,value] of [['Full name','Mobile Maker'],['Email','mobile.pending@ecommerce.test'],['Password (12+ characters)','Mobile-vendor-only-password-4839!'],['Store name','Mobile Review Studio'],['Phone','1234567890'],['Business address','45 Mobile Business Street']])await page.getByLabel(label,{exact:true}).fill(value);
 await page.getByLabel('Your store story').fill('A dedicated mobile application created in the disposable test database.');
 await page.getByLabel('Store logo').setInputFiles(process.env.AUDIT_IMAGE);
 await page.getByRole('button',{name:'Submit application'}).click();
 await expect(page.getByRole('heading',{name:'Application received.',exact:true})).toBeVisible();
 await login(page,'admin');await navigate(page,'Vendors','/admin/vendors');
 const row=page.getByRole('row').filter({hasText:'mobile.pending@ecommerce.test'});
 const restore=await failWrites(page,'**/api/vendors/*/decision/','POST');
 await row.getByRole('button',{name:'Approve',exact:true}).click();
 await expect(page.getByText(unavailable,{exact:true})).toBeVisible();
 await expect(row.getByText('PENDING',{exact:true})).toBeVisible();
 await restore();await row.getByRole('button',{name:'Approve',exact:true}).click();
 await expect(row.getByText('APPROVED',{exact:true})).toBeVisible();
 await page.reload();await expect(row.getByText('APPROVED',{exact:true})).toBeVisible();
 await fit(page);
});

test('mobile checkout failure preserves cart; retry creates one paid mock order',async({page})=>{
 await login(page,'customer');
 const before=await page.request.get(process.env.BACKEND_TEST_URL+'/api/orders/');
 const count=(await before.json()).count;
 await page.goto('/shop');
 await page.locator('.product-card').first().getByRole('button',{name:/Add .* to bag/}).click();
 await expect(page.getByText('A good choice. Added to your bag.',{exact:true})).toBeVisible();
 await page.goto('/checkout');
 for(const [label,value] of [['Full name','Mobile Buyer'],['Street address','51 Mobile Checkout Street'],['City','Portland'],['Postal code','97201'],['Country','United States']])await page.getByLabel(label,{exact:true}).fill(value);
 const restore=await failWrites(page,'**/api/orders/','POST');
 await page.getByRole('button',{name:/Place demo order/}).click();
 await expect(page.getByText(unavailable,{exact:true})).toBeVisible();
 await expect(page).toHaveURL(/\/checkout$/);
 const unchanged=await page.request.get(process.env.BACKEND_TEST_URL+'/api/orders/');
 expect((await unchanged.json()).count).toBe(count);
 const cart=await page.request.get(process.env.BACKEND_TEST_URL+'/api/cart/');
 expect((await cart.json()).length).toBeGreaterThan(0);
 await fit(page);await restore();
 await page.getByRole('button',{name:/Place demo order/}).click();
 await expect(page).toHaveURL(/\/account\/orders\/.*confirmed=1/);
 await expect(page.locator('main')).toContainText('SUCCEEDED');
 await page.reload();await expect(page.locator('main')).toContainText('51 Mobile Checkout Street');
 const after=await page.request.get(process.env.BACKEND_TEST_URL+'/api/orders/');
 expect((await after.json()).count).toBe(count+1);
});

test('mobile logout failure retains session and retry signs out',async({page})=>{
 await login(page,'customer');
 const restore=await failWrites(page,'**/api/auth/logout/','POST');
 await page.locator('.profile-trigger').click();
 await page.locator('.dropdown').getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByText(unavailable,{exact:true})).toBeVisible();
 await expect(page).toHaveURL(/\/account$/);
 const session=await page.request.get(process.env.BACKEND_TEST_URL+'/api/auth/session/');
 expect((await session.json()).user.role).toBe('customer');
 await restore();
 await page.locator('.dropdown').getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page).toHaveURL(/\/$/);
 const signedOut=await page.request.get(process.env.BACKEND_TEST_URL+'/api/auth/session/');
 expect((await signedOut.json()).user).toBeNull();
});

test('mobile payment verification retry reuses its order and stock reservation',async({page})=>{
 await login(page,'customer');
 const before=await page.request.get(process.env.BACKEND_TEST_URL+'/api/orders/');
 const count=(await before.json()).count;
 await page.goto('/shop');
 await page.locator('.product-card').first().getByRole('button',{name:/Add .* to bag/}).click();
 await expect(page.getByText('A good choice. Added to your bag.',{exact:true})).toBeVisible();
 const cart=await page.request.get(process.env.BACKEND_TEST_URL+'/api/cart/');
 const line=(await cart.json())[0];
 const productUrl=process.env.BACKEND_TEST_URL+`/api/products/${line.productId}/`;
 const product=await page.request.get(productUrl);
 const initialStock=(await product.json()).stock;
 await page.goto('/checkout');
 for(const [label,value] of [['Full name','Mobile Buyer'],['Street address','52 Mobile Payment Retry Street'],['City','Portland'],['Postal code','97201'],['Country','United States']])await page.getByLabel(label,{exact:true}).fill(value);
 const restore=await failWrites(page,'**/api/payments/*/verify/','POST');
 await page.getByRole('button',{name:/Place demo order/}).click();
 await expect(page.getByText(unavailable,{exact:true})).toBeVisible();
 await expect(page).toHaveURL(/\/checkout$/);
 const failed=await page.request.get(process.env.BACKEND_TEST_URL+'/api/orders/');
 const pending=await failed.json();
 expect(pending.count).toBe(count+1);
 const order=pending.results.find(item=>item.address.includes('52 Mobile Payment Retry Street'));
 expect(order.payment_status).toBe('PENDING');
 const reserved=await page.request.get(productUrl);
 expect((await reserved.json()).stock).toBe(initialStock-line.quantity);
 await restore();
 await page.getByRole('button',{name:/Place demo order/}).click();
 await expect(page).toHaveURL(new RegExp(`/account/orders/${order.id}\\?confirmed=1$`));
 await expect(page.locator('main')).toContainText('SUCCEEDED');
 const after=await page.request.get(process.env.BACKEND_TEST_URL+'/api/orders/');
 expect((await after.json()).count).toBe(count+1);
 const finalProduct=await page.request.get(productUrl);
 expect((await finalProduct.json()).stock).toBe(initialStock-line.quantity);
});
