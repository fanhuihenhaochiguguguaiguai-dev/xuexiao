"""Blender CLI adapter: reuse one existing building without rebuilding it."""
import bpy,bmesh,sys,json,re
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:];source=Path(args[0]);building=int(args[1]);out=Path(args[2]);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(source))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('building_index')==building]
extra=json.loads(args[3]) if len(args)>3 else []
for name in extra:
 ob=bpy.data.objects.get(name)
 if ob is None or ob.type!='MESH' or ob.get('building_index') not in [None,building]:raise RuntimeError('Invalid explicit source part: '+name)
 if ob not in objects:objects.append(ob)
if not objects:raise RuntimeError('No mesh with building_index='+str(building))
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
images=[]
for im in bpy.data.images:
 if im.type=='IMAGE':
  sample=list(im.pixels[:4]);images.append({'name':im.name,'decoded':im.has_data and min(im.size)>0})
if any(not i['decoded'] for i in images):raise RuntimeError('Source texture did not decode')
structures=[]
for ob in objects:
 if re.match(r'^B\d\d_(tower|dorm|arcade|library|admin|teaching|grandstand)(?:_\d+)?$',ob.name):
  bm=bmesh.new();bm.from_mesh(ob.data);bm.normal_update();bad=sum(not e.is_manifold for e in bm.edges);volume=abs(bm.calc_volume(signed=True));bm.free()
  structures.append({'object':ob.name,'non_manifold_edges':bad,'volume_m3':volume})
if not structures or any(s['non_manifold_edges'] or s['volume_m3']<=0 for s in structures):raise RuntimeError('Source building body is not a closed solid')
bpy.ops.export_scene.gltf(filepath=str(out/'model.glb'),export_format='GLB',use_selection=True,export_extras=True,export_animations=False)
report={'building_index':building,'mesh_objects':len(objects),'source_objects':[o.name for o in objects],
        'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects),'decoded_source_images':images,
        'source_structures':structures,'method':'REUSED_EXISTING_MESH_NOT_REMODELLED','accuracy':'XY from existing mapped draft; heights and details remain estimated unless separately measured.'}
(out/'export.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
