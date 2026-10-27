import * as pc from 'playcanvas';
// Preserve CPU image sources so a texture can shrink or grow without retaining
// two GPU allocations. Compressed WebP transfers are lossless normal maps.
export function createTextureQuality(app){
 const originals=new WeakMap(),textures=new Set(),roots=new Set();let limit=1024,changed=0,detail=null,albedo=null,detailStatus='loading',skipped=0,loaded=0;
 function resize(tex){
  if(!tex||tex.cubemap||!tex.getSource)return;const source=originals.get(tex)||tex.getSource();if(!source||ArrayBuffer.isView(source))return;
  if(!originals.has(tex))originals.set(tex,source);textures.add(tex);
  const max=Math.max(source.width||0,source.height||0),scale=Math.min(1,limit/max),width=Math.max(1,Math.round(source.width*scale)),height=Math.max(1,Math.round(source.height*scale));
  tex.anisotropy=Math.min(limit===2048?8:4,app.graphicsDevice.maxAnisotropy);
  if(tex.width===width&&tex.height===height)return;
  try{
   if(scale===1)tex.setSource(source);else{const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;canvas.getContext('2d').drawImage(source,0,0,width,height);tex.setSource(canvas);}
   tex.anisotropy=Math.min(8,app.graphicsDevice.maxAnisotropy);changed++;
  }catch{skipped++;}
 }
 function apply(root){
  roots.add(root);
  for(const render of root.findComponents('render'))for(const mesh of render.meshInstances){
   const m=mesh.material;
   if(albedo&&/V06_pale_stone|Library_photo_guided_stone|Library_granite_steps|V05_Pale_stone/.test(m.name)){m.diffuseMap=albedo;m.update();}
   if(detail&&/stone|wall|dorm|tower|admin|arcade|teaching|paving/i.test(m.name)&&!m.name.startsWith('Runtime_water')){m.normalDetailMap=detail;m.normalDetailMapBumpiness=.08;m.normalDetailMapTiling.set(3,3);m.update();}
   for(const key of ['diffuseMap','normalMap','normalDetailMap','aoMap','glossMap','metalnessMap'])resize(m[key]);
  }
 }
 if(navigator.onLine!==false)for(const [name,isColor] of [['stone-normal-2048.webp',false],['stone-basecolor-2048.webp',true]])app.assets.loadFromUrl('/assets/v06/'+name,'texture',(error,asset)=>{
  if(error){detailStatus='unavailable; embedded PBR retained';return;}if(isColor){albedo=asset.resource;albedo.srgb=true;}else{detail=asset.resource;detail.srgb=false;}loaded++;detailStatus=loaded===2?'loaded':'partial';for(const root of roots)if(!root._destroying)apply(root);
 });
 else detailStatus='offline; embedded PBR retained';
 return {apply,release(root){roots.delete(root);textures.clear();for(const live of roots)if(!live._destroying)apply(live);},setScale(scale){limit=scale>=1.49?2048:1024;for(const root of roots)if(!root._destroying)apply(root);},state:()=>({limit,trackedTextures:textures.size,resizes:changed,detailStatus,unsupportedSources:skipped,transferCompression:'LOSSLESS_WEBP',gpuBlockCompression:false})};
}
