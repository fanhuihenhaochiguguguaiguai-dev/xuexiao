"""Local refinement of the existing scene, guided by cached 2017 photographs.
Run with Blender. Does not rebuild the other campus buildings.
"""
from pathlib import Path
import os
import bpy,math,json,sys
from mathutils import Vector,Matrix
ROOT=Path(os.environ.get('CAMPUS_ASSET_ROOT', str(Path(__file__).resolve().parents[1])));P=ROOT/'project';A=P/'assets'
sys.path.insert(0,str(ROOT/'tools/geometry_deps'))
# GEOS wheels target the workspace Python, so geometry preparation is delegated
# to prepare_library_refinement.py rather than imported into Blender's Python.
spec=json.loads((P/'scene_specification.json').read_text())
config=json.loads((ROOT/'metadata/library_refinement.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(P/'HenanCampus.blend'))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
collection=bpy.data.collections.get('Library_refined')
if not collection:collection=bpy.data.collections.new('Library_refined');scene.collection.children.link(collection)
for o in list(collection.objects):bpy.data.objects.remove(o,do_unlink=True)
def srgb(c):return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
def material(name,color,rough=.75,metal=0,texture=None):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True
 n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*[srgb(v) for v in color],1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal
 if texture:
  t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(A/texture));t.extension='REPEAT';m.node_tree.links.new(t.outputs['Color'],n.inputs['Base Color'])
 return m
stone=material('Library_photo_guided_stone',(.77,.70,.65),.85,0,'library_stone.png')
glass=material('Library_blue_glazing',(.10,.31,.40),.24,.20)
frame=material('Library_window_frames',(.43,.48,.48),.45,.25)
roof=material('Library_metal_eaves',(.65,.67,.65),.52,.18)
gold=material('Library_gold_lettering',(.88,.58,.15),.32,.55)
paving=material('Library_granite_paving',(.71,.54,.47),.95,texture='library_paving.png')
stepmat=material('Library_granite_steps',(.65,.63,.59),.85)
foliage=material('Library_planter_shrubs',(.24,.41,.15),.88)
u=Vector((math.cos(math.radians(35)),math.sin(math.radians(35)),0));v=Vector((-u.y,u.x,0))
front=config['front_profile_uv'];uc=(front[0][0]+front[-1][0])/2
def fpoint(x,offset=0,z=0):
 for a,b in zip(front,front[1:]):
  if a[0]-1e-5<=x<=b[0]+1e-5:
   t=(x-a[0])/(b[0]-a[0]);yy=a[1]+t*(b[1]-a[1]);return u*x+v*(yy-offset)+Vector((0,0,z))
 a=front[0] if x<front[0][0] else front[-1];return u*x+v*(a[1]-offset)+Vector((0,0,z))
def mesh_object(name,verts,faces,mat,group=collection):
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();ob=bpy.data.objects.new(name,mesh);group.objects.link(ob);mesh.materials.append(mat)
 ob['source']='Cached 2017 panorama: scene_ef8a1b1d35eefd7f b/l and scene_c5fd9763ca141592 l'
 ob['confidence']='PHOTO_GUIDED_APPEARANCE_AND_ESTIMATED_DIMENSIONS';ob['building_index']=13
 return ob
def extrusion(o,mat,target=None):
 vs=[];fs=[];uvs=[];lookup={};z=o['z'];h=o['height']
 def vertex(x,y,z):
  k=(round(x,8),round(y,8),round(z,8))
  if k not in lookup:lookup[k]=len(vs);vs.append((x,y,z))
  return lookup[k]
 for ring in o['polygon']['rings']:
  for a,b in zip(ring,ring[1:]+ring[:1]):
   fs.append((vertex(*a,z),vertex(*b,z),vertex(*b,z+h),vertex(*a,z+h)));length=math.dist(a,b);uvs.append([(0,0),(length/3,0),(length/3,h/3),(0,h/3)])
 for tri in o['polygon']['triangles']:
  a,b,c=tri
  if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<0:tri=list(reversed(tri))
  for zz,t in [(z+h,tri),(z,list(reversed(tri)))]:fs.append(tuple(vertex(*p,zz) for p in t));uvs.append([(p[0]/4,p[1]/4) for p in t])
 ob=mesh_object(o['name'],vs,fs,mat) if target is None else target
 if target:
  old=target.data;mesh=bpy.data.meshes.new(o['name']);mesh.from_pydata(vs,[],fs);mesh.update();target.data=mesh;mesh.materials.append(mat)
 layer=ob.data.uv_layers.new(name='UVMap')
 for f,coords in zip(ob.data.polygons,uvs):
  for li,xy in zip(f.loop_indices,coords):layer.data[li].uv=xy
 if o.get('building_index'):ob['building_index']=o['building_index']
 elif 'building_index' in ob:del ob['building_index']
 return ob
for ob in list(bpy.data.objects):
 if ob.name.startswith(('B13_library_parapet','B13_library_plant','Library_stair_','Library_entry_terrace','Library_south_plaza_')):bpy.data.objects.remove(ob,do_unlink=True)
main=next(o for o in spec['objects'] if o['name']=='B13_library');extrusion(main,stone,bpy.data.objects['B13_library'])
for ob in list(bpy.data.objects):
 if ob.name.startswith('Campus_roads'):bpy.data.objects.remove(ob,do_unlink=True)
asphalt=bpy.data.materials.get('asphalt')
for o in spec['objects']:
 if o['name'].startswith('Campus_roads'):extrusion(o,asphalt)
 elif o['name']=='Library_south_plaza':extrusion(o,paving,bpy.data.objects[o['name']])
 elif o['name'].startswith(('Library_stair_','Library_entry_terrace')):extrusion(o,stepmat)
def panel(name,a,b,z0,z1,offset,mat):
 return mesh_object(name,[fpoint(a,offset,z0),fpoint(b,offset,z0),fpoint(b,offset,z1),fpoint(a,offset,z1)],[(0,1,2,3)],mat)
def box(name,center,scale,mat,right=u):
 bpy.ops.mesh.primitive_cube_add(size=1,location=center);ob=bpy.context.object;ob.name=name
 for c in list(ob.users_collection):c.objects.unlink(ob)
 collection.objects.link(ob);ob.rotation_euler.z=math.atan2(right.y,right.x);ob.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);ob.data.materials.append(mat)
 ob['confidence']='PHOTO_GUIDED_ESTIMATED_DETAIL';ob['building_index']=13;return ob
