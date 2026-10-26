"""Re-import both deliverables and compare world-space building dimensions."""
from pathlib import Path
import os
import bpy,bmesh,json,math,re
from mathutils import Vector
P=Path(os.environ.get('CAMPUS_ASSET_ROOT', str(Path(__file__).resolve().parents[1])))/'project'
def inspect():
 meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
 bounds={};invalid=[];checks=[]
 for o in meshes:
  vv=[o.matrix_world@v.co for v in o.data.vertices]
  if any(not math.isfinite(c) for v in vv for c in v):invalid.append(o.name)
  idx=o.get('building_index')
  if idx:
   k=str(int(idx));b=bounds.setdefault(k,{'min':[float('inf')]*3,'max':[float('-inf')]*3})
   for v in vv:
    for j in range(3):b['min'][j]=min(b['min'][j],v[j]);b['max'][j]=max(b['max'][j],v[j])
   # Window panels and glyphs are intentionally thin decorative surfaces. Test
   # manifold structure only for the actual extruded building bodies.
   if re.match(r'^B\d\d_(tower|dorm|arcade|library|admin|teaching|grandstand)(?:_\d+)?$',o.name):
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
    bm.normal_update();non_manifold=sum(not e.is_manifold for e in bm.edges)
    vol=abs(bm.calc_volume(signed=True));bm.free()
    checks.append({'object':o.name,'building_index':int(idx),'non_manifold_edges_after_seam_weld':non_manifold,'volume_m3':vol})
 # Access packed image pixels to force lazy glTF images to decode before checking.
 for image in bpy.data.images:
  if image.type=='IMAGE':sample=list(image.pixels[:4])
 images=[{'name':i.name,'has_pixels':i.has_data,'size':list(i.size),
          'packed':bool(i.packed_file),'path':i.filepath} for i in bpy.data.images if i.type=='IMAGE']
 return {'mesh_objects':len(meshes),'building_bounds':bounds,'temporary_uv_seam_weld_tolerance_m':.0001,
   'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),
   'invalid_coordinate_objects':invalid,'building_geometry_checks':checks,'images':images,
   'all_images_loaded':all(i['has_pixels'] and min(i['size'])>0 for i in images),
   'all_building_solids_closed':all(c['non_manifold_edges_after_seam_weld']==0 and c['volume_m3']>0 for c in checks)}
bpy.ops.wm.open_mainfile(filepath=str(P/'HenanCampus.blend'));baseline=inspect()
result={'baseline':baseline,'formats':{},'note':'Checks mesh geometry, units, placement and loaded images; not proof of surveyed accuracy or UE runtime behaviour.'}
for fmt in ['glb','fbx']:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 if fmt=='glb':bpy.ops.import_scene.gltf(filepath=str(P/'HenanCampus.glb'))
 else:bpy.ops.import_scene.fbx(filepath=str(P/'HenanCampus.fbx'),use_custom_props=True)
 data=inspect();deviations=[]
 for idx,b in baseline['building_bounds'].items():
  n=data['building_bounds'].get(idx)
  if not n:deviations.append({'building':idx,'missing':True});continue
  delta=max(abs(b[k][j]-n[k][j]) for k in ['min','max'] for j in range(3))
  if delta>.001:deviations.append({'building':idx,'max_delta_m':delta})
 data['bounds_deviations_over_1mm']=deviations
 data['passed']=not deviations and len(data['building_bounds'])==20 and data['all_images_loaded'] and data['all_building_solids_closed'] and not data['invalid_coordinate_objects']
 result['formats'][fmt]=data
result['passed']=all(x['passed'] for x in result['formats'].values())
(P/'verification/reimport_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':result['passed'],'formats':{k:{'passed':v['passed'],'meshes':v['mesh_objects'],'triangles':v['triangles'],'closed_buildings':v['all_building_solids_closed'],'images_loaded':v['all_images_loaded'],'bounds_deviations':v['bounds_deviations_over_1mm']} for k,v in result['formats'].items()}},ensure_ascii=False),flush=True)
