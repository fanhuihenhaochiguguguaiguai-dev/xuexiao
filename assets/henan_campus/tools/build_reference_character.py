"""Reference-guided clothed game character from a CC0 human base, not photogrammetry."""
from pathlib import Path
import os
import bpy, math, json, hashlib, shutil
from mathutils import Vector, Matrix
from collections import defaultdict
P=Path(os.environ.get('CAMPUS_ASSET_ROOT', str(Path(__file__).resolve().parents[1])))/'character';SRC=P/'source';OUT=P/'output'
OUT.mkdir(parents=True,exist_ok=True)
REF=P/'reference'
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0
verts=[];faces=[];groups=defaultdict(set);group=''
for l in (SRC/'base.obj').read_text().splitlines():
 if l.startswith('v '):verts.append(Vector(map(float,l.split()[1:4])))
 elif l.startswith('g '):group=l[2:]
 elif l.startswith('f '):
  f=[int(s.split('/')[0])-1 for s in l.split()[1:]];groups[group].update(f)
  if group=='body':faces.append(f)
for file in ['asian-female-young.target','universal-female-young-averagemuscle-averageweight.target']:
 for l in (SRC/file).read_text().splitlines():
  if not l or l.startswith('#'):continue
  i,*d=l.split();verts[int(i)]+=Vector(map(float,d))
jraw={g:sum((verts[i] for i in ids),Vector())/len(ids) for g,ids in groups.items() if g.startswith('joint-')}
body_ids=sorted(groups['body']);ground=min(verts[i].y for i in body_ids)
scale=1.68/(max(verts[i].y for i in body_ids)-ground)
def convert(p):return Vector((p.x*scale,-p.z*scale,(p.y-ground)*scale))
vs=[convert(v) for v in verts];original_vs=[v.copy() for v in vs];joints={k:convert(v) for k,v in jraw.items()}
# Bring the CC0 base's relaxed A-pose arms down toward a natural standing pose.
for side in ['l','r']:
 sh=joints['joint-'+side+'-shoulder'];sign=1 if side=='l' else -1
 rot=Matrix.Rotation(sign*.62,3,'Y')
 for i in body_ids:
  v=vs[i]
  if v.x*sign>.14 and v.z>.80:
   w=max(0,min(1,(v.x*sign-.14)/.075));vs[i]=v.lerp(sh+rot@(v-sh),w)
 for n in ['elbow','hand','hand-2','hand-3']:
  key='joint-'+side+'-'+n
  if key in joints:joints[key]=sh+rot@(joints[key]-sh)

