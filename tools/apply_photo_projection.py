"""Blender: attach rectified photographed walls to the existing three facade planes."""
import argparse,bpy,bmesh,json,math,sys,hashlib,subprocess
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/photo-projection';P=ROOT/'assets/henan_campus/project';cfg=json.loads((ROOT/'configs/photo-projection-library.json').read_text());parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',choices=['pilot','small','front'],default='pilot');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);OUT=S/args.campaign;OUT.mkdir(parents=True,exist_ok=True);baseline=ROOT/'.campus-cache/photo-fit/baseline';baseline.mkdir(parents=True,exist_ok=True)
for rel,name in [('assets/henan_campus/project/HenanCampus.blend','HenanCampus.blend'),('assets/henan_campus/project/scene_specification.json','scene_specification.json'),('game/dist/assets/world.json','world.json'),('game/dist/assets/zones.json','zones.json')]:
 if not (baseline/name).exists():(baseline/name).write_bytes(subprocess.run(['git','show',cfg['baseline_commit']+':'+rel],cwd=ROOT,capture_output=True,check=True).stdout)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();mr=json.loads((S/'materials.json').read_text());assert mr['passed'] and all(sha(S/'assets'/n)==h for n,h in mr['textures'].items());fingerprint=hashlib.sha256((sha(Path(__file__))+sha(ROOT/'configs/photo-projection-library.json')+sha(baseline/'HenanCampus.blend')+mr['fingerprint']+args.campaign+bpy.app.version_string).encode()).hexdigest();receipt=OUT/'fit-report.json'
if receipt.exists():
 old=json.loads(receipt.read_text())
 if old.get('fingerprint')==fingerprint and all((OUT/n).is_file() and sha(OUT/n)==h for n,h in old['outputs'].items()):print('PHOTO_PROJECTION_CACHED');raise SystemExit(0)
bpy.ops.wm.open_mainfile(filepath=str(baseline/'HenanCampus.blend'));scene=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0;meshes=lambda:[o for o in scene.objects if o.type=='MESH'];before=sum(len(p.vertices)-2 for o in meshes() for p in o.data.polygons);profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];u=Vector((math.cos(math.radians(35)),math.sin(math.radians(35)),0));v=Vector((-u.y,u.x,0));selected=cfg['campaigns'][args.campaign]
def front(x):
 for a,b in zip(profile,profile[1:]):
  if a[0]<=x<=b[0]:return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
 return profile[0][1] if x<profile[0][0] else profile[-1][1]
def segment(x):return next((i for i,(a,b) in enumerate(zip(profile,profile[1:])) if a[0]-.01<=x<=b[0]+.01),None)
def point(x,y,z):return u*x+v*(front(x)-y)+Vector((0,0,z))
removed_faces=0
for name in ['Library_refined_details','V07_library_window_returns']:
 obj=bpy.data.objects[name];bm=bmesh.new();bm.from_mesh(obj.data);drop=[]
 for f in bm.faces:
  vv=[obj.matrix_world@q.co for q in f.verts];x=sum(q.dot(u) for q in vv)/len(vv)
  if segment(x) not in selected:continue
  if name=='Library_refined_details':
   if f.material_index==3:continue  # Keep the actual existing roof geometry.
   d=sum(front(q.dot(u))-q.dot(v) for q in vv)/len(vv)
   if not .1<d<.7:continue
   if f.material_index in [0,1] and max(q.z for q in vv)<cfg['projection_bottom_m']:continue # Existing entrance doors.
  drop.append(f)
 removed_faces+=len(drop);bmesh.ops.delete(bm,geom=drop,context='FACES');loose=[q for q in bm.verts if not q.link_faces]
 if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
 bm.to_mesh(obj.data);bm.free();obj.data.update()
 if not obj.data.polygons:bpy.data.objects.remove(obj,do_unlink=True)
if 1 in selected:
 old=bpy.data.objects.get('Library_v06_name')
 if old:bpy.data.objects.remove(old,do_unlink=True) # Actual photographed lettering is already in the facade texture.
for i in selected:
 a,b=profile[i],profile[i+1];z0=cfg['projection_bottom_m'];z1=cfg['projection_top_m'];vv=[point(a[0],.10,z0),point(b[0],.10,z0),point(b[0],.10,z1),point(a[0],.10,z1)];mesh=bpy.data.meshes.new('PhotoFacade_'+str(i));mesh.from_pydata(vv,[],[(0,1,2,3)]);mesh.update();obj=bpy.data.objects.new('Photo_projected_library_facade_'+str(i),mesh);scene.collection.objects.link(obj);obj['building_index']=13;obj['photo_projection']='EXISTING_WALL_GEOMETRY_WITH_RECTIFIED_PHOTO_NOT_A_SPHERICAL_VIEWER';obj['source_scene']=cfg['panorama_scene'];uv=mesh.uv_layers.new(name='UVMap')
 for li,coord in zip(mesh.polygons[0].loop_indices,[(0,0),(1,0),(1,1),(0,1)]):uv.data[li].uv=coord
 m=bpy.data.materials.new('PhotoProjectedFacade_'+str(i));m.use_nodes=True;n=m.node_tree.nodes;n.clear();tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(S/'assets'/('library-facade-'+str(i)+'.jpg')));em=n.new('ShaderNodeEmission');em.inputs['Strength'].default_value=1;output=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(tex.outputs['Color'],em.inputs['Color'])
 # Blender's documented camera-ray unlit pattern exports KHR_materials_unlit
 # and prevents these captured surfaces from emitting light onto the scene.
 path=n.new('ShaderNodeLightPath');transparent=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');m.node_tree.links.new(path.outputs['Is Camera Ray'],mix.inputs[0]);m.node_tree.links.new(transparent.outputs[0],mix.inputs[1]);m.node_tree.links.new(em.outputs[0],mix.inputs[2]);m.node_tree.links.new(mix.outputs[0],output.inputs['Surface']);mesh.materials.append(m)
