import * as pc from 'playcanvas';
import RAPIER from '@dimforge/rapier3d-compat';
import {createSimulation} from './simulation.js';
import {enterLandscape} from './dist/pwa.js';
import {createDiagnostics} from './diagnostics.js';
import {enhanceWater} from './water.js';
import {BUILD_ID} from './performance-core.js';

const $=id=>document.getElementById(id),canvas=$('game');
const params=new URLSearchParams(location.search),qa=params.has('qa');
const meta={ready:false,started:false,engine:pc.version,buildId:BUILD_ID,requestedRenderer:params.get('renderer')==='webgl2'?'webgl2':'webgpu',errors:[],frames:0};
window.__campusGameState=meta;
window.addEventListener('error',e=>meta.errors.push(e.message));
window.addEventListener('unhandledrejection',e=>meta.errors.push(String(e.reason)));
function progress(n,text){$('progress').style.width=n+'%';$('load-message').textContent=text;}
const input={x:0,y:0,run:false,jump:false},keys=new Set();let active=false,simulation,worldData,character,app,camera,sun;
let cameraYaw=.55,cameraPitch=.06,cameraZoom=5.6,heading=-2.59,animName='Idle',verticalFrames=0;
let quality=params.get('quality')||'balanced';
let toastTimer,nearby=null,mapArrows=[],accumulator=0,position,smoothedCamera=new pc.Vec3(),cameraInitial=true,blob;
let renderScale=1,fpsWindow=performance.now(),fpsFrames=0,water,qaView=null,v05Config,postFrame,smoothedSpeed=0,startupReflections=true;
const effects={ssao:false,bloom:false};
const diagnostics=createDiagnostics({meta,toast,
 context:()=>({version:'0.5',quality,renderScale,viewport:[innerWidth,innerHeight],canvas:app?[app.graphicsDevice.width,app.graphicsDevice.height]:null,devicePixelRatio,shadows:!!sun?.light.castShadows,shadowMapSize:1024,effects:{...effects},speedMultiplier:simulation?.state().speedMultiplier,antiAlias:true}),
 onStart:()=>{
  const saved={quality,renderScale,cameraYaw,cameraPitch,cameraZoom,heading,feet:{...simulation.state().feet},active,boot:$('boot').hidden,hud:$('hud').hidden};
  keys.clear();input.x=input.y=0;input.jump=false;$('stick').style.transform='';quality='low';changeQuality();
  active=true;$('boot').hidden=true;$('hud').hidden=false;return saved;
 },
 onRestore:saved=>{
  quality=saved.quality;changeQuality();renderScale=saved.renderScale;app.graphicsDevice.maxPixelRatio=renderScale;resize();
  cameraYaw=saved.cameraYaw;cameraPitch=saved.cameraPitch;cameraZoom=saved.cameraZoom;cameraInitial=true;active=saved.active;
  simulation.setFeet(saved.feet.x,saved.feet.y,saved.feet.z);heading=saved.heading;
  $('boot').hidden=saved.boot;$('hud').hidden=saved.hud;keys.clear();input.x=input.y=0;fpsWindow=performance.now();fpsFrames=0;
 },
 onPose:(phase,seconds)=>{
  const yaw=phase.yaw+Math.sin(seconds*.2)*.12;
  camera.setPosition(phase.target[0]+Math.sin(yaw)*phase.radius,phase.height,phase.target[2]+Math.cos(yaw)*phase.radius);
  camera.lookAt(...phase.target);
 }
});
const scratch=new pc.Vec3(),target=new pc.Vec3();
const paused=()=>!active||diagnostics.running||!!document.querySelector('dialog[open]')||(matchMedia('(pointer:coarse)').matches&&innerHeight>innerWidth);
function toast(text){$('toast').hidden=false;$('toast').textContent=text;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,2600);}
function loadContainer(url){return new Promise((resolve,reject)=>app.assets.loadFromUrl(url,'container',(err,asset)=>err?reject(new Error(String(err))):resolve(asset)));}
function changeQuality(notify=false){
 const standard=quality==='low';renderScale=standard?1:1.25;app.graphicsDevice.maxPixelRatio=renderScale;
 if(sun)sun.light.castShadows=!startupReflections;resize();
 $('quality').title=standard?'当前：标准清晰':'当前：高清';$('quality-preset').value=quality;
 meta.quality=quality;meta.renderScale=renderScale;if(notify)toast(standard?'已切换到标准清晰画质':'已切换到高清画质');
}
function applyEffects(){
 try{
  if(effects.ssao||effects.bloom){
   postFrame??=new pc.CameraFrame(app,camera.camera);postFrame.enabled=true;
   postFrame.rendering.toneMapping=pc.TONEMAP_ACES;postFrame.rendering.renderFormats=[pc.PIXELFORMAT_RGBA16F,pc.PIXELFORMAT_RGBA8];
   postFrame.ssao.type=effects.ssao?pc.SSAOTYPE_COMBINE:pc.SSAOTYPE_NONE;postFrame.ssao.samples=8;postFrame.ssao.scale=.5;postFrame.ssao.radius=12;postFrame.ssao.power=1.2;postFrame.ssao.intensity=.25;
   postFrame.bloom.intensity=effects.bloom?.035:0;postFrame.bloom.threshold=1;postFrame.bloom.blurLevel=4;postFrame.update();
  }else if(postFrame)postFrame.enabled=false;
  meta.effects={...effects,active:!!postFrame?.enabled};
 }catch(e){effects.ssao=effects.bloom=false;postFrame?.destroy();postFrame=null;$('effect-ssao').checked=$('effect-bloom').checked=false;meta.effects={ssao:false,bloom:false,error:String(e)};toast('这台设备暂未启用附加效果');}
}
function resize(){if(app)app.resizeCanvas(innerWidth,innerHeight);}
function setAnimation(name){
 if(!character?.anim||name===animName)return;
 character.anim.baseLayer.transition(name,.16);animName=name;meta.animation=name;
}
function reset(poi=worldData.spawn){simulation.reset(poi);cameraYaw=poi.yaw??.55;cameraPitch=.06;heading=cameraYaw+Math.PI;cameraInitial=true;input.jump=false;keys.clear();input.x=input.y=0;$('stick').style.transform='';toast(poi.name?'已到达 '+poi.name:'已返回出生点');}
function createMap(){
 const ns='http://www.w3.org/2000/svg';
 const path=rings=>rings.map(r=>'M'+r.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join('L')+'Z').join('');
 for(const id of ['minimap','large-map']){
  const svg=$(id);const add=(tag,attrs)=>{const el=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);svg.appendChild(el);return el;};
  add('path',{d:path([worldData.map.boundary]),fill:'#bdcba4',stroke:'#8a9c78','stroke-width':4});
  for(const r of worldData.map.roads)add('path',{d:path([r]),fill:'#dce0cb'});
  for(const b of worldData.map.buildings)add('path',{d:path(b.rings),fill:b.id===13?'#7d9476':'#9caa89',stroke:'#e4e4ca','stroke-width':2,'fill-rule':'evenodd'});
  for(const p of worldData.pois)add('circle',{cx:p.x,cy:p.z,r:id==='minimap'?8:6,class:'map-poi'});
  const g=add('g',{class:'map-player'}),ring=document.createElementNS(ns,'circle');ring.setAttribute('r',id==='minimap'?24:14);ring.setAttribute('fill','#f2efce');ring.setAttribute('opacity','.7');g.appendChild(ring);
  const arrow=document.createElementNS(ns,'path');arrow.setAttribute('d',id==='minimap'?'M0,-23 L15,17 L0,10 L-15,17Z':'M0,-15 L10,11 L0,7 L-10,11Z');arrow.setAttribute('fill','#234e3f');g.appendChild(arrow);mapArrows.push(g);
 }
 for(const p of worldData.pois){const b=document.createElement('button');b.textContent=p.name;const s=document.createElement('span');s.textContent='切换出发点 →';b.appendChild(s);b.onclick=()=>{reset(p);$('map-dialog').close();};$('poi-list').appendChild(b);}
}
function openDialog(id){keys.clear();input.x=input.y=0;$('stick').style.transform='';$(id).showModal();}
function showPlace(){if(!nearby)return;$('place-title').textContent=nearby.name;$('place-content').textContent=`模型索引 B${String(nearby.id).padStart(2,'0')}。主体高 ${nearby.height.toFixed(1)} 米（${nearby.floorCount}层×3米）；地图轮廓长约 ${nearby.lengthMeters.toFixed(1)} 米、宽约 ${nearby.widthMeters.toFixed(1)} 米。楼层数及平面尺寸尚未实测，屋顶构件另计，室内尚未开放。`;openDialog('place-dialog');}
function bindControls(){
 $('start').onclick=async()=>{if(!meta.ready)return;active=true;meta.started=true;$('boot').hidden=true;$('hud').hidden=false;if(matchMedia('(pointer:coarse)').matches&&!qa)await enterLandscape();toast('左侧移动，右侧滑动看向四周');if(!qa)diagnostics.afterStart();};
 $('reset').onclick=()=>reset();$('info').onclick=()=>openDialog('info-dialog');$('map-toggle').onclick=()=>openDialog('map-dialog');
 $('quality').onclick=()=>openDialog('settings-dialog');
 $('quality-preset').onchange=e=>{quality=e.target.value;changeQuality(true);};
 $('speed-multiplier').onchange=e=>{simulation.setSpeedMultiplier(Number(e.target.value));toast(e.target.value==='5'?'快速漫游：原速度5倍':'已切换到标准速度');};
 $('effect-ssao').onchange=e=>{effects.ssao=e.target.checked;applyEffects();};$('effect-bloom').onchange=e=>{effects.bloom=e.target.checked;applyEffects();};
 $('run').onclick=()=>{input.run=!input.run;$('run').setAttribute('aria-pressed',String(input.run));};
 $('jump').addEventListener('pointerdown',e=>{e.preventDefault();input.jump=true;});
 $('view-toggle').onclick=()=>{cameraYaw+=Math.PI;toast('滑动画面可继续调整视角');};
 $('interact').onclick=showPlace;
 for(const b of document.querySelectorAll('[data-close]'))b.onclick=()=>b.closest('dialog').close();
 for(const d of document.querySelectorAll('dialog'))d.addEventListener('click',e=>{if(e.target===d)d.close();});
 window.addEventListener('keydown',e=>{
  if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code))e.preventDefault();
  keys.add(e.code);if(e.code==='Space'&&!e.repeat)input.jump=true;
  if(e.code==='KeyM'&&active){$('map-dialog').open?$('map-dialog').close():openDialog('map-dialog');}
  if(e.code==='KeyE'&&active)showPlace();
 });window.addEventListener('keyup',e=>keys.delete(e.code));
 window.addEventListener('blur',()=>{keys.clear();input.x=input.y=0;});
 let stickPointer=null;
 const joy=$('joystick');joy.addEventListener('pointerdown',e=>{if(stickPointer!==null)return;e.preventDefault();stickPointer=e.pointerId;joy.setPointerCapture(e.pointerId);moveStick(e);});
 function moveStick(e){const r=joy.getBoundingClientRect(),radius=r.width*.33;let x=(e.clientX-r.left-r.width/2)/radius,y=(e.clientY-r.top-r.height/2)/radius;const len=Math.hypot(x,y);if(len>1){x/=len;y/=len;}input.x=x;input.y=-y;$('stick').style.transform=`translate(${x*radius}px,${y*radius}px)`;}
 joy.addEventListener('pointermove',e=>{if(e.pointerId===stickPointer){e.preventDefault();moveStick(e);}});
 function endStick(e){if(e.pointerId!==stickPointer)return;stickPointer=null;input.x=input.y=0;$('stick').style.transform='';}
 joy.addEventListener('pointerup',endStick);joy.addEventListener('pointercancel',endStick);joy.addEventListener('lostpointercapture',endStick);
 const looks=new Map();let pinchDistance=0;
 canvas.addEventListener('pointerdown',e=>{if(!active||paused())return;if(e.pointerType==='touch'&&e.clientX<innerWidth*.42)return;looks.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);$('look-hint').hidden=true;});
 canvas.addEventListener('pointermove',e=>{
  const old=looks.get(e.pointerId);if(!old)return;
  if(looks.size===1){cameraYaw-=(e.clientX-old.x)*.005;cameraPitch=Math.max(-.08,Math.min(1.05,cameraPitch+(e.clientY-old.y)*.0035));}
  looks.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(looks.size===2){const [a,b]=[...looks.values()],d=Math.hypot(a.x-b.x,a.y-b.y);if(pinchDistance)cameraZoom=Math.max(2.5,Math.min(10,cameraZoom+(pinchDistance-d)*.015));pinchDistance=d;}
 });
 function stopLook(e){looks.delete(e.pointerId);pinchDistance=0;}
 canvas.addEventListener('pointerup',stopLook);canvas.addEventListener('pointercancel',stopLook);
 canvas.addEventListener('wheel',e=>{e.preventDefault();cameraZoom=Math.max(2.5,Math.min(10,cameraZoom+e.deltaY*.004));},{passive:false});
 window.addEventListener('resize',resize);
}
function update(dt){
 meta.frames++;
 fpsFrames++;const now=performance.now();
 if(now-fpsWindow>3500){
  const fps=fpsFrames*1000/(now-fpsWindow);meta.observedFps=fps;
  if(!diagnostics.running&&fps<23&&renderScale>1){renderScale=1;app.graphicsDevice.maxPixelRatio=renderScale;resize();}
  meta.renderScale=renderScale;fpsFrames=0;fpsWindow=now;
 }
 let x=0,y=0,run=false;
 if(!paused()){
  x=input.x+(keys.has('KeyD')||keys.has('ArrowRight')?1:0)-(keys.has('KeyA')||keys.has('ArrowLeft')?1:0);
  y=input.y+(keys.has('KeyW')||keys.has('ArrowUp')?1:0)-(keys.has('KeyS')||keys.has('ArrowDown')?1:0);
  run=input.run||keys.has('ShiftLeft')||keys.has('ShiftRight');
 }
 const len=Math.hypot(x,y);if(len>1){x/=len;y/=len;}
 const wx=x*Math.cos(cameraYaw)-y*Math.sin(cameraYaw),wz=-x*Math.sin(cameraYaw)-y*Math.cos(cameraYaw);
 accumulator=Math.min(accumulator+dt,.25);let jumped=false;
 while(accumulator>=1/120){simulation.step(wx,wz,1/120,run,input.jump&&!paused()&&!jumped);jumped=true;accumulator-=1/120;}
 if(jumped)input.jump=false;
 const state=simulation.state(),p=state.feet;position=p;
 if(state.horizontalSpeed>.1&&len>.08&&!paused()){
  const goal=Math.atan2(wx,wz);let diff=Math.atan2(Math.sin(goal-heading),Math.cos(goal-heading));heading+=diff*Math.min(1,dt*12);
 }
 character.setPosition(p.x,p.y-.025,p.z);character.setEulerAngles(0,heading*180/Math.PI,0);
 if(blob){blob.setPosition(p.x,p.y-.023,p.z);blob.enabled=p.y<.45;}
 const jumping=!state.grounded&&Math.abs(state.verticalVelocity)>1;
 smoothedSpeed+=(state.horizontalSpeed-smoothedSpeed)*(1-Math.exp(-dt*10));
 const action=jumping?'Jump':smoothedSpeed>.15&&!paused()?(smoothedSpeed>3.4||run?'Run':'Walk'):'Idle';setAnimation(action);
 if(character.anim)character.anim.speed=action==='Walk'?Math.max(.75,Math.min(1.8,smoothedSpeed/1.45)):action==='Run'?Math.max(.85,Math.min(1.8,smoothedSpeed/4.2)):1;
 meta.speedMetersPerSecond=state.horizontalSpeed;meta.speedMultiplier=state.speedMultiplier;meta.animationRate=character.anim.speed;
 $('motion').textContent={Idle:'待机',Walk:'行走',Run:'奔跑',Jump:'跳跃'}[action];$('session-distance').textContent=`已探索 ${Math.floor(state.distanceTravelled)} 米`;
 target.set(p.x,p.y+1.13,p.z);
 const cp=Math.cos(cameraPitch);scratch.set(target.x+Math.sin(cameraYaw)*cameraZoom*cp,target.y+Math.sin(cameraPitch)*cameraZoom,target.z+Math.cos(cameraYaw)*cameraZoom*cp);
 const allowed=simulation.cameraDistance(target,scratch),ratio=Math.min(1,allowed/cameraZoom);
 scratch.lerp(target,scratch,ratio);
 if(cameraInitial){smoothedCamera.copy(scratch);cameraInitial=false;}else smoothedCamera.lerp(smoothedCamera,scratch,1-Math.exp(-dt*13));
 // Clamp the smoothed path as well, so interpolation cannot carry the camera
 // through a wall when the character approaches it or turns at a corner.
 const smoothDistance=smoothedCamera.distance(target),safeSmooth=simulation.cameraDistance(target,smoothedCamera);
 if(safeSmooth<smoothDistance)smoothedCamera.lerp(target,smoothedCamera,safeSmooth/Math.max(smoothDistance,.001));
 camera.setPosition(smoothedCamera);camera.lookAt(target);
 water?.update(dt);diagnostics.pose();
 if(postFrame?.enabled)postFrame.update();
 if(qaView&&!diagnostics.running){camera.setPosition(...qaView.eye);camera.lookAt(...qaView.look);}
 if(meta.frames%10===0){
  for(const g of mapArrows)g.setAttribute('transform',`translate(${p.x} ${p.z}) rotate(${heading*180/Math.PI+180})`);
  const nearPoi=[...worldData.pois].sort((a,b)=>Math.hypot(a.x-p.x,a.z-p.z)-Math.hypot(b.x-p.x,b.z-p.z))[0];
  $('location-name').textContent=Math.hypot(nearPoi.x-p.x,nearPoi.z-p.z)<70?nearPoi.name:'校园道路';
  nearby=[...worldData.buildings].sort((a,b)=>Math.hypot(a.x-p.x,a.z-p.z)-Math.hypot(b.x-p.x,b.z-p.z))[0];
  if(Math.hypot(nearby.x-p.x,nearby.z-p.z)>58)nearby=null;$('interact').hidden=!nearby;
 }
 meta.position={...p};meta.grounded=state.grounded;meta.travel=state.distanceTravelled;meta.camera={x:camera.getPosition().x,y:camera.getPosition().y,z:camera.getPosition().z,yaw:cameraYaw,pitch:cameraPitch};
 meta.drawCalls=app.stats.drawCalls.total;
}
async function main(){
 progress(8,'正在初始化图形与人物碰撞…');
 const gpuOptions={deviceTypes:[pc.DEVICETYPE_WEBGPU,pc.DEVICETYPE_WEBGL2],antialias:true,alpha:false,
  glslangUrl:'/assets/engine/glslang.js',twgslUrl:'/assets/engine/twgsl.js'};
 if(params.get('renderer')==='webgl2')gpuOptions.deviceTypes=[pc.DEVICETYPE_WEBGL2];
 const [device,world,benchmarkRoute,renderConfig,waterMetadata]=await Promise.all([pc.createGraphicsDevice(canvas,gpuOptions),fetch('/assets/world.json').then(r=>{if(!r.ok)throw Error('校园配置读取失败');return r.json();}),fetch('/assets/benchmark-route.json').then(r=>{if(!r.ok)throw Error('设备检测路线读取失败');return r.json();}),fetch('/assets/v05-config.json').then(r=>r.json()),fetch('/assets/v05/lighting-water.json').then(r=>r.json()),RAPIER.init()]);
 v05Config=renderConfig;meta.version='0.5';meta.renderConfig=renderConfig;meta.effects={...effects,active:false};
 worldData=world;simulation=createSimulation(RAPIER,worldData);meta.colliderCount=world.colliders.length;meta.actualRenderer=device.deviceType;
 device.wgpu?.addEventListener('uncapturederror',e=>diagnostics.graphicsFailure('WebGPU: '+String(e.error?.message||e.error).slice(0,350)));
 app=new pc.Application(canvas,{graphicsDevice:device});
 app.maxDeltaTime=.25;
 app.setCanvasFillMode(pc.FILLMODE_NONE);app.setCanvasResolution(pc.RESOLUTION_AUTO);resize();
 app.scene.ambientLight=new pc.Color(.57,.64,.67);
 app.scene.fog.type=pc.FOG_LINEAR;app.scene.fog.color=new pc.Color(.72,.80,.80);app.scene.fog.start=210;app.scene.fog.end=750;
 camera=new pc.Entity('Follow_camera');camera.addComponent('camera',{clearColor:new pc.Color(.68,.79,.82),fov:58,nearClip:.07,farClip:1100});app.root.addChild(camera);
 camera.camera.toneMapping=pc.TONEMAP_ACES;
 sun=new pc.Entity('Daylight');sun.addComponent('light',{type:'directional',color:new pc.Color(1,.94,.81),intensity:1.9,castShadows:true,shadowDistance:22,shadowResolution:1024,numCascades:1,normalOffsetBias:.025,shadowBias:.1,shadowType:pc.SHADOW_PCF3});sun.setEulerAngles(-43,-36,0);app.root.addChild(sun);
 const fill=new pc.Entity('Sky_fill');fill.addComponent('light',{type:'directional',color:new pc.Color(.72,.84,1),intensity:.35});fill.setEulerAngles(35,135,0);app.root.addChild(fill);
 progress(29,'正在载入校园建筑和人物…');
 const [campusAsset,characterAsset]=await Promise.all([loadContainer('/assets/campus.glb'),loadContainer('/assets/character.glb')]);
 const campus=campusAsset.resource.instantiateRenderEntity();campus.name='Existing_campus_draft';app.root.addChild(campus);
 for(const render of campus.findComponents('render')){
  render.castShadows=false;
  for(const mesh of render.meshInstances)if(mesh.material.name.startsWith('V05_terrain_')){mesh.material.occludeDirect=true;mesh.material.update();}
 }
 water=enhanceWater(app,campus,camera,waterMetadata);meta.water={surfaces:water.surfaces,reflection:water.reflection};
 character=characterAsset.resource.instantiateRenderEntity();character.name='Reference_character';app.root.addChild(character);
 // A cheap contact shadow keeps the character grounded on mobile low quality.
 const shadowCanvas=document.createElement('canvas');shadowCanvas.width=shadowCanvas.height=64;
 const ctx=shadowCanvas.getContext('2d'),gradient=ctx.createRadialGradient(32,32,2,32,32,31);
 gradient.addColorStop(0,'rgba(0,0,0,.25)');gradient.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=gradient;ctx.fillRect(0,0,64,64);
 const tex=new pc.Texture(device,{width:64,height:64,mipmaps:false});tex.setSource(shadowCanvas);
 const shadowMat=new pc.StandardMaterial();shadowMat.useLighting=false;shadowMat.diffuse=new pc.Color(.16,.20,.16);shadowMat.diffuseMap=tex;shadowMat.opacityMap=tex;shadowMat.opacityMapChannel='a';shadowMat.blendType=pc.BLEND_NORMAL;shadowMat.depthWrite=false;shadowMat.update();
 blob=new pc.Entity('Character_contact_shadow');blob.addComponent('render',{type:'plane',material:shadowMat,castShadows:false});blob.setLocalScale(1.05,1,.88);app.root.addChild(blob);
 progress(76,'正在接入骨骼动画与跟随镜头…');
 character.addComponent('anim',{activate:true});
 const clips=characterAsset.resource.animations;
 for(const name of ['Idle','Walk','Run','Jump']){
  const asset=clips.find(a=>a.resource?.name===name||a.name===name||a.name.endsWith('|'+name)||a.name.includes(name));if(!asset)throw Error('缺少人物动画：'+name);
  character.anim.assignAnimation(name,asset.resource,undefined,1,true);
 }
 character.anim.baseLayer.transition('Idle',0);meta.animations=clips.map(a=>({asset:a.name,clip:a.resource.name,duration:a.resource.duration}));meta.animation='Idle';
 const batch=app.batcher.addGroup('Campus_static',false,1024);
 for(const render of campus.findComponents('render'))render.batchGroupId=batch.id;
 app.batcher.generate([batch.id]);
 createMap();bindControls();changeQuality();
 app.on('update',update);app.start();
 progress(92,'正在准备湖面与校园远景…');await water.ready;startupReflections=false;sun.light.castShadows=true;meta.water={...meta.water,...water.state()};
 meta.ready=true;progress(100,'校园与人物已就绪');$('start').disabled=false;$('start').innerHTML='开始探索 <span>→</span>';
 diagnostics.attach(app,benchmarkRoute);
 if(qa)window.__campusTest={
  state:()=>({...meta,...simulation.state()}),
  teleport:(x,y,z)=>{simulation.setFeet(x,y,z);cameraInitial=true;},
  poi:id=>reset(worldData.pois.find(p=>p.id===id)||worldData.spawn),
  fixedSteps:(n,x,z,run=false,jump=false)=>{for(let i=0;i<n;i++)simulation.step(x,z,1/60,run,jump&&i===0);},
  simulateFall:()=>simulation.setFeet(worldData.spawn.x,-6,worldData.spawn.z),
  input,
  camera:()=>({yaw:cameraYaw,pitch:cameraPitch}),
  water:()=>water.state(),
  settings:()=>({quality,renderScale,shadowMapSize:sun.light.shadowResolution,localShadows:sun.light.castShadows,effects:meta.effects,config:v05Config}),
  lightingProof:()=>({terrainAoMaterials:campus.findComponents('render').flatMap(r=>r.meshInstances).filter(m=>m.material.aoMap&&m.material.occludeDirect).map(m=>({name:m.material.name,uv:m.material.aoMapUv,width:m.material.aoMap.width})),staticCampusCasters:campus.findComponents('render').filter(r=>r.castShadows).length,characterCasters:character.findComponents('render').filter(r=>r.castShadows).length}),
  inspectView:(eye,look)=>{qaView=eye?{eye,look}:null;},
  pose:()=>['Thigh_L','Shin_L','UpperArm_L'].map(n=>{const b=character.findByName(n);return {name:n,rotation:b?.getLocalRotation().toString()};}),
  worldSummary:()=>({colliders:worldData.colliders.map(c=>({name:c.name,kind:c.kind})),spawn:worldData.spawn})
 };
}
main().catch(e=>{console.error(e);meta.errors.push(String(e));progress(0,'加载失败：'+e.message);diagnostics.failure();$('start').disabled=false;$('start').textContent='重新加载';$('start').onclick=()=>location.reload();});