def mat(name,c,rough=.65,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
 n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal
 return m
skin=mat('Warm_skin',(.63,.40,.29),.5);shirt=mat('Ivory_ribbed_top',(.86,.82,.73),.9)
denim=mat('Blue_denim',(.14,.23,.34),.9);shoe=mat('White_leather_sneaker',(.90,.89,.85),.7)
sole=mat('Sneaker_sole',(.73,.74,.72),.8);hair=mat('Dark_brown_hair',(.028,.020,.017),.42)
hairlight=mat('Hair_soft_highlights',(.065,.043,.030),.5);gold=mat('Gold_pendant',(.72,.47,.15),.3,.75)
eye=mat('Eye_white',(.84,.80,.72),.35);iris=mat('Dark_brown_iris',(.022,.012,.008),.3)
seam=mat('Jeans_stitching',(.30,.28,.22),.9)
# Extract only the useful texture swatches from the user-provided reference.
# This is texture preparation for a mesh, not a standalone generated image.
ref=bpy.data.images.load(str(REF/'face_details.jpg'));pixels=list(ref.pixels);rw,rh=ref.size
def texture_crop(name,rect):
 x0,y0,x1,y1=rect;w=x1-x0;h=y1-y0;im=bpy.data.images.new(name,width=w,height=h,alpha=False)
 arr=[]
 for yy in range(y1-1,y0-1,-1):
  off=((rh-1-yy)*rw+x0)*4;arr.extend(pixels[off:off+w*4])
 im.pixels=arr;im.filepath_raw=str(OUT/(name+'.png'));im.file_format='PNG';im.save();return im
denim_img=texture_crop('denim_reference_swatch',(875,555,1005,881))
face_img=texture_crop('face_reference_projection',(80,120,318,360))
# Bake a uniform small woven swatch: avoid repeating large photographic folds.
denim_img=bpy.data.images.new('denim_game_weave',width=128,height=128,alpha=False)
arr=[]
for yy in range(128):
 for xx in range(128):
  weave=(.035 if (xx+yy)%5<2 else -.015)+.008*math.sin(xx*17+yy*31)
  arr.extend((.37+weave,.46+weave,.56+weave,1))
denim_img.pixels=arr;denim_img.filepath_raw=str(OUT/'denim_game_weave.png');denim_img.file_format='PNG';denim_img.save()
# Feather the photograph toward a skin-coloured border instead of a hard mask.
fpx=list(face_img.pixels);fw,fh=face_img.size
for yy in range(fh):
 for xx in range(fw):
  px=xx+80;py=120+(fh-1-yy);dx=(px-195-.17*(py-240))/83;dy=(py-240)/105
  a=max(0,min(1,(1-dx*dx-dy*dy)*3.2));off=(yy*fw+xx)*4
  luma=sum(fpx[off:off+3])/3
  if luma<.32 and not (176<py<232 and 126<px<267):a*=max(0,min(1,(luma-.12)/.20))
  for k,c in enumerate((.79,.66,.57)):fpx[off+k]=c*(1-a)+fpx[off+k]*a
face_img.pixels=fpx;face_img.save()
facemat=mat('Reference_projected_face',(.7,.5,.4),.6)
for m,im in [(denim,denim_img),(facemat,face_img)]:
 node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=im;node.extension='REPEAT' if m==denim else 'EXTEND';m.node_tree.links.new(node.outputs['Color'],m.node_tree.nodes['Principled BSDF'].inputs['Base Color'])

# Expand the legs to a straight-cut jeans silhouette and cover torso with a top.
waist=.91;neck=joints['joint-neck'];eyeZ=joints['joint-l-eye'].z
for i in body_ids:
 v=vs[i]
 if .10<v.z<waist:
  sign=1 if v.x>=0 else -1
  center=.13*sign
  if v.z<.80:
   dx=v.x-center;dy=v.y+.025
   v.x=center+dx*1.12;v.y=-.025+dy*1.10
 if waist<v.z<1.40 and abs(v.x)<.18:
  v.y*=1.025;v.x*=1.02

remap={old:i for i,old in enumerate(body_ids)};newfaces=[];face_mats=[]
for f in faces:
 center=sum((vs[i] for i in f),Vector())/len(f)
 if center.z<.105:continue # Covered, individually modelled sneakers replace the feet.
 oc=sum((original_vs[i] for i in f),Vector())/len(f)
 mi=0;near_hand=abs(oc.x)>.385 and oc.z<1.10
 if center.z<waist and not near_hand:mi=2
 elif center.z<neck.z-.025:
  # Round neckline, long sleeves; hands are kept as skin.
  neckline=abs(center.x)<.09 and center.z>neck.z-.105 and center.y<-.015
  if not near_hand and not neckline:mi=1
 if center.z>eyeZ-.105 and center.z<eyeZ+.09 and center.y<-.075 and abs(center.x)<.075:mi=3
 if mi==1 and center.z>neck.z-.15 and abs(oc.x)<.19:mi=0
 if mi in (1,2):continue # Clothing is independently modelled below.
 newfaces.append([remap[i] for i in f]);face_mats.append(mi)
used=sorted({i for f in newfaces for i in f});compact={i:k for k,i in enumerate(used)}
mesh=bpy.data.meshes.new('Clothed_body_mesh');mesh.from_pydata([vs[body_ids[i]] for i in used],[],[[compact[i] for i in f] for f in newfaces]);mesh.update()
body=bpy.data.objects.new('Reference_clothed_body',mesh);bpy.context.collection.objects.link(body)
for m in [skin,shirt,denim,facemat]:mesh.materials.append(m)
uv=mesh.uv_layers.new(name='UVMap')
for poly,mi in zip(mesh.polygons,face_mats):
 poly.material_index=mi;poly.use_smooth=True
 for li in poly.loop_indices:
  v=mesh.vertices[mesh.loops[li].vertex_index].co
  if mi==3:
   # The reference front view is slightly tilted; compensate in this projection.
   px=195+v.x*1200+(v.z-eyeZ)*235
   py=211-(v.z-eyeZ)*1250+v.x*180
   xy=((px-80)/238,1-(py-120)/240)
  else:xy=(v.x*14+v.y*10,v.z*14)
  uv.data[li].uv=xy
body['source']='MakeHuman CC0 base + user photo appearance guidance'
body['accuracy']='Approximation; no recovered scan or guaranteed facial likeness'

rig_data=bpy.data.armatures.new('Campus_character_skeleton');rig=bpy.data.objects.new('Campus_character_rig',rig_data);bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
bones=[]
def bone(name,head,tail,parent=None):
 b=rig_data.edit_bones.new(name);b.head=head;b.tail=tail
 if (b.tail-b.head).length<.005:b.tail.z+=.04
 if parent:b.parent=rig_data.edit_bones[parent]
 bones.append((name,Vector(head),Vector(tail)))
pelvis=joints['joint-pelvis'];chest=joints['joint-spine-1']
bone('Hips',pelvis,joints['joint-spine-2'])
bone('Spine',joints['joint-spine-2'],chest,'Hips')
bone('Chest',chest,neck,'Spine')
bone('Neck',neck,joints['joint-head'],'Chest')
bone('Head',joints['joint-head'],joints['joint-head-2']+Vector((0,0,.06)),'Neck')
for s,cap in [('l','L'),('r','R')]:
 sh,el,ha=[joints['joint-'+s+'-'+n] for n in ['shoulder','elbow','hand']]
 hip,knee,ankle,foot=[joints['joint-'+s+'-'+n] for n in ['upper-leg','knee','ankle','foot-2']]
 bone('UpperArm_'+cap,sh,el,'Chest');bone('ForeArm_'+cap,el,ha,'UpperArm_'+cap)
 bone('Hand_'+cap,ha,ha+(ha-el).normalized()*.08,'ForeArm_'+cap)
 bone('Thigh_'+cap,hip,knee,'Hips');bone('Shin_'+cap,knee,ankle,'Thigh_'+cap);bone('Foot_'+cap,ankle,foot,'Shin_'+cap)
bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False)
def bind(obj,rigid=None):
 if rigid:
  obj.vertex_groups.new(name=rigid).add(list(range(len(obj.data.vertices))),1,'REPLACE')
 else:
  for name,a,b in bones:obj.vertex_groups.new(name=name)
  for v in obj.data.vertices:
   distances=[]
   for name,a,b in bones:
    d=b-a;t=max(0,min(1,(v.co-a).dot(d)/d.length_squared));dist=(v.co-(a+t*d)).length
    # Keep leg/arm assignments from jumping across the body at close surfaces.
    if name.endswith('_L') and v.co.x<-.02:dist+=.4
    if name.endswith('_R') and v.co.x>.02:dist+=.4
    distances.append((dist,name))
   best=sorted(distances)[:2];weights=[1/max(d,.012)**4 for d,n in best];total=sum(weights)
   for (d,n),w in zip(best,weights):obj.vertex_groups[n].add([v.index],w/total,'REPLACE')
 mod=obj.modifiers.new('Skinning','ARMATURE');mod.object=rig;obj.parent=rig
