import * as pc from 'playcanvas';
import {qualityProfile} from './quality-policy.js';
// Extend the MIT-licensed PlayCanvas 2.23.3 resolve with bounded history and
// reactive regions. The locked engine remains unmodified.
import taaGLSL from './node_modules/playcanvas/build/playcanvas/src/scene/shader-lib/glsl/chunks/render-pass/frag/taaResolve.js';
import taaWGSL from './node_modules/playcanvas/build/playcanvas/src/scene/shader-lib/wgsl/chunks/render-pass/frag/taaResolve.js';

export function createHdrEnvironment(app){
 const size=256,faces=[];let maximum=0;
 const bitsFloat=new Float32Array(1),bitsInt=new Uint32Array(bitsFloat.buffer);
 const half=value=>{bitsFloat[0]=value;const bits=bitsInt[0];return ((bits>>>23)-112)<<10 | (bits>>>13)&1023;};
 const hash=(x,y)=>{const n=Math.sin(x*127.1+y*311.7)*43758.5453;return n-Math.floor(n);};
 const noise=(x,y)=>{const ix=Math.floor(x),iy=Math.floor(y);let a=x-ix,b=y-iy;a=a*a*(3-2*a);b=b*b*(3-2*b);return (hash(ix,iy)*(1-a)+hash(ix+1,iy)*a)*(1-b)+(hash(ix,iy+1)*(1-a)+hash(ix+1,iy+1)*a)*b;};
 const sun=new pc.Vec3(-.32,.78,-.45).normalize();
 for(let face=0;face<6;face++){
  const pixels=new Uint16Array(size*size*4);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
   const u=2*(x+.5)/size-1,v=2*(y+.5)/size-1;
   const d=new pc.Vec3(...[[1,-v,-u],[-1,-v,u],[u,1,v],[u,-1,-v],[u,-v,1],[-u,-v,-1]][face]).normalize();
   const h=Math.max(0,d.y),haze=Math.exp(-h*5),sunlight=Math.pow(Math.max(0,d.dot(sun)),850)*11;
   const cx=d.x/(Math.max(d.y,.08)+.2)*2,cz=d.z/(Math.max(d.y,.08)+.2)*2;
   const density=noise(cx,cz)*.57+noise(cx*2.03+12,cz*2.03+8)*.29+noise(cx*4.1+31,cz*4.1-4)*.14;
   const cloud=Math.max(0,Math.min(1,(density-.48)*4))*Math.max(0,Math.min(1,(d.y-.03)*3));
   const color=d.y<0?[.075,.095,.055]:[.13+.37*haze+cloud*.42+sunlight,.29+.30*haze+cloud*.35+sunlight*.92,.53+.15*haze+cloud*.2+sunlight*.76];
   const i=(y*size+x)*4;pixels.set([...color,1].map(half),i);maximum=Math.max(maximum,...color);
  }
  faces.push(pixels);
 }
 const source=new pc.Texture(app.graphicsDevice,{name:'Campus_authored_HDR_sky',cubemap:true,width:size,height:size,format:pc.PIXELFORMAT_RGBA16F,mipmaps:false,minFilter:pc.FILTER_LINEAR,magFilter:pc.FILTER_LINEAR,levels:[faces]});source.upload();
 app.scene.skybox=source;app.scene.skyboxIntensity=.85;
 const lighting=pc.EnvLighting.generateLightingSource(source,{size:64});
 const atlas=pc.EnvLighting.generateAtlas(lighting,{size:128,numReflectionSamples:32,numAmbientSamples:64});app.scene.envAtlas=atlas;app.scene.ambientLuminance=180;
 return {source,atlas,state:{hdr:true,format:'RGBA16F',maximumRadiance:maximum,ibl:true,atlasSize:128,source:'SELF_AUTHORED_ANALYTIC_SKY_NOT_A_PHOTO_OF_THE_SCHOOL',publicHdriAttempt:'Poly Haven API returned 403; no retry or bypass'}};
}