# Blue horizontal window bands, tall stone piers, deep window reveals.
for row in range(1,7):
 z0=4.1+(row-1)*3.65
 for k in range(12):
  center=uc-34.1+k*6.2;a=center-2.55;b=center+2.55
  panel(f'Library_window_{row}_{k}',a,b,z0,z0+2.0,.23,glass)
  panel(f'Library_sill_{row}_{k}',a-.13,b+.13,z0-.16,z0-.03,.38,stone)
  for q in [a,(a+b)/2,b]:panel(f'Library_mullion_{row}_{k}_{q:.1f}',q-.035,q+.035,z0,z0+2,.26,frame)
  panel(f'Library_transom_{row}_{k}',a,b,z0+1.15,z0+1.20,.26,frame)
for k in range(13):
 center=uc-37.2+k*6.2
 panel(f'Library_pier_{k}',center-.38,center+.38,1.45,27.3,.52,stone)
panel('Library_top_glass',front[0][0]+2,front[-1][0]-2,26.1,29.8,.15,glass)
for k in range(31):
 q=front[0][0]+2+(front[-1][0]-front[0][0]-4)*k/30
 panel(f'Library_clerestory_mullion_{k}',q-.035,q+.035,26.1,29.8,.23,frame)
# Entrance doors are closed in this version; the external approach is walkable.
for k in range(7):
 center=uc-18+k*6
 panel(f'Library_entrance_glazing_{k}',center-2.45,center+2.45,1.4,4.3,.29,glass)
 for d in [-.8,.8]:panel(f'Library_entrance_doorframe_{k}_{d}',center+d-.045,center+d+.045,1.4,4.3,.34,frame)
for side in [-1,1]:
 for k in range(3):
  center=uc+side*(34.2+k*.6)
  panel(f'Library_side_vertical_slot_{side}_{k}',center-.18,center+.18,2.0,26.0,.24,glass)
# Lifted curved eaves, visible in both ground and aerial source photographs.
rv=[];rf=[];steps=65
for i in range(steps):
 xx=front[0][0]-1+(front[-1][0]-front[0][0]+2)*i/(steps-1);s=(xx-uc)/40;zz=30.6+1.25*s*s
 for offset,zadd in [(-2.2,0),(2.25,0),(2.25,.28),(-2.2,.28)]:rv.append(fpoint(xx,offset,zz+zadd))
