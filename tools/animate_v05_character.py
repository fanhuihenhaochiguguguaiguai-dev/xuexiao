"""Reuse existing skinned meshes; replace only the gait with two-bone solutions."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
root=Path(__file__).resolve().parents[1];out=root/'.campus-cache/v05/character';out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'assets/henan_campus/character/output/CampusExplorer.blend'));scene=bpy.context.scene;scene.render.fps=30;bpy.context.preferences.filepaths.save_version=0
rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.animation_data_create()
for tr in list(rig.animation_data.nla_tracks):rig.animation_data.nla_tracks.remove(tr)
rig.animation_data.action=None
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
for pb in rig.pose.bones:pb.rotation_mode='QUATERNION'
rest={n:(rig.data.bones[n].head_local.copy(),rig.data.bones[n].tail_local.copy()) for n in rig.pose.bones.keys()};stance_errors=[]
def aim(name,head,tail):
 pb=rig.pose.bones[name];direction=tail-head;old=rest[name][1]-rest[name][0];rotation=old.rotation_difference(direction)
 pb.matrix=Matrix.Translation(head)@rotation.to_matrix().to_4x4()@pb.bone.matrix_local.to_3x3().to_4x4()
 bpy.context.view_layer.update()
for name,length in [('Idle',60),('Walk',30),('Run',24),('Jump',30)]:
 action=bpy.data.actions.new(name);rig.animation_data.action=action
 for f in range(length+1):
  scene.frame_set(f+1)
  t=f/length;phase=2*math.pi*t
  for pb in rig.pose.bones:pb.rotation_quaternion=Quaternion();pb.location=(0,0,0);pb.scale=(1,1,1)
  if name in ['Walk','Run']:
   running=name=='Run';hip_z=(-.06+.012*(1-math.cos(phase*2))) if running else (-.035+.008*(1-math.cos(phase*2)))
   rig.pose.bones['Hips'].location=rig.data.bones['Hips'].matrix_local.to_3x3().inverted()@Vector((0,0,hip_z))
   rig.pose.bones['Hips'].rotation_quaternion=Quaternion((0,1,0),.025*math.sin(phase));rig.pose.bones['Chest'].rotation_quaternion=Quaternion((1,0,0),.065 if running else .02)
   bpy.context.view_layer.update()
   for side,shift in [('L',0),('R',.5)]:
    p=(t+shift)%1;duty=.46 if running else .62;stride=.24 if running else .16;lift=.105 if running else .065
    if p<duty:fore=(1-2*p/duty)*stride;raise_z=0;foot_pitch=(-.10*max(0,1-p/.1)+.22*max(0,(p/duty-.78)/.22))
    else:q=(p-duty)/(1-duty);fore=-stride*math.cos(math.pi*q);raise_z=lift*math.sin(math.pi*q);foot_pitch=-.12*math.sin(math.pi*q)
    thigh='Thigh_'+side;shin='Shin_'+side;foot='Foot_'+side;hip=rig.pose.bones[thigh].head.copy();ankle=rest[foot][0].copy();ankle.y-=fore;ankle.z+=raise_z
    l1=rig.data.bones[thigh].length;l2=rig.data.bones[shin].length;delta=ankle-hip;dist=min(delta.length,l1+l2-.0002);u=delta.normalized();ankle=hip+u*dist;a=(l1*l1-l2*l2+dist*dist)/(2*dist);h=math.sqrt(max(0,l1*l1-a*a));perp=Vector((0,u.z,-u.y)).normalized();knee=hip+u*a+perp*h
    aim(thigh,hip,knee);aim(shin,knee,ankle);forward=Matrix.Rotation(foot_pitch,3,'X')@(rest[foot][1]-rest[foot][0]);aim(foot,ankle,ankle+forward)
    if p<duty:stance_errors.append(abs(rig.pose.bones[foot].head.z-rest[foot][0].z))
    swing=math.sin(2*math.pi*p);rig.pose.bones['UpperArm_'+side].rotation_quaternion=Quaternion((1,0,0),-(.42 if running else .20)*swing);rig.pose.bones['ForeArm_'+side].rotation_quaternion=Quaternion((1,0,0),-.65 if running else -.22)
  elif name=='Idle':rig.pose.bones['Chest'].rotation_quaternion=Quaternion((1,0,0),.009*math.sin(phase))
  else:
   bend=math.sin(math.pi*t)
   for side in ['L','R']:
    rig.pose.bones['Thigh_'+side].rotation_quaternion=Quaternion((1,0,0),.25*bend);rig.pose.bones['Shin_'+side].rotation_quaternion=Quaternion((1,0,0),-.5*bend);rig.pose.bones['UpperArm_'+side].rotation_quaternion=Quaternion((1,0,0),-.22*bend)
  for pb in rig.pose.bones:pb.keyframe_insert('rotation_quaternion',frame=f+1);pb.keyframe_insert('location',frame=f+1)
 for curve in action.fcurves:
  for key in curve.keyframe_points:key.interpolation='LINEAR'
 track=rig.animation_data.nla_tracks.new();track.name=name;track.strips.new(name,1,action);track.mute=True;rig.animation_data.action=None
if max(stance_errors)>.025:raise RuntimeError('Planted foot vertical drift exceeds 2.5cm: '+str(max(stance_errors)))
for tr in rig.animation_data.nla_tracks:tr.mute=False
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
 if o.type in ['MESH','ARMATURE']:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(out/'CampusExplorer.glb'),export_format='GLB',use_selection=True,export_skins=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(out/'CampusExplorer.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},bake_anim=True,add_leaf_bones=False,path_mode='COPY',embed_textures=True)
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'CampusExplorer.blend'),compress=True)
report={'passed':True,'method':'Existing mesh and rig reused; analytic two-bone sagittal gait, support/swing phases, toe roll and opposite arm swing','bones':len(rig.data.bones),'animations':['Idle','Walk','Run','Jump'],'max_planted_ankle_vertical_error_m':max(stance_errors),'fast_exploration_caveat':'5x spatial travel is intentionally beyond human walking speed; runtime cadence is capped rather than pretending a physically exact 13.25m/s walk.'}
(out/'animation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('V05_GAIT_PASSED',json.dumps(report),flush=True)
