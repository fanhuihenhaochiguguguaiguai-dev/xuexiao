"""Blender: adapt photographic components to existing facade bays, not a panorama shell."""
import argparse,bpy,bmesh,json,math,sys,hashlib,subprocess
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/photo-fit';P=ROOT/'assets/henan_campus/project'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',choices=['pilot','small','front'],default='pilot');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads((ROOT/'configs/photo-fit-library.json').read_text());selection=cfg['campaigns'][args.campaign];OUT=S/args.campaign;OUT.mkdir(parents=True,exist_ok=True)
baseline=S/'baseline';baseline.mkdir(exist_ok=True)
for rel,name in [('assets/henan_campus/project/HenanCampus.blend','HenanCampus.blend'),('assets/henan_campus/project/scene_specification.json','scene_specification.json'),('game/dist/assets/world.json','world.json'),('game/dist/assets/zones.json','zones.json')]:
 if not (baseline/name).exists():(baseline/name).write_bytes(subprocess.run(['git','show',cfg['baseline_commit']+':'+rel],cwd=ROOT,capture_output=True,check=True).stdout)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();materials=json.loads((S/'materials.json').read_text());assert materials['passed'];assert all(sha(S/'assets'/n)==h for n,h in materials['texture_hashes'].items())
fingerprint=hashlib.sha256((sha(Path(__file__))+sha(ROOT/'configs/photo-fit-library.json')+sha(baseline/'HenanCampus.blend')+materials['fingerprint']+args.campaign+bpy.app.version_string).encode()).hexdigest();receipt=OUT/'fit-report.json'
if receipt.exists():
 old=json.loads(receipt.read_text())
 if old.get('fingerprint')==fingerprint and all((OUT/n).is_file() and sha(OUT/n)==h for n,h in old.get('outputs',{}).items()):print('PHOTO_FIT_CACHED',args.campaign);sys.exit(0)
bpy.ops.wm.open_mainfile(filepath=str(baseline/'HenanCampus.blend'));bpy.context.preferences.filepaths.save_version=0;scene=bpy.context.scene;before_triangles=sum(len(p.vertices)-2 for o in scene.objects if o.type=='MESH' for p in o.data.polygons)
profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];u=Vector((math.cos(math.radians(35)),math.sin(math.radians(35)),0));v=Vector((-u.y,u.x,0));uc=(profile[0][0]+profile[-1][0])/2;base=1.96
def front(x):
 for a,b in zip(profile,profile[1:]):
  if a[0]<=x<=b[0]:return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
 return profile[0][1] if x<profile[0][0] else profile[-1][1]
def point(x,d,z):return u*x+v*(front(x)-d)+Vector((0,0,z))
def photo_material(name,image,roughness,metal=0,normal=None):
 m=bpy.data.materials.new(name);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=roughness;bs.inputs['Metallic'].default_value=metal
 t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(S/'assets'/image),check_existing=True);m.node_tree.links.new(t.outputs['Color'],bs.inputs['Base Color'])
 if normal:
  t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(S/'assets'/normal),check_existing=True);t.image.colorspace_settings.name='Non-Color';n=m.node_tree.nodes.new('ShaderNodeNormalMap');n.inputs['Strength'].default_value=.16;m.node_tree.links.new(t.outputs['Color'],n.inputs['Color']);m.node_tree.links.new(n.outputs['Normal'],bs.inputs['Normal'])
 return m
wall=photo_material('PhotoLibraryCladding','library-photo-cladding.png',.84,normal='library-photo-normal.png');glass=photo_material('PhotoLibraryGlazing','library-photo-windows.png',.38,.04)
# Remove only the selected old front glazing and its thin framing. Roof, door,
# return walls, rear glazing and all physical solids remain in place.
detail=bpy.data.objects['Library_refined_details'];bm=bmesh.new();bm.from_mesh(detail.data);removed=[];per_cell={}
for f in bm.faces:
 if f.material_index not in [0,1]:continue
 vv=[detail.matrix_world@q.co for q in f.verts];x=sum(q.dot(u) for q in vv)/len(vv);d=sum(front(q.dot(u))-q.dot(v) for q in vv)/len(vv);lo=min(q.z for q in vv);hi=max(q.z for q in vv)
 row=round((lo-base-.65)/3.9);bay=round((x-(uc-34.1))/6.2)
 if row in selection['rows'] and bay in selection['bays'] and .18<d<.37 and 2.3<hi-lo<2.5:
  removed.append(f);per_cell[(bay,row)]=per_cell.get((bay,row),0)+1
