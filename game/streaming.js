import {qualityProfile} from './quality-policy.js';
// Low-cost mapped solids remain visible while nearby facade zones stream in.
export function createZoneStreaming(app,campus,manifest,loadContainer,onLoaded=()=>{},onUnloaded=()=>{},initialProfile=qualityProfile('balanced')){
 let profile=initialProfile;
 const zones=manifest.zones.map(z=>({...z,asset:null,entity:null,loading:false,failed:false,lastFailure:null}));let loading=0,clock=0,disposed=0,lastPosition=null;
 const coarse=z=>z.coarse_nodes.map(name=>campus.findByName(name)).filter(Boolean);
 async function load(z){
  if(navigator.onLine===false)return;
  z.loading=true;loading++;
  try{
   const asset=await loadContainer(z.url);z.asset=asset;z.entity=asset.resource.instantiateRenderEntity();z.entity.name='Detail_zone_'+z.id;campus.addChild(z.entity);
   for(const r of z.entity.findComponents('render'))r.castShadows=['Stadium_ceremonial_platform','B20_grandstand','Grandstand_seating'].includes(r.entity.name);
   onLoaded(z.entity);for(const ob of coarse(z))ob.enabled=false;
  }catch(e){z.failed=true;z.lastFailure=String(e);}
  finally{z.loading=false;loading--;}
 }
 function reconcile(position,initial=false){
  lastPosition={...position};const candidates=zones.map(z=>({z,d:Math.hypot(z.x-position.x,z.z-position.z)})).sort((a,b)=>a.d-b.d);
  const retained=new Set(candidates.filter(({d})=>d<profile.unloadDistance).slice(0,profile.maxZones).map(({z})=>z));
  for(const {z} of candidates){
   if(z.entity&&!retained.has(z)){const old=z.entity;old.destroy();onUnloaded(old);z.entity=null;app.assets.remove(z.asset);z.asset.unload();z.asset=null;for(const ob of coarse(z))ob.enabled=true;disposed++;}
  }
  for(const {z,d} of candidates){
   const resident=zones.filter(z=>z.entity||z.loading).length;
   if(retained.has(z)&&d<profile.loadDistance&&!z.asset&&!z.loading&&!z.failed&&loading<profile.concurrency&&resident<profile.maxZones)load(z);
  }
 }
 async function initial(position){
  lastPosition={...position};const needed=zones.filter(z=>Math.hypot(z.x-position.x,z.z-position.z)<profile.loadDistance).sort((a,b)=>Math.hypot(a.x-position.x,a.z-position.z)-Math.hypot(b.x-position.x,b.z-position.z)).slice(0,profile.maxZones);
  for(let i=0;i<needed.length;i+=profile.concurrency)await Promise.all(needed.slice(i,i+profile.concurrency).map(load));
 }
 function update(dt,position){clock+=dt;if(clock<.35)return;clock=0;reconcile(position);}
 return {initial,update,reconcile,setProfile(next){profile=next;if(lastPosition)reconcile(lastPosition);},state:()=>({zones:zones.length,loaded:zones.filter(z=>z.entity).map(z=>z.id),loading,failed:zones.filter(z=>z.failed).map(z=>({id:z.id,error:z.lastFailure})),disposed,maxZones:profile.maxZones,loadDistance:profile.loadDistance,coarseFallbackAlwaysVisible:true,position:lastPosition})};
}
