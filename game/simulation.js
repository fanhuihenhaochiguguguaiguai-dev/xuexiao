// The same Rapier controller is used by the browser and the executable checks.
export function createSimulation(R, data) {
 const world=new R.World({x:0,y:-20,z:0});const labels=new Map();
 for(const c of data.colliders){
  const desc=R.ColliderDesc.trimesh(new Float32Array(c.vertices),new Uint32Array(c.indices));
  desc.setFriction(.75);const collider=world.createCollider(desc);labels.set(collider.handle,{name:c.name,kind:c.kind,building:c.building});
 }
 const halfHeight=.52,radius=.27,heightOffset=halfHeight+radius;
 const body=world.createRigidBody(R.RigidBodyDesc.kinematicPositionBased().setTranslation(data.spawn.x,2,data.spawn.z));
 const collider=world.createCollider(R.ColliderDesc.capsule(halfHeight,radius).setFriction(0),body);
 const controller=world.createCharacterController(.025);controller.enableAutostep(.30,.20,true);controller.enableSnapToGround(.27);
 controller.setMaxSlopeClimbAngle(Math.PI*.27);controller.setMinSlopeSlideAngle(Math.PI*.32);
 let vy=0,grounded=false,respawns=0,travel=0,lastCollision=null,jumpCount=0;
 const feet=()=>{const p=body.translation();return {x:p.x,y:p.y-heightOffset,z:p.z};};
 function setFeet(x,y,z){body.setTranslation({x,y:y+heightOffset,z},true);body.setNextKinematicTranslation({x,y:y+heightOffset,z});vy=0;grounded=false;world.step();}
 function reset(poi=data.spawn){setFeet(poi.x,.55,poi.z);respawns++;}
 function step(ix,iz,dt,run=false,jump=false){
  if(!Number.isFinite(dt)||dt<=0)return;
  const before=feet();let length=Math.hypot(ix,iz);if(length>1){ix/=length;iz/=length;}
  const speed=run?5.3:2.65;
  if(jump&&grounded){vy=6.1;grounded=false;jumpCount++;}
  if(grounded&&vy<0)vy=-.8;else vy=Math.max(vy-20*dt,-25);
  controller.computeColliderMovement(collider,{x:ix*speed*dt,y:vy*dt,z:iz*speed*dt});
  const movement=controller.computedMovement(),p=body.translation();
  body.setNextKinematicTranslation({x:p.x+movement.x,y:p.y+movement.y,z:p.z+movement.z});
  world.timestep=dt;world.step();grounded=controller.computedGrounded();
  if(grounded&&vy<0)vy=-.8;
  let count=controller.numComputedCollisions();
  if(count){
   const hits=[];for(let i=0;i<count;i++){const c=controller.computedCollision(i);if(c?.collider)hits.push(labels.get(c.collider.handle));}
   lastCollision=hits.find(h=>h?.building||h?.kind==='Boundary')||hits.find(Boolean)||null;
  }
  const after=feet();travel+=Math.hypot(after.x-before.x,after.z-before.z);
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
 return {world,body,collider,controller,labels,step,reset,setFeet,cameraDistance,
  state:()=>({feet:feet(),grounded,verticalVelocity:vy,respawns,distanceTravelled:travel,lastCollision,jumpCount,colliders:labels.size})};
}
