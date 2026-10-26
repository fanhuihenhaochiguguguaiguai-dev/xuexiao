// A hysteresis controller driven only by real postrender intervals.
export class QualityBudget{
 constructor({scale=1,min=.75,max=1.25}={}){this.scale=scale;this.min=min;this.max=max;this.mode='auto';this.samples=[];this.goodWindows=0;this.adjustments=[];this.lastTime=0;this.windowStart=0;this.metrics=null;}
 setMode(mode){this.mode=mode;this.goodWindows=0;this.samples=[];this.windowStart=0;this.lastTime=0;if(mode==='low')this.scale=.8;else if(mode==='balanced')this.scale=1.25;else this.scale=Math.max(this.min,Math.min(1,this.scale));return this.scale;}
 reset(){this.samples=[];this.windowStart=0;this.lastTime=0;this.goodWindows=0;}
 frame(time,{hidden=false,suppressed=false}={}){if(hidden||suppressed){this.reset();return null;}if(!this.lastTime){this.lastTime=time;this.windowStart=time;return null;}const dt=time-this.lastTime;this.lastTime=time;if(dt<=0||dt>6000){this.reset();return null;}this.samples.push(dt);if(time-this.windowStart<4000||this.samples.length<12)return null;
  const a=[...this.samples].sort((a,b)=>a-b),average=a.reduce((n,v)=>n+v,0)/a.length,p95=a[Math.ceil(a.length*.95)-1],fps=1000/average;this.metrics={fps,p95,frames:a.length,sampledMs:time-this.windowStart};this.samples=[];this.windowStart=time;if(this.mode!=='auto')return null;let next=this.scale;
  if(fps<26&&p95>48){next=Math.max(this.min,this.scale-.15);this.goodWindows=0;}
  else if(fps>43&&p95<28){this.goodWindows++;if(this.goodWindows>=3){next=Math.min(this.max,this.scale+.1);this.goodWindows=0;}}
  else this.goodWindows=0;
  next=Math.round(next*100)/100;if(next===this.scale)return null;const previous=this.scale;this.scale=next;const change={time,from:previous,to:next,reason:next<previous?'sustained_slow_frames':'three_fast_windows',metrics:this.metrics};this.adjustments.push(change);if(this.adjustments.length>30)this.adjustments.shift();return change;
 }
}
