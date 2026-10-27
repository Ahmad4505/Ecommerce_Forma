import axios from 'axios';
// Match the page's hostname in development so SameSite session cookies work
// whether the browser uses localhost or 127.0.0.1. Production uses its /api proxy.
const developmentApi=import.meta.env?.DEV&&typeof window!=='undefined'?`${window.location.protocol}//${window.location.hostname}:8000/api/`:'/api/';
export const client=axios.create({baseURL:import.meta.env?.VITE_API_BASE_URL||developmentApi,timeout:20000,withCredentials:true});
let csrfToken;
let sessionExpired=()=>{};
export const onSessionExpired=fn=>{sessionExpired=fn};
export async function csrf(){const {data}=await client.get('auth/csrf/');csrfToken=data.csrfToken;return csrfToken}
client.interceptors.request.use(async config=>{if(!['get','head','options'].includes(config.method)){if(!csrfToken)await csrf();config.headers['X-CSRFToken']=csrfToken}return config});
const validationMessages=value=>typeof value==='string'?value:value&&typeof value==='object'?Object.values(value).map(validationMessages).filter(Boolean).join(' '):'';
client.interceptors.response.use(r=>r,error=>{const status=error.response?.status;const details=error.response?.data?.error?.details;error.message=status>=500?'The service is temporarily unavailable. Please try again.':details?validationMessages(details):status===429?'Too many requests. Please wait and try again.':!error.response?'We could not reach the service. Please check your connection.':error.message;if(status===401)sessionExpired();return Promise.reject(error)});
const empty={products:[],vendors:[],users:[],categories:[],categoryRecords:[],orders:[],addresses:[],promotions:[],banners:[],reports:[],settings:{name:'Forma',shipping:8,freeShipping:150,newsletter:true}};
let snapshot=structuredClone(empty);
export const readDB=()=>snapshot;
async function allRecords(path){const rows=[];let next=path;let first=true;while(next){const {data}=await client.get(next,first?{params:{page_size:100}}:undefined);rows.push(...data.results);next=data.next;first=false}return rows}
export async function loadDB(role){const {data}=await client.get('bootstrap/');
 const paths={products:'products/',vendors:'vendors/',categoryRecords:'categories/',...(role?{orders:'orders/',addresses:'addresses/'}:{}),...(role==='admin'?{users:'admin/users/',promotions:'admin/promotions/',banners:'admin/banners/',reports:'admin/reports/'}:{})};
 await Promise.all(Object.entries(paths).map(async([collection,path])=>{if(data[collection]?.length===100)data[collection]=await allRecords(path)}));
 data.categories=data.categoryRecords.map(category=>category.name);
data.products=data.products.map(p=>({...p,price:Number(p.price),discountPrice:p.discountPrice===null?null:Number(p.discountPrice),createdAt:p.createdAt.slice(0,10),reviews:p.reviews.map(r=>({...r,date:r.date.slice(0,10)}))}));data.orders=data.orders.map(o=>({...o,date:o.date.slice(0,10),total:Number(o.total),items:o.items.map(i=>({...i,price:Number(i.price)}))}));data.settings.shipping=Number(data.settings.shipping);data.settings.freeShipping=Number(data.settings.freeShipping);snapshot=data;return data}
export function authorize(user,roles){if(!user||!roles.includes(user.role))throw Error('You do not have access to this action.')}
export const api={
 async login(email,password){await csrf();const {data}=await client.post('auth/login/',{email,password});await csrf();return data},
 async register(values){return (await client.post('auth/register/',values)).data},
 async logout(){await client.post('auth/logout/');csrfToken=null},
 async session(){return (await client.get('auth/session/')).data.user},
 async profile(user,values){return (await client.patch('auth/profile/',values)).data},
 async changePassword(values){const {data}=await client.post('auth/password-change/',values);await csrf();return data},
 async preferences(values){return (await client.patch('auth/preferences/',values)).data},
 async payments(page=1){return (await client.get('admin/payments/',{params:{page}})).data},
 async mutate(user,collection,record,remove=false){
  const paths={products:'products',vendors:'vendors',addresses:'addresses',users:'admin/users',promotions:'admin/promotions',banners:'admin/banners',reports:'admin/reports'};
  const path=paths[collection];if(!path)throw Error('Unsupported collection');
  const exists=snapshot[collection].some(r=>r.id===record.id);
  if(remove){await client.delete(`${path}/${record.id}/`);return}
  let values;
  if(collection==='products')values=Object.fromEntries(['name','slug','description','price','discountPrice','category','vendorId','stock','sku','featured','status'].filter(k=>record[k]!==undefined).map(k=>[k,record[k]]));
  else if(collection==='vendors')values=Object.fromEntries(['name','description','location','phone'].filter(k=>record[k]!==undefined).map(k=>[k,record[k]]));
  else values=record;
  let imageForm;
  if(collection==='products'){
   const old=snapshot.products.find(p=>p.id===record.id);
   const images=(record.images||[]).filter(url=>!old?.images?.includes(url));
   if(images.length){
    imageForm=new FormData();
    if(old&&record.images?.[0]!==old.images?.[0])imageForm.append('replace','true');
    for(const url of images){
     let response;
     try{response=await fetch(url)}catch{throw Error('The product image could not be loaded. Upload a local image.')}
     if(!response.ok)throw Error('The product image could not be loaded. Upload a local image.');
     imageForm.append('images',await response.blob(),'product.jpg');
    }
   }
  }
  const {data}=exists?await client.patch(`${path}/${record.id}/`,values):await client.post(`${path}/`,values);
  if(imageForm)try{await client.post(`products/${data.id}/images/`,imageForm)}catch(error){error.savedRecord=data;throw error}
  return data;
 },
 async checkout(user,cart,values,code,key){return (await client.post('orders/',{idempotency_key:key,items:cart,address:{name:values.name,street:values.street,city:values.city,zip:values.zip,country:values.country},code})).data},
 async orderStatus(user,id,status){return (await client.post(`orders/${id}/status/`,{status})).data},
 async review(user,productId,text,rating){await client.post('reviews/',{productId,text,rating})},
 async saveCategory(previous,name,remove=false){const category=snapshot.categoryRecords.find(c=>c.name===previous);if(remove)return client.delete(`categories/${category.id}/`);return category?client.patch(`categories/${category.id}/`,{name}):client.post('categories/',{name})},
 async settings(values){await client.patch('admin/settings/',values)},
 async decision(id,status,reason=''){await client.post(`vendors/${id}/decision/`,{status,reason})},
 async syncCart(cart){return (await client.put('cart/',cart)).data},
 async cart(){return (await client.get('cart/')).data},
 async wishlist(){return (await client.get('wishlist/')).data},
 async wish(productId){return (await client.post('wishlist/',{productId})).data},
 async payment(order_id,provider){return (await client.post('payments/',{order_id,provider})).data},
 async verifyPayment(id,mock_outcome){return (await client.post(`payments/${id}/verify/`,{mock_outcome})).data},
};
