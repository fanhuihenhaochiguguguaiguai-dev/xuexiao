"""Bind the new AO/shadow image and re-export only affected shared assets."""
import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/v06';A=S/'assets';bpy.ops.wm.open_mainfile(filepath=str(S/'HenanCampus.blend'));scene=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0;combined=bpy.data.images.load(str(A/'ground-occlusion-v06.png'),check_existing=True);combined.colorspace_settings.name='Non-Color'
rebound=0
for m in bpy.data.materials:
 if not m.use_nodes:continue
 for node in m.node_tree.nodes:
  if node.type=='TEX_IMAGE' and node.image and 'ground-occlusion' in node.image.name:node.image=combined;rebound+=1
assert rebound>0
albedo=bpy.data.images.load(str(A/'stone-basecolor-1024.png'),check_existing=True)
for name in ['V06_pale_stone','Library_photo_guided_stone','Library_granite_steps','V05_Pale_stone']:
 m=bpy.data.materials.get(name)
 if not m:continue
 tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=albedo;m.node_tree.links.new(tex.outputs['Color'],m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
for im in bpy.data.images:
 if im.type=='IMAGE' and im.source=='FILE':im.pack()
all_meshes=[o for o in scene.objects if o.type=='MESH']
def export(path,objects):
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_extras=True)
export(S/'HenanCampus.glb',all_meshes);bpy.ops.export_scene.fbx(filepath=str(S/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True);bpy.ops.wm.save_as_mainfile(filepath=str(S/'HenanCampus.blend'),compress=True)
manifest=json.loads((S/'zones.json').read_text());base=[o for o in all_meshes if not o.get('building_index')]
for z in manifest['zones']:
 objects=[o for o in all_meshes if o.get('building_index')==z['id']];export(S/'zones'/f'b{z["id"]:02d}.glb',objects);base.extend(o for o in objects if o.name in z['coarse_nodes'])
export(S/'campus-base.glb',base);print('V06_LIGHTING_EXPORTED',rebound,flush=True)
