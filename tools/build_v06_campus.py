"""Blender: correct cached campus geometry, export formal and streaming assets."""
import bpy,bmesh,json,math,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.campus-cache/v06';A=OUT/'assets';P=ROOT/'assets/henan_campus/project'
spec=json.loads((OUT/'scene_specification.json').read_text());cfg=spec['v06_policy'];baseline=OUT/'baseline';bpy.ops.wm.open_mainfile(filepath=str(baseline/'HenanCampus.blend' if (baseline/'HenanCampus.blend').exists() else P/'HenanCampus.blend'));scene=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
def material(name,color,rough=.8,metal=0):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in color],1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
stone=material('V06_pale_stone',(.75,.72,.67));bedmat=material('V06_lake_bed',(.25,.28,.18),.96);glass=bpy.data.materials['Library_blue_glazing'];frame=bpy.data.materials['Library_window_frames'];roof=bpy.data.materials['Library_metal_eaves'];gold=bpy.data.materials['Library_gold_lettering'];steps=material('Library_granite_steps',(.65,.63,.59),.85)
material('seat_red',(.57,.24,.25));material('seat_blue',(.17,.38,.65))
def object_mesh(name,verts,faces,mats,indices=None,extras=None):
 ob=bpy.data.objects.get(name)
 if ob:
  old=ob.data;ob.data=bpy.data.meshes.new(name+'_v06')
 else:ob=bpy.data.objects.new(name,bpy.data.meshes.new(name+'_v06'));scene.collection.objects.link(ob)
 ob.matrix_world.identity();ob.data.from_pydata(verts,[],faces);ob.data.update()
 for m in mats:ob.data.materials.append(m)
 if indices:
  for p,i in zip(ob.data.polygons,indices):p.material_index=i
 uv=ob.data.uv_layers.new(name='UVMap')
 for face in ob.data.polygons:
  for li in face.loop_indices:
   p=ob.data.vertices[ob.data.loops[li].vertex_index].co
   uv.data[li].uv=(p.x/2,p.y/2) if abs(face.normal.z)>.5 else ((p.x if abs(face.normal.y)>.5 else p.y)/2,p.z/2)
 for k,v in (extras or {}).items():ob[k]=v
 return ob
def extrude(o,mats):
 vertices=[];faces=[]
 def v(x,y,z):vertices.append((x,y,z));return len(vertices)-1
 # Merge coincident vertices to keep exported solids manifold.
 for ring in o['polygon']['rings']:
  for a,b in zip(ring,ring[1:]+ring[:1]):faces.append([v(*a,o['z']),v(*b,o['z']),v(*b,o['z']+o['height']),v(*a,o['z']+o['height'])])
 for tri in o['polygon']['triangles']:
  a,b,c=tri
  if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<0:tri=list(reversed(tri))
  faces.append([v(*p,o['z']+o['height']) for p in tri]);faces.append([v(*p,o['z']) for p in reversed(tri)])
 ob=object_mesh(o['name'],vertices,faces,mats,extras={k:o[k] for k in ['building_index','confidence','source'] if k in o});bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-4);bm.to_mesh(ob.data);bm.free();return ob
oldspec=json.loads((baseline/'scene_specification.json' if (baseline/'scene_specification.json').exists() else P/'scene_specification.json').read_text());assert oldspec['version']=='0.5';newnames={o['name'] for o in spec['objects']}
for ob in list(bpy.data.objects):
 if ob.name.startswith(('Library_stair_','Library_entry_terrace','Grandstand_seat_row_','B20_grandstand_parapet')) or ob.name=='Library_refined_details':bpy.data.objects.remove(ob,do_unlink=True)