bind(body)

def garment_mesh(name,vertices,polygons,material):
 m=bpy.data.meshes.new(name);m.from_pydata(vertices,[],polygons);m.update();ob=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(ob);m.materials.append(material)
 uv=m.uv_layers.new(name='UVMap')
 for p in m.polygons:
  p.use_smooth=True
  for li in p.loop_indices:
   co=m.vertices[m.loops[li].vertex_index].co;uv.data[li].uv=(co.x*16+co.y*11,co.z*16)
 bind(ob);ob['construction']='INDEPENDENT_CLOTHING_MESH__REFERENCE_GUIDED_APPROXIMATION';return ob
def loft(name,rings,material,n=32,cap=False):
 vv=[];ff=[]
 for center,rx,ry in rings:
  for i in range(n):a=i*math.tau/n;vv.append((center[0]+rx*math.cos(a),center[1]+ry*math.sin(a),center[2]))
 for j in range(len(rings)-1):
  for i in range(n):a=j*n+i;b=j*n+(i+1)%n;ff.append((a,b,b+n,a+n))
 if cap:ff.extend([tuple(reversed(range(n))),tuple(range((len(rings)-1)*n,len(rings)*n))])
 return garment_mesh(name,vv,ff,material)
# Extract a fitted garment from the licensed body's topology, then give it its
# own thickness and a level hem. This keeps the photo's fitted knit silhouette.
vv=[];ff=[];lookup={}
def clip_hem(points):
 result=[]
 for a,b in zip(points,points[1:]+points[:1]):
  ina=a.z>=waist;inb=b.z>=waist
  if ina:result.append(a)
  if ina!=inb:result.append(a.lerp(b,(waist-a.z)/(b.z-a.z)))
 return result
