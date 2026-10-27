import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

// This viewer deliberately ships with no invented campus geometry.
// Debug plane is used only to demonstrate controls until verified official scan data is added.
const $ = id => document.getElementById(id);
const viewport = $('viewport');
const renderer = new THREE.WebGLRenderer({antialias:true, alpha:false, powerPreference:'default'});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
viewport.append(renderer.domElement);

const world = new THREE.Scene();
world.background = new THREE.Color(0x29445b);
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, .1, 1200);
const hemi = new THREE.HemisphereLight(0xc8eaff, 0x42515a, 2.4);world.add(hemi);
const sun = new THREE.DirectionalLight(0xffe1af, 2.4);sun.position.set(7, 18, 10);world.add(sun);
const debug = new THREE.Group();
const ground = new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.MeshStandardMaterial({color:0x203b4a,roughness:1}));ground.rotation.x=-Math.PI/2; ground.position.y=-.015;debug.add(ground);
const grid = new THREE.GridHelper(80,80,0x557587,0x2e4b5b);grid.position.y=.008;debug.add(grid);
const origin = new THREE.Mesh(new THREE.TorusGeometry(2,.014,5,60), new THREE.MeshBasicMaterial({color:0xdfc18a}));origin.rotation.x=-Math.PI/2;origin.position.y=.03;debug.add(origin);
world.add(debug);
const scanGroup = new THREE.Group();world.add(scanGroup);
const hitMeshes = [];

