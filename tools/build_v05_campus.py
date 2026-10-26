"""Blender: metric height policy and reusable photo-type facade grammar.
Only the configured building types receive new facade detail. XY is retained.
"""
import bpy,bmesh,json,math,sys,hashlib,re
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];source=Path(args[0]);out=Path(args[1]);ids=[int(x) for x in args[2].split(',') if x];out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1];asset=root/'assets/henan_campus';config=json.loads((root/'configs/v05-buildings.json').read_text());spec=json.loads((asset/'project/scene_specification.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.;bpy.context.preferences.filepaths.save_version=0
policy={b['id']:b for b in config['buildings']};profile=config['facade_profile']
if not scene.get('v05_height_policy_applied'):
 for ob in scene.objects:
  if ob.type!='MESH':continue
  idx=ob.get('building_index')
  if ob.name=='Grandstand_canopy_estimated':idx=20;ob['building_index']=20
  if not idx or int(idx) not in policy:continue
  p=policy[int(idx)];old=p['old_body_height_m'];new=p['body_height_m'];base=.16;anchor=1.36 if int(idx)==13 else base
  def remap(z):
   if z<=anchor:return z
   if z<=base+old:return anchor+(z-anchor)*(base+new-anchor)/(base+old-anchor)
   return z+new-old
  ob.data=ob.data.copy();inv=ob.matrix_world.inverted()
  for vertex in ob.data.vertices:
   pos=ob.matrix_world@vertex.co;pos.z=remap(pos.z);vertex.co=inv@pos
  ob['floor_height_m']=3.;ob['height_policy']='USER_RULE_NOT_SURVEY';ob.data.update()
  if re.match(r'^B\d\d_(tower|dorm|arcade|library|admin|teaching|grandstand)(?:_\d+)?$',ob.name):
   ob['floor_count']=p['floor_count'];ob['body_height_m']=new
   # UV facade rows follow the same 3m storey grid.
   uv=ob.data.uv_layers.active
   if uv:
    for face in ob.data.polygons:
     if abs(face.normal.z)<.5:
      for li in face.loop_indices:uv.data[li].uv.y=((ob.matrix_world@ob.data.vertices[ob.data.loops[li].vertex_index].co).z-base)/3
 scene['v05_height_policy_applied']=True

def mat(name,color,rough=.8,metal=0):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True
 c=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in color)
 n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;m.diffuse_color=(*c,1);return m
brick=mat('V05_Orange_wall',(.65,.32,.23));stone=mat('V05_Pale_stone',(.77,.76,.69));glass=mat('V05_Blue_glass',(.19,.34,.38),.28,.15);frame=mat('V05_Window_frames',(.61,.65,.63),.5,.2)
collection=bpy.data.collections.get('V05_Modular_facades')
if not collection:collection=bpy.data.collections.new('V05_Modular_facades');scene.collection.children.link(collection)
completed=set(json.loads(scene.get('v05_facade_buildings','[]')))
for idx in ids:
 if idx in completed:continue
 main=next(o for o in spec['objects'] if o.get('building_index')==idx and o['group']=='Buildings')
 ob=bpy.data.objects[main['name']];ob.data.materials[0]=brick
 vertices=[];faces=[];materials=[];uvs=[];floor_count=policy[idx]['floor_count'];ring=main['polygon']['rings'][0];longest=max(math.dist(a,b) for a,b in zip(ring,ring[1:]+ring[:1]));window_count=0
 def quad(points,mi,uv=None):
  k=len(vertices);vertices.extend([tuple(p) for p in points]);faces.append((k,k+1,k+2,k+3));materials.append(mi);uvs.append(uv or [(0,0),(1,0),(1,1),(0,1)])
 for a,b in zip(ring,ring[1:]+ring[:1]):
  a=Vector((*a,0));b=Vector((*b,0));length=(b-a).length
  if length<2:continue
  t=(b-a).normalized();n=Vector((t.y,-t.x,0));bays=max(1,int(length/profile['preferred_bay_m']));width=length/bays
  # Original wall UVs use one bay per tile, resetting at each edge.
  uv=ob.data.uv_layers.active
  if uv:
   for face in ob.data.polygons:
    if abs(face.normal.z)<.5:
     coords=[ob.matrix_world@ob.data.vertices[ob.data.loops[li].vertex_index].co for li in face.loop_indices]
     if all(abs((Vector((c.x,c.y,0))-a).dot(n))<.01 for c in coords):
      for li,c in zip(face.loop_indices,coords):uv.data[li].uv=(((Vector((c.x,c.y,0))-a).dot(t)/width),(c.z-.16)/3)
  def panel(x0,x1,z0,z1,offset,material):quad([a+t*x0+n*offset+Vector((0,0,z0)),a+t*x1+n*offset+Vector((0,0,z0)),a+t*x1+n*offset+Vector((0,0,z1)),a+t*x0+n*offset+Vector((0,0,z1))],material)
  for row in range(floor_count):
   z=.16+row*3
   panel(0,length,z+.03,z+.23,.08,0)
   for col in range(bays):
    x=(col+.5)*width;w=min(profile['window_width_m'],width*.68);z0=z+profile['window_sill_m'];z1=z0+profile['window_height_m']
    curtain=length>longest*.95 and col<2
    if curtain:
     panel(col*width+.08,(col+1)*width-.08,z+.26,z+2.98,.07,1)
     panel(col*width,(col*width)+.07,z+.24,z+2.99,.13,2)
    else:
     panel(x-w/2,x+w/2,z0,z1,.065,1)
     for l,r,lo,hi in [(x-w/2-.07,x+w/2+.07,z0-.07,z0),(x-w/2-.07,x+w/2+.07,z1,z1+.07),(x-w/2-.07,x-w/2,z0,z1),(x+w/2,x+w/2+.07,z0,z1),(x-.025,x+.025,z0,z1)]:panel(l,r,lo,hi,.14,2)
    window_count+=1
 mesh=bpy.data.meshes.new(f'V05_B{idx:02d}_facade');mesh.from_pydata(vertices,[],faces);mesh.update();detail=bpy.data.objects.new(mesh.name,mesh);collection.objects.link(detail)
 for m in [stone,glass,frame]:mesh.materials.append(m)
 uv=mesh.uv_layers.new(name='UVMap')
 for face,mi,coords in zip(mesh.polygons,materials,uvs):
  face.material_index=mi
  for li,p in zip(face.loop_indices,coords):uv.data[li].uv=p
 detail['building_index']=idx;detail['profile']='orange_stone_curtain_v1';detail['source']='Photos 2022081153-56; facade type only, exact per-building correspondence unverified';detail['window_bays_total']=window_count;completed.add(idx)
sys.path.insert(0,str(Path(__file__).parent));from apply_v05_palette import apply_palette
apply_palette(scene,spec,{**profile,'building_ids':sorted(completed)})
scene['v05_facade_buildings']=json.dumps(sorted(completed));scene['v05_status']='Metric user rule + photo-type approximation, not survey restoration'
# A consistent second UV set lets ground AO/shadow atlases survive GLB and FBX.
ground=bpy.data.objects['Campus_ground'];uv=ground.data.uv_layers.get('GroundAtlas') or ground.data.uv_layers.new(name='GroundAtlas');world=[ground.matrix_world@v.co for v in ground.data.vertices];xmin=min(v.x for v in world);xmax=max(v.x for v in world);ymin=min(v.y for v in world);ymax=max(v.y for v in world)
for face in ground.data.polygons:
 for li in face.loop_indices:
  p=ground.matrix_world@ground.data.vertices[ground.data.loops[li].vertex_index].co;uv.data[li].uv=((p.x-xmin)/(xmax-xmin),(p.y-ymin)/(ymax-ymin))
report={'version':'0.5','floor_height_m':3,'units':'METERS','facade_buildings':sorted(completed),'buildings':[],'ground_atlas_blender_bounds':[xmin,ymin,xmax,ymax]}
for idx,p in policy.items():
 main=next(o for o in scene.objects if o.type=='MESH' and o.get('building_index')==idx and re.match(r'^B\d\d_(tower|dorm|arcade|library|admin|teaching|grandstand)(?:_\d+)?$',o.name))
 coords=[main.matrix_world@v.co for v in main.data.vertices];dims=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)];bm=bmesh.new();bm.from_mesh(main.data);bad=sum(not e.is_manifold for e in bm.edges);bm.free()
 if abs(dims[2]-p['body_height_m'])>.002 or bad:raise RuntimeError('Height/solid gate failed: '+main.name)
 report['buildings'].append({**p,'mesh':main.name,'axis_aligned_dimensions_m':dims,'non_manifold_edges':bad,'source_xy_retained':True})
for image in bpy.data.images:
 if image.type=='IMAGE' and image.source=='FILE':image.pack()
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
 if o.type=='MESH':o.select_set(True)
bpy.context.view_layer.objects.active=ground
bpy.ops.export_scene.gltf(filepath=str(out/'HenanCampus.glb'),export_format='GLB',use_selection=True,export_extras=True)
if len(completed)==5:bpy.ops.export_scene.fbx(filepath=str(out/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'HenanCampus.blend'),compress=True)
(out/'geometry-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('V05_GEOMETRY_PASSED',json.dumps({'facades':sorted(completed),'buildings':len(report['buildings'])}),flush=True)
