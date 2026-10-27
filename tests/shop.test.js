import test from 'node:test';
import assert from 'node:assert/strict';
import {totals,filterProducts,canAccess} from '../src/utils/shop.js';
import {products,categories,vendors} from '../src/data/seed.js';
test('catalog contains stable, related records',()=>{assert.equal(products.length,40);assert.equal(categories.length,8);assert.equal(vendors.length,5);for(const p of products){assert.ok(vendors.some(v=>v.id===p.vendorId));assert.ok(categories.some(c=>c.name===p.category));assert.ok(p.images[0].startsWith('https://'));}});
test('search, price, category and rating filters compose',()=>{const list=filterProducts(products,{q:'chair',category:'Furniture',max:300,rating:4.5,sort:'low'});assert.ok(list.length);assert.ok(list.every(p=>p.name.toLowerCase().includes('chair')&&p.category==='Furniture'));assert.deepEqual(filterProducts(products,{q:'doesnotexist'}),[]);});
test('cart totals use sale prices, shipping threshold, and promo',()=>{const p=products[0];const t=totals([{id:p.id,quantity:2}],products,'FORMA10');assert.equal(t.subtotal,p.discountPrice*2);assert.equal(t.shipping,0);assert.equal(t.total,t.subtotal*.9);assert.equal(totals([{id:'p4',quantity:1}],products).shipping,12);assert.equal(totals([],products).total,0);});
test('roles remain distinct',()=>{assert.equal(canAccess(null,['customer']),false);assert.equal(canAccess({role:'vendor'},['admin']),false);assert.equal(canAccess({role:'customer'},['customer']),true);});
