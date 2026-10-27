"""Blender: reuse existing meshes, apply gated storeys, add referenced relief."""
import bpy,bmesh,json,math,sys,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.campus-cache/v07';P=ROOT/'assets/henan_campus/project'
spec=json.loads((OUT/'scene_specification.json').read_text());cfg=spec['v07_policy'];policy={int(k):v for k,v in json.loads((OUT/'transform-policy.json').read_text()).items()}
bpy.ops.wm.open_mainfile(filepath=str(OUT/'baseline/HenanCampus.blend'));scene=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
oldspec=json.loads((OUT/'baseline/scene_specification.json').read_text())
report={'version':spec['version'],'floor_height_m':3.9,'source_xy_retained':True,'footprint_accuracy':'OSM_NOT_SURVEYED','selected':list(policy),'buildings':[],'previous_triangles':sum(len(p.vertices)-2 for ob in scene.objects if ob.type=='MESH' for p in ob.data.polygons)}
def remap(z,p):
    top=p['base']+p['old_height']
    return z+p['new_height']-p['old_height'] if z>=top else p['base']+(z-p['base'])*p['factor']
for ob in scene.objects:
    idx=ob.get('building_index');p=policy.get(idx)
    if ob.type!='MESH' or not p or ob.name.endswith('_plinth'):continue
    if ob.name=='Library_v06_name':ob.location.z=remap(ob.location.z,p);continue
    ob.data=ob.data.copy();inverse=ob.matrix_world.inverted();keep=set()
    # Keep entrance doors at human scale while increasing actual storeys.
    if ob.name=='Library_refined_details':
        for face in ob.data.polygons:
            z=[(ob.matrix_world@ob.data.vertices[i].co).z for i in face.vertices]
            if abs(min(z)-1.96)<.02 and abs(max(z)-4.06)<.02:keep.update(face.vertices)
    for vertex in ob.data.vertices:
        if vertex.index in keep:continue
        q=ob.matrix_world@vertex.co;q.z=remap(q.z,p);vertex.co=inverse@q
    ob['floor_height_m']=3.9;ob['height_policy']='USER_RULE_NOT_SURVEY';ob.data.update()
    if ob.name==next(b['mesh_name'] for b in spec['buildings'] if b['map_index']==idx):ob['body_height_m']=p['new_height']

def material(name,color,rough=.8,metal=0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');c=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in color];p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;m.diffuse_color=(*c,1);return m

class Parts:
    def __init__(self):self.v=[];self.f=[];self.mi=[];self.m=[]
    def box(self,c,d,mat,u=(1,0,0),v=None,w=(0,0,1)):
        u=Vector(u);v=Vector(v) if v else Vector((-u.y,u.x,0));w=Vector(w);c=Vector(c);k=len(self.v)
        self.v.extend([tuple(c+u*(x*d[0]/2)+v*(y*d[1]/2)+w*(z*d[2]/2)) for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]])
        if mat not in self.m:self.m.append(mat)
        for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.f.append(tuple(k+i for i in ids));self.mi.append(self.m.index(mat))
    def finish(self,name,collision=False):
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(self.v,[],self.f);mesh.update();ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
        for m in self.m:mesh.materials.append(m)
        for f,i in zip(mesh.polygons,self.mi):f.material_index=i
        uv=mesh.uv_layers.new(name='UVMap')
        for f in mesh.polygons:
            for li in f.loop_indices:
                q=mesh.vertices[mesh.loops[li].vertex_index].co;uv.data[li].uv=(q.x/2,q.y/2) if abs(f.normal.z)>.5 else ((q.x if abs(f.normal.y)>.5 else q.y)/2,q.z/2)
        ob['building_index']=13;ob['source']='User photos 1000069957/9959; dimensions estimated';ob['collision_kind']='PlanterOrRail' if collision else 'FacadeDetail'
        return ob

extra_colliders=[]
if 13 in policy:
    profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];u=Vector((math.cos(math.radians(35)),math.sin(math.radians(35)),0));v=Vector((-u.y,u.x,0));uc=(profile[0][0]+profile[-1][0])/2
    def front(x):
        for a,b in zip(profile,profile[1:]):
            if a[0]<=x<=b[0]:return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
        return profile[0][1] if x<profile[0][0] else profile[-1][1]
    def point(x,d,z):return u*x+v*(front(x)-d)+Vector((0,0,z))
    stone=bpy.data.materials['Library_photo_guided_stone'];metal=material('V07_library_handrail',(.48,.49,.45),.4,.5);leaf=material('V07_trimmed_shrubs',(.26,.35,.17),.92)
    relief=Parts();rails=Parts();planters=Parts();base=policy[13]['base'];height=policy[13]['new_height']
    # Concrete window returns and repeated ledges add depth in a single batch.
    for k in range(13):
        x=uc-37.2+k*6.2;relief.box(point(x,.39,base+height/2),(.55,.55,height),stone,u,v)
    for row in range(1,10):
        z=base+min(row*3.9,height)-.17
        for k in range(12):
            x=uc-34.1+k*6.2;relief.box(point(x,.36,z),(5.7,.43,.28),stone,u,v)
    relief.finish('V07_library_window_returns')
    for x in [uc-17,uc+17]:
        # Hollow planters retain a clear central door/step route.
        for dx,dy,dims in [(-1.5,0,(.2,1.1,.88)),(1.5,0,(.2,1.1,.88)),(0,-.45,(3.2,.2,.88)),(0,.45,(3.2,.2,.88))]:planters.box(point(x+dx,.45+dy,base+.44),dims,stone,u,v)
        for k in [-.8,0,.8]:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.65,location=point(x+k,.45,base+1.04));ob=bpy.context.object;ob.name='V07_library_shrub';ob.scale=(1,.7,.75);ob.data.materials.append(leaf);ob['building_index']=13
    planters.finish('V07_library_entry_planters',True)
    for x in [uc-23,uc+23]:
        tops=[]
        for k in range(5):
            d=.8+k*1.03;j=max(0,12-math.floor((d-.7)/.38));z=.16+j*.15
            rails.box(point(x,d,z+.46),(.055,.055,.92),metal,u,v);tops.append(point(x,d,z+.95))
        for a,b in zip(tops,tops[1:]):
            along=(b-a).normalized();across=u;up=across.cross(along).normalized();rails.box((a+b)/2,(.06,(b-a).length,.06),metal,across,along,up)
    rails.finish('V07_library_entry_handrails',True)
    report['library_reference_changes']=['warm stone window returns and ledges','two shallow stone planters and low-poly shrubs','two slim stair handrails','entrance door height retained at 2.1m']