assert len(per_cell)==len(selection['bays'])*len(selection['rows']),(args.campaign,per_cell)
assert all(n==4 for n in per_cell.values()),per_cell
bmesh.ops.delete(bm,geom=removed,context='FACES');loose=[q for q in bm.verts if not q.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
bm.to_mesh(detail.data);bm.free();detail.data.update()
verts=[];faces=[];indices=[];uvs=[]
def quad(points,mat,uv=None):
 k=len(verts);verts.extend([tuple(p) for p in points]);faces.append((k,k+1,k+2,k+3));indices.append(mat);uvs.append(uv or [(p.dot(u)/1.5,p.z) for p in points])
def surface(a,b,z0,z1,d,mat):
 cuts=[a,*[x for x,_ in profile if a<x<b],b]
 for x0,x1 in zip(cuts,cuts[1:]):quad([point(x0,d,z0),point(x1,d,z0),point(x1,d,z1),point(x0,d,z1)],mat)
window_count=0
for row in selection['rows']:
 for bay in selection['bays']:
  center=uc-34.1+bay*6.2;z=base+row*3.9
  surface(center-2.79,center+2.79,z+.04,z+3.65,.075,0)
  for sub in [-1,1]:
   x=center+sub*1.55;a=x-cfg['window_width_m']/2;b=x+cfg['window_width_m']/2;z0=z+cfg['window_sill_m'];z1=z0+cfg['window_height_m'];variant=(bay*2+(sub+1)//2+row)%4;left=(variant*128+16)/512;right=(variant*128+112)/512
   quad([point(a,.145,z0),point(b,.145,z0),point(b,.145,z1),point(a,.145,z1)],1,[(left,.125),(right,.125),(right,.875),(left,.875)])
   outer=[point(a-.055,.22,z0-.055),point(b+.055,.22,z0-.055),point(b+.055,.22,z1+.055),point(a-.055,.22,z1+.055)];inner=[point(a,.145,z0),point(b,.145,z0),point(b,.145,z1),point(a,.145,z1)]
   for k in range(4):j=(k+1)%4;quad([outer[k],outer[j],inner[j],inner[k]],0)
   window_count+=1
mesh=bpy.data.meshes.new('Photo_fit_existing_library_front');mesh.from_pydata(verts,[],faces);mesh.update();ob=bpy.data.objects.new('Photo_fit_existing_library_front',mesh);scene.collection.objects.link(ob);ob['building_index']=13;ob['source']='User photograph 1000069959; homography-derived component maps';ob['photo_fit_profile']=cfg['id'];mesh.materials.append(wall);mesh.materials.append(glass);uv=mesh.uv_layers.new(name='UVMap')
for face,mi,coords in zip(mesh.polygons,indices,uvs):
 face.material_index=mi
 for li,p in zip(face.loop_indices,coords):uv.data[li].uv=p
if args.campaign=='front':
 # Same-building cladding reuse; unchanged rear window geometry remains generic.
 for obj in scene.objects:
  if obj.type!='MESH' or obj.get('building_index')!=13:continue
  changed=False
  for slot in obj.material_slots:
   if slot.material and slot.material.name=='Library_photo_guided_stone':slot.material=wall;changed=True
  if changed and obj.data.uv_layers.active:
   for face in obj.data.polygons:
    if obj.data.materials[face.material_index]!=wall:continue
    for li in face.loop_indices:
     p=obj.matrix_world@obj.data.vertices[obj.data.loops[li].vertex_index].co;obj.data.uv_layers.active.data[li].uv=((p.x if abs(face.normal.y)>.5 else p.y)/1.5,p.z)
 paving=bpy.data.objects['Library_south_plaza'];old=paving.data.materials[0];m=old.copy();m.name='PhotoLibraryPavers';nodes=m.node_tree.nodes;bs=nodes.get('Principled BSDF');t=nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(S/'assets/library-photo-pavers.png'));m.node_tree.links.new(t.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.9;paving.data.materials[0]=m
 uv=paving.data.uv_layers.get('UVMap') or paving.data.uv_layers[0]
 for loop in paving.data.loops:
  p=paving.matrix_world@paving.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(p.x/.9,p.y/.6)
for im in bpy.data.images:
 if im.type=='IMAGE' and im.source=='FILE' and not im.packed_file:im.pack()
all_meshes=[o for o in scene.objects if o.type=='MESH'];triangles=sum(len(p.vertices)-2 for o in all_meshes for p in o.data.polygons);added=triangles-before_triangles;assert added<=cfg['budget']['maximum_added_triangles'],added
def export(path,objects):
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_extras=True)
source_mesh=bpy.data.objects['B13_library'];coords=[source_mesh.matrix_world@v.co for v in source_mesh.data.vertices];body_height=max(p.z for p in coords)-min(p.z for p in coords);assert abs(body_height-35.1)<.002
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'HenanCampus.blend'),compress=True)
export(OUT/'library.glb',[o for o in all_meshes if o.get('building_index')==13])
if args.campaign=='front':
 export(OUT/'HenanCampus.glb',all_meshes);bpy.ops.export_scene.fbx(filepath=str(OUT/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
 manifest=json.loads((baseline/'zones.json').read_text());coarse={name for z in manifest['zones'] for name in z['coarse_nodes']};export(OUT/'campus-base.glb',[o for o in all_meshes if not o.get('building_index') or o.name in coarse])
outputs=['HenanCampus.blend','library.glb']+(['HenanCampus.glb','HenanCampus.fbx','campus-base.glb'] if args.campaign=='front' else [])
report={'passed':True,'fingerprint':fingerprint,'campaign':args.campaign,'selection':selection,'old_panels_removed':len(removed),'photo_windows':window_count,'baseline_triangles':before_triangles,'triangles':triangles,'added_triangles':added,'body_height_m':body_height,'floor_height_m':3.9,'original_photos_embedded':False,'photo_texture_bytes':materials['texture_bytes'],'geometry_status':'EXISTING_PHYSICAL_SOLIDS_AND_FOOTPRINTS_RETAINED; FACADE_COMPONENTS_APPROXIMATE','outputs':{n:sha(OUT/n) for n in outputs},'materials':materials}
receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PHOTO_FIT_PASSED',json.dumps({'campaign':args.campaign,'windows':window_count,'removed':len(removed),'added_triangles':added,'texture_bytes':materials['texture_bytes']}),flush=True)
