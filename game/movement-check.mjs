import {test} from 'node:test';import assert from 'node:assert/strict';
import R from '@dimforge/rapier3d-compat';import {createSimulation} from './simulation.js';await R.init();
const floor={name:'test_ground',kind:'Ground',vertices:[-500,0,-500,500,0,-500,500,0,500,-500,0,500],indices:[0,2,1,0,3,2]};
const wall={name:'thin_wall',kind:'Buildings',building:99,vertices:[12,0,-8,12,15,-8,12,15,8,12,0,8,12.1,0,-8,12.1,15,-8,12.1,15,8,12.1,0,8],indices:[0,1,2,0,2,3,4,6,5,4,7,6,0,4,5,0,5,1,3,2,6,3,6,7,1,5,6,1,6,2,0,3,7,0,7,4]};
function simulation(multiplier=5,colliders=[floor]){const s=createSimulation(R,{spawn:{x:0,z:0},colliders},{speedMultiplier:multiplier});for(let i=0;i<120;i++)s.step(0,0,1/120);return s;}
function move(s,seconds,x=1,z=0,run=false,hz=120){for(let i=0;i<Math.round(seconds*hz);i++)s.step(x,z,1/hz,run);}
test('steady exploration speed is exactly five times the original preset',()=>{
 for(const run of [false,true]){const a=simulation(1),b=simulation(5);move(a,1,1,0,run);move(b,1,1,0,run);const x=a.state().feet.x,y=b.state().feet.x;move(a,1,1,0,run);move(b,1,1,0,run);const da=a.state().feet.x-x,db=b.state().feet.x-y;assert.ok(Math.abs(db/da-5)<.002);assert.ok(Math.abs(db-(run?26.5:13.25))<.01);a.world.free();b.world.free();}
});
test('fast controller stops at a ten-centimetre wall',()=>{
 const s=simulation(5,[floor,wall]);move(s,3,1,0,true);assert.ok(s.state().feet.x<11.76);assert.equal(s.state().lastCollision?.building,99);s.world.free();
});
test('diagonal movement stays normalized and acceleration eases in',()=>{
 const a=simulation(),b=simulation();a.step(1,0,1/120);assert.ok(a.state().horizontalSpeed<3);move(a,1);move(b,1,1,1);assert.ok(b.state().horizontalSpeed<=13.26);a.world.free();b.world.free();
});
test('release decelerates and fixed-step results agree at 60 and 120Hz',()=>{
 const a=simulation(),b=simulation();move(a,2,1,0,false,60);move(b,2,1,0,false,120);assert.ok(Math.abs(a.state().feet.x-b.state().feet.x)<.07);move(a,1,0,0);assert.ok(a.state().horizontalSpeed<.01);a.world.free();b.world.free();
});
