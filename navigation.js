// Collision-derived, bounded A* over a conservative clearance grid. No teleporting.
export const planar=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
class Heap{a=[];push(id,f){let i=this.a.length;this.a.push({id,f});while(i){const p=(i-1)>>1;if(this.a[p].f<=f)break;this.a[i]=this.a[p];i=p;}this.a[i]={id,f};}pop(){const first=this.a[0],last=this.a.pop();if(this.a.length){let i=0;while(i*2+1<this.a.length){let c=i*2+1;if(c+1<this.a.length&&this.a[c+1].f<this.a[c].f)c++;if(last.f<=this.a[c].f)break;this.a[i]=this.a[c];i=c;}this.a[i]=last;}return first.id;}get length(){return this.a.length;}}
export class CampusNavigator{
 constructor(data){this.data=data;const raw=typeof atob==='function'?atob(data.cells):Buffer.from(data.cells,'base64').toString('binary');this.cells=Uint8Array.from(raw,c=>c.charCodeAt(0));if(this.cells.length!==data.width*data.height)throw Error('Navigation grid is truncated');}
 point(id){const {width,cellSize,origin}=this.data;return{x:origin[0]+(id%width)*cellSize,z:origin[1]+Math.floor(id/width)*cellSize};}
 cell(p){const {width,height,cellSize,origin}=this.data,x=Math.round((p.x-origin[0])/cellSize),z=Math.round((p.z-origin[1])/cellSize);return x>=0&&z>=0&&x<width&&z<height?z*width+x:-1;}
 free(id){return id>=0&&id<this.cells.length&&this.cells[id]>0;}
 nearest(p,maxDistance=8){const exact=this.cell(p);if(this.free(exact))return{id:exact,point:this.point(exact),distance:planar(p,this.point(exact))};let found=null;const {width,height,origin,cellSize}=this.data,cx=Math.round((p.x-origin[0])/cellSize),cz=Math.round((p.z-origin[1])/cellSize),r=Math.ceil(maxDistance/cellSize);for(let z=Math.max(0,cz-r);z<=Math.min(height-1,cz+r);z++)for(let x=Math.max(0,cx-r);x<=Math.min(width-1,cx+r);x++){const id=z*width+x;if(!this.free(id))continue;const point=this.point(id),d=planar(p,point);if(d<=maxDistance&&(!found||d<found.distance))found={id,point,distance:d};}return found;}
 clear(a,b){const n=Math.max(1,Math.ceil(planar(a,b)/(this.data.cellSize*.23)));let previous=this.cell(a);for(let i=0;i<=n;i++){const p={x:a.x+(b.x-a.x)*i/n,z:a.z+(b.z-a.z)*i/n},id=this.cell(p);if(!this.free(id))return false;const w=this.data.width;if(previous>=0&&Math.abs((id%w)-(previous%w))===1&&Math.abs(Math.floor(id/w)-Math.floor(previous/w))===1&&(!this.free(Math.floor(id/w)*w+previous%w)||!this.free(Math.floor(previous/w)*w+id%w)))return false;previous=id;}return true;}
 route(from,to){const start=this.nearest(from),end=this.nearest(to);if(!start||!end)return{ok:false,reason:'no_walkable_anchor',visited:0};const {width,height,cellSize}=this.data,size=this.cells.length,g=new Float64Array(size).fill(Infinity),parent=new Int32Array(size).fill(-1),closed=new Uint8Array(size),heap=new Heap();g[start.id]=0;const ep=end.point;heap.push(start.id,planar(start.point,ep));let visited=0;
  while(heap.length&&visited<180000){const id=heap.pop();if(closed[id])continue;closed[id]=1;visited++;if(id===end.id)break;const x=id%width,z=Math.floor(id/width);
   for(const[dx,dz]of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,1],[1,-1],[-1,-1]]){const nx=x+dx,nz=z+dz;if(nx<0||nz<0||nx>=width||nz>=height)continue;const next=nz*width+nx;if(!this.free(next)||closed[next]||(dx&&dz&&(!this.free(z*width+nx)||!this.free(nz*width+x))))continue;const cost=g[id]+cellSize*Math.hypot(dx,dz)*(this.cells[next]===2?1:1.14);if(cost>=g[next])continue;g[next]=cost;parent[next]=id;heap.push(next,cost+planar(this.point(next),ep));}}
  if(!closed[end.id])return{ok:false,reason:'disconnected',visited};const raw=[];let cursor=end.id;while(cursor>=0){raw.push(this.point(cursor));if(cursor===start.id)break;cursor=parent[cursor];}raw.reverse();
  const points=[raw[0]];let i=0;while(i<raw.length-1){let j=raw.length-1;while(j>i+1&&!this.clear(raw[i],raw[j]))j--;points.push(raw[j]);i=j;}
  // Keep the literal destination only when its connector is inside clearance cells.
  if(this.clear(points.at(-1),to)&&planar(points.at(-1),to)>.1)points.push({...to});
  const distance=points.slice(1).reduce((n,p,i)=>n+planar(points[i],p),0);
  return{ok:true,points,distance,visited,startOffset:start.distance,destinationOffset:planar(points.at(-1),to)};
 }
}
export class WalkingGuide{
 constructor(navigator,callbacks={}){this.nav=navigator;this.callbacks=callbacks;this.status='idle';this.points=[];this.index=0;this.replans=0;this.elapsed=0;this.visited=new Set();this.history=[];this.progressDistance=0;this.watchTime=0;}
 start(position,destination,tour=[]){const route=this.nav.route(position,destination);if(!route.ok){this.status='unreachable';this.callbacks.change?.(this.snapshot());return route;}
  this.destination=destination;this.points=route.points;this.index=planar(position,this.points[0])<1.2?1:0;this.status='walking';this.replans=0;this.elapsed=0;this.progressDistance=Infinity;this.watchTime=0;this.routeDistance=route.distance;this.tour=[...tour];this.callbacks.route?.(route);this.callbacks.change?.(this.snapshot());return route;}
 pause(reason='manual'){if(this.status==='walking'){this.status='paused';this.reason=reason;this.callbacks.change?.(this.snapshot());}}
 resume(position){if(this.status!=='paused'||!this.destination)return false;const route=this.nav.route(position,this.destination);if(!route.ok){this.status='unreachable';return false;}this.points=route.points;this.index=planar(position,this.points[0])<1.2?1:0;this.progressDistance=Infinity;this.watchTime=0;this.status='walking';this.callbacks.route?.(route);this.callbacks.change?.(this.snapshot());return true;}
 cancel(){this.status='idle';this.points=[];this.tour=[];this.callbacks.change?.(this.snapshot());}
 next(position){if(this.status!=='arrived'||!this.tour.length)return false;const next=this.tour.shift(),remaining=[...this.tour];return this.start(position,next,remaining).ok;}
 steer(position,dt){if(this.status!=='walking')return{x:0,z:0};this.elapsed+=dt;
  while(this.index<this.points.length&&planar(position,this.points[this.index])<.65){this.index++;this.progressDistance=Infinity;this.watchTime=0;}
  const goal=this.points.at(-1),remaining=planar(position,goal);
  if(this.index>=this.points.length||remaining<1.15){this.status='arrived';this.visited.add(this.destination.id);this.history.push({id:this.destination.id,seconds:this.elapsed,offset:planar(position,this.destination),replans:this.replans});this.callbacks.arrive?.(this.destination);this.callbacks.change?.(this.snapshot());return{x:0,z:0};}
  const target=this.points[this.index],range=planar(position,target);
  if(range<this.progressDistance-.25){this.progressDistance=range;this.watchTime=0;}else this.watchTime+=dt;
  if(this.watchTime>4){if(this.replans>=2){this.pause('blocked');return{x:0,z:0};}this.replans++;const route=this.nav.route(position,this.destination);if(!route.ok){this.pause('blocked');return{x:0,z:0};}this.points=route.points;this.index=planar(position,this.points[0])<1.2?1:0;this.watchTime=0;this.progressDistance=Infinity;this.callbacks.route?.(route);return{x:0,z:0};}
  // Analog braking retains the ordinary character controller and acceleration.
  const analog=Math.min(1,range/2.2);return{x:(target.x-position.x)/range*analog,z:(target.z-position.z)/range*analog};
 }
 snapshot(){return{status:this.status,reason:this.reason??'',destination:this.destination?.id??null,destinationName:this.destination?.name??'',index:this.index,points:this.points.map(p=>({...p})),distance:this.routeDistance??0,elapsed:this.elapsed,replans:this.replans,visited:[...this.visited],tourRemaining:this.tour.map(p=>p.id),history:[...this.history]};}
}