# Reuse the same updated, self-authored atlas across the existing dorm meshes.
dorm=bpy.data.images.load(str(OUT/'assets/dorm-facade-v07.png'));occlusion=bpy.data.images.load(str(OUT/'assets/ground-occlusion-v07.png'));occlusion.colorspace_settings.name='Non-Color'
for m in bpy.data.materials:
    if not m.use_nodes:continue
    for node in m.node_tree.nodes:
        if node.type!='TEX_IMAGE' or not node.image:continue
        if 'ground-occlusion' in node.image.name:node.image=occlusion
        if m.name=='dorm' and 'dorm_facade' in node.image.name:node.image=dorm
for image in bpy.data.images:
    if image.type=='IMAGE' and image.source=='FILE' and not image.packed_file:
        if not Path(bpy.path.abspath(image.filepath)).is_file():
            candidates=[P/'assets'/Path(image.filepath).name,P/'assets/v06'/Path(image.filepath).name]
            found=next((p for p in candidates if p.is_file()),None)
            if not found:raise RuntimeError('Missing unpacked texture: '+image.name)
            image.filepath=str(found)
        image.pack()

for b in spec['buildings']:
    ob=bpy.data.objects[b['mesh_name']];coords=[ob.matrix_world@v.co for v in ob.data.vertices];lo=[min(v[i] for v in coords) for i in range(3)];hi=[max(v[i] for v in coords) for i in range(3)]
    bm=bmesh.new();bm.from_mesh(ob.data);bad=sum(not e.is_manifold for e in bm.edges);volume=abs(bm.calc_volume());bm.free();expected=b['height_m']
    assert abs(hi[2]-lo[2]-expected)<.002 and bad==0 and volume>0,(b['map_index'],lo,hi,expected,bad)
    report['buildings'].append({'id':b['map_index'],'body_height_m':hi[2]-lo[2],'floor_count':b['floor_count'],'floor_height_m':b['floor_height_m'],'rule_applied':b['map_index'] in policy,'closed':bad==0,'volume_m3':volume})
for ob in scene.objects:
    if ob.type=='MESH' and ob.get('collision_kind')=='PlanterOrRail':
        ob.data.calc_loop_triangles();extra_colliders.append({'name':ob.name,'kind':'Landscape','building':13,'vertices':[q for vert in ob.data.vertices for q in ((ob.matrix_world@vert.co).x,(ob.matrix_world@vert.co).z,-(ob.matrix_world@vert.co).y)],'indices':[i for tri in ob.data.loop_triangles for i in tri.vertices]})
world=json.loads((OUT/'world.json').read_text());world['colliders'].extend(extra_colliders)
all_meshes=[o for o in scene.objects if o.type=='MESH'];report['triangles']=sum(len(p.vertices)-2 for ob in all_meshes for p in ob.data.polygons);report['triangle_increase_ratio']=report['triangles']/report['previous_triangles']-1
assert report['triangle_increase_ratio']<.05,'Detail budget exceeded; do not expand this method'
def export(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_extras=True)
export(OUT/'HenanCampus.glb',all_meshes)
bpy.ops.export_scene.fbx(filepath=str(OUT/'HenanCampus.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'HenanCampus.blend'),compress=True)
manifest=json.loads((OUT/'baseline/zones.json').read_text());base=[ob for ob in all_meshes if not ob.get('building_index')];zones=OUT/'zones';zones.mkdir(exist_ok=True)
for z in manifest['zones']:
    objects=[ob for ob in all_meshes if ob.get('building_index')==z['id']];export(zones/f'b{z["id"]:02d}.glb',objects);base.extend(ob for ob in objects if ob.name in z['coarse_nodes'])
manifest['version']=spec['version'];export(OUT/'campus-base.glb',base)
world['source_model_sha256']=hashlib.sha256((OUT/'HenanCampus.glb').read_bytes()).hexdigest();world['runtime_base_sha256']=hashlib.sha256((OUT/'campus-base.glb').read_bytes()).hexdigest()
(OUT/'world.json').write_text(json.dumps(world,ensure_ascii=False,separators=(',',':')));(OUT/'zones.json').write_text(json.dumps(manifest,indent=2)+'\n');report['passed']=True
(OUT/'geometry-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('V07_REUSE_GATE',json.dumps({'passed':True,'selected':list(policy),'floor_height_m':3.9,'library_body_m':next(b['body_height_m'] for b in report['buildings'] if b['id']==13),'triangle_increase_ratio':report['triangle_increase_ratio']}),flush=True)
