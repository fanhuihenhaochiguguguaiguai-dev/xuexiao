const CACHE='henan-campus-v05-hd-1';
const SHELL=['/','/style.css','/game.js','/pwa.js','/manifest.webmanifest','/assets/app-icon-192.png','/assets/app-icon-512.png','/assets/campus.glb','/assets/character.glb','/assets/world.json','/assets/benchmark-route.json','/assets/v05-config.json','/assets/v05/lighting-water.json','/assets/engine/glslang.js','/assets/engine/glslang.wasm','/assets/engine/twgsl.js','/assets/engine/twgsl.wasm'];
async function safeResponse(request,response){
 if(!response.ok||response.redirected||response.type==='opaque'||/no-store/i.test(response.headers.get('cache-control')||''))return false;
 const url=new URL(request.url||request,self.location.origin);
 if(url.pathname==='/')return (response.headers.get('content-type')||'').includes('text/html')&&(await response.clone().text()).includes('name="application-name" content="河南经贸3D数字校园"');
 return !((response.headers.get('content-type')||'').includes('text/html'));
}
self.addEventListener('install',event=>{event.waitUntil((async()=>{const cache=await caches.open(CACHE);await Promise.all(SHELL.map(async path=>{try{const request=new Request(path,{credentials:'same-origin',cache:'reload'}),r=await fetch(request);if(await safeResponse(request,r))await cache.put(path,r);}catch{}}));await self.skipWaiting();})());});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{await Promise.all((await caches.keys()).filter(k=>k.startsWith('henan-campus-')&&k!==CACHE).map(k=>caches.delete(k)));await self.clients.claim();})());});
self.addEventListener('fetch',event=>{
 const req=event.request,url=new URL(req.url);
 if(req.method!=='GET'||url.origin!==self.location.origin||(!SHELL.includes(url.pathname)&&req.mode!=='navigate'))return;
 event.respondWith((async()=>{const cache=await caches.open(CACHE),key=req.mode==='navigate'?'/':url.pathname;
  try{const response=await fetch(req);if(await safeResponse(new Request(key,{credentials:'same-origin'}),response))await cache.put(key,response.clone());return response;}
  catch(error){const saved=await cache.match(key);if(saved)return saved;throw error;}
 })());
});