ground_meta=json.loads((P/'assets/lighting-water.json').read_text());xmin,ymin,xmax,ymax=ground_meta['ground_blender_bounds']
old_by_name={o['name']:o for o in oldspec['objects']}
for o in spec['objects']:
 name=o['name'];existing=bpy.data.objects.get(name)
 changed=name not in old_by_name or o['polygon']!=old_by_name[name]['polygon']
 if o['group'] in ['Ground','Roads'] and (changed or name.startswith(('Library_stair','Library_entry'))):
  mats=list(existing.data.materials) if existing else [steps if name.startswith('Library_') else bpy.data.materials['V05_terrain_paving']]
  ob=extrude(o,mats)
  layer=ob.data.uv_layers.new(name='GroundAtlas')
  for face in ob.data.polygons:
   for li in face.loop_indices:
    p=ob.data.vertices[ob.data.loops[li].vertex_index].co;layer.data[li].uv=((p.x-xmin)/(xmax-xmin),(p.y-ymin)/(ymax-ymin))
 if name=='B13_library':
  # Keep the already validated closed mesh and its footprint topology.
  ob=existing;inv=ob.matrix_world.inverted()
  for vert in ob.data.vertices:
   p=ob.matrix_world@vert.co;p.z=.16+(p.z-.16)*27/24;vert.co=inv@p
  ob['floor_count']=9;ob['body_height_m']=27;ob['floor_height_m']=3
 if o['group']=='Bridge' and name!='Stone_bridge_deck':extrude(o,[stone])
 if o['group']=='Buildings' and o.get('building_index') not in [13,20] and existing:
  uv=existing.data.uv_layers.get('UVMap')
  if uv:
   for face in existing.data.polygons:
    if abs(face.normal.z)<.5:
     for li in face.loop_indices:uv.data[li].uv.y=((existing.matrix_world@existing.data.vertices[existing.data.loops[li].vertex_index].co).z-.16)/3
class Parts:
 def __init__(self):self.v=[];self.f=[];self.mi=[];self.m=[]
 def quad(self,pts,mat):
  k=len(self.v);self.v.extend([tuple(p) for p in pts]);self.f.append(tuple(range(k,k+len(pts))))
  if mat not in self.m:self.m.append(mat)
  self.mi.append(self.m.index(mat))
 def box(self,center,dims,mat,u=(1,0,0),v=None):
  u=Vector(u);v=Vector(v) if v else Vector((-u.y,u.x,0));w=Vector((0,0,1));c=Vector(center);pts=[c+u*(x*dims[0]/2)+v*(y*dims[1]/2)+w*(z*dims[2]/2) for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
  for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.quad([pts[i] for i in ids],mat)
 def finish(self,name,**extras):return object_mesh(name,self.v,self.f,self.m,self.mi,extras)
# Rebuild only the library facade; every repeated storey is actually 3 metres.
profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];u=Vector((math.cos(math.radians(35)),math.sin(math.radians(35)),0));v=Vector((-u.y,u.x,0));uc=(profile[0][0]+profile[-1][0])/2
def front(x):
 for a,b in zip(profile,profile[1:]):
  if a[0]<=x<=b[0]:return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
 return profile[0][1] if x<profile[0][0] else profile[-1][1]
def point(x,offset,z):return u*x+v*(front(x)-offset)+Vector((0,0,z))
lib=Parts()
def panel(a,b,z0,z1,offset,mat):lib.quad([point(a,offset,z0),point(b,offset,z0),point(b,offset,z1),point(a,offset,z1)],mat)
for row in range(1,8):
 z=.16+row*3+.5
 for k in range(12):
  center=uc-34.1+k*6.2;panel(center-2.55,center+2.55,z,z+1.85,.23,glass)
  for xx in [center-2.55,center,center+2.55]:panel(xx-.035,xx+.035,z,z+1.85,.3,frame)
for k in range(13):
 center=uc-37.2+k*6.2;panel(center-.38,center+.38,1.96,27.16,.52,bpy.data.materials['Library_photo_guided_stone'])
panel(profile[0][0]+2,profile[-1][0]-2,24.55,26.85,.15,glass)
for k in range(31):
 q=profile[0][0]+2+(profile[-1][0]-profile[0][0]-4)*k/30;panel(q-.035,q+.035,24.55,26.85,.23,frame)