function humanoid(){
  const p = new THREE.Group();
  const material=(color,metalness=0)=>new THREE.MeshStandardMaterial({color,roughness:.75,metalness});
  const shirt=material(0x9bb9ca), skin=material(0xf0cfb0), pants=material(0x243b53), boots=material(0x19232e), hair=material(0x242c37);
  function part(geo,mat,x,y,z,parent=p){const o=new THREE.Mesh(geo,mat);o.position.set(x,y,z);parent.add(o);return o}
  part(new THREE.CapsuleGeometry(.30,.53,5,12),shirt,0,1.28,0);
  part(new THREE.SphereGeometry(.24,12,10),skin,0,1.92,0);
  const cap=part(new THREE.SphereGeometry(.25,12,8),hair,0,2.09,-.025);cap.scale.set(1.04,.58,1.08);
  const larm=new THREE.Group(),rarm=new THREE.Group(),lleg=new THREE.Group(),rleg=new THREE.Group();
  for(const [g,x,y,z] of [[larm,-.38,1.51,0],[rarm,.38,1.51,0],[lleg,-.16,.81,0],[rleg,.16,.81,0]]){g.position.set(x,y,z);p.add(g)}
  part(new THREE.CapsuleGeometry(.105,.42,4,8),shirt,0,-.34,0,larm);
  part(new THREE.CapsuleGeometry(.105,.42,4,8),shirt,0,-.34,0,rarm);
  part(new THREE.CapsuleGeometry(.135,.45,4,8),pants,0,-.38,0,lleg);
  part(new THREE.CapsuleGeometry(.135,.45,4,8),pants,0,-.38,0,rleg);
  part(new THREE.BoxGeometry(.24,.16,.36),boots,0,-.82,-.06,lleg);
  part(new THREE.BoxGeometry(.24,.16,.36),boots,0,-.82,-.06,rleg);
  part(new THREE.BoxGeometry(.3,.09,.12),material(0xe2bd78,.4),0,1.07,-.29);
  return {mesh:p,limbs:[larm,rarm,lleg,rleg]};
}
const hero=humanoid();world.add(hero.mesh);
const player=new THREE.Vector3(0,0,0);
let cameraYaw=0, cameraPitch=.36, activePointer=null, currentIndex=-1, manifest={scenes:[]};
let loadedBackground=null, activeModel=null, modelColliderEnabled=false;
const keyState = new Set();
const controls={x:0,y:0};
const localFiles=new Map();
const pendingObjectUrls=new Set();
const panoLoader=new THREE.TextureLoader();
const scanLoader=new GLTFLoader();
function msg(s){$('status').textContent=s}
function setMode(s){$('modeTag').textContent=s}
function assetUrl(path){
 if(!path)return '';
 const clean=String(path).replace(/^\.\//,'');
 if(localFiles.has(clean))return localFiles.get(clean);
 if(localFiles.has(clean.split('/').pop()))return localFiles.get(clean.split('/').pop());
 return clean;
}
function releaseScene(){
 if(loadedBackground){loadedBackground.dispose();loadedBackground=null;}
 world.background=new THREE.Color(0x29445b);
 hitMeshes.length=0;
 while(scanGroup.children.length){const obj=scanGroup.children[0];scanGroup.remove(obj);obj.traverse(n=>{if(n.geometry)n.geometry.dispose(); if(n.material){const mats=Array.isArray(n.material)?n.material:[n.material];mats.forEach(m=>m.dispose())}})}
 activeModel=null;modelColliderEnabled=false;
}
function readScene(index){
 if(!manifest.scenes || !manifest.scenes.length){currentIndex=-1;setMode('操作测试区 · 非校园模型');msg('未导入官方场景；可以先试人物行走');debug.visible=true;return;}
 currentIndex=Math.max(0,Math.min(index,manifest.scenes.length-1));
 const s=manifest.scenes[currentIndex];
 releaseScene();
 debug.visible=true;
 player.set(...(Array.isArray(s.spawn)&&s.spawn.length===3 ? s.spawn : [0,0,0]));
 hero.mesh.position.copy(player);
 cameraYaw=typeof s.camera_heading==='number' ? s.camera_heading : 0;
 $('sceneName').textContent=s.name||s.id||'未命名场景';
 $('sceneNotes').textContent=s.notes||'此场景未提供其他信息。';
 $('sceneTotal').textContent=`${currentIndex+1} / ${manifest.scenes.length}`;
 $('nextScene').disabled=manifest.scenes.length<2;
 if(s.panorama){
  const url=assetUrl(s.panorama);
  msg('加载官方全景：'+$('sceneName').textContent);
  panoLoader.load(url,tex=>{
   if(currentIndex<0||manifest.scenes[currentIndex]!==s){tex.dispose();return;}
   tex.mapping=THREE.EquirectangularReflectionMapping;
   tex.colorSpace=THREE.SRGBColorSpace;
   loadedBackground=tex;
   world.background=tex;
   setMode('官方全景定位 · 未有真实深度');
   msg('全景已显示；空间位置和碰撞不可从单张照片确定');
  },undefined,()=>msg('全景无法加载：请检查授权素材路径或远程 CORS'));
 }else if(Array.isArray(s.cube_faces) && s.cube_faces.length===6){
  const urls=s.cube_faces.map(assetUrl);
  new THREE.CubeTextureLoader().load(urls,tex=>{
   if(currentIndex<0||manifest.scenes[currentIndex]!==s){tex.dispose();return;}
   loadedBackground=tex;world.background=tex;
   setMode('官方六面全景 · 不是扫描网格');msg('六面全景已载入；方向需与官方源对应');
  },undefined,()=>msg('六面全景加载失败，请核查文件命名与顺序'));
 }else{setMode('场景无图像 · 待官方授权资源');msg('已载入导航记录，缺少官方影像');}
 if(s.scan_glb){
  msg('尝试载入已验证的三维扫描模型...');
  scanLoader.load(assetUrl(s.scan_glb),gltf=>{
   if(currentIndex<0||manifest.scenes[currentIndex]!==s)return;
   activeModel=gltf.scene;
   scanGroup.add(activeModel);
   const k=typeof s.model_scale==='number'?s.model_scale:1;
   activeModel.scale.setScalar(k);
   const loc=Array.isArray(s.model_position)&&s.model_position.length===3?s.model_position:[0,0,0];
   activeModel.position.set(...loc);
   activeModel.updateMatrixWorld(true);
   activeModel.traverse(n=>{if(n.isMesh)hitMeshes.push(n)});
   modelColliderEnabled=hitMeshes.length>0;
   debug.visible=false;
   setMode('已导入扫描网格 · 碰撞为试验版');
   msg('扫描网格已载入；请核验比例、地面碰撞与测量精度');
  },undefined,()=>msg('扫描 GLB 加载失败；未使用任何旧模型替代'));
 }
 renderList();
}
function renderList(){
 const list=$('sceneList');list.replaceChildren();
 if(!manifest.scenes.length){const n=document.createElement('div');n.className='empty';n.textContent='没有附带虚构的校园楼栋。请载入学校官方素材生成的 manifest.json，或使用素材按钮预览本地官方全景。';list.append(n);return;}
 manifest.scenes.forEach((s,i)=>{const b=document.createElement('button');b.className='sceneentry'+(i===currentIndex?' active':'');b.textContent=s.name||s.id||`场景${i+1}`;
 const meta=document.createElement('span');meta.textContent=s.scan_glb?'已配置扫描 GLB':s.panorama||s.cube_faces?'全景影像':'只有导航信息';b.append(meta);b.addEventListener('click',()=>{readScene(i);if(innerWidth<740)$('side').classList.add('collapsed')});list.append(b)})
}
function applyManifest(obj){
 if(!obj||obj.schema!==1||!Array.isArray(obj.scenes))throw Error('格式不正确：需要 schema=1 与 scenes 数组');
 if(obj.source_policy!=='official-source-only')throw Error('只允许官方数据来源清单');
 if(obj.scenes.length>500)throw Error('场景数量超过安全限制');
 for(const s of obj.scenes){if(!s||typeof s!=='object'||typeof s.name!=='string')throw Error('场景需要 name');}
 manifest=obj;readScene(obj.scenes.length?0:-1);
 $('dataState').textContent=`官方场景记录：${obj.scenes.length} 处；第三方素材未打包到本程序`;
}
$('manifestButton').addEventListener('click',()=>$('manifestInput').click());
$('assetsButton').addEventListener('click',()=>$('assetsInput').click());
$('manifestInput').addEventListener('change',async e=>{try{const f=e.target.files[0];if(f)applyManifest(JSON.parse(await f.text()))}catch(err){msg('清单错误：'+err.message)}});
$('assetsInput').addEventListener('change',e=>{
 const files=Array.from(e.target.files||[]);
 files.forEach(f=>{const url=URL.createObjectURL(f);pendingObjectUrls.add(url);localFiles.set(f.name,url);if(f.webkitRelativePath)localFiles.set(f.webkitRelativePath,url)});
 if(manifest.scenes.length){readScene(Math.max(currentIndex,0));$('dataState').textContent=`已选 ${files.length} 个本地授权素材；仅浏览器临时载入`}
 else{
  const file=files.find(f=>/\.(jpe?g|png|webp)$/i.test(f.name));
  if(file){applyManifest({schema:1,source_policy:'official-source-only',scenes:[{id:'import-preview',name:'导入的官方全景（待核实来源）',notes:'临时导入预览，尚非真实扫描的可步行空间。',panorama:file.name}]})}
  else msg('请先载入官方 manifest.json 或选择全景图片');
 }
});
$('nextScene').addEventListener('click',()=>{if(manifest.scenes.length)readScene((currentIndex+1)%manifest.scenes.length)});
$('resetCamera').addEventListener('click',()=>{cameraYaw=0;cameraPitch=.36});
$('toggleSide').addEventListener('click',()=>$('side').classList.toggle('collapsed'));
$('helpButton').addEventListener('click',()=>$('modal').classList.remove('hidden'));
$('closeHelp').addEventListener('click',()=>$('modal').classList.add('hidden'));
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))$('modal').classList.add('hidden')});