function resolveChunks(){
 const glslUniforms='uniform vec2 textureSize;\nuniform float campusCurrentWeight;\nuniform vec4 campusReactiveRect;\nuniform vec4 campusWater0;\nuniform vec4 campusWater1;\nuniform vec4 campusWater2;';
 const glslReactive=`
  if(uv0.x>campusReactiveRect.x && uv0.y>campusReactiveRect.y && uv0.x<campusReactiveRect.z && uv0.y<campusReactiveRect.w) mixFactor=1.0;
  vec4 campusNdc=vec4(uv0*2.0-1.0,depth*2.0-1.0,1.0);campusNdc.xy-=jitters.xy;
  vec4 campusWorld=matrix_viewProjectionInverse*campusNdc;campusWorld/=campusWorld.w;
  vec2 q=campusWorld.xz;
  bool wet=(q.x>campusWater0.x && q.y>campusWater0.y && q.x<campusWater0.z && q.y<campusWater0.w) || (q.x>campusWater1.x && q.y>campusWater1.y && q.x<campusWater1.z && q.y<campusWater1.w) || (q.x>campusWater2.x && q.y>campusWater2.y && q.x<campusWater2.z && q.y<campusWater2.w);
  if(wet && abs(campusWorld.y-0.217)<0.055) mixFactor=1.0;
 `;
 const wgslUniforms='uniform textureSize: vec2f;\nuniform campusCurrentWeight: f32;\nuniform campusReactiveRect: vec4f;\nuniform campusWater0: vec4f;\nuniform campusWater1: vec4f;\nuniform campusWater2: vec4f;';
 const wgslReactive=`
  let r=uniform.campusReactiveRect;
  if(uv0.x>r.x && (1.0-uv0.y)>r.y && uv0.x<r.z && (1.0-uv0.y)<r.w){mixFactor=1.0;}
  var campusNdc=vec4f(vec2f(uv0.x,1.0-uv0.y)*2.0-1.0,depth,1.0);campusNdc=vec4f(campusNdc.xy-uniform.jitters.xy,campusNdc.zw);
  var campusWorld=uniform.matrix_viewProjectionInverse*campusNdc;campusWorld=campusWorld/campusWorld.w;
  let q=campusWorld.xz;let a=uniform.campusWater0;let b=uniform.campusWater1;let c=uniform.campusWater2;
  let wet=(q.x>a.x && q.y>a.y && q.x<a.z && q.y<a.w)||(q.x>b.x && q.y>b.y && q.x<b.z && q.y<b.w)||(q.x>c.x && q.y>c.y && q.x<c.z && q.y<c.w);
  if(wet && abs(campusWorld.y-0.217)<0.055){mixFactor=1.0;}
 `;
 return {
  glsl:taaGLSL.replace('uniform vec2 textureSize;',glslUniforms).replace('1.0 : 0.05;','1.0 : max(campusCurrentWeight,min(0.65,length(historyUv-uv0)*length(textureSize)*0.025));\n'+glslReactive),
  wgsl:taaWGSL.replace('uniform textureSize: vec2f;',wgslUniforms).replace('let mixFactor = select(0.05, 1.0, mixFactor_condition);','var mixFactor = select(max(uniform.campusCurrentWeight,min(0.65,length(historyUv-uv0)*length(uniform.textureSize)*0.025)),1.0,mixFactor_condition);\n'+wgslReactive)
 };
}

