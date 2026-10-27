import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const accounts=new Map(fs.readFileSync(process.env.DEMO_CREDENTIALS_FILE||'.setup/postgresql-demo-accounts-created.txt','utf8').split(/\r?\n/).map(line=>line.match(/^NEW LOCAL ACCOUNT (\S+) password: (.+)$/)).filter(Boolean).map(m=>[m[1],m[2]]));
const frontend=process.env.FRONTEND_TEST_URL||'http://127.0.0.1:5176';
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={visited:[],failures:[],warnings:[],abortedRequests:[]};
const safePath=url=>{try{const value=new URL(url);return value.origin+value.pathname}catch{return 'unknown'}};
function monitor(page,role){
 const source=()=>({role,page:safePath(page.url())});
 page.on('console',message=>{
  const entry={...source(),kind:'console',message:message.text().slice(0,500)};
  if(message.type()==='error')report.failures.push(entry);
  else if(message.type()==='warning')report.warnings.push(entry);
 });
 page.on('pageerror',error=>report.failures.push({...source(),kind:'runtime',message:error.message.slice(0,500)}));
 page.on('requestfailed',request=>{
  const entry={...source(),kind:'request',url:safePath(request.url()),message:request.failure()?.errorText};
  // Navigation can cancel downloads; retain that evidence separately.
  (entry.message==='net::ERR_ABORTED'?report.abortedRequests:report.failures).push(entry);
 });
 page.on('response',response=>{
  if(response.status()>=400)report.failures.push({...source(),kind:response.url().includes('/api/')?'api':'http',url:safePath(response.url()),status:response.status()});
 });
}
async function inspect(page,path,role){
 await page.goto(path);
 await page.locator('main h1,main h2').first().waitFor();
 await page.waitForLoadState('networkidle');
 assert.equal(await page.getByText('Something went wrong',{exact:true}).count(),0);
 report.visited.push({role,path});
}
try{
 const guest=await browser.newContext({baseURL:frontend});
 const page=await guest.newPage();monitor(page,'guest');
 for(const path of ['/','/shop','/categories','/vendors','/offers','/wishlist','/cart','/about','/contact','/faq','/privacy','/terms','/login','/register','/forgot-password','/reset-password','/resend-verification','/vendor-register'])await inspect(page,path,'guest');
 await page.goto('/shop');
 const product=await page.locator('.product-name').first().getAttribute('href');
 await inspect(page,product,'guest');await guest.close();
 for(const role of ['customer','vendor','admin','pending.vendor']){
  const context=await browser.newContext({baseURL:frontend});
  const view=await context.newPage();monitor(view,role);
  await view.goto('/login');
  await view.getByLabel('Email address',{exact:true}).fill(`${role}@ecommerce.test`);
  assert(accounts.has(`${role}@ecommerce.test`),'Local credential not found');
  await view.getByLabel('Password',{exact:true}).fill(accounts.get(`${role}@ecommerce.test`));
  await view.getByRole('button',{name:'Sign in',exact:true}).click();
  if(role==='pending.vendor'){
   await view.waitForURL('**/vendor-pending');await inspect(view,'/vendor-pending',role);
  }else{
   await view.locator('.dash-sidebar').waitFor();
   const links=await view.locator('.dash-sidebar nav a').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href')));
   for(const path of links)await inspect(view,path,role);
  }
  await context.close();
 }
 assert.deepEqual(report.failures,[]);
 console.log(`PASS: ${report.visited.length} public/dashboard page visits; no console errors, uncaught exceptions, non-aborted failed requests or HTTP/API errors. Warnings: ${report.warnings.length}; aborted requests: ${report.abortedRequests.length}.`);
}catch(error){
 report.failures.push({kind:'audit',message:error.message.slice(0,2000)});throw error;
}finally{
 await browser.close();
 if(process.env.CONSOLE_AUDIT_REPORT)fs.writeFileSync(process.env.CONSOLE_AUDIT_REPORT,JSON.stringify(report,null,2));
}
