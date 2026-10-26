"""Preserve validated locomotion; add aquatic clips and cloth/hair shading."""
import bpy,json,math
from pathlib import Path
from mathutils import Quaternion,Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.campus-cache/v06/character';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/henan_campus/character/output/CampusExplorer.blend'));scene=bpy.context.scene;scene.render.fps=30;bpy.context.preferences.filepaths.save_version=0;rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.animation_data_create()
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=None
for name,length in [('Swim',36),('Tread',60)]:
 action=bpy.data.actions.new(name);rig.animation_data.action=action
 for frame in range(length+1):
  scene.frame_set(frame+1);phase=2*math.pi*frame/length
  for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.rotation_quaternion=Quaternion();bone.location=(0,0,0)
  for side,offset in [('L',0),('R',math.pi)]:
   if name=='Swim':
    rig.pose.bones['UpperArm_'+side].rotation_quaternion=Quaternion((1,0,0),-.8+.65*math.cos(phase+offset));rig.pose.bones['ForeArm_'+side].rotation_quaternion=Quaternion((1,0,0),-.65-.25*math.sin(phase+offset));rig.pose.bones['Thigh_'+side].rotation_quaternion=Quaternion((1,0,0),.18*math.sin(phase+offset));rig.pose.bones['Shin_'+side].rotation_quaternion=Quaternion((1,0,0),-.22+.14*math.cos(phase+offset))
   else:
    rig.pose.bones['UpperArm_'+side].rotation_quaternion=Quaternion((1,0,0),-.4+.17*math.sin(phase+offset));rig.pose.bones['ForeArm_'+side].rotation_quaternion=Quaternion((1,0,0),-.9);rig.pose.bones['Thigh_'+side].rotation_quaternion=Quaternion((1,0,0),.15*math.sin(phase+offset));rig.pose.bones['Shin_'+side].rotation_quaternion=Quaternion((1,0,0),-.28)
  if name=='Swim' and rig.pose.bones.get('Head'):rig.pose.bones['Head'].rotation_quaternion=Quaternion((1,0,0),-.45)
  for bone in rig.pose.bones:bone.keyframe_insert('rotation_quaternion',frame=frame+1);bone.keyframe_insert('location',frame=frame+1)
 for curve in action.fcurves:
  for key in curve.keyframe_points:key.interpolation='LINEAR'
 track=rig.animation_data.nla_tracks.new();track.name=name;track.strips.new(name,1,action);track.mute=True;rig.animation_data.action=None
# New source-normal texture is generated at its native resolution.
image=bpy.data.images.new('V06_ribbed_fabric_normal',width=512,height=512);pixels=[]
for y in range(512):
 for x in range(512):
  nx=.12*math.sin(x*2*math.pi/8);ny=.02*math.sin(y*2*math.pi/11);n=math.sqrt(1+nx*nx+ny*ny);pixels.extend((nx/n*.5+.5,ny/n*.5+.5,1/n*.5+.5,1))
image.pixels=pixels;image.colorspace_settings.name='Non-Color';image.filepath_raw=str(OUT/'fabric-normal.png');image.file_format='PNG';image.save();image.pack()
for name,rough in [('Ivory_ribbed_top',.86),('Blue_denim',.94)]:
 m=bpy.data.materials[name];bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=rough;tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;normal=m.node_tree.nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.22 if 'Ivory' in name else .08;m.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color']);m.node_tree.links.new(normal.outputs['Normal'],bs.inputs['Normal'])
for name in ['Dark_brown_hair','Hair_soft_highlights']:
 m=bpy.data.materials.get(name)
 if m:m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.48
for name in ['Warm_skin','Reference_projected_face']:
 m=bpy.data.materials.get(name)
 if m:
  bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.56
for tr in rig.animation_data.nla_tracks:tr.mute=False
bpy.ops.object.select_all(action='DESELECT')
for ob in scene.objects:
 if ob.type in ['MESH','ARMATURE']:ob.select_set(True)
bpy.context.view_layer.objects.active=rig;bpy.ops.export_scene.gltf(filepath=str(OUT/'CampusExplorer.glb'),export_format='GLB',use_selection=True,export_skins=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'CampusExplorer.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},bake_anim=True,add_leaf_bones=False,path_mode='COPY',embed_textures=True)
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1)
coords=[ob.matrix_world@Vector(p) for ob in scene.objects if ob.type=='MESH' for p in ob.bound_box];height=max(p.z for p in coords)-min(p.z for p in coords);assert 1.65<height<1.75
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'CampusExplorer.blend'),compress=True)
report={'passed':True,'height_m':height,'original_mesh_and_rig_reused':True,'preserved_clips':['Idle','Walk','Run','Jump'],'added_clips':['Swim','Tread'],'shading':'New ribbed cloth normal, denim roughness, hair/skin roughness','likeness_status':'REFERENCE_GUIDED_APPROXIMATION_NOT_PHOTO_REAL_SCAN'};(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('V06_CHARACTER_PASSED',height)
