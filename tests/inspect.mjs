import {chromium} from 'playwright';
import fs from 'node:fs';
fs.mkdirSync('tests/screenshots',{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:5175');
await page.getByRole('heading',{level:1}).waitFor();
for(let y=0;y<7000;y+=700){await page.evaluate(v=>window.scrollTo(0,v),y);await page.waitForTimeout(100)}
await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(1500);
await page.screenshot({path:'tests/screenshots/home-desktop.png',fullPage:true});
console.log('Desktop:',await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,images:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).length,canvases:document.querySelectorAll('canvas').length})));
await page.setViewportSize({width:390,height:844});await page.screenshot({path:'tests/screenshots/home-mobile.png',fullPage:true});
console.log('Mobile:',await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth})));console.log('Uncaught errors:',errors);
await browser.close();
