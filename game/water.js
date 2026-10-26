import * as pc from 'playcanvas';
// Shared StandardMaterial is compiled by PlayCanvas for both WebGPU and WebGL 2.
// Static scene cubemaps are captured once; the procedural sky is a fallback.
export function enhanceWater(app,campus,mainCamera,metadata={water:[]}){
 const device=app.graphicsDevice,size=128,canvas=document.createElement('canvas');canvas.width=canvas.height=size;
 const ctx=canvas.getContext('2d'),image=ctx.createImageData(size,size),colorCanvas=document.createElement('canvas');colorCanvas.width=colorCanvas.height=size;
 const colorCtx=colorCanvas.getContext('2d'),colors=colorCtx.createImageData(size,size);
 const height=(x,y)=>Math.sin(x*2*Math.PI/size*7+y*2*Math.PI/size*3)*.42+Math.sin(x*2*Math.PI/size*3-y*2*Math.PI/size*8)*.29+Math.sin(x*2*Math.PI/size*13+y*2*Math.PI/size*11)*.09;
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const dx=(height(x+1,y)-height(x-1,y))*.62,dy=(height(x,y+1)-height(x,y-1))*.62,n=Math.hypot(dx,dy,1),i=(y*size+x)*4;
  image.data[i]=Math.round((-dx/n*.5+.5)*255);image.data[i+1]=Math.round((-dy/n*.5+.5)*255);image.data[i+2]=Math.round((1/n*.5+.5)*255);image.data[i+3]=255;
  const tint=height(x,y)*.04+1;colors.data[i]=Math.round(112*tint);colors.data[i+1]=Math.round(151*tint);colors.data[i+2]=Math.round(139*tint);colors.data[i+3]=255;
 }
 ctx.putImageData(image,0,0);
 colorCtx.putImageData(colors,0,0);const color=new pc.Texture(device,{name:'Water_subtle_current_color',width:size,height:size,mipmaps:true,addressU:pc.ADDRESS_REPEAT,addressV:pc.ADDRESS_REPEAT});color.setSource(colorCanvas);
 const normal=new pc.Texture(device,{name:'Water_periodic_wave_normals',width:size,height:size,mipmaps:true,addressU:pc.ADDRESS_REPEAT,addressV:pc.ADDRESS_REPEAT,minFilter:pc.FILTER_LINEAR_MIPMAP_LINEAR,magFilter:pc.FILTER_LINEAR});normal.setSource(canvas);
 const faces=[];
 for(let face=0;face<6;face++){
  const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d'),gradient=g.createLinearGradient(0,0,0,64);
  if(face===2){gradient.addColorStop(0,'#8cb7ce');gradient.addColorStop(1,'#c1d4d5');}
  else if(face===3){gradient.addColorStop(0,'#677c67');gradient.addColorStop(1,'#a4b2a1');}
  else{gradient.addColorStop(0,'#87adbd');gradient.addColorStop(.65,'#c4d2cb');gradient.addColorStop(1,'#82927b');}
  g.fillStyle=gradient;g.fillRect(0,0,64,64);faces.push(c);
  if(face!==3){g.globalAlpha=.16;g.fillStyle='#f3f2e4';g.filter='blur(3px)';for(let i=0;i<5;i++){g.beginPath();g.ellipse((i*23+face*9)%76,17+(i%3)*5,13,3,0,0,Math.PI*2);g.fill();}g.filter='none';g.globalAlpha=1;}
 }
 const sky=new pc.Texture(device,{name:'Water_procedural_sky_reflection',cubemap:true,width:64,height:64,mipmaps:true});sky.setSource(faces);
 const mat=new pc.StandardMaterial();mat.name='Campus_water_ripples';mat.diffuse=new pc.Color(.23,.42,.36);mat.diffuseMap=color;mat.diffuseMapTiling=new pc.Vec2(.33,.33);mat.specular=new pc.Color(.025,.025,.025);
 mat.useMetalness=false;mat.gloss=.91;mat.fresnelModel=pc.FRESNEL_SCHLICK;mat.reflectivity=.9;mat.cubeMap=app.scene.skybox||sky;
 mat.normalMap=normal;mat.bumpiness=.18;mat.normalMapTiling=new pc.Vec2(.55,.55);
 mat.normalDetailMap=normal;mat.normalDetailMapTiling=new pc.Vec2(.91,.73);mat.normalDetailMapBumpiness=.05;
 // The engine's clear-coat lobe supplies angular Fresnel reflectance; the old
 // low-intensity legacy specular path suppressed it at the water horizon.
 mat.clearCoat=1;mat.clearCoatGloss=.97;mat.clearCoatNormalMap=normal;mat.clearCoatNormalMapTiling=new pc.Vec2(.55,.55);mat.clearCoatBumpiness=.1;mat.refraction=0;mat.refractionIndex=1/1.333;mat.thickness=.3;mat.attenuation=new pc.Color(.42,.65,.52);mat.attenuationDistance=3;
 mat.cull=pc.CULLFACE_BACK;mat.update();let surfaces=0;
 const materials=[],pondIndices=[],materialByObject=new Map();let depthMapped=0;
 const isWater=m=>m.name==='water'||m.name.startsWith('V05_water_');
 const waterLayer=new pc.Layer({name:'Water_excluded_from_reflection_capture'});app.scene.layers.insert(waterLayer,app.scene.layers.getOpaqueIndex(pc.LAYERID_SKYBOX)+1);
 mainCamera.camera.layers=[...mainCamera.camera.layers,waterLayer.id];
 for(const render of campus.findComponents('render')){
  if(render.meshInstances.every(m=>isWater(m.material)))render.layers=[waterLayer.id];
  for(const mesh of render.meshInstances)if(isWater(mesh.material)){
   const key=render.entity.name;
   if(!materialByObject.has(key)){
    const m=mat.clone();m.name='Runtime_water_'+key;const info=metadata.water.find(w=>key===w.object)||metadata.water.find(w=>key.endsWith(w.object));
    if(info&&mesh.material.diffuseMap){
     m.diffuseMap=mesh.material.diffuseMap;m.diffuse.set(.8,.8,.8);m.diffuseMapTiling.set(1,1);m.campusDepthAnchored=true;
     const width=info.blender_bounds[2]-info.blender_bounds[0],depth=info.blender_bounds[3]-info.blender_bounds[1];
     m.normalMapTiling.set(width/14,depth/14);m.clearCoatNormalMapTiling.copy(m.normalMapTiling);m.normalDetailMapTiling.set(width/8,depth/8);depthMapped++;
    }
    m.update();materialByObject.set(key,m);materials.push(m);pondIndices.push(/north/.test(key)?0:1);
   }
   mesh.material=materialByObject.get(key);surfaces++;
  }
 }
 // Capture the existing scene once per pond. This gives actual draft-building
 // reflections without paying for a second scene render on every phone frame.
 const hdr=!!device.textureHalfFloatRenderable,queue=[],cubes=[],origins=[[-131,.65,-23],[67,.65,-7]],directions=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],ups=[[0,-1,0],[0,-1,0],[0,0,1],[0,0,-1],[0,-1,0],[0,-1,0]];
 for(const [pond,origin] of [[0,[-131,.65,-23]],[1,[67,.65,-7]]]){
  const cube=new pc.Texture(device,{name:'Existing_scene_pond_reflection_'+pond,cubemap:true,width:128,height:128,format:hdr?pc.PIXELFORMAT_RGBA16F:pc.PIXELFORMAT_RGBA8,mipmaps:false,minFilter:pc.FILTER_LINEAR,magFilter:pc.FILTER_LINEAR});cubes.push(cube);
  for(let face=0;face<6;face++){
   const c=new pc.Entity('Reflection_capture_'+pond+'_'+face),rt=new pc.RenderTarget({colorBuffer:cube,face,depth:true});
   c.addComponent('camera',{clearColor:new pc.Color(.68,.79,.82),fov:90,aspectRatio:1,aspectRatioMode:pc.ASPECT_MANUAL,nearClip:.12,farClip:440,priority:-10,renderTarget:rt,layers:mainCamera.camera.layers.filter(id=>id!==waterLayer.id)});
   c.camera.toneMapping=hdr?pc.TONEMAP_NONE:pc.TONEMAP_ACES;c.camera.gammaCorrection=pc.GAMMA_NONE;
   c.setPosition(...origin);const d=directions[face];c.lookAt(new pc.Vec3(origin[0]+d[0],origin[1]+d[1],origin[2]+d[2]),new pc.Vec3(...ups[face]));c.enabled=false;app.root.addChild(c);queue.push(c);
  }
 }
 let capturedFaces=0,captureSucceeded=false,resolveCapture,timeout=null,captureTimedOut=false;const ready=new Promise(resolve=>{resolveCapture=resolve;});
 let current=-1;
 const capture=()=>{
  if(current===-1)timeout=setTimeout(()=>{app.off('postrender',capture);for(const c of queue)c.enabled=false;captureTimedOut=true;resolveCapture();},60000);
  if(current>=0){queue[current].enabled=false;capturedFaces++;}
  current++;
  if(current<queue.length)queue[current].enabled=true;
  else{app.off('postrender',capture);clearTimeout(timeout);materials.forEach((m,i)=>{m.cubeMap=cubes[pondIndices[i]];m.update();});captureSucceeded=true;resolveCapture();}
 };
 app.on('postrender',capture);
 let time=0,dynamicFaces=0,dynamicCurrent=null,dynamicNextFace=0,lastDynamic=0,localEnabled=true,localPosition=null,forced=0,refractionActive=false;const started=performance.now();
 app.on('postrender',()=>{
  if(dynamicCurrent!==null){queue[dynamicCurrent].enabled=false;dynamicFaces++;if(!captureSucceeded){capturedFaces++;if(capturedFaces===12){materials.forEach((m,i)=>{m.cubeMap=cubes[pondIndices[i]];m.update();});captureSucceeded=true;}}dynamicCurrent=null;return;}
  const now=performance.now(),budget=(app.stats.frame.ms||0)<45;
  if((!captureSucceeded&&!captureTimedOut)||!localPosition||!localEnabled||(!budget&&!forced)||now-lastDynamic<1500&&!forced)return;
  const distances=origins.map(o=>Math.hypot(o[0]-localPosition.x,o[2]-localPosition.z)),pond=distances[0]<distances[1]?0:1;
  if(distances[pond]>85&&!forced)return;
  dynamicCurrent=captureSucceeded?pond*6+dynamicNextFace:capturedFaces;dynamicNextFace=(dynamicNextFace+1)%6;queue[dynamicCurrent].enabled=true;lastDynamic=now;forced=Math.max(0,forced-1);
 });
 const wakeCanvas=document.createElement('canvas');wakeCanvas.width=wakeCanvas.height=64;const wg=wakeCanvas.getContext('2d'),wi=wg.createImageData(64,64);
 for(let y=0;y<64;y++)for(let x=0;x<64;x++){const r=Math.hypot(x-31.5,y-31.5)/31.5,i=(y*64+x)*4;wi.data.set([210,232,223,Math.round(Math.exp(-Math.pow((r-.72)/.055,2))*190)],i);}wg.putImageData(wi,0,0);
 const wakeTexture=new pc.Texture(device,{width:64,height:64,mipmaps:true});wakeTexture.setSource(wakeCanvas);const wakes=[];
 for(let i=0;i<10;i++){const m=new pc.StandardMaterial();m.useLighting=false;m.diffuse=new pc.Color(.7,.85,.78);m.opacityMap=wakeTexture;m.opacityMapChannel='a';m.blendType=pc.BLEND_NORMAL;m.depthWrite=false;m.update();const e=new pc.Entity('Water_contact_ripple_'+i);e.addComponent('render',{type:'plane',material:m,castShadows:false,layers:[waterLayer.id]});e.enabled=false;app.root.addChild(e);wakes.push({entity:e,material:m,age:2});}
 let lastWake=0,wakeCursor=0;
 return {surfaces,ready,reflection:'ONCE_CAPTURED_SCENE_CUBEMAPS_WITH_SKY_FALLBACK_NOT_PLANAR',
  update(dt,position,enabled=true,contact=null){time=(performance.now()-started)/1000;localPosition=position;localEnabled=enabled;for(const m of materials){m.normalMapOffset.set((time*.009)%1,(time*.004)%1);m.clearCoatNormalMapOffset.copy(m.normalMapOffset);m.normalDetailMapOffset.set((-time*.006)%1,(time*.008)%1);if(!m.campusDepthAnchored)m.diffuseMapOffset.set((time*.004)%1,(time*.002)%1);m.update();}
   if(contact?.position&&time-lastWake>.4){const w=wakes[wakeCursor++%wakes.length];w.age=0;w.entity.enabled=true;w.entity.setPosition(contact.position.x,contact.surface+.025,contact.position.z);lastWake=time;}
   for(const w of wakes){w.age+=dt;if(w.age>=1.7){w.entity.enabled=false;continue;}const radius=.3+w.age*.9;w.entity.setLocalScale(radius,1,radius);w.material.opacity=(1-w.age/1.7)*.3;w.material.update();}
  },
  setRefraction(enabled){refractionActive=enabled;for(const m of materials){m.useDynamicRefraction=enabled;m.refraction=enabled?.38:0;m.update();}},
  requestLocalRefresh(){forced=Math.max(1,12-capturedFaces);lastDynamic=0;},
  state:()=>({surfaces,time,normalOffset:materials[0]?[materials[0].normalMapOffset.x,materials[0].normalMapOffset.y]:[],capturedFaces,captureSucceeded,initialCaptureTimedOut:captureTimedOut,depthMappedPonds:depthMapped,depthSource:'ESTIMATED_SHORE_DISTANCE_NOT_SURVEYED',shoreFoam:depthMapped>0,refraction:refractionActive,hdrCubemap:hdr,dynamicCapturedFaces:dynamicFaces,localReflectionBudgetPaused:(app.stats.frame.ms||0)>=45,contactRipples:wakes.filter(w=>w.entity.enabled).length,reflection:captureSucceeded?'hdr_local_scene_cubemaps_2x128_budgeted_refresh':'hdr_sky_fallback'})};
}
