import {test} from 'node:test';
import assert from 'node:assert/strict';
import {api,client,readDB,loadDB} from '../src/services/marketplaceApi.js';
import {authDestination} from '../src/utils/auth.js';

test('browser login sends CSRF, rotates it after login, and uses credential cookies',async()=>{
 const requests=[];let counter=0;
 client.defaults.adapter=async config=>{requests.push(config);const data=config.url==='auth/csrf/'?{csrfToken:`csrf-${++counter}`}:{id:'server-user',name:'Buyer',role:'customer'};return {data,status:200,statusText:'OK',headers:{},config}};
 const user=await api.login('buyer@example.test','only-sent-to-backend');
 assert.equal(user.id,'server-user');const login=requests.find(r=>r.url==='auth/login/');assert.equal(login.headers['X-CSRFToken'],'csrf-1');assert.equal(login.withCredentials,true);
 await api.logout();assert.equal(requests.at(-1).headers['X-CSRFToken'],'csrf-2');
 assert.equal(readDB().users.length,0);
});

test('checkout sends product identities and quantities without browser-computed prices',async()=>{
 let request;
 client.defaults.adapter=async config=>{if(config.url==='auth/csrf/')return {data:{csrfToken:'csrf'},status:200,headers:{},config};request=config;return {data:{id:'order'},status:201,headers:{},config}};
 await api.checkout({},[{productId:'product',quantity:2}],{name:'Buyer',street:'Main Street',city:'Town',zip:'1234',country:'US'},'WELCOME10','checkout-key');
 const payload=JSON.parse(request.data);assert.deepEqual(payload.items,[{productId:'product',quantity:2}]);assert.equal(payload.idempotency_key,'checkout-key');assert.equal('total' in payload,false);assert.equal('price' in payload,false);
});

test('nested validation errors are readable and server internals stay hidden',async()=>{
 client.defaults.adapter=async()=>{throw {response:{status:422,data:{error:{details:{items:[{quantity:['Choose a positive quantity.']}]}}}}}};
 await assert.rejects(client.get('validation-test/'),error=>error.message==='Choose a positive quantity.');
 client.defaults.adapter=async()=>{throw {response:{status:500,data:{error:{details:'sensitive internal message'}}}}};
 await assert.rejects(client.get('server-test/'),error=>!error.message.includes('sensitive')&&error.message.includes('temporarily unavailable'));
});

test('bootstrap follows scoped pagination instead of truncating collections at 100',async()=>{
 const product=id=>({id:String(id),price:'10.00',discountPrice:null,createdAt:'2026-10-24T00:00:00Z',reviews:[]});
 const first=Array.from({length:100},(_,index)=>product(index));
 const requests=[];
 client.defaults.adapter=async config=>{
  requests.push(config.url);
  const data=config.url==='bootstrap/'?{products:first,vendors:[],users:[],categoryRecords:[],orders:[],addresses:[],promotions:[],banners:[],reports:[],settings:{shipping:'8.00',freeShipping:'150.00'}}:config.url==='products/'?{results:first,next:'products/?page=2'}:{results:[product(100)],next:null};
  return {data,status:200,headers:{},config};
 };
 const data=await loadDB();
 assert.equal(data.products.length,101);
 assert.deepEqual(requests,['bootstrap/','products/','products/?page=2']);
 assert.equal(data.products[100].price,10);
});

test('an unreachable image cannot leave a newly-created product behind',async()=>{
 const originalFetch=globalThis.fetch;const requests=[];
 client.defaults.adapter=async config=>{requests.push(config);return {data:{id:'created'},status:201,headers:{},config}};
 globalThis.fetch=async()=>{throw Error('Image host is unavailable')};
 try{
  await assert.rejects(api.mutate({role:'vendor'},'products',{id:'image-failure',name:'Image failure product',images:['https://image.invalid/unavailable.jpg']}),error=>error.message.includes('Upload a local image'));
  assert.equal(requests.length,0);
 }finally{globalThis.fetch=originalFetch}
});

test('login return paths respect roles and stay on the application',()=>{
 assert.equal(authDestination({role:'customer'},'/checkout?coupon=SAVE'),'/checkout?coupon=SAVE');
 assert.equal(authDestination({role:'admin'},'/checkout'),'/admin');
 assert.equal(authDestination({role:'vendor',vendorStatus:'APPROVED'},'/admin/vendors'),'/vendor');
 assert.equal(authDestination({role:'vendor',vendorStatus:'PENDING'},'/vendor/products'),'/vendor-pending');
 assert.equal(authDestination({role:'customer'},'//external.example'),'/account');
 assert.equal(authDestination({role:'customer'},'/\\external.example'),'/account');
});
