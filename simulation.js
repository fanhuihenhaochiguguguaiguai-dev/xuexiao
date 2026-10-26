// The same Rapier controller is used by the browser and the executable checks.
export const MOVEMENT={walkBase:2.65,runBase:5.3,defaultMultiplier:5,acceleration:12,deceleration:18};
export function createSimulation(R, data,options={}) {
 const world=new R.World({x:0,y:-20,z:0});const labels=new Map();
 for(const c of data.colliders){
  let desc;
  // The existing campus assumes a flat base. An analytic plane avoids
  // character jitter on very large ground shapes; perimeter walls still
  // enforce the real polygon boundary and pond barriers remain separate.
  if(c.kind==='Ground'){
   const ys=[];for(let i=1;i<c.vertices.length;i+=3)ys.push(c.vertices[i]);
   if(Math.max(...ys)-Math.min(...ys)<.001)desc=new R.ColliderDesc(new R.HalfSpace({x:0,y:1,z:0})).setTranslation(0,ys[0],0);
  }
  desc??=R.ColliderDesc.trimesh(new Float32Array(c.vertices),new Uint32Array(c.indices),R.TriMeshFlags.FIX_INTERNAL_EDGES);
  desc.setFriction(.75);const collider=world.createCollider(desc);labels.set(collider.handle,{name:c.name,kind:c.kind,building:c.building});
 }
 const halfHeight=.52,radius=.27,heightOffset=halfHeight+radius;
 const body=world.createRigidBody(R.RigidBodyDesc.kinematicPositionBased().setTranslation(data.spawn.x,2,data.spawn.z));
 const collider=world.createCollider(R.ColliderDesc.capsule(halfHeight,radius).setFriction(0),body);
 const controller=world.createCharacterController(.025);controller.enableAutostep(.30,.20,true);controller.enableSnapToGround(.27);
 controller.setMaxSlopeClimbAngle(Math.PI*.27);controller.setMinSlopeSlideAngle(Math.PI*.32);
 let vy=0,vx=0,vz=0,horizontalSpeed=0,multiplier=options.speedMultiplier??MOVEMENT.defaultMultiplier,grounded=false,respawns=0,travel=0,lastCollision=null,jumpCount=0;
 const feet=()=>{const p=body.translation();return {x:p.x,y:p.y-heightOffset,z:p.z};};
 function setFeet(x,y,z){body.setTranslation({x,y:y+heightOffset,z},true);body.setNextKinematicTranslation({x,y:y+heightOffset,z});vy=vx=vz=horizontalSpeed=0;grounded=false;world.step();}
 function reset(poi=data.spawn){setFeet(poi.x,.55,poi.z);respawns++;}
 function step(ix,iz,dt,run=false,jump=false){
  if(!Number.isFinite(dt)||dt<=0)return;
  const before=feet();let length=Math.hypot(ix,iz);if(length>1){ix/=length;iz/=length;}
  const speed=(run?MOVEMENT.runBase:MOVEMENT.walkBase)*multiplier;
  const smoothing=length>.01?MOVEMENT.acceleration:MOVEMENT.deceleration;
  const alpha=1-Math.exp(-smoothing*dt);
  const dx=ix*speed*dt+(vx-ix*speed)*alpha/smoothing,dz=iz*speed*dt+(vz-iz*speed)*alpha/smoothing;
  vx+=(ix*speed-vx)*alpha;vz+=(iz*speed-vz)*alpha;
  if(length<.01&&Math.hypot(vx,vz)<.005)vx=vz=0;
  if(jump&&grounded){vy=6.1;grounded=false;jumpCount++;}
  if(grounded&&vy<0)vy=-.8;else vy=Math.max(vy-20*dt,-25);
  controller.computeColliderMovement(collider,{x:dx,y:vy*dt,z:dz});
  const movement=controller.computedMovement(),p=body.translation();
  body.setNextKinematicTranslation({x:p.x+movement.x,y:p.y+movement.y,z:p.z+movement.z});
  world.timestep=dt;world.step();grounded=controller.computedGrounded();
  if(grounded&&vy<0)vy=-.8;
  let count=controller.numComputedCollisions();
  if(count){
   const hits=[];for(let i=0;i<count;i++){const c=controller.computedCollision(i);if(c?.collider)hits.push(labels.get(c.collider.handle));}
   lastCollision=hits.find(h=>h?.building||h?.kind==='Boundary')||hits.find(Boolean)||null;
  }
  const after=feet();const distance=Math.hypot(after.x-before.x,after.z-before.z);travel+=distance;horizontalSpeed=distance/dt;
  if(!Number.isFinite(after.x+after.y+after.z)||after.y< -4||Math.abs(after.x)>1000||Math.abs(after.z)>1100)reset();
 }
 function cameraDistance(origin,desired){
  const delta={x:desired.x-origin.x,y:desired.y-origin.y,z:desired.z-origin.z};const length=Math.hypot(delta.x,delta.y,delta.z);
  if(length<.001)return .65;
  const ray=new R.Ray(origin,{x:delta.x/length,y:delta.y/length,z:delta.z/length});
  const hit=world.castRay(ray,length,true,undefined,undefined,collider,body,c=>labels.get(c.handle)?.kind!=='WaterBarrier');
  return hit?Math.max(.65,hit.timeOfImpact-.23):length;
 }
 reset();
 function setSpeedMultiplier(value){if(value!==1&&value!==5)throw Error('Unsupported movement multiplier');multiplier=value;vx=vz=0;}
 return {world,body,collider,controller,labels,step,reset,setFeet,cameraDistance,setSpeedMultiplier,
  state:()=>({feet:feet(),grounded,verticalVelocity:vy,horizontalSpeed,speedMultiplier:multiplier,respawns,distanceTravelled:travel,lastCollision,jumpCount,colliders:labels.size})};
}