if args.campaign=='front':
 paving=bpy.data.objects['Library_south_plaza'];m=bpy.data.materials['V05_terrain_paving'].copy();m.name='V05_terrain_PhotoPavers';nodes=m.node_tree.nodes;tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(S/'assets/library-pavers.png'));m.node_tree.links.new(tex.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color']);nodes.get('Principled BSDF').inputs['Roughness'].default_value=.9;paving.data.materials[0]=m
 uv=paving.data.uv_layers.get('UVMap');atlas=paving.data.uv_layers.get('GroundAtlas') or paving.data.uv_layers.new(name='GroundAtlas');x0,y0,x1,y1=json.loads((P/'assets/lighting-water.json').read_text())['ground_blender_bounds']
 for loop in paving.data.loops:
  q=paving.matrix_world@paving.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(q.x/.9,q.y/.6);atlas.data[loop.index].uv=((q.x-x0)/(x1-x0),(q.y-y0)/(y1-y0))
for im in bpy.data.images:
 if im.type=='IMAGE' and im.source=='FILE' and not im.packed_file:im.pack()
all_meshes=meshes();triangles=sum(len(p.vertices)-2 for o in all_meshes for p in o.data.polygons);assert triangles-before<=cfg['budget']['maximum_added_triangles']
def export(path,objects):
 bpy.ops.object.select_all(action='DESELECT')
 for obj in objects:obj.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_extras=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'HenanCampus.blend'),compress=True);export(OUT/'library.glb',[o for o in all_meshes if o.get('building_index')==13])
if args.campaign=='front':
 export(OUT/'HenanCampus.glb',all_meshes)
 # FBX has no portable KHR unlit extension. Export the same photographic colors
 # as ordinary base-color maps; keep the formal Blender/GLB unlit materials.
 replaced=[];fbx_materials={}
 for obj in all_meshes:
  for slot in obj.material_slots:
   source=slot.material
   if not source or not source.name.startswith('PhotoProjectedFacade'):continue
   if source.name not in fbx_materials:
    m=bpy.data.materials.new(source.name+'_FBX');m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=next(n.image for n in source.node_tree.nodes if n.type=='TEX_IMAGE');m.node_tree.links.new(t.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.95;fbx_materials[source.name]=m
   replaced.append((slot,source));slot.material=fbx_materials[source.name]
 bpy.ops.export_scene.fbx(filepath=str(OUT/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
 for slot,source in replaced:slot.material=source
 manifest=json.loads((baseline/'zones.json').read_text());coarse={n for z in manifest['zones'] for n in z['coarse_nodes']};base_objects=[o for o in all_meshes if not o.get('building_index') or o.name in coarse];lib=next(z for z in manifest['zones'] if z['id']==13)
 for i in selected:
  source=bpy.data.objects['Photo_projected_library_facade_'+str(i)];copy=source.copy();copy.data=source.data.copy();copy.name='Photo_coarse_library_facade_'+str(i);scene.collection.objects.link(copy);m=source.data.materials[0].copy();m.name='PhotoProjectedCoarse_'+str(i)
  next(n for n in m.node_tree.nodes if n.type=='TEX_IMAGE').image=bpy.data.images.load(str(S/'assets'/('library-coarse-'+str(i)+'.jpg')));copy.data.materials[0]=m;base_objects.append(copy);lib['coarse_nodes'].append(copy.name)
 export(OUT/'campus-base.glb',base_objects);(OUT/'zones.json').write_text(json.dumps(manifest,indent=2)+'\n')
outputs=['HenanCampus.blend','library.glb']+(['HenanCampus.glb','HenanCampus.fbx','campus-base.glb','zones.json'] if args.campaign=='front' else []);report={'passed':True,'strategy':'RECTIFIED_WHOLE_FACADE_PIECES_ON_EXISTING_3D_WALLS','fingerprint':fingerprint,'campaign':args.campaign,'selected_facade_planes':selected,'baseline_triangles':before,'triangles':triangles,'triangle_change':triangles-before,'old_decorative_faces_removed':removed_faces,'photo_texture_bytes':mr['texture_bytes'],'collision_solids_modified':False,'floor_height_rule_m':3.9,'body_height_m':35.1,'window_to_floor_alignment':'NOT_FULLY_VALIDATED_NOT_SURVEYED','lighting':'CAPTURED_STATIC_LIGHTING_IN_PHOTO; UNLIT_MATERIAL','limitations':cfg['quality_limits'],'materials':mr,'outputs':{n:sha(OUT/n) for n in outputs}};receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PHOTO_PROJECTION_MESH_PASSED',json.dumps({k:report[k] for k in ['campaign','selected_facade_planes','triangle_change','photo_texture_bytes']}),flush=True)
