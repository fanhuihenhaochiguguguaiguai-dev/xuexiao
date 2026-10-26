"""Shared photo-type palette assignment; reuses geometry and existing bake maps."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
def apply_palette(scene,spec,profile):
 def material(name,color):
  m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;c=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in color);m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*c,1);m.diffuse_color=(*c,1);return m
 palette=profile.get('palette',{});brick=material('V05_Orange_wall',palette.get('short_wall',[.65,.32,.23]));pale=material('V05_Pale_wall',palette.get('long_wall',[.77,.76,.69]));changed=[]
 # Reuse the already ray-traced facade cell; no rebake for a color change.
 ao=next((n for n in brick.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'facade-cell-ao' in n.image.name),None)
 if ao and not any(n.type=='GROUP' and n.node_tree and n.node_tree.name.startswith('glTF Material Output') for n in pale.node_tree.nodes):
  from io_scene_gltf2.blender.com.material_helpers import create_settings_group
  group=bpy.data.node_groups.get('glTF Material Output') or create_settings_group('glTF Material Output');n=pale.node_tree.nodes.new('ShaderNodeGroup');n.node_tree=group;t=pale.node_tree.nodes.new('ShaderNodeTexImage');t.image=ao.image;pale.node_tree.links.new(t.outputs['Color'],n.inputs['Occlusion'])
 for idx in profile['building_ids']:
  source=next(o for o in spec['objects'] if o.get('building_index')==idx and o['group']=='Buildings');ob=bpy.data.objects[source['name']];ring=source['polygon']['rings'][0];edges=[]
  for a,b in zip(ring,ring[1:]+ring[:1]):
   a=Vector((*a,0));b=Vector((*b,0));length=(b-a).length
   if length>1e-4:edges.append((a,(b-a).normalized(),length))
  longest=max(e[2] for e in edges);ob.data.materials[0]=brick
  if pale.name not in ob.data.materials:ob.data.materials.append(pale)
  pale_index=list(ob.data.materials).index(pale)
  for face in ob.data.polygons:
   if abs(face.normal.z)>.5:continue
   coords=[ob.matrix_world@ob.data.vertices[v].co for v in face.vertices]
   for a,t,length in edges:
    n=Vector((t.y,-t.x,0))
    if all(abs((Vector((p.x,p.y,0))-a).dot(n))<.02 and -.02<=(Vector((p.x,p.y,0))-a).dot(t)<=length+.02 for p in coords):face.material_index=pale_index if length>=longest*profile.get('long_face_threshold',.55) else 0;break
  changed.append(idx)
 return changed
if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:];source=Path(args[0]);out=Path(args[1]);out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.filepaths.save_version=0
 spec=json.loads((ROOT/'assets/henan_campus/project/scene_specification.json').read_text());profile=json.loads((ROOT/'configs/v05-buildings.json').read_text())['facade_profile'];changed=apply_palette(bpy.context.scene,spec,profile)
 bpy.ops.object.select_all(action='DESELECT')
 for o in bpy.context.scene.objects:
  if o.type=='MESH':o.select_set(True)
 bpy.context.view_layer.objects.active=bpy.data.objects['Campus_ground']
 for image in bpy.data.images:
  if image.type=='IMAGE' and image.source=='FILE':image.pack()
 bpy.ops.export_scene.gltf(filepath=str(out/'HenanCampus.glb'),export_format='GLB',use_selection=True,export_extras=True)
 bpy.ops.export_scene.fbx(filepath=str(out/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'HenanCampus.blend'),compress=True);print('PALETTE_RULE_APPLIED',changed)
