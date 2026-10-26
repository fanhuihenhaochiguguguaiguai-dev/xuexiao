"""Remove coincident interior faces while preserving the checked aisle shape."""
import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'));from metric_steps import stepped_stand
S=ROOT/'.campus-cache/v06';bpy.ops.wm.open_mainfile(filepath=str(S/'HenanCampus.blend'));bpy.context.preferences.filepaths.save_version=0;spec=json.loads((S/'scene_specification.json').read_text());o=next(o for o in spec['objects'] if o['name']=='B20_grandstand');ring=[Vector((*p,0)) for p in o['polygon']['rings'][0]];a,b=max([(a,ring[(i+1)%len(ring)]) for i,a in enumerate(ring)],key=lambda p:(p[1]-p[0]).length);u=(b-a).normalized();v=Vector((-u.y,u.x,0));c=sum(ring,Vector())/len(ring)
if v.x<0:u=-u;v=-v
length=max((p-c).dot(u) for p in ring)-min((p-c).dot(u) for p in ring);width=max((p-c).dot(v) for p in ring)-min((p-c).dot(v) for p in ring);verts,faces=stepped_stand(tuple(c),tuple(u),tuple(v),length,width);ob=bpy.data.objects['B20_grandstand'];materials=list(ob.data.materials);mesh=bpy.data.meshes.new('B20_closed_contiguous_steps');mesh.from_pydata(verts,[],faces);mesh.update();ob.data=mesh
for m in materials:mesh.materials.append(m)
uv=mesh.uv_layers.new(name='UVMap')
for face in mesh.polygons:
 for li in face.loop_indices:
  p=mesh.vertices[mesh.loops[li].vertex_index].co;uv.data[li].uv=(p.x/2,p.y/2)
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=.0001);assert all(e.is_manifold for e in bm.edges);assert bm.calc_volume(signed=True)>0;bm.free();mesh.calc_loop_triangles();colliders=json.loads((S/'special-colliders.json').read_text());colliders=[x for x in colliders if x['name']!='B20_grandstand'];colliders.append({'name':'B20_grandstand','kind':'Grandstand','building':20,'vertices':[q for p in verts for q in [p[0],p[2],-p[1]]],'indices':[i for t in mesh.loop_triangles for i in t.vertices]});(S/'special-colliders.json').write_text(json.dumps(colliders,separators=(',',':')));bpy.ops.wm.save_as_mainfile(filepath=str(S/'HenanCampus.blend'),compress=True);print('CONTIGUOUS_STAND_PASSED')