for f in faces:
 oc=sum((original_vs[i] for i in f),Vector())/len(f);c=sum((vs[i] for i in f),Vector())/len(f)
 arm=abs(oc.x)>.175 and oc.z>1.0
 if (not arm and not (waist-.07<c.z<neck.z+.01)) or (arm and abs(oc.x)>.385):continue
 neckline=(c.x/.088)**2+((c.y+.02)/.065)**2<1 and c.z>neck.z-.11
 if neckline:continue
 points=[vs[i].copy() for i in f]
 if not arm:points=clip_hem(points)
 if len(points)<3:continue
 face=[]
 for pt in points:
  key=tuple(round(c,7) for c in pt)
  if key not in lookup:lookup[key]=len(vv);vv.append(pt)
  face.append(lookup[key])
 ff.append(face)
top=garment_mesh('Ivory_top_fitted',vv,ff,shirt)
for vert in top.data.vertices:vert.co+=vert.normal*.004
top.data.update()
bpy.context.view_layer.objects.active=top;bpy.ops.object.select_all(action='DESELECT');top.select_set(True)
smooth=top.modifiers.new('Knit_edge_smoothing','SMOOTH');smooth.factor=.35;smooth.iterations=3;bpy.ops.object.modifier_apply(modifier=smooth.name)
solid=top.modifiers.new('Knit_thickness','SOLIDIFY');solid.thickness=.003;bpy.ops.object.modifier_apply(modifier=solid.name)
# Relaxed straight legs retain volume through the knees and cuffs.
loft('Jeans_waist',[((0,-.024,.80),.183,.116),((0,-.024,.88),.184,.114),((0,-.023,.965),.156,.101)],denim,40,True)
for s,cap in [('l','L'),('r','R')]:
 sign=1 if s=='l' else -1
 loft('Jeans_leg_'+cap,[((sign*.138,-.014,.11),.078,.095),((sign*.133,-.018,.27),.081,.096),((sign*.125,-.018,.46),.084,.100),((sign*.109,-.022,.66),.091,.106),((sign*.097,-.024,.85),.097,.112)],denim,32,True)

def sphere(name,loc,scale,material,bone_name,segments=16):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=12,location=loc)
 o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 # Bake object translation into mesh so skin bind uses a shared coordinate space.
 for v in o.data.vertices:v.co+=o.location
 o.location=(0,0,0);o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=True
 bind(o,bone_name);return o
for s,cap in [('l','L'),('r','R')]:
 ep=joints['joint-'+s+'-eye'];sphere('Eye_'+cap,ep,(.012,.012,.010),eye,'Head')
 sphere('Iris_'+cap,ep+Vector((0,-.0105,0)),(.0052,.002,.0052),iris,'Head')
 ankle=joints['joint-'+s+'-ankle'];loc=Vector((ankle.x,-.052,.06))
 shoe_parts=[('Sneaker_sole_'+cap,[(.015,1),(.039,1)],sole),('Sneaker_upper_'+cap,[(.039,.96),(.068,.91),(.105,.66)],shoe)]
 for name,levels,ma in shoe_parts:
  vv=[];ff=[];n=32
  for z,fac in levels:
   for i in range(n):a=i*math.tau/n;vv.append((loc.x+.058*fac*math.cos(a),loc.y+.126*fac*math.sin(a),z))
  for j in range(len(levels)-1):
   for i in range(n):a=j*n+i;b=j*n+(i+1)%n;ff.append((a,b,b+n,a+n))
  ff.extend([tuple(reversed(range(n))),tuple(range((len(levels)-1)*n,len(levels)*n))])
  ob=garment_mesh(name,vv,ff,ma)
  for vg in list(ob.vertex_groups):ob.vertex_groups.remove(vg)
  ob.vertex_groups.new(name='Foot_'+cap).add(list(range(len(vv))),1,'REPLACE')