export function createRenderQuality(app,camera,sun,waterZones){
 const frame=new pc.CameraFrame(app,camera.camera),chunks=resolveChunks(),scope=app.graphicsDevice.scope;let patchedPass=null,resetFrames=3,resets=0,prevCamera=null,prevRotation=null,previousRect=null;
 frame.rendering.renderFormats=[pc.PIXELFORMAT_RGBA16F,pc.PIXELFORMAT_RGBA8];frame.rendering.samples=1;frame.rendering.sceneColorMap=true;frame.rendering.sceneDepthMap=true;frame.rendering.toneMapping=pc.TONEMAP_ACES;frame.rendering.sharpness=.22;frame.taa.enabled=true;frame.taa.jitter=.65;
 frame.grading.enabled=true;frame.grading.saturation=1.02;frame.grading.contrast=1.015;frame.grading.brightness=1;
 for(let i=0;i<3;i++)scope.resolve('campusWater'+i).setValue(waterZones[i]?.bounds||[1e6,1e6,1e6,1e6]);
 function resetHistory(){resetFrames=3;resets++;previousRect=null;}
 function configure(effects,profile=qualityProfile('balanced')){
  frame.rendering.sceneColorMap=profile.refraction;
  frame.enabled=true;frame.ssao.type=effects.ssao?pc.SSAOTYPE_COMBINE:pc.SSAOTYPE_NONE;frame.ssao.samples=12;frame.ssao.scale=.5;frame.ssao.radius=8;frame.ssao.power=1.2;frame.ssao.intensity=.18;
  frame.bloom.intensity=effects.bloom?.025:0;frame.bloom.threshold=1.1;frame.bloom.blurLevel=4;
  frame.volumetricFog.enabled=!!effects.fog;frame.volumetricFog.light=sun.light;frame.volumetricFog.steps=8;frame.volumetricFog.scale=.25;frame.volumetricFog.density=.001;frame.volumetricFog.maxDistance=240;frame.volumetricFog.heightFalloff=.07;frame.volumetricFog.intensity=.35;
  sun.light.shadowType=effects.pcss?pc.SHADOW_PCSS_32F:(profile.pcf===5?pc.SHADOW_PCF5:pc.SHADOW_PCF3);sun.light.shadowSamples=16;sun.light.penumbraSize=1;sun.light.numCascades=profile.cascades;sun.light.cascadeDistribution=.75;sun.light.shadowResolution=profile.shadowSize;resetHistory();frame.update();
 }
 function patch(){
  const pass=frame.renderPassCamera?.taaPass;if(!pass||patchedPass===pass)return;
  pc.ShaderChunks.get(app.graphicsDevice,pc.SHADERLANGUAGE_GLSL).set('campusTaaResolvePS',chunks.glsl);pc.ShaderChunks.get(app.graphicsDevice,pc.SHADERLANGUAGE_WGSL).set('campusTaaResolvePS',chunks.wgsl);
  const defines=new Map([['QUALITY_HIGH',true]]),key=pc.ShaderUtils.addScreenDepthChunkDefines(camera.camera.shaderParams,defines);
  pass.shader=pc.ShaderUtils.createShader(app.graphicsDevice,{uniqueName:'CampusReactiveTaaV06'+key,attributes:{aPosition:pc.SEMANTIC_POSITION},vertexChunk:'quadVS',fragmentChunk:'campusTaaResolvePS',fragmentDefines:defines});patchedPass=pass;resetHistory();
 }
 function update(characterPosition){
  frame.update();patch();const p=camera.getPosition(),r=camera.getRotation();
  if(prevCamera&&(p.distance(prevCamera)>2.5||Math.abs(r.dot(prevRotation))<.96))resetHistory();prevCamera=p.clone();prevRotation=r.clone();
  let rect=[1,1,0,0];
  if(characterPosition){
   const points=[];for(const x of [-.55,.55])for(const y of [-.1,1.9])for(const z of [-.55,.55])points.push(camera.camera.worldToScreen(new pc.Vec3(characterPosition.x+x,characterPosition.y+y,characterPosition.z+z)));
   const valid=points.filter(p=>p.z>0);if(valid.length)rect=[Math.min(...valid.map(p=>p.x))/innerWidth,1-Math.max(...valid.map(p=>p.y))/innerHeight,Math.max(...valid.map(p=>p.x))/innerWidth,1-Math.min(...valid.map(p=>p.y))/innerHeight];
  }
  const current=rect.slice();if(previousRect)rect=[Math.min(rect[0],previousRect[0]),Math.min(rect[1],previousRect[1]),Math.max(rect[2],previousRect[2]),Math.max(rect[3],previousRect[3])];previousRect=current;
  scope.resolve('campusReactiveRect').setValue(rect);scope.resolve('campusCurrentWeight').setValue(resetFrames>0?1:.12);if(resetFrames>0)resetFrames--;
 }
 return {frame,configure,update,resetHistory,state:()=>({taa:frame.taa.enabled,reactiveCharacterAndWater:!!patchedPass,historyResets:resets,currentHistoryReset:resetFrames>0,sharpness:frame.rendering.sharpness,hdr:frame.renderPassCamera?.rt?.colorBuffer?.format===pc.PIXELFORMAT_RGBA16F,ssaoScale:frame.ssao.scale,colorGrading:frame.grading.enabled,volumetricFog:frame.volumetricFog.enabled,shadowMapSize:sun.light.shadowResolution,cascades:sun.light.numCascades,shadowType:sun.light.shadowType})};
}
