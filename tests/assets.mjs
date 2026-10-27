import {chromium} from 'playwright';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const failed=[];page.on('requestfailed',r=>failed.push([r.url(),r.failure()?.errorText]));
await page.goto('http://127.0.0.1:5175');await page.locator('h1').waitFor();await page.evaluate(()=>document.querySelectorAll('img').forEach(i=>i.loading='eager'));await page.waitForTimeout(3000);
console.log('Images using fallback:',await page.evaluate(()=>[...document.images].filter(i=>i.src.includes('fallback')).map(i=>i.alt)));
console.log('Failed requests:',failed);console.log('Image sample:',await page.locator('.category-card img').evaluateAll(imgs=>imgs.map(i=>({src:i.src,loaded:i.complete,width:i.naturalWidth}))));
await page.screenshot({path:'tests/screenshots/home-loaded.png',fullPage:true});await browser.close();
