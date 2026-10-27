import {create} from 'zustand';
import {persist} from 'zustand/middleware';
import toast from 'react-hot-toast';
import {api,readDB,loadDB,onSessionExpired} from '../services/marketplaceApi';
export const useStore=create(persist((set,get)=>({user:null,cart:[],wishlist:[],db:readDB(),ready:false,loadError:null,drawer:false,searchOpen:false,
 init:async()=>{try{const user=await api.session();set({user});if(user){set({cart:await api.cart(),wishlist:await api.wishlist()})}await get().refresh();set({ready:true})}catch(e){set({loadError:e.message,ready:true})}},
 refresh:async()=>set({db:await loadDB(get().user?.role)}),
 login:async(email,password)=>{const guest=get().cart;const user=await api.login(email,password);set({user});const saved=await api.cart();const cart=saved.map(line=>({...line}));for(const line of guest){const match=cart.find(i=>i.productId===line.productId&&i.variant===line.variant);if(match)match.quantity+=line.quantity;else cart.push({...line})}if(cart.length)try{await api.syncCart(cart)}catch(e){set({cart:saved,wishlist:await api.wishlist()});await get().refresh();throw Error('Signed in, but your guest bag could not be merged: '+e.message)}set({cart,wishlist:await api.wishlist()});await get().refresh();return user},
 register:async values=>api.register(values),
 logout:async()=>{try{await api.logout();set({user:null,cart:[],wishlist:[]});await get().refresh();return true}catch(e){toast.error(e.message);return false}},
 setUser:async user=>{set({user});await get().refresh()},
 saveCart:async cart=>{const previous=get().cart;set({cart});if(get().user)try{set({cart:await api.syncCart(cart)})}catch(e){set({cart:previous});toast.error(e.message);return false}return true},
 add:async(productId,quantity=1,variant='Natural')=>{const p=get().db.products.find(p=>p.id===productId);const existing=get().cart.find(i=>i.productId===productId&&i.variant===variant);const all=get().cart.filter(i=>i.productId===productId).reduce((s,i)=>s+i.quantity,0);if(!p||all+quantity>p.stock)throw Error('Not enough stock available');return await get().saveCart(existing?get().cart.map(i=>i===existing?{...i,quantity:i.quantity+quantity}:i):[...get().cart,{productId,quantity,variant}])},
 quantity:async(productId,variant,quantity)=>{const p=get().db.products.find(p=>p.id===productId);if(quantity>0&&(!p||quantity>p.stock)){toast.error('Not enough stock');return}await get().saveCart(quantity<1?get().cart.filter(i=>!(i.productId===productId&&i.variant===variant)):get().cart.map(i=>i.productId===productId&&i.variant===variant?{...i,quantity}:i))},
 clearCart:()=>set({cart:[]}),toggleWish:async id=>{try{if(get().user)set({wishlist:await api.wish(id)});else set({wishlist:get().wishlist.includes(id)?get().wishlist.filter(x=>x!==id):[...get().wishlist,id]});return true}catch(e){toast.error(e.message);return false}},setDrawer:drawer=>set({drawer}),setSearch:searchOpen=>set({searchOpen})
}),{name:'forma-browser-bag-v3',partialize:s=>({cart:s.user?[]:s.cart,wishlist:s.user?[]:s.wishlist})}));
onSessionExpired(()=>useStore.setState({user:null,cart:[],wishlist:[]}));
