import R from '@dimforge/rapier3d-compat';import fs from 'node:fs';import assert from 'node:assert/strict';import {createSimulation} from './simulation.js';
await R.init();const data=JSON.parse(fs.readFileSync(process.env.CAMPUS_WORLD_PATH||new URL('./dist/assets/world.json',import.meta.url)));const sim=createSimulation(R,data,{speedMultiplier:1});const result={};
function advance(n,x=0,z=0){for(let i=0;i<n;i++)sim.step(x,z,1/120);}
for(const zone of data.waterZones){sim.setFeet(zone.testPoint[0],.1,zone.testPoint[1]);advance(1000);const s=sim.state();assert(s.water&&s.feet.y>=s.water.bottom-.03);assert.equal(s.respawns,1);result[zone.id]={water:s.water,feet:s.feet,verticalVelocity:s.verticalVelocity,passed:true};}
const bridge=data.landmarks.bridge,[dx,dz]=bridge.direction;sim.setFeet(bridge.center[0]-dx*(bridge.half_length+1),.65,bridge.center[2]-dz*(bridge.half_length+1));advance(180);let peak=-Infinity;
for(let i=0;i<1150;i++){sim.step(dx,dz,1/120);peak=Math.max(peak,sim.state().feet.y);}
let s=sim.state(),along=(s.feet.x-bridge.center[0])*dx+(s.feet.z-bridge.center[2])*dz;assert(along>bridge.half_length-.5);assert(peak>.29);result.bridge={crossed:true,along,peak,passed:true};
const p=data.landmarks.podium;sim.setFeet(p.approach[0],.8,p.approach[2]);advance(180);peak=-Infinity;
for(let i=0;i<210;i++){sim.step(...p.direction,1/120);peak=Math.max(peak,sim.state().feet.y);}assert(peak>.72);result.podium={peak,passed:true};
const g=data.landmarks.grandstand;sim.setFeet(g.approach[0],.8,g.approach[2]);advance(180);peak=-Infinity;
for(let i=0;i<900;i++){sim.step(...g.direction,1/120);peak=Math.max(peak,sim.state().feet.y);}assert(peak>3.05);result.grandstandAisle={peak,passed:true};
if(data.landmarks.libraryEntrance){
 const l=data.landmarks.libraryEntrance;sim.setFeet(...l.approach);advance(180);peak=-Infinity;
 // Autostep reduces horizontal progress on each riser; allow the complete
 // approach and ascent rather than assuming flat-ground travel time.
 for(let i=0;i<650;i++){sim.step(...l.direction,1/120);peak=Math.max(peak,sim.state().feet.y);}
 const s=sim.state();assert(peak>l.landing_top_m-.03);assert(s.feet.y>l.landing_top_m-.03);assert(s.feet.y<l.landing_top_m+.15);
 result.libraryEntrance={peak,feet:s.feet,door_height_m:l.door_height_m,passed:true};
}
result.passed=true;fs.writeFileSync(process.env.CAMPUS_INTERACTIONS_REPORT||'qa/current_interactions_validation.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));sim.world.free();