for k in range(7):
 center=uc-18+k*6;panel(center-2.45,center+2.45,1.96,4.06,.29,glass)
 for off in [-.8,.8]:panel(center+off-.045,center+off+.045,1.96,4.06,.35,frame)
for i in range(64):
 a=profile[0][0]-1+(profile[-1][0]-profile[0][0]+2)*i/64;b=profile[0][0]-1+(profile[-1][0]-profile[0][0]+2)*(i+1)/64;za=27.7+1.1*((a-uc)/40)**2;zb=27.7+1.1*((b-uc)/40)**2
 lib.quad([point(a,-2.2,za),point(b,-2.2,zb),point(b,2.25,zb),point(a,2.25,za)],roof)
main=next(o for o in spec['objects'] if o['name']=='B13_library');ring=main['polygon']['rings'][0]
for edge in [0,4,5,6,7]:
 a=Vector((*ring[edge],0));b=Vector((*ring[(edge+1)%len(ring)],0));t=(b-a).normalized();normal=Vector((t.y,-t.x,0));bays=max(1,int((b-a).length/5.5))
 for row in range(9):
  for k in range(bays):
   c=a+(b-a)*(k+.5)/bays+normal*.04;z=.16+row*3+.65;lib.quad([c+t*dx+Vector((0,0,zz)) for dx,zz in [(-1.65,z),(1.65,z),(1.65,z+1.85),(-1.65,z+1.85)]],glass)
