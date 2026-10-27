"""Blender CPU reference preview; fixed camera for before/after comparison."""
import bpy,sys,math,json
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];source=Path(args[0]);output=Path(args[1]);bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
for ob in scene.objects:
    if ob.type=='MESH':ob.hide_render=not(ob.get('building_index')==13 or ob.name.startswith('Library_') or ob.name=='Campus_ground')
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=2
world=bpy.data.worlds.new('Reference_preview_sky');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.40,.49,.56,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65;scene.world=world
light=bpy.data.lights.new('Reference_preview_sun','SUN');light.energy=2.3;light.angle=math.radians(2);sun=bpy.data.objects.new('Reference_preview_sun',light);scene.collection.objects.link(sun);sun.rotation_euler=Vector((-.4,.7,-1)).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.cameras.new('Reference_fixed_camera');camera=bpy.data.objects.new('Reference_fixed_camera',cam);scene.collection.objects.link(camera);camera.location=(35,-85,13);camera.rotation_euler=(Vector((-25,0,14))-camera.location).to_track_quat('-Z','Y').to_euler();cam.lens=25;cam.clip_end=1200;scene.camera=camera
scene.render.resolution_x=915;scene.render.resolution_y=412;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(output);output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.render.render(write_still=True)
print('REFERENCE_PREVIEW_RENDERED',json.dumps({'source':str(source),'camera_blender_m':list(camera.location),'target_blender_m':[-25,0,14],'output':str(output),'renderer':'ACTUAL_CYCLES_CPU_NOT_PHONE_PERFORMANCE'}))
