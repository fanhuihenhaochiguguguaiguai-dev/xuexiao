"""Bind real bake maps and pond depth/foam textures, then export the same scene."""
import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];stage=root/'.campus-cache/v05/final';assets=stage/'assets'
bpy.ops.wm.open_mainfile(filepath=str(stage/'HenanCampus.blend'));scene=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
spec=json.loads((root/'assets/henan_campus/project/scene_specification.json').read_text());terrain={o['name'] for o in spec['objects'] if o['group'] in ['Ground','Roads','Sports']};meta=json.loads((assets/'lighting-water.json').read_text());xmin,ymin,xmax,ymax=meta['ground_blender_bounds']
from io_scene_gltf2.blender.com.material_helpers import create_settings_group
settings=bpy.data.node_groups.get('glTF Material Output') or create_settings_group('glTF Material Output')
image_ground=bpy.data.images.load(str(assets/'ground-occlusion.png'));image_ground.colorspace_settings.name='Non-Color';image_facade=bpy.data.images.load(str(assets/'facade-cell-ao.png'));image_facade.colorspace_settings.name='Non-Color'
def attach_ao(material,image,uv_name):
 nodes=material.node_tree.nodes;group=nodes.new('ShaderNodeGroup');group.node_tree=settings;tex=nodes.new('ShaderNodeTexImage');tex.image=image;uv=nodes.new('ShaderNodeUVMap');uv.uv_map=uv_name;material.node_tree.links.new(uv.outputs[0],tex.inputs['Vector']);material.node_tree.links.new(tex.outputs['Color'],group.inputs['Occlusion']);material['baked_ao_source']='Blender Cycles AO + static directional shadow for terrain' if image==image_ground else 'Blender Cycles facade-cell AO'
cache={};ground_surfaces=0
for ob in scene.objects:
 if ob.type!='MESH' or ob.name not in terrain:continue
 layer=ob.data.uv_layers.get('GroundAtlas') or ob.data.uv_layers.new(name='GroundAtlas')
 for face in ob.data.polygons:
  for li in face.loop_indices:
   p=ob.matrix_world@ob.data.vertices[ob.data.loops[li].vertex_index].co;layer.data[li].uv=((p.x-xmin)/(xmax-xmin),(p.y-ymin)/(ymax-ymin))
 for i,m in enumerate(ob.data.materials):
  if not m:continue
  if m.name not in cache:
   n=m.copy();n.name='V05_terrain_'+m.name;attach_ao(n,image_ground,'GroundAtlas');cache[m.name]=n
  ob.data.materials[i]=cache[m.name]
 ground_surfaces+=1
attach_ao(bpy.data.materials['V05_Orange_wall'],image_facade,'UVMap')
for water in meta['water']:
 ob=bpy.data.objects[water['object']];x0,y0,x1,y1=water['blender_bounds'];layer=ob.data.uv_layers.active
 for face in ob.data.polygons:
  for li in face.loop_indices:
   p=ob.matrix_world@ob.data.vertices[ob.data.loops[li].vertex_index].co;layer.data[li].uv=((p.x-x0)/(x1-x0),(p.y-y0)/(y1-y0))
 m=ob.data.materials[0].copy();m.name='V05_water_'+water['object'];tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(assets/water['color_image']));tex.extension='EXTEND';bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(1,1,1,1);m.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
 for i in range(len(ob.data.materials)):ob.data.materials[i]=m
 ob['depth_model']='Estimated bank-distance profile, maximum 1.3m; not measured bathymetry';ob['shore_foam']='Subtle procedural bank band'
for image in bpy.data.images:
 if image.type=='IMAGE' and image.source=='FILE':image.pack()
scene['v05_lighting']='Actual baked Cycles AO + CPU directional static shadow atlas; local dynamic character shadows in engine'
bpy.ops.object.select_all(action='DESELECT')
for ob in scene.objects:
 if ob.type=='MESH':ob.select_set(True)
bpy.context.view_layer.objects.active=bpy.data.objects['Campus_ground']
bpy.ops.export_scene.gltf(filepath=str(stage/'HenanCampus.glb'),export_format='GLB',use_selection=True,export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(stage/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
bpy.ops.wm.save_as_mainfile(filepath=str(stage/'HenanCampus.blend'),compress=True)
print('V05_LIGHTING_BOUND',ground_surfaces,'terrain surfaces',len(cache),'materials',flush=True)
