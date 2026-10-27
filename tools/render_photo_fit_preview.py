"""Actual fixed-camera Cycles previews of existing geometry and photo adaptation."""
import argparse,bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--view',choices=['bay','front'],default='bay');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);bpy.ops.wm.open_mainfile(filepath=str(args.source));scene=bpy.context.scene
for o in scene.objects:
 if o.type=='MESH':o.hide_render=not(o.get('building_index')==13 or o.name.startswith('Library_') or o.name=='Campus_ground')
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=1
world=bpy.data.worlds.new('Photo_fit_preview_sky');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.4,.49,.56,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65;scene.world=world
light=bpy.data.lights.new('Photo_fit_preview_sun','SUN');light.energy=2.3;light.angle=math.radians(2);sun=bpy.data.objects.new('Photo_fit_preview_sun',light);scene.collection.objects.link(sun);sun.rotation_euler=Vector((-.4,.7,-1)).to_track_quat('-Z','Y').to_euler()
if args.view=='bay':
 profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];x=(profile[0][0]+profile[-1][0])/2-3.1;f=next(a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]) for a,b in zip(profile,profile[1:]) if a[0]<=x<=b[0]);u=Vector((math.cos(math.radians(35)),math.sin(math.radians(35)),0));v=Vector((-u.y,u.x,0));target=u*x+v*f+Vector((0,0,1.96+2*3.9+1.9));eye=target-v*11+Vector((0,0,.8));size=(768,512)
else:eye=Vector((35,-85,13));target=Vector((-25,0,14));size=(915,412)
cam=bpy.data.cameras.new('Photo_fit_fixed_camera');camera=bpy.data.objects.new('Photo_fit_fixed_camera',cam);scene.collection.objects.link(camera);camera.location=eye;camera.rotation_euler=(target-eye).to_track_quat('-Z','Y').to_euler();cam.sensor_fit='VERTICAL';cam.sensor_height=24;cam.lens=12/math.tan(math.radians(29));cam.clip_end=1200;scene.camera=camera
scene.render.resolution_x,scene.render.resolution_y=size;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';args.output.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(args.output);bpy.ops.render.render(write_still=True)
print('PHOTO_PREVIEW_RENDERED',json.dumps({'source':str(args.source),'output':str(args.output),'eye_blender':list(eye),'target_blender':list(target),'samples':32,'renderer':'ACTUAL_CYCLES_CPU_NOT_PHONE_PERFORMANCE'}),flush=True)