def curve_mesh(name,points,radius,material,bone_name):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=8;cu.bevel_depth=radius;cu.bevel_resolution=2
 sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
 for b,p in zip(sp.bezier_points,points):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);o.data.materials.append(material)
 bpy.context.view_layer.objects.active=o;bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.ops.object.convert(target='MESH');bind(o,bone_name);return o

# Scalp and layered back hair, with separately modelled face-framing locks.
head=joints['joint-head'];top=max(v.z for v in vs if abs(v.x)<.11)
hc=Vector((0,.005,eyeZ+.025));hv=[];hf=[];rows=14;cols=32
for j in range(rows):
 theta=.07+(math.pi*.73)*j/(rows-1)
 for i in range(cols):
  a=i*math.tau/cols;z=hc.z+.122*math.cos(theta)
  # Hairline is high at the face; drop farther down at the back of the head.
  if math.sin(a)<-.20:theta2=min(theta,1.30)
  else:theta2=theta
  hv.append((.101*math.sin(theta2)*math.cos(a),hc.y+.105*math.sin(theta2)*math.sin(a),hc.z+.122*math.cos(theta2)))
for j in range(rows-1):
 for i in range(cols):a=j*cols+i;b=j*cols+(i+1)%cols;hf.append((a,b,b+cols,a+cols))
m=bpy.data.meshes.new('Hair_cap');m.from_pydata(hv,[],hf);m.update();o=bpy.data.objects.new('Dark_long_hair_cap',m);bpy.context.collection.objects.link(o);m.materials.append(hair)
for p in m.polygons:p.use_smooth=True
bind(o,'Head')
# A continuous back curtain provides volume; fine strands supply detail.
backverts=[];backfaces=[]
for z,rx,depth in [(eyeZ+.09,.082,.03),(eyeZ-.02,.105,.06),(1.35,.119,.095),(1.23,.110,.105),(1.11,.077,.102)]:
 for i in range(25):
  a=math.pi*i/24;backverts.append((rx*math.cos(a),depth+.058*math.sin(a),z+.008*math.cos(i*1.7)))
for row in range(4):
 for i in range(24):a=row*25+i;backfaces.append((a,a+1,a+26,a+25))
bm=bpy.data.meshes.new('Hair_back_curtain');bm.from_pydata(backverts,[],backfaces);bm.update();bo=bpy.data.objects.new('Layered_hair_volume',bm);bpy.context.collection.objects.link(bo);bm.materials.append(hair)
for p in bm.polygons:p.use_smooth=True
solid=bo.modifiers.new('Hair_thickness','SOLIDIFY');solid.thickness=.012;bind(bo,'Head')
for k in range(27):
 a=math.pi*k/26;x=math.cos(a);back=math.sin(a)
 end=1.11+.055*math.sin(k*1.7)
 pts=[(x*.084,.02+back*.052,eyeZ+.10),(x*.104,.04+back*.07,eyeZ-.02),
      (x*.116,.075+back*.067,1.36),(x*.105,.085+back*.048,1.23),(x*.080,.095+back*.02,end)]
 curve_mesh('Layered_back_hair_'+str(k),pts,.0025,hair if k%4 else hairlight,'Head')
for sign in [-1,1]:
 for k in range(3):
  x=sign*(.075+.006*k)
  pts=[(sign*.025,-.045,eyeZ+.13),(x,-.072,eyeZ+.035),
       (sign*(.085+.006*k),-.075,1.42),(sign*(.10+.006*k),-.075,1.30),
       (sign*(.09+.004*k),-.09,1.19+.025*k)]
  curve_mesh('Face_framing_lock_'+str(sign)+'_'+str(k),pts,.003,hair if k%3 else hairlight,'Head')
