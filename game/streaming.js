// Low-cost mapped solids remain visible while nearby facade zones stream in.
export function createZoneStreaming(app,campus,manifest,loadContainer,onLoaded=()=>{}){
 const zones=manifest.zones.map(z=>({...z,asset:null,entity:null,loading:false,failed:false,lastFailure:null}));let loading=0,clock=0,disposed=0,lastPosition=null;
 const coarse=z=>z.coarse_nodes.map(name=>campus.findByName(name)).filter(Boolean);
 async function load(z){
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
  for(const {z,d} of candidates){
   if(z.entity&&d>z.unload_distance_m){z.entity.destroy();z.entity=null;app.assets.remove(z.asset);z.asset.unload();z.asset=null;for(const ob of coarse(z))ob.enabled=true;disposed++;}
   if(d<z.load_distance_m&&!z.asset&&!z.loading&&!z.failed&&loading<2)load(z);
  }
 }
 async function initial(position){
  const needed=zones.filter(z=>Math.hypot(z.x-position.x,z.z-position.z)<z.load_distance_m).sort((a,b)=>Math.hypot(a.x-position.x,a.z-position.z)-Math.hypot(b.x-position.x,b.z-position.z));
  for(let i=0;i<needed.length;i+=2)await Promise.all(needed.slice(i,i+2).map(load));
 }
 function update(dt,position){clock+=dt;if(clock<.35)return;clock=0;reconcile(position);}
 return {initial,update,reconcile,state:()=>({zones:zones.length,loaded:zones.filter(z=>z.entity).map(z=>z.id),loading,failed:zones.filter(z=>z.failed).map(z=>({id:z.id,error:z.lastFailure})),disposed,coarseFallbackAlwaysVisible:true,position:lastPosition})};
}
