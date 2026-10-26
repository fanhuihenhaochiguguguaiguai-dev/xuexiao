"""Blender CPU ambient-occlusion bake for actual scene and reusable facade cell."""
import bpy,json,sys,math
from pathlib import Path
root=Path(__file__).resolve().parents[1];stage=root/'.campus-cache/v05/final';out=stage/'assets'
bpy.ops.wm.open_mainfile(filepath=str(stage/'HenanCampus.blend'));scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4;bpy.context.preferences.filepaths.save_version=0
spec=json.loads((root/'assets/henan_campus/project/scene_specification.json').read_text());flat={o['name'] for o in spec['objects'] if o['group'] in ['Roads','Sports']};hidden=[]
for ob in scene.objects:
 if ob.name in flat and not ob.hide_render:hidden.append(ob);ob.hide_render=True

def bake(ob,name,res,distance):
 bpy.ops.object.select_all(action='DESELECT');ob.hide_render=False;ob.select_set(True);bpy.context.view_layer.objects.active=ob
 image=bpy.data.images.new(name,width=res,height=res,alpha=False);image.colorspace_settings.name='Non-Color'
 material=bpy.data.materials.new(name+'_temporary');material.use_nodes=True;n=material.node_tree.nodes;n.clear();ao=n.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=distance;ao.samples=8;ao.only_local=False;em=n.new('ShaderNodeEmission');output=n.new('ShaderNodeOutputMaterial');target=n.new('ShaderNodeTexImage');target.image=image;n.active=target
 material.node_tree.links.new(ao.outputs['AO'],em.inputs['Color']);material.node_tree.links.new(em.outputs[0],output.inputs['Surface']);old=list(ob.data.materials);ob.data.materials.clear();ob.data.materials.append(material)
 bpy.ops.object.bake(type='EMIT',margin=4,use_clear=True)
 image.filepath_raw=str(out/(name+'.png'));image.file_format='PNG';image.save();ob.data.materials.clear()
 for m in old:ob.data.materials.append(m)
 return image

ground=bpy.data.objects['Campus_ground'];previous_uv=ground.data.uv_layers.active_index;ground.data.uv_layers.active=ground.data.uv_layers['GroundAtlas'];bake(ground,'ground-ao',1024,6);ground.data.uv_layers.active_index=previous_uv
for ob in hidden:ob.hide_render=False
# Bake the same 3.2m x 3m window/rail cell used by the facade grammar.
mesh=bpy.data.meshes.new('AO_facade_cell');mesh.from_pydata([(-1.6,0,0),(1.6,0,0),(1.6,0,3),(-1.6,0,3)],[],[(0,1,2,3)]);mesh.update();wall=bpy.data.objects.new('AO_facade_cell',mesh);scene.collection.objects.link(wall);wall.location.x=1000;uv=mesh.uv_layers.new(name='UVMap')
for li,xy in zip(mesh.polygons[0].loop_indices,[(0,0),(1,0),(1,1),(0,1)]):uv.data[li].uv=xy
blocks=[]
for x,z,sx,sz in [(0,.765,1.89,.07),(0,2.485,1.89,.07),(-.91,1.625,.07,1.65),(.91,1.625,.07,1.65),(0,1.625,.05,1.65)]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=(1000+x,-.08,z));ob=bpy.context.object;ob.scale=(sx,.14,sz);blocks.append(ob)
bake(wall,'facade-cell-ao',256,.45)
for ob in [wall,*blocks]:bpy.data.objects.remove(ob,do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=str(stage/'HenanCampus.blend'),compress=True)
(out/'ao-bake.json').write_text(json.dumps({'passed':True,'method':'ACTUAL_BLENDER_CYCLES_AMBIENT_OCCLUSION_SHADER_TO_EMISSION_BAKE','ground_resolution':1024,'facade_cell_resolution':256,'cycles_samples':8,'ao_distance_ground_m':6,'ao_distance_facade_m':.45,'ground_scope':'Flat base with covering roads/sport slabs hidden while baking; reused on nearby flat surfaces.'},indent=2)+'\n');print('V05_AO_BAKE_PASSED',flush=True)