necklace_points=[(.07*math.cos(t),-.053-.03*math.sin(t),neck.z-.07-.035*math.sin(t)) for t in [i*math.pi/16 for i in range(17)]]
curve_mesh('Fine_gold_necklace',necklace_points,.0014,gold,'Chest')
sphere('Round_gold_pendant',(0,-.089,neck.z-.108),(.010,.0025,.010),gold,'Chest')
for i in range(4):sphere('Top_button_'+str(i),(0,-.081,neck.z-.13-i*.045),(.003,.002,.003),shoe,'Chest',12)
curve_mesh('Round_neckline',[(-.085,-.045,neck.z-.06),(-.055,-.078,neck.z-.11),(0,-.083,neck.z-.12),(.055,-.078,neck.z-.11),(.085,-.045,neck.z-.06)],.006,shirt,'Chest')
curve_mesh('Jeans_waistband',[(.145*math.cos(a),-.024+.092*math.sin(a),waist) for a in [i*math.tau/32 for i in range(33)]],.014,denim,'Hips')
for s,cap in [('l','L'),('r','R')]:
 ankle=joints['joint-'+s+'-ankle']
 for k in range(5):
  yy=-.105+k*.017
  curve_mesh('Sneaker_lace_'+cap+'_'+str(k),[(ankle.x-.025,yy,.102),(ankle.x,yy+.004,.107),(ankle.x+.025,yy,.102)],.0016,shoe,'Foot_'+cap)
 sign=1 if s=='l' else -1
 curve_mesh('Jeans_back_pocket_'+cap,[(sign*.09-.035,.087,.89),(sign*.09+.035,.087,.89),(sign*.09+.031,.094,.82),(sign*.09,.099,.80),(sign*.09-.031,.094,.82),(sign*.09-.035,.087,.89)],.0017,seam,'Hips')
# Consolidate all skinned pieces. Keep a single mesh with shared material slots.
bpy.ops.object.select_all(action='DESELECT')
for ob in list(bpy.context.scene.objects):
 if ob.type=='MESH':
  bpy.context.view_layer.objects.active=ob;ob.select_set(True)
  for mod in list(ob.modifiers):
   if mod.type!='ARMATURE':bpy.ops.object.modifier_apply(modifier=mod.name)
  ob.select_set(False)
def group_name(ob):
 n=ob.name.lower()
 if any(w in n for w in ['hair','lock']):return 'Hair_layered'
 if any(w in n for w in ['ivory_top','top_button','neckline']):return 'Clothing_ivory_top'
 if 'jeans' in n:return 'Clothing_straight_jeans'
 if any(w in n for w in ['sneaker','sole','lace']):return 'Clothing_white_sneakers'
 if any(w in n for w in ['necklace','pendant']):return 'Accessories_gold'
 return 'Body_skin_and_face'
mesh_groups=defaultdict(list)
for ob in list(bpy.context.scene.objects):
 if ob.type=='MESH':mesh_groups[group_name(ob)].append(ob)
for name,objects in mesh_groups.items():
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 if len(objects)>1:bpy.ops.object.join()
 ob=bpy.context.object;ob.name=name
 if name=='Clothing_straight_jeans':
  for mod in list(ob.modifiers):ob.modifiers.remove(mod)
  for vg in list(ob.vertex_groups):ob.vertex_groups.remove(vg)
  ob.data.remesh_voxel_size=.006;ob.data.remesh_voxel_adaptivity=0
  bpy.ops.object.voxel_remesh()
  sm=ob.modifiers.new('Cloth_seam_smoothing','SMOOTH');sm.factor=.7;sm.iterations=5;bpy.ops.object.modifier_apply(modifier=sm.name)
  bind(ob)
  ob.data.materials.clear();ob.data.materials.append(denim)
  uv=ob.data.uv_layers.new(name='UVMap')
  for p in ob.data.polygons:
   p.use_smooth=True
   for li in p.loop_indices:
    c=ob.data.vertices[ob.data.loops[li].vertex_index].co;uv.data[li].uv=(c.x*14+c.y*10,c.z*14)
 lod=ob.modifiers.new('Mobile_mesh_simplification','DECIMATE');lod.ratio=.80 if name=='Body_skin_and_face' else (.12 if name=='Clothing_straight_jeans' else .60);lod.use_collapse_triangulate=True
 bpy.ops.object.modifier_apply(modifier=lod.name)
 if name=='Body_skin_and_face':body=ob

