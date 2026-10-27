import test from 'node:test';
import assert from 'node:assert/strict';
import {qualityProfile,normalizeQuality,reducedScale} from './quality-policy.js';
import {createZoneStreaming} from './streaming.js';

test('phone default reduces pixel work without removing temporal antialiasing or campus coverage',()=>{
 const p=qualityProfile();assert.equal(normalizeQuality('unknown'),'balanced');
 assert(p.scale*p.scale/(1.5*1.5)<.5);assert(p.targetFps>=30);
 assert(p.shadowSize<=1024&&p.cascades===1&&!p.dynamicReflections&&!p.ssao);
 let scale=p.scale;for(let i=0;i<20;i++)scale=reducedScale(scale,'balanced');
 assert.equal(scale,.85);assert.equal(qualityProfile('ultra').scale,1.5);
});

test('streaming budgets bound residents, release old zones and preserve solids on load failures',async()=>{
 const solids=new Map(Array.from({length:12},(_,id)=>['B'+id,{enabled:true}]));
 let inflight=0,maxInflight=0,released=0;
 const loader=async url=>{inflight++;maxInflight=Math.max(inflight,maxInflight);await new Promise(r=>setTimeout(r,1));inflight--;if(url==='fail')throw Error('fixture missing');return {resource:{instantiateRenderEntity:()=>({findComponents:()=>[],destroy(){}})},unload(){released++;}};};
 const app={assets:{remove(){}}},campus={findByName:name=>solids.get(name),addChild(){}};
 const zones=Array.from({length:12},(_,id)=>({id,x:id*5,z:0,url:id===2?'fail':'z'+id,coarse_nodes:['B'+id]}));
 const stream=createZoneStreaming(app,campus,{zones},loader);
 await stream.initial({x:0,z:0});assert(maxInflight<=1);assert(stream.state().loaded.length<=6);
 assert(solids.get('B2').enabled);assert(stream.state().failed.some(z=>z.id===2));
 stream.setProfile(qualityProfile('low'));assert(stream.state().loaded.length<=4);assert(released>0);
 stream.reconcile({x:500,z:500});assert.equal(stream.state().loaded.length,0);
 assert([...solids.values()].every(s=>s.enabled));
});