for i in range(steps-1):
 for j in range(4):a=i*4+j;b=i*4+(j+1)%4;rf.append((a,b,b+4,a+4))
rf.extend([(3,2,1,0),tuple(range((steps-1)*4,steps*4))]);mesh_object('Library_curved_roof_eaves',rv,rf,roof)
try:
 font=bpy.data.fonts.load('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
except:font=None
cu=bpy.data.curves.new('Library_name','FONT');cu.body='图   书   馆';cu.align_x='CENTER';cu.size=3.2;cu.extrude=.045
if font:cu.font=font
ob=bpy.data.objects.new('Library_gold_name_sign',cu);collection.objects.link(ob);ob.location=fpoint(uc,.85,5.15)
ob.rotation_euler=Matrix(((u.x,0,-v.x),(u.y,0,-v.y),(0,1,0))).to_euler();cu.materials.append(gold)
bpy.context.view_layer.objects.active=ob;bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.ops.object.convert(target='MESH');ob['building_index']=13
coords=[q.co.copy() for q in ob.data.vertices]
if coords:
 xmin,xmax=min(q.x for q in coords),max(q.x for q in coords);ymin,ymax=min(q.y for q in coords),max(q.y for q in coords)
 for q in ob.data.vertices:q.co.x=(q.co.x-(xmin+xmax)/2)*22/max(xmax-xmin,.001);q.co.y=(q.co.y-ymin)*2.4/max(ymax-ymin,.001)
for xx in [uc-25.5,uc+25.5]:
 base=fpoint(xx,2.0,1.45);box('Library_entry_planter',base,(2.0,1.6,1.2),stone)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=base+Vector((0,0,1.0)));ob=bpy.context.object;ob.name='Library_entry_shrub';ob.scale=(1.25,1.0,.7);ob.data.materials.append(foliage)
 for c in list(ob.users_collection):c.objects.unlink(ob)
 collection.objects.link(ob)
# Side and rear faces keep generic window detail, with correct broad proportions.
ring=main['polygon']['rings'][0]
for edge in [0,4,5,6,7]:
 a=Vector((*ring[edge],0));b=Vector((*ring[(edge+1)%len(ring)],0));t=(b-a).normalized();normal=Vector((t.y,-t.x,0));length=(b-a).length
 for row in range(7):
  for k in range(max(1,int(length/5.5))):
   center=a+(b-a)*(k+.5)/max(1,int(length/5.5))+normal*.04;zz=2.0+row*3.65
   points=[center+t*dx+Vector((0,0,z)) for dx,z in [(-1.65,zz),(1.65,zz),(1.65,zz+1.85),(-1.65,zz+1.85)]]
   mesh_object('Library_side_window',points,[(0,1,2,3)],glass)
scene['library_refinement']='Cached 2017 photo-guided facade, steps, eaves and paving; dimensions remain estimates.'
# Consolidate only the new details; do not touch the other campus buildings.
bpy.ops.object.select_all(action='DESELECT')
details=[o for o in collection.objects if o.type=='MESH' and not o.name.startswith(('Campus_roads','Library_stair','Library_entry_terrace'))]
for o in details:o.select_set(True)
if details:bpy.context.view_layer.objects.active=details[0];bpy.ops.object.join();bpy.context.object.name='Library_refined_details';bpy.context.object['building_index']=13
meshobs=[o for o in scene.objects if o.type=='MESH'];bpy.ops.object.select_all(action='DESELECT')
for o in meshobs:o.select_set(True)
bpy.context.view_layer.objects.active=meshobs[0]
bpy.ops.export_scene.gltf(filepath=str(P/'HenanCampus.glb'),export_format='GLB',use_selection=True,export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(P/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
for im in bpy.data.images:
 if im.type=='IMAGE' and im.source=='FILE':im.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(P/'HenanCampus.blend'),compress=True)
scene.camera=bpy.data.objects['Library_plaza_view'];scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.cycles.samples=24;scene.cycles.use_denoising=False;scene.render.filepath=str(P/'preview/library_refined.png');bpy.ops.render.render(write_still=True)
cam=scene.camera;cam.location=fpoint(uc,83,8);cam.rotation_euler=(fpoint(uc,0,12)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=37;scene.render.filepath=str(P/'preview/library_refined_front.png');bpy.ops.render.render(write_still=True)
print('LIBRARY_REFINEMENT_COMPLETE',len(meshobs),flush=True)