# Keyframed skeletal clips are exported as real glTF animations.
for pb in rig.pose.bones:pb.rotation_mode='XYZ'
def animate(name,frames,rate,amp):
 action=bpy.data.actions.new(name);rig.animation_data_create();rig.animation_data.action=action
 for f in frames:
  t=(f-1)/(frames[-1]-1);phase=t*math.tau
  for pb in rig.pose.bones:pb.rotation_euler=(0,0,0);pb.location=(0,0,0)
  if name in ['Walk','Run']:
   for cap,sign in [('L',1),('R',-1)]:
    swing=math.sin(phase)*sign
    rig.pose.bones['Thigh_'+cap].rotation_euler.x=amp*swing
    rig.pose.bones['Shin_'+cap].rotation_euler.x=-max(0,-swing)*amp*1.15
    rig.pose.bones['Foot_'+cap].rotation_euler.x=.10*swing
    rig.pose.bones['UpperArm_'+cap].rotation_euler.x=-amp*.65*swing
    rig.pose.bones['ForeArm_'+cap].rotation_euler.x=-.12-amp*.13
   rig.pose.bones['Hips'].location.y=.012*abs(math.sin(phase*2))
   rig.pose.bones['Spine'].rotation_euler.z=.025*math.sin(phase)
  elif name=='Idle':rig.pose.bones['Chest'].rotation_euler.x=.013*math.sin(phase)
  elif name=='Jump':
   bend=math.sin(math.pi*t)
   for cap in ['L','R']:
    rig.pose.bones['Thigh_'+cap].rotation_euler.x=.35*bend
    rig.pose.bones['Shin_'+cap].rotation_euler.x=-.65*bend
    rig.pose.bones['UpperArm_'+cap].rotation_euler.x=-.25*bend
  for pb in rig.pose.bones:
   pb.keyframe_insert('rotation_euler',frame=f)
   if pb.name=='Hips':pb.keyframe_insert('location',frame=f)
 strip=rig.animation_data.nla_tracks.new();strip.name=name;clip=strip.strips.new(name,1,action);clip.name=name
 rig.animation_data.action=None
animate('Idle',list(range(1,62,5)),30,.0)
animate('Walk',list(range(1,32,3)),30,.42)
animate('Run',list(range(1,23,2)),30,.78)
animate('Jump',list(range(1,32,3)),30,.0)
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle'];bpy.context.scene.frame_set(1)
for im in bpy.data.images:
 if im.type=='IMAGE' and im!=ref:im.pack()
if ref.users==0:bpy.data.images.remove(ref)
scene=bpy.context.scene;scene.render.fps=30;scene.unit_settings.system='METRIC'
bpy.ops.object.select_all(action='DESELECT')
for ob in scene.objects:
 if ob.type in ['MESH','ARMATURE']:ob.select_set(True)
bpy.context.view_layer.objects.active=rig
for tr in rig.animation_data.nla_tracks:tr.mute=False
rig.animation_data.action=None
bpy.ops.export_scene.gltf(filepath=str(OUT/'CampusExplorer.glb'),export_format='GLB',use_selection=True,export_skins=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'CampusExplorer.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},bake_anim=True,add_leaf_bones=False,path_mode='COPY',embed_textures=True)
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1)
scene['character_status']='Reference-guided approximate character; CC0 base; not a recovered scan.'
world=bpy.data.worlds.new('Studio');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.39,.42,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65
ld=bpy.data.lights.new('Key','AREA');ld.energy=450;ld.shape='DISK';ld.size=4;lo=bpy.data.objects.new('Key',ld);bpy.context.collection.objects.link(lo);lo.location=(2,-3,3)
cd=bpy.data.cameras.new('Character_preview');co=bpy.data.objects.new('Character_preview',cd);bpy.context.collection.objects.link(co);co.location=(2.0,-4.0,1.9);co.rotation_euler=(Vector((0,0,.87))-co.location).to_track_quat('-Z','Y').to_euler();cd.lens=65;scene.camera=co
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.resolution_x=700;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'CampusExplorer.blend'),compress=True)
scene.render.filepath=str(OUT/'character_preview.png');bpy.ops.render.render(write_still=True)
report={'method':'CC0 MakeHuman base + supplied photo appearance/texture reference + procedural clothing/hair/rig/animation',
 'reference_files':[str(REF/'body_views.jpg'),str(REF/'face_details.jpg')],
 'height_m':1.68,'bones':len(rig_data.bones),'animations':['Idle','Walk','Run','Jump'],
 'face_likeness':'APPROXIMATE_NOT_VERIFIED','photogrammetry':False,'clothing_construction':'Separate skinned top, long sleeves, straight jeans and sneaker meshes',
 'base_license':'CC0 1.0','body_vertices':len(body.data.vertices),'mesh_triangles_total':sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in scene.objects if o.type=='MESH'),'source_asset_records':'../source/asset_acquisition.json'}
(OUT/'character_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('CHARACTER_EXPORTED',json.dumps(report,ensure_ascii=False),flush=True)
