// Non-destructive checks against the configured local Django/PostgreSQL instance.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const credentials=new Map(fs.readFileSync(process.env.DEMO_CREDENTIALS_FILE||'.setup/postgresql-demo-accounts-created.txt','utf8').split(/\r?\n/).map(line=>line.match(/^NEW LOCAL ACCOUNT (\S+) password: (.+)$/)).filter(Boolean).map(match=>[match[1],match[2]]));
const frontend=process.env.FRONTEND_TEST_URL||'http://127.0.0.1:5176';
const backend=process.env.BACKEND_TEST_URL||'http://127.0.0.1:8000';
let stage='launch browser';
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 for(const role of ['customer','vendor','admin','pending.vendor']){
  stage=`${role}: load React`;
  const context=await browser.newContext({baseURL:frontend});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',()=>errors.push('page error'));
  await page.goto('/login');
  await page.getByLabel('Email address',{exact:true}).waitFor();
  stage=`${role}: authenticate through React`;
  const email=`${role}@ecommerce.test`;
  assert(credentials.has(email),'Local credential not found');
  await page.getByLabel('Email address',{exact:true}).fill(email);
  await page.getByLabel('Password',{exact:true}).fill(credentials.get(email));
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  const destination=role==='customer'?'/account':role==='pending.vendor'?'/vendor-pending':`/${role}`;
  await page.waitForURL(`**${destination}`,{timeout:20000});
  assert.deepEqual(errors,[]);
  console.log(`PASS: React session login ${role} -> ${destination}`);
  if(role==='customer'){
   stage='customer: API/CORS/CSRF checks';
   const result=await page.evaluate(async(root)=>{
    const catalog=await fetch(root+'/api/bootstrap/',{credentials:'include'});
    const data=await catalog.json();
    const csrf=await fetch(root+'/api/auth/csrf/',{credentials:'include'});
    const {csrfToken}=await csrf.json();
    const blocked=await fetch(root+'/api/auth/logout/',{method:'POST',credentials:'include'});
    const logout=await fetch(root+'/api/auth/logout/',{method:'POST',credentials:'include',headers:{'X-CSRFToken':csrfToken}});
    return {catalog:catalog.status,products:data.products.length,csrf:csrf.status,withoutCsrf:blocked.status,logout:logout.status};
   },backend);
   assert.deepEqual(result,{catalog:200,products:60,csrf:200,withoutCsrf:403,logout:204});
   console.log('PASS: browser cross-origin API, 60 products, CSRF retrieval, missing-CSRF rejection and secure logout');
  }
  await context.close();
 }
 stage='catalog photographs';
 const page=await browser.newPage();
 await page.goto(frontend+'/');
 await page.locator('.product-card img').first().waitFor();
 await page.waitForFunction(()=>{const image=document.querySelector('.product-card img');return image?.complete&&image.naturalWidth>0});
 console.log('PASS: React homepage renders Django product records and loads photography');
} catch {
 console.error(`FAIL: ${stage}. Inspect local server logs; credentials intentionally omitted.`);
 process.exitCode=1;
} finally {
 await browser.close();
}
