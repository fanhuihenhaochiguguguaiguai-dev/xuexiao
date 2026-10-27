// Frame timing measures the browser's rendered cadence, not isolated GPU time.
export const BUILD_ID='campus-v07-20261027-1';
export const TARGET_FPS=30;
export function percentile(values,q){
 if(!values.length)return null;
 const a=[...values].sort((x,y)=>x-y);return a[Math.min(a.length-1,Math.max(0,Math.ceil(q*a.length)-1))];
}
export function summarizeFrames(values){
 const a=values.filter(v=>Number.isFinite(v)&&v>0),ms=a.reduce((s,v)=>s+v,0);
 if(!a.length)return {frames:0,sampledMs:0,averageFps:null,p95FrameMs:null,p99FrameMs:null,onePercentLowFps:null,over50msPercent:null};
 const p99=percentile(a,.99);
 return {frames:a.length,sampledMs:Math.round(ms),averageFps:Math.round(a.length*100000/ms)/100,
  p95FrameMs:Math.round(percentile(a,.95)*100)/100,p99FrameMs:Math.round(p99*100)/100,
  onePercentLowFps:Math.round(100000/p99)/100,over50msPercent:Math.round(a.filter(v=>v>50).length*10000/a.length)/100};
}
export function rendererEvidence(environment){
 const software=/swiftshader|llvmpipe|lavapipe|software|basic render/i.test(JSON.stringify(environment.adapter||{})+' '+(environment.webglRenderer||''));
 const webgpu=environment.actualRenderer==='webgpu';
 const fallback=environment.adapter?.isFallbackAdapter;
 return {webgpuActive:webgpu,softwareDetected:software||fallback===true,
  hardwareAdapterEvidence:webgpu&&!software&&fallback===false&&environment.adapterBoundToDevice===true,
  status:!webgpu?'WEBGL2_FALLBACK':software||fallback===true?'WEBGPU_SOFTWARE':fallback===false&&environment.adapterBoundToDevice===true?'WEBGPU_NON_FALLBACK_ADAPTER':'WEBGPU_ADAPTER_UNCONFIRMED'};
}
export function evaluateReport(report){
 const evidence=rendererEvidence(report.environment),stages=report.stages||[];
 const complete=report.status==='completed'&&stages.length===report.expectedStages&&stages.every(s=>s.metrics.frames>=10&&s.metrics.sampledMs>=1000);
 const performancePass=complete&&!report.environment.deviceLost&&!(report.errors||[]).length&&stages.every(s=>s.metrics.averageFps>=TARGET_FPS&&s.metrics.p95FrameMs<=50);
 return {...evidence,complete,performancePass,webgpuPerformancePass:performancePass&&evidence.hardwareAdapterEvidence,
  target:{averageFps:TARGET_FPS,p95FrameMsMaximum:50,scope:'Fixed camera route at recorded resolution/quality; excludes battery, thermals and extended play.'},
  notes:[...(!complete?['采样未完成或帧数不足，不能作为性能通过依据。']:[]),
   ...(!evidence.webgpuActive?['当前实际使用 WebGL 2，不能记为 WebGPU 验收通过。']:[]),
   ...(evidence.softwareDetected?['检测到软件适配器，不能代表手机硬件性能。']:[]),
   ...(evidence.webgpuActive&&!evidence.hardwareAdapterEvidence&&!evidence.softwareDetected?['浏览器未提供足够适配器信息，硬件类型仍待确认。']:[]),
   '本报告来自当前浏览器自检，不证明设备出厂年份，也不替代长时间真机游玩。']};
}
