import {chromium} from 'playwright';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:4174/');
await page.waitForTimeout(4000);
console.log('TITLE',await page.title());console.log('H1',await page.locator('h1').allTextContents());
await page.screenshot({path:'tests/home-desktop.png',fullPage:true});
console.log('ERRORS',JSON.stringify(errors));await browser.close();

