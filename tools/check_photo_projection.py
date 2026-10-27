"""Independently compare physical meshes and verify actual unlit GLB materials."""
import bpy,json,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/photo-projection/front';BASE=ROOT/'.campus-cache/photo-fit/baseline';world=json.loads((BASE/'world.json').read_text());names={c['name'] for c in world['colliders']}
def physical():
 result={}
 for name in names:
  ob=bpy.data.objects.get(name)
  if not ob or ob.type!='MESH':continue
  vv=[list(ob.matrix_world@v.co) for v in ob.data.vertices];faces=[list(p.vertices) for p in ob.data.polygons];result[name]=hashlib.sha256(json.dumps({'vertices':vv,'faces':faces},sort_keys=True).encode()).hexdigest()
 return result
bpy.ops.wm.open_mainfile(filepath=str(BASE/'HenanCampus.blend'));before=physical();bpy.ops.wm.open_mainfile(filepath=str(S/'HenanCampus.blend'));after=physical();assert before==after,'Physical geometry changed during a texture-only operation'
materials=[]
for filename in ['HenanCampus.glb','library.glb','campus-base.glb']:
 raw=(S/filename).read_bytes();n=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+n]);found=[m for m in doc['materials'] if m['name'].startswith('PhotoProjected')];assert len(found)==3,(filename,len(found));assert all('KHR_materials_unlit' in m.get('extensions',{}) for m in found),filename;materials.append({'file':filename,'photo_materials':[m['name'] for m in found],'explicit_unlit':True})
r={'passed':True,'physical_meshes_compared':len(before),'physical_mesh_signatures':before,'world_colliders_sha256':hashlib.sha256(json.dumps(world['colliders'],sort_keys=True).encode()).hexdigest(),'materials':materials,'scope':'Exact unchanged world-space collision-source meshes plus actual glTF unlit extension; not surveyed shape or photorealism proof.'};(S/'physical-and-materials.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('PHOTO_PHYSICAL_AND_MATERIALS_PASSED',len(before),flush=True)
