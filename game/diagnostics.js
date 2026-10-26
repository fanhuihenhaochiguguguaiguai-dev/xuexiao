import {BUILD_ID,summarizeFrames,evaluateReport,rendererEvidence} from './performance-core.js';
const STORAGE='henan-campus-device-report-v1';
const $=id=>document.getElementById(id);
const safeRead=()=>{try{return JSON.parse(localStorage.getItem(STORAGE)||'null');}catch{return null;}};
const bounded=(promise,ms)=>Promise.race([promise,new Promise(resolve=>setTimeout(()=>resolve(null),ms))]);
export function createDiagnostics({meta,context,onStart,onRestore,onPose,toast}){
 let app,route,run=null,latest=safeRead(),adapter=null,probeFinished=false,probeError='',lost=false;
 let persistence='尚无报告',autoScheduled=false;
 const environment=()=>{const info=app?.graphicsDevice.wgpu?.adapterInfo;return {secureContext:isSecureContext,webgpuApiAvailable:!!navigator.gpu,
  actualRenderer:meta.actualRenderer||'not_initialized',requestedRenderer:meta.requestedRenderer,
  adapter:info?{vendor:info.vendor||'',architecture:info.architecture||'',description:info.description||'',isFallbackAdapter:typeof info.isFallbackAdapter==='boolean'?info.isFallbackAdapter:null}:adapter,
  adapterBoundToDevice:!!info,adapterEvidenceSource:info?'ACTUAL_GPU_DEVICE':'SEPARATE_CAPABILITY_PROBE_ONLY',adapterProbeFinished:probeFinished,adapterProbeError:probeError,
  webglRenderer:app?.graphicsDevice.unmaskedRenderer||'',webglVendor:app?.graphicsDevice.unmaskedVendor||'',
  platform:navigator.userAgentData?.platform||navigator.platform,android:/Android/i.test(navigator.userAgent),
  browser:navigator.userAgent,deviceYear:'UNKNOWN_NOT_EXPOSED_BY_BROWSER',deviceLost:lost};};
 async function probe(){
  try{
   if(navigator.gpu&&isSecureContext){
    const a=await bounded(navigator.gpu.requestAdapter({powerPreference:'high-performance'}),4000);
    if(a){const info=a.info||(a.requestAdapterInfo?await a.requestAdapterInfo():{});
     adapter={vendor:info.vendor||'',architecture:info.architecture||'',description:info.description||'',
      isFallbackAdapter:typeof a.isFallbackAdapter==='boolean'?a.isFallbackAdapter:typeof info.isFallbackAdapter==='boolean'?info.isFallbackAdapter:null};
    }else probeError='未取得可用适配器，或检测超过4秒。';
   }else probeError=isSecureContext?'浏览器未提供 WebGPU API。':'页面不处于安全上下文。';
  }catch(e){probeError=String(e).slice(0,250);}
  probeFinished=true;render();
 }
 function documentReport(status='capability_only',reason=''){
  const report={schemaVersion:1,buildId:BUILD_ID,createdUtc:new Date().toISOString(),status,reason,
   environment:environment(),settings:run?.settings||context(),
   routeVersion:route?.version||null,expectedStages:route?.phases.length||4,
   warmupMs:route?.warmupMs||5000,stageMs:route?.stageMs||10000,
   stages:run?run.samples.map((a,i)=>({id:route.phases[i].id,name:route.phases[i].name,metrics:summarizeFrames(a)})):[],
   errors:meta.errors.slice(-15),privacy:'Local only. No report is uploaded automatically.',
   measurement:'Real postrender-to-postrender wall time; CPU, GPU, browser and display combined. No isolated GPU timestamp claims.'};
  report.assessment=evaluateReport(report);return report;
 }
 function remember(report){
  latest=report;try{localStorage.setItem(STORAGE,JSON.stringify(report));persistence='报告已保存在这台设备';}
  catch{persistence='浏览器禁止保存，报告仅在本页保留，请导出';}
 }
 function finish(status,reason=''){
  if(!run)return;
  const report=documentReport(status,reason),saved=run.saved;run=null;remember(report);onRestore(saved);
  document.body.classList.remove('benchmark-running');$('benchmark-banner').hidden=true;render();
  if(status==='completed'){toast('设备检测已完成，可查看或导出报告');show();}
  else toast('检测已停止，报告保留停止原因');
 }
 function begin(){
  if(run||!app||!meta.ready||!route)return;
  if(document.hidden||matchMedia('(pointer:coarse)').matches&&innerHeight>innerWidth){toast('请保持页面在前台，并横屏后检测');return;}
  if($('performance-dialog').open)$('performance-dialog').close();
  const saved=onStart();run={started:performance.now(),last:null,previousIndex:-1,samples:route.phases.map(()=>[]),saved,settings:context()};
  document.body.classList.add('benchmark-running');$('benchmark-banner').hidden=false;render();
 }
 function frame(){
  if(!run)return;
  const now=performance.now(),elapsed=now-run.started;
  if(elapsed>=route.warmupMs+route.stageMs*route.phases.length){finish('completed');return;}
  const index=Math.floor((elapsed-route.warmupMs)/route.stageMs);
  if(index>=0){
   const phaseElapsed=elapsed-route.warmupMs-index*route.stageMs;
   if(run.last!==null&&run.previousIndex===index&&phaseElapsed>=route.settleMs&&run.last>=run.started+route.warmupMs+index*route.stageMs+route.settleMs){
    if(run.samples[index].length<10000)run.samples[index].push(now-run.last);
   }
   run.previousIndex=index;
  }
  run.last=now;
 }
 function pose(){
  if(!run)return;
  const elapsed=performance.now()-run.started,index=Math.max(0,Math.min(route.phases.length-1,Math.floor((elapsed-route.warmupMs)/route.stageMs)));
  const phase=route.phases[index],local=Math.max(0,elapsed-route.warmupMs-index*route.stageMs)/1000;
  onPose(phase,local);$('benchmark-progress').textContent=elapsed<route.warmupMs?'准备场景与着色器…':`${phase.name} · ${Math.max(0,Math.ceil((route.warmupMs+route.stageMs*route.phases.length-elapsed)/1000))} 秒后完成`;
 }
 function render(){
  const env=environment(),e=rendererEvidence(env);
  $('gpu-backend').textContent=env.actualRenderer==='webgpu'?'WebGPU':env.actualRenderer==='webgl2'?'WebGL 2（兼容模式）':'正在初始化';
  $('gpu-adapter').textContent=adapter?.description||adapter?.vendor||env.webglRenderer||probeError||'正在识别设备…';
  $('gpu-evidence').textContent=e.softwareDetected?'检测到软件渲染':e.hardwareAdapterEvidence?'浏览器报告为非回退 WebGPU 适配器':e.webgpuActive?'WebGPU 已启用，硬件类型尚未确认':'将按实际渲染方式记录性能';
  $('benchmark-start').disabled=!meta.ready||!route||!!run;$('benchmark-export').disabled=!!run;
  const report=latest&&latest.buildId===BUILD_ID?latest:null,body=$('benchmark-results');body.replaceChildren();
  if(report){
   const h=document.createElement('p');h.className='performance-verdict';h.textContent=report.status!=='completed'?'检测未完成：'+(report.reason||report.status):report.assessment.webgpuPerformancePass?'固定场景 WebGPU 性能达标':report.assessment.performancePass?'固定场景帧率达标，WebGPU 硬件验收仍未通过':'检测完成，尚未达到本版性能目标';body.append(h);
   for(const stage of report.stages){const row=document.createElement('div');row.className='performance-row';const label=document.createElement('span');label.textContent=stage.name;const value=document.createElement('strong');value.textContent=stage.metrics.averageFps===null?'采样不足':`${stage.metrics.averageFps.toFixed(1)} FPS · P95 ${stage.metrics.p95FrameMs.toFixed(1)} ms`;row.append(label,value);body.append(row);}
   const note=document.createElement('p');note.className='fineprint';note.textContent=report.assessment.notes.join(' ');body.append(note);
   $('benchmark-storage').textContent=(persistence==='尚无报告'?'已读取本机上次报告':persistence)+' · '+new Date(report.createdUtc).toLocaleString();
  }else $('benchmark-storage').textContent=latest?'旧版本报告保留在本机；请运行当前版本检测。':'首次开始探索后将自动检测一次，也可随时跳过。';
 }
 function show(){render();if(!$('performance-dialog').open)$('performance-dialog').showModal();}
 function exportReport(){
  const report=latest?.buildId===BUILD_ID?latest:documentReport(),blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=`校园设备检测-${report.createdUtc.slice(0,10)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
 }
 document.querySelectorAll('[data-performance]').forEach(b=>b.addEventListener('click',show));
 $('benchmark-start').onclick=begin;$('benchmark-cancel').onclick=()=>finish('cancelled','用户跳过检测');$('benchmark-export').onclick=exportReport;
 document.addEventListener('visibilitychange',()=>{if(document.hidden)finish('interrupted','页面进入后台，采样作废');});
 window.addEventListener('resize',()=>{if(run)finish('interrupted','窗口尺寸或横竖屏发生改变，请保持横屏重新检测');});
 window.addEventListener('pagehide',()=>finish('interrupted','页面离开或关闭'));
 probe();
 const api={
  attach(application,config){app=application;route=config;app.on('postrender',frame);app.graphicsDevice.on('devicelost',()=>{lost=true;meta.errors.push('Graphics device lost');finish('interrupted','图形设备丢失');render();});render();},
  start:begin,cancel:()=>finish('cancelled','用户跳过检测'),show,pose,
  get running(){return !!run;},get report(){return latest||documentReport();},get environment(){return environment();},
  afterStart(){if(autoScheduled)return;autoScheduled=true;if($('auto-benchmark').checked&&!(latest?.buildId===BUILD_ID&&latest.status==='completed'))setTimeout(begin,500);},
  failure(){render();remember(documentReport('initialization_failed','游戏初始化失败，未进行性能采样'));},
  graphicsFailure(message){if(meta.errors.length<50)meta.errors.push(message);finish('interrupted',message);render();}
 };
 window.__campusDiagnostics=api;return api;
}