const stick=$('stick'),pad=$('joystick');let padPointer=null;
function moveStick(e){const b=pad.getBoundingClientRect();const cx=b.left+b.width/2,cy=b.top+b.height/2;let dx=e.clientX-cx,dy=e.clientY-cy;const limit=b.width*.31;const len=Math.hypot(dx,dy);if(len>limit){dx*=limit/len;dy*=limit/len}controls.x=dx/limit;controls.y=dy/limit;stick.style.transform=`translate(${dx}px,${dy}px)`}
pad.addEventListener('pointerdown',e=>{e.preventDefault();padPointer=e.pointerId;pad.setPointerCapture(e.pointerId);moveStick(e)});
pad.addEventListener('pointermove',e=>{if(e.pointerId===padPointer)moveStick(e)});
function resetStick(e){if(e.pointerId!==padPointer)return;padPointer=null;controls.x=controls.y=0;stick.style.transform='translate(0,0)'}
pad.addEventListener('pointerup',resetStick);pad.addEventListener('pointercancel',resetStick);
let lastXY=null;
viewport.addEventListener('pointerdown',e=>{if(activePointer!==null)return;activePointer=e.pointerId;lastXY=[e.clientX,e.clientY];viewport.setPointerCapture(e.pointerId)});
viewport.addEventListener('pointermove',e=>{if(e.pointerId!==activePointer||!lastXY)return;const dx=e.clientX-lastXY[0],dy=e.clientY-lastXY[1];cameraYaw-=dx*.005;cameraPitch=THREE.MathUtils.clamp(cameraPitch+dy*.003,-.08,1.1);lastXY=[e.clientX,e.clientY]});
function stopPointer(e){if(activePointer===e.pointerId){activePointer=null;lastXY=null}}
viewport.addEventListener('pointerup',stopPointer);viewport.addEventListener('pointercancel',stopPointer);
window.addEventListener('keydown',e=>{const k=e.key.toLowerCase();if(['w','a','s','d','arrowup','arrowdown','arrowleft','arrowright'].includes(k)){e.preventDefault();keyState.add(k)}});
window.addEventListener('keyup',e=>keyState.delete(e.key.toLowerCase()));
window.addEventListener('blur',()=>{keyState.clear();controls.x=controls.y=0;stick.style.transform='translate(0,0)'});
function resized(){camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));renderer.setSize(innerWidth,innerHeight)}
window.addEventListener('resize',resized);
const ray=new THREE.Raycaster(),camTarget=new THREE.Vector3(),desiredCamera=new THREE.Vector3(),tmp=new THREE.Vector3();
const clock=new THREE.Clock();let walkingTime=0,frameCount=0;
function frame(){
 const dt=Math.min(clock.getDelta(),.05);
 let x=controls.x+(keyState.has('d')||keyState.has('arrowright')?1:0)-(keyState.has('a')||keyState.has('arrowleft')?1:0);
 let y=-controls.y+(keyState.has('w')||keyState.has('arrowup')?1:0)-(keyState.has('s')||keyState.has('arrowdown')?1:0);
 const len=Math.hypot(x,y);if(len>1){x/=len;y/=len}
 const motion=new THREE.Vector3(Math.sin(cameraYaw)*y+Math.cos(cameraYaw)*x,0,-Math.cos(cameraYaw)*y+Math.sin(cameraYaw)*x);
 const moving=motion.lengthSq()>.002;
 if(moving){
  motion.normalize();let allowed=true;
  if(modelColliderEnabled){ray.set(tmp.copy(player).add(new THREE.Vector3(0,1,0)),motion);ray.far=.72;const blockers=ray.intersectObjects(hitMeshes,true);allowed=!blockers.some(i=>i.distance>.04&&i.distance<.72&&Math.abs(i.face?.normal.y||0)<.8)}
  if(allowed){player.addScaledVector(motion,dt*2.6);if(!modelColliderEnabled){player.x=THREE.MathUtils.clamp(player.x,-37,37);player.z=THREE.MathUtils.clamp(player.z,-37,37)}}
  hero.mesh.rotation.y=THREE.MathUtils.lerp(hero.mesh.rotation.y,Math.atan2(-motion.x,-motion.z),Math.min(1,dt*8));
  walkingTime+=dt*10;
  hero.limbs[0].rotation.x=Math.sin(walkingTime)*.42;hero.limbs[1].rotation.x=-Math.sin(walkingTime)*.42;
  hero.limbs[2].rotation.x=-Math.sin(walkingTime)*.4;hero.limbs[3].rotation.x=Math.sin(walkingTime)*.4;
 }else hero.limbs.forEach(g=>g.rotation.x*=Math.max(0,1-dt*9));
 if(modelColliderEnabled){
  ray.set(tmp.set(player.x,player.y+1.7,player.z),new THREE.Vector3(0,-1,0));ray.far=3.1;
  const hits=ray.intersectObjects(hitMeshes,true);
  if(hits.length){const h=hits.find(i=>i.face?.normal.y>.45 || i.object.material?.side===THREE.DoubleSide);
   if(h && Math.abs(h.point.y-player.y)<.65)player.y=THREE.MathUtils.lerp(player.y,h.point.y,Math.min(1,dt*8))}
 }
 hero.mesh.position.lerp(player,Math.min(1,dt*15));
 camTarget.set(player.x,player.y+1.4,player.z);
 const dist=6.3;desiredCamera.set(player.x+Math.sin(cameraYaw)*Math.cos(cameraPitch)*dist,player.y+1.4+Math.sin(cameraPitch)*dist,player.z+Math.cos(cameraYaw)*Math.cos(cameraPitch)*dist);
 camera.position.lerp(desiredCamera,Math.min(1,dt*8));camera.lookAt(camTarget);
 if(++frameCount%15===0){$('coordinates').textContent=`X ${player.x.toFixed(1)} · Z ${player.z.toFixed(1)}`}
 renderer.render(world,camera);requestAnimationFrame(frame);
}
readScene(-1);
fetch('./manifest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(applyManifest).catch(()=>msg('请通过静态网页服务器打开，或手动载入 manifest.json'));
frame();
window.addEventListener('beforeunload',()=>pendingObjectUrls.forEach(URL.revokeObjectURL));
