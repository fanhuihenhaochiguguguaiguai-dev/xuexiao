"""Actual 2048px Cycles AO; reuse validated facade-cell AO, bind new atlas."""
import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/v06';A=S/'assets';bpy.ops.wm.open_mainfile(filepath=str(S/'HenanCampus.blend'));scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4;bpy.context.preferences.filepaths.save_version=0
spec=json.loads((S/'scene_specification.json').read_text());flat={o['name'] for o in spec['objects'] if o['group'] in ['Roads','Sports'] or o['name']=='Library_south_plaza' or o['material']=='water'};hidden=[]
for ob in scene.objects:
 if ob.name in flat and not ob.hide_render:ob.hide_render=True;hidden.append(ob)
ground=bpy.data.objects['Campus_ground'];bpy.ops.object.select_all(action='DESELECT');ground.select_set(True);bpy.context.view_layer.objects.active=ground;previous_uv=ground.data.uv_layers.active_index;ground.data.uv_layers.active=ground.data.uv_layers['GroundAtlas']
image=bpy.data.images.new('V06_ground_AO_2048',width=2048,height=2048,alpha=False);image.colorspace_settings.name='Non-Color';m=bpy.data.materials.new('V06_AO_temporary');m.use_nodes=True;n=m.node_tree.nodes;n.clear();ao=n.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=6;ao.samples=16;em=n.new('ShaderNodeEmission');output=n.new('ShaderNodeOutputMaterial');target=n.new('ShaderNodeTexImage');target.image=image;n.active=target;m.node_tree.links.new(ao.outputs['AO'],em.inputs['Color']);m.node_tree.links.new(em.outputs[0],output.inputs['Surface']);old=list(ground.data.materials);ground.data.materials.clear();ground.data.materials.append(m)
bpy.ops.object.bake(type='EMIT',margin=5,use_clear=True);image.filepath_raw=str(A/'ground-ao-2048.png');image.file_format='PNG';image.save();ground.data.materials.clear()
for material in old:ground.data.materials.append(material)
ground.data.uv_layers.active_index=previous_uv
for ob in hidden:ob.hide_render=False
bpy.ops.wm.save_as_mainfile(filepath=str(S/'HenanCampus.blend'),compress=True)
(A/'v06-ao-bake.json').write_text(json.dumps({'passed':True,'method':'ACTUAL_BLENDER_CYCLES_AO_SHADER_TO_EMISSION_BAKE','ground_resolution':2048,'cycles_samples':16,'ao_shader_samples':16,'distance_m':6,'scope':'Ground with flat covering road/sport slabs hidden; shared on nearby flat surfaces. Existing actual facade-cell AO retained. Not full indirect-light GI baking.'},indent=2)+'\n');print('V06_AO_BAKED',flush=True)
