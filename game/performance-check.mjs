import {test} from 'node:test';
import assert from 'node:assert/strict';
import {summarizeFrames,evaluateReport,rendererEvidence} from './performance-core.js';
const report=(environment,frames=Array(300).fill(1000/60))=>({status:'completed',expectedStages:4,environment,stages:Array.from({length:4},()=>({metrics:summarizeFrames(frames)}))});
test('frame rate uses elapsed frame times, and preserves stalls',()=>{
 assert.equal(summarizeFrames(Array(60).fill(1000/60)).averageFps,60);
 const result=summarizeFrames([...Array(90).fill(16),...Array(10).fill(100)]);
 assert.equal(result.averageFps,40.98);assert.equal(result.p95FrameMs,100);assert.equal(result.over50msPercent,10);
});
test('invalid samples never create fabricated performance',()=>{
 assert.equal(summarizeFrames([0,-1,NaN,Infinity]).averageFps,null);
 const r=report({actualRenderer:'webgpu',adapter:{isFallbackAdapter:false}},[]);assert.equal(evaluateReport(r).complete,false);assert.equal(evaluateReport(r).webgpuPerformancePass,false);
});
test('WebGL2 performance cannot pass WebGPU acceptance',()=>{
 const result=evaluateReport(report({actualRenderer:'webgl2'}));assert.equal(result.performancePass,true);assert.equal(result.webgpuPerformancePass,false);
});
test('known software devices cannot pass even when fallback flag is false',()=>{
 for(const description of ['SwiftShader Device','llvmpipe','lavapipe'])assert.equal(evaluateReport(report({actualRenderer:'webgpu',adapter:{description,isFallbackAdapter:false}})).webgpuPerformancePass,false);
});
test('redacted adapter details stay unconfirmed',()=>{
 const result=rendererEvidence({actualRenderer:'webgpu',adapter:{}});assert.equal(result.status,'WEBGPU_ADAPTER_UNCONFIRMED');assert.equal(result.hardwareAdapterEvidence,false);
});
test('a non-fallback adapter and all four measured stages are required',()=>{
 const r=report({actualRenderer:'webgpu',adapterBoundToDevice:true,adapter:{description:'Adreno',isFallbackAdapter:false}});assert.equal(evaluateReport(r).webgpuPerformancePass,true);
 r.stages.pop();assert.equal(evaluateReport(r).webgpuPerformancePass,false);
});
test('a separate adapter probe cannot certify the active device',()=>{
 const r=report({actualRenderer:'webgpu',adapterBoundToDevice:false,adapter:{description:'Adreno',isFallbackAdapter:false}});assert.equal(evaluateReport(r).webgpuPerformancePass,false);
});
test('a single slow stage or interrupted run rejects acceptance',()=>{
 const r=report({actualRenderer:'webgpu',adapter:{isFallbackAdapter:false}});r.stages[2].metrics=summarizeFrames(Array(100).fill(50));assert.equal(evaluateReport(r).performancePass,false);
 r.stages[2].metrics=summarizeFrames(Array(100).fill(16));r.status='interrupted';assert.equal(evaluateReport(r).performancePass,false);
});
test('device loss and runtime errors block otherwise fast samples',()=>{
 const r=report({actualRenderer:'webgpu',adapterBoundToDevice:true,adapter:{isFallbackAdapter:false}});assert.equal(evaluateReport(r).webgpuPerformancePass,true);
 r.environment.deviceLost=true;assert.equal(evaluateReport(r).webgpuPerformancePass,false);r.environment.deviceLost=false;
 r.errors=['GPU validation failed'];assert.equal(evaluateReport(r).webgpuPerformancePass,false);
});
