import test from 'node:test';import assert from 'node:assert/strict';
import R from '@dimforge/rapier3d-compat';import {createSimulation,waterAtPosition} from './simulation.js';
await R.init();
const zone={id:'test-lake',rings:[[[-4,-4],[4,-4],[4,4],[-4,4]]],bounds:[-4,-4,4,4],surface:.217,maximumDepth:1.3,depthPerBankDistance:.6};
const ground={name:'base',kind:'Ground',vertices:[-100,0,-100,100,0,-100,100,0,100,-100,0,100],indices:[0,2,1,0,3,2]};
const base={spawn:{x:0,z:6},colliders:[ground],waterZones:[zone]};
function steps(sim,n,x=0,z=0){for(let i=0;i<n;i++)sim.step(x,z,1/120);}
test('lake has continuous shore-depth profile, never an image-only barrier',()=>{assert.equal(waterAtPosition([zone],8,0),null);assert(waterAtPosition([zone],3.8,0).depth<.13);assert.equal(waterAtPosition([zone],0,0).depth,1.3);});
test('buoyancy settles above the bed and reports swimming',()=>{const sim=createSimulation(R,base);sim.setFeet(0,.05,0);steps(sim,900);const s=sim.state();assert.equal(s.water?.mode,'swimming');assert(s.feet.y>s.water.bottom+.1);assert(Math.abs(s.verticalVelocity)<.05);assert(s.feet.y<s.water.surface-.2);sim.world.free();});
test('walking enters water, slows under drag and can leave the far shore',()=>{const sim=createSimulation(R,base);steps(sim,120);let entered=false,maxWaterSpeed=0;for(let i=0;i<1800;i++){sim.step(0,-1,1/120);const s=sim.state();if(s.water){entered=true;if(i>600)maxWaterSpeed=Math.max(maxWaterSpeed,s.horizontalSpeed);}}const s=sim.state();assert(entered);assert(s.feet.z< -4.3);assert(s.grounded);assert(s.feet.y>-.02);assert(maxWaterSpeed<4);sim.world.free();});
test('bridge deck remains dry and collidable above a lake',()=>{const deck={name:'bridge',kind:'Bridge',vertices:[-2,.5,-4,2,.5,-4,2,.5,4,-2,.5,4],indices:[0,2,1,0,3,2]};const sim=createSimulation(R,{...base,colliders:[ground,deck]});sim.setFeet(0,1,0);steps(sim,240);const s=sim.state();assert.equal(s.water,null);assert(s.grounded);assert(Math.abs(s.feet.y-.525)<.04);sim.world.free();});