lib.finish('Library_refined_details',building_index=13,storey_spacing_m=3,appearance_source='Cached panoramas; nine floors documented, dimensions approximate')
cu=bpy.data.curves.new('Library_v06_name','FONT');cu.body='图 书 馆';cu.align_x='CENTER';cu.size=2.5;cu.extrude=.04
try:cu.font=bpy.data.fonts.load('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
except RuntimeError:pass
sign=bpy.data.objects.new('Library_v06_name',cu);scene.collection.objects.link(sign);sign.location=point(uc,.9,5.1)
from mathutils import Matrix
sign.rotation_euler=Matrix(((u.x,0,-v.x),(u.y,0,-v.y),(0,1,0))).to_euler();cu.materials.append(gold);bpy.ops.object.select_all(action='DESELECT');sign.select_set(True);bpy.context.view_layer.objects.active=sign;bpy.ops.object.convert(target='MESH');sign['building_index']=13
# Broad, flat stone bridge with open balustrades and collidable posts.
b=cfg['bridge'];ang=math.radians(b['angle_degrees']);bu=Vector((math.cos(ang),math.sin(ang),0));bv=Vector((-bu.y,bu.x,0));bc=Vector((*b['center_blender_xy'],0));deck=extrude(next(o for o in spec['objects'] if o['name']=='Stone_bridge_deck'),[stone]);rail=Parts()
for side in [-1,1]:
 for z,h in [(.48,.30),(1.27,.13)]:rail.box(bc+bv*(side*(b['width_m']/2-.1))+Vector((0,0,z)),(b['length_m'],.23,h),stone,bu)
 for i in range(9):rail.box(bc+bu*((i/8-.5)*b['length_m'])+bv*(side*(b['width_m']/2-.1))+Vector((0,0,.87)),(.30,.34,1.14),stone,bu)
rail.finish('Stone_bridge_balustrades',collision_kind='BridgeRail',source_scene=b['source_scene'])
# Replace the old floating rows with a closed, stepped grandstand body.
o=next(o for o in spec['objects'] if o['name']=='B20_grandstand');ring=[Vector((*p,0)) for p in o['polygon']['rings'][0]];edges=[(a,ring[(i+1)%len(ring)]) for i,a in enumerate(ring)];a,b=max(edges,key=lambda e:(e[1]-e[0]).length);gu=(b-a).normalized();gv=Vector((-gu.y,gu.x,0));gc=sum(ring,Vector())/len(ring)
if gv.x<0:gu=-gu;gv=-gv
length=max((p-gc).dot(gu) for p in ring)-min((p-gc).dot(gu) for p in ring);width=max((p-gc).dot(gv) for p in ring)-min((p-gc).dot(gv) for p in ring)
verts=[];faces=[]
for left,right,count in [(-length/2,-1.4,7),(-1.4,1.4,14),(1.4,length/2,7)]:
 profile2=[(width/2,.16),(-width/2,.16),(-width/2,3.16)]
 for i in range(count):
  d=-width/2+(i+1)*width/count;z=.16+(count-i)*3/count;profile2.append((d,z))
  if i<count-1:profile2.append((d,z-3/count))
 k=len(verts);n=len(profile2);verts.extend(tuple(gc+gu*x+gv*d+Vector((0,0,z))) for x in [left,right] for d,z in profile2);faces.extend([tuple(k+i for i in reversed(range(n))),tuple(range(k+n,k+2*n))]+[(k+i,k+(i+1)%n,k+(i+1)%n+n,k+i+n) for i in range(n)])
stand=object_mesh('B20_grandstand',verts,faces,[stone],extras={'building_index':20,'body_height_m':3,'floor_height_m':3,'collision_kind':'Grandstand'});bm=bmesh.new();bm.from_mesh(stand.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(stand.data);bm.free()
seats=Parts()
for i in range(7):
 d=-width/2+(i+.5)*width/7;z=.16+(7-i)*3/7+.07
 for side in [-1,1]:seats.box(gc+gu*(side*(length/4+.7))+gv*d+Vector((0,0,z)),(length/2-1.8,width/7*.60,.14),bpy.data.materials['seat_red' if i%3==0 else 'seat_blue'],gu)
seats.finish('Grandstand_seating',building_index=20)
canopy=bpy.data.objects.get('Grandstand_canopy_estimated')
if canopy:
 zs=[(canopy.matrix_world@v.co).z for v in canopy.data.vertices];lo=min(zs)
 for vertex in canopy.data.vertices:vertex.co.z+=6.4-lo
 canopy['building_index']=20
podium=Parts();center=gc+gv*(width/2+2.1);podium.box(center+Vector((0,0,.46)),(14,4.2,.60),stone,gu)
for i in range(5):podium.box(center+gv*(2.1+(4-i+.5)*.36)+Vector((0,0,(i+1)*.15/2)),(8,.36,(i+1)*.15),stone,gu)
for side in [-1,1]:
 for k in range(4):podium.box(center+gu*(side*6.85)+gv*(-1.6+k*1.05)+Vector((0,0,1.23)),(.08,.08,.96),frame,gu)
 podium.box(center+gu*(side*6.85)+Vector((0,0,1.71)),(.08,4.2,.08),frame,gu)
platform=podium.finish('Stadium_ceremonial_platform',building_index=20,collision_kind='Platform',dimension_status='PHOTO_GUIDED_ESTIMATE')
def pcpoint(p):return [p.x,p.z,-p.y]
(OUT/'landmarks.json').write_text(json.dumps({'bridge':{'center':pcpoint(bc+Vector((0,0,.3))),'direction':[bu.x,-bu.y],'half_length':cfg['bridge']['length_m']/2},'podium':{'center':pcpoint(center+Vector((0,0,.76))),'approach':pcpoint(center+gv*4.5),'direction':[-gv.x,gv.y]},'grandstand':{'approach':pcpoint(gc+gv*(width/2+1)),'direction':[-gv.x,gv.y],'aisle_length':width+1}},indent=2)+'\n')
for b in json.loads((OUT/'lake-beds.json').read_text()):object_mesh(b['name'],b['vertices'],b['faces'],[bedmat],extras={'depth_status':'ESTIMATED_BANK_DISTANCE_PROFILE'})
# Physically meaningful normal and roughness maps, authored at 4096px.
for m in [stone,steps,bpy.data.materials['Library_photo_guided_stone'],bpy.data.materials['V05_Pale_stone'],bpy.data.materials['V05_Orange_wall']]:
 nodes=m.node_tree.nodes;bs=nodes.get('Principled BSDF');tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(A/'stone-normal-1024.png'));tex.image.colorspace_settings.name='Non-Color';normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.32;m.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color']);m.node_tree.links.new(normal.outputs['Normal'],bs.inputs['Normal']);rough=nodes.new('ShaderNodeTexImage');rough.image=bpy.data.images.load(str(A/'stone-roughness-1024.png'));rough.image.colorspace_settings.name='Non-Color';m.node_tree.links.new(rough.outputs['Color'],bs.inputs['Roughness'])
for image in bpy.data.images:
 if image.type=='IMAGE' and image.source=='FILE':image.pack()
# Actual collision triangles for the bridge rails, stepped stand and podium.
collision=[]
for name,kind in [('Stone_bridge_balustrades','BridgeRail'),('B20_grandstand','Grandstand'),('Stadium_ceremonial_platform','Platform')]:
 ob=bpy.data.objects[name];ob.data.calc_loop_triangles();collision.append({'name':name,'kind':kind,'building':20 if 'Stadium' in name or name.startswith('B20') else None,'vertices':[q for vert in ob.data.vertices for q in ((ob.matrix_world@vert.co).x,(ob.matrix_world@vert.co).z,-(ob.matrix_world@vert.co).y)],'indices':[i for tri in ob.data.loop_triangles for i in tri.vertices]})
(OUT/'special-colliders.json').write_text(json.dumps(collision,separators=(',',':')))
report={'version':'0.6','floor_height_m':3,'library_floor_count':9,'library_body_height_m':27,'stairs':{'count':12,'riser_m':.15,'top_m':1.96},'bridge':cfg['bridge'],'grandstand_floating_rows_fixed':True,'pbr_source_resolution':4096,'runtime_embedded_resolution':1024,'source_xy_retained':True,'buildings':[]}
for o in spec['objects']:
 if o['group']!='Buildings' or not o.get('display_name'):continue
 ob=bpy.data.objects.get(o['name'])
 if not ob:continue
 coords=[ob.matrix_world@v.co for v in ob.data.vertices];dims=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)];bm=bmesh.new();bm.from_mesh(ob.data);bad=sum(not e.is_manifold for e in bm.edges);bm.free()
 assert abs(dims[2]-o['height'])<.002 and bad==0,(ob.name,dims,bad)
 report['buildings'].append({'id':o['building_index'],'mesh':ob.name,'height_m':dims[2],'expected_height_m':o['height'],'non_manifold_edges':bad})
