import R from '@dimforge/rapier3d-compat';
import {createSimulation} from './simulation.js';
import fs from 'node:fs';
await R.init();const data=JSON.parse(fs.readFileSync(new URL('./dist/assets/world.json',import.meta.url)));
const sim=createSimulation(R,data),results={};
function advance(n,x=0,z=0,run=false,jump=false){for(let i=0;i<n;i++)sim.step(x,z,1/60,run,jump&&i===0);}
function settle(p=data.spawn){sim.reset(p);advance(120);return sim.state();}
const s=settle();results.spawn={...s,passed:s.grounded&&s.feet.y>-.1&&s.feet.y<.5};
advance(120,1,0);let walked=sim.state();results.walk={distance:Math.hypot(walked.feet.x-s.feet.x,walked.feet.z-s.feet.z),passed:sim.state().distanceTravelled>4};
let p=settle();advance(60,1,0,true);let r=sim.state();results.run={distance:Math.hypot(r.feet.x-p.feet.x,r.feet.z-p.feet.z),passed:Math.hypot(r.feet.x-p.feet.x,r.feet.z-p.feet.z)>4.8};
p=settle();let max=p.feet.y;for(let i=0;i<120;i++){sim.step(0,0,1/60,false,i===0);max=Math.max(max,sim.state().feet.y);}r=sim.state();results.jump={rise:max-p.feet.y,landed:r.grounded,passed:max-p.feet.y>.7&&r.grounded};
// Approach the long, straight south-facing wall of the mapped library.
// X=-20 is in the south wall extent. The expected z wall is obtained from
// actual collision triangles rather than an unrelated mock wall.
const ring=data.map.buildings.find(b=>b.id===13).rings[0];
const edges=ring.map((a,i)=>{const b=ring[(i+1)%ring.length];return {a,b,length:Math.hypot(b[0]-a[0],b[1]-a[1])};});
const e=edges.sort((a,b)=>b.length-a.length)[0];const midpoint=[(e.a[0]+e.b[0])/2,(e.a[1]+e.b[1])/2];
let normal=[-(e.b[1]-e.a[1])/e.length,(e.b[0]-e.a[0])/e.length];
function inside(x,z){let b=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],c=ring[j];if((a[1]>z)!=(c[1]>z)&&x<(c[0]-a[0])*(z-a[1])/(c[1]-a[1])+a[0])b=!b;}return b;}
if(inside(midpoint[0]+normal[0],midpoint[1]+normal[1]))normal=normal.map(a=>-a);
sim.setFeet(midpoint[0]+normal[0]*4,.6,midpoint[1]+normal[1]*4);advance(90);p=sim.state();advance(180,-normal[0],-normal[1],true);r=sim.state();
results.buildingCollision={start:p.feet,end:r.feet,lastCollision:r.lastCollision,desiredTravel:26.5*3,actualTravel:Math.hypot(r.feet.x-p.feet.x,r.feet.z-p.feet.z),passed:r.lastCollision?.building===13&&Math.hypot(r.feet.x-p.feet.x,r.feet.z-p.feet.z)<10};
results.pois=data.pois.map(poi=>{const state=settle(poi);return {id:poi.id,feet:state.feet,grounded:state.grounded,passed:state.grounded&&state.feet.y>-.1&&state.feet.y<.6};});
const before=sim.state().respawns;sim.setFeet(data.spawn.x,-6,data.spawn.z);advance(2);r=sim.state();results.fallRecovery={respawns:r.respawns,passed:r.respawns>before&&r.feet.y>-.1};
const stairs=data.colliders.filter(c=>c.name.startsWith('Library_stair_')).sort((a,b)=>a.name.localeCompare(b.name));
if(stairs.length){
 const center=c=>{let x=0,z=0;for(let i=0;i<c.vertices.length;i+=3){x+=c.vertices[i];z+=c.vertices[i+2];}return {x:x/(c.vertices.length/3),z:z/(c.vertices.length/3)};};
 const a=center(stairs[0]),b=center(stairs.at(-1)),len=Math.hypot(b.x-a.x,b.z-a.z),dx=(b.x-a.x)/len,dz=(b.z-a.z)/len;
 sim.setFeet(a.x-dx*2,.6,a.z-dz*2);advance(90);let highest=sim.state().feet.y;
 for(let i=0;i<180;i++){sim.step(dx,dz,1/60,false,false);highest=Math.max(highest,sim.state().feet.y);}
 results.librarySteps={highestFeet:highest,finalFeet:sim.state().feet,passed:highest>1.1};
}
results.passed=results.spawn.passed&&results.walk.passed&&results.run.passed&&results.jump.passed&&results.buildingCollision.passed&&results.pois.every(p=>p.passed)&&results.fallRecovery.passed&&(!results.librarySteps||results.librarySteps.passed);
fs.writeFileSync(process.env.CAMPUS_PHYSICS_REPORT || new URL('./qa/current_physics_validation.json',import.meta.url),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));if(!results.passed)process.exitCode=1;
