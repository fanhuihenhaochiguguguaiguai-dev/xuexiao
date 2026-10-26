// The same Rapier controller is used by the browser and the executable checks.
export const MOVEMENT={walkBase:2.65,runBase:5.3,defaultMultiplier:5,acceleration:12,deceleration:18};
export function waterAtPosition(zones,x,z){
 const inside=(ring)=>{let hit=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;};
 for(const zone of zones||[]){
  if(zone.bounds&&(x<zone.bounds[0]||z<zone.bounds[1]||x>zone.bounds[2]||z>zone.bounds[3]))continue;
  if(!inside(zone.rings[0])||zone.rings.slice(1).some(inside))continue;
  let distance=Infinity;
  for(const ring of zone.rings)for(let i=0;i<ring.length;i++){
   const a=ring[i],b=ring[(i+1)%ring.length],dx=b[0]-a[0],dz=b[1]-a[1],t=Math.max(0,Math.min(1,((x-a[0])*dx+(z-a[1])*dz)/(dx*dx+dz*dz||1)));
   distance=Math.min(distance,Math.hypot(x-a[0]-t*dx,z-a[1]-t*dz));
  }
  const depth=Math.min(zone.maximumDepth??1.3,distance*(zone.depthPerBankDistance??.6)),surface=zone.surface??.217;
  return {zone:zone.id,depth,surface,bottom:surface-depth,bankDistance:distance};
 }
 return null;
}
export function createSimulation(R, data,options={}) {
 const world=new R.World({x:0,y:-20,z:0});const labels=new Map();
 for(const c of data.colliders){
  if(c.kind==='WaterBarrier')continue;
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
  const wet=waterAtPosition(data.waterZones,before.x,before.z),immersed=wet&&before.y<wet.surface+.07;
  const swimming=immersed&&wet.depth>.85&&before.y<wet.surface-.2;
  const speed=immersed?Math.min((run?MOVEMENT.runBase:MOVEMENT.walkBase)*multiplier,swimming?2.2:2.8):(run?MOVEMENT.runBase:MOVEMENT.walkBase)*multiplier;
  const smoothing=length>.01?MOVEMENT.acceleration:MOVEMENT.deceleration;
  const alpha=1-Math.exp(-smoothing*dt);
  const dx=ix*speed*dt+(vx-ix*speed)*alpha/smoothing,dz=iz*speed*dt+(vz-iz*speed)*alpha/smoothing;
  vx+=(ix*speed-vx)*alpha;vz+=(iz*speed-vz)*alpha;
  if(length<.01&&Math.hypot(vx,vz)<.005)vx=vz=0;
  if(jump&&(grounded||swimming)){vy=immersed?2.6:6.1;grounded=false;jumpCount++;}
  if(immersed){
   // Displacement-based buoyancy plus drag; bathymetry is explicitly estimated.
   const submerged=Math.max(0,Math.min(1,(wet.surface-before.y)/.64));
   // A horizontal body-volume proxy, density 0.96 relative to water. The
   // upright collision capsule remains conservative around hard obstacles.
   vy+=(-20+(20/.96)*submerged-4.5*vy)*dt;
  }else if(grounded&&vy<0)vy=-.8;else vy=Math.max(vy-20*dt,-25);
  const entering=waterAtPosition(data.waterZones,before.x+dx,before.z+dz);
  controller.computeColliderMovement(collider,{x:dx,y:vy*dt,z:dz},undefined,undefined,c=>{
   const kind=labels.get(c.handle)?.kind;
   return !(entering&&['Ground','Roads','Landscape'].includes(kind));
  });
  const movement=controller.computedMovement(),p=body.translation();
  const next={x:p.x+movement.x,y:p.y+movement.y,z:p.z+movement.z};
  const nextWet=waterAtPosition(data.waterZones,next.x,next.z);let bedContact=false;
  if(nextWet&&next.y-heightOffset<nextWet.bottom+.025){next.y=nextWet.bottom+.025+heightOffset;vy=Math.max(0,vy);bedContact=true;}
  if(wet&&!nextWet&&next.y-heightOffset<(data.groundTopMeters??0)+.025){next.y=(data.groundTopMeters??0)+.025+heightOffset;vy=Math.max(0,vy);bedContact=true;}
  body.setNextKinematicTranslation(next);
  world.timestep=dt;world.step();grounded=controller.computedGrounded()||bedContact;
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
  state:()=>{const p=feet(),water=waterAtPosition(data.waterZones,p.x,p.z),immersed=!!water&&p.y<water.surface+.07;return {feet:p,grounded,verticalVelocity:vy,horizontalSpeed,speedMultiplier:multiplier,respawns,distanceTravelled:travel,lastCollision,jumpCount,colliders:labels.size,water:immersed?{...water,mode:water.depth>.85&&p.y<water.surface-.2?'swimming':'wading',depthStatus:'ESTIMATED_NOT_MEASURED'}:null};}};
}
