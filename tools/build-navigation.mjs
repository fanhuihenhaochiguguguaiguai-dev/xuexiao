import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import R from '@dimforge/rapier3d-compat';
import {createSimulation} from '../simulation.js';
const file='dist/assets/world.json',sha=createHash('sha256').update(readFileSync(file)).digest('hex'),out='dist/assets/navigation.json';
if(existsSync(out)){const prior=JSON.parse(readFileSync(out));if(prior.source_sha256===sha&&prior.version===1){console.log('SKIP unchanged collision navigation');process.exit(0);}}
await R.init();const data=JSON.parse(readFileSync(file)),sim=createSimulation(R,data);const size=1.5,boundary=data.map.boundary,minX=Math.floor(Math.min(...boundary.map(p=>p[0])))-3,minZ=Math.floor(Math.min(...boundary.map(p=>p[1])))-3,width=Math.ceil((Math.max(...boundary.map(p=>p[0]))-minX+3)/size),height=Math.ceil((Math.max(...boundary.map(p=>p[1]))-minZ+3)/size);
const inside=(p,poly)=>{let ok=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>p.z)!==(b[1]>p.z)&&p.x<(b[0]-a[0])*(p.z-a[1])/(b[1]-a[1])+a[0])ok=!ok;}return ok;};
const cells=new Uint8Array(width*height),shape=new R.Cuboid(size/2+.35,.7,size/2+.35),rotation={x:0,y:0,z:0,w:1};let free=0,roads=0;
const included=c=>!['Ground','Roads'].includes(sim.labels.get(c.handle)?.kind)&&c.handle!==sim.collider.handle;
const started=performance.now();for(let z=0;z<height;z++)for(let x=0;x<width;x++){const p={x:minX+x*size,z:minZ+z*size};if(!inside(p,boundary))continue;let blocked=false;
 sim.world.intersectionsWithShape({x:p.x,y:.95,z:p.z},rotation,shape,()=>{blocked=true;return false;},undefined,undefined,sim.collider,sim.body,included);
 if(!blocked){const road=data.map.roads.some(poly=>inside(p,poly));cells[z*width+x]=road?2:1;free++;if(road)roads++;}}
const result={version:1,source_sha256:sha,method:'Existing Rapier collision meshes + real campus polygon; conservative cuboid clearance per cell, ground/road surfaces excluded',cellSize:size,origin:[minX,minZ],width,height,agentRadius:.27,clearanceMargin:.08,cells:Buffer.from(cells).toString('base64')};writeFileSync(out,JSON.stringify(result)+'\n');writeFileSync('reports/navigation-build.json',JSON.stringify({status:'PASS_GRID_BUILD_ONLY',source_sha256:sha,width,height,cellSize:size,freeCells:free,roadCells:roads,elapsedSeconds:(performance.now()-started)/1000,method:result.method,route_physics_verified:false},null,2)+'\n');console.log({width,height,free,roads,seconds:(performance.now()-started)/1000});sim.world.free();