assert len({b['id'] for b in report['buildings']})==20
def export(path,objects):
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_extras=True)
all_meshes=[o for o in scene.objects if o.type=='MESH'];export(OUT/'HenanCampus.glb',all_meshes)
bpy.ops.export_scene.fbx(filepath=str(OUT/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'HenanCampus.blend'),compress=True)
zones=OUT/'zones';zones.mkdir(exist_ok=True);base=[o for o in all_meshes if not o.get('building_index')];manifest=[]
for b in spec['buildings']:
 idx=b['map_index'];objects=[o for o in all_meshes if o.get('building_index')==idx];assert objects
 export(zones/f'b{idx:02d}.glb',objects)
 body_names={o['name'] for o in spec['objects'] if o.get('building_index')==idx and o['group']=='Buildings' and o.get('display_name')};bodies=[o for o in objects if o.name in body_names];assert bodies
 # Base retains low-cost mapped solids; facade/seat/detail meshes stream nearby.
 for body in bodies:body['lod_coarse_building']=idx;base.append(body)
 manifest.append({'id':idx,'url':f'/assets/zones/b{idx:02d}.glb','coarse_nodes':[o.name for o in bodies],'x':b['centroid_local_m'][0],'z':-b['centroid_local_m'][1],'load_distance_m':190,'unload_distance_m':250})
export(OUT/'campus-base.glb',base);(OUT/'zones.json').write_text(json.dumps({'version':'0.6','zones':manifest},indent=2)+'\n');(OUT/'geometry-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('V06_GEOMETRY_PASSED',len(report['buildings']),len(all_meshes),flush=True)
