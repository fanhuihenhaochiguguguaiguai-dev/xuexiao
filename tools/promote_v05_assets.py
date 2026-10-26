"""Promote gated staged assets; keep rollback bytes in ignored cache only."""
from pathlib import Path
import json,shutil,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from automation.quality import glb_gate
A=ROOT/'assets/henan_campus';P=A/'project';stage=ROOT/'.campus-cache/v05';final=stage/'final';character=stage/'character';backup=stage/'rollback'
current=json.loads((P/'scene_specification.json').read_text())
if current.get('version')=='0.5':
 assert current.get('v05_floor_policy')==json.loads((ROOT/'configs/v05-buildings.json').read_text()),'Changed floor policy requires a new explicit revision; refusing to rescale promoted geometry'
 print('V05_ALREADY_PROMOTED: reuse verified assets without rescaling');raise SystemExit(0)
backup.mkdir(exist_ok=True)
assert glb_gate(final/'HenanCampus.glb',10)['passed'];assert glb_gate(character/'CampusExplorer.glb',1,True)['passed']
assert json.loads((character/'animation-report.json').read_text())['passed'];geo=json.loads((final/'geometry-report.json').read_text());assert geo['facade_buildings']==[15,16,17,18,19]
for src in [P/'HenanCampus.blend',P/'HenanCampus.fbx',P/'scene_specification.json',A/'character/output/CampusExplorer.blend',A/'character/output/CampusExplorer.fbx',A/'character/output/CampusExplorer.glb']:
 target=backup/src.relative_to(A);target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists():shutil.copy2(src,target)
for name in ['HenanCampus.blend','HenanCampus.glb','HenanCampus.fbx']:shutil.copy2(final/name,P/name)
for name in ['CampusExplorer.blend','CampusExplorer.glb','CampusExplorer.fbx']:shutil.copy2(character/name,A/'character/output'/name)
for f in (final/'assets').iterdir():
 if f.is_file():shutil.copy2(f,P/'assets'/f.name)
spec=json.loads((P/'scene_specification.json').read_text());cfg=json.loads((ROOT/'configs/v05-buildings.json').read_text());policy={p['id']:p for p in cfg['buildings']}
for o in spec['objects']:
 idx=o.get('building_index')
 if idx not in policy:continue
 p=policy[idx];old=p['old_body_height_m'];new=p['body_height_m'];anchor=1.36 if idx==13 else .16
 def remap(z):
  if z<=anchor:return z
  return anchor+(z-anchor)*(.16+new-anchor)/(.16+old-anchor) if z<=.16+old else z+new-old
 low=remap(o['z']);high=remap(o['z']+o['height']);o.update({'z':low,'height':high-low,'floor_height_estimated':3,'height_rule':'USER_3M_FLOOR_RULE'})
from shapely.geometry import Polygon
for b in spec['buildings']:
 p=policy[b['map_index']];b.update({'height_m':p['body_height_m'],'floor_height_m':3,'height_status':'USER_RULE_NOT_SURVEY','model_units':'METERS','scale_status':'MAP_XY_METERS_AND_USER_RULE_HEIGHT_NOT_SURVEY_1_TO_1'})
 o=next(o for o in spec['objects'] if o.get('building_index')==b['map_index'] and o['group']=='Buildings');rect=Polygon(o['polygon']['rings'][0]).minimum_rotated_rectangle;c=list(rect.exterior.coords);lengths=sorted({round(((c[i+1][0]-c[i][0])**2+(c[i+1][1]-c[i][1])**2)**.5,3) for i in range(4)})
 b['oriented_length_m']=max(lengths);b['oriented_width_m']=min(lengths);b['xy_dimension_source']='OSM_FOOTPRINT_NOT_MEASURED'
 if b['map_index'] in [15,16,17,18,19]:b['visual_revision']='V05_ORANGE_STONE_CURTAIN_TYPE_APPROXIMATION'
spec['version']='0.5';spec['v05_floor_policy']=cfg;spec['v05_geometry_report']='../../../reports/v05-geometry.json';(P/'scene_specification.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
for p in [A/'metadata/building_model_parameters.json',P/'source_data/building_model_parameters.json']:p.write_text(json.dumps(spec['buildings'],ensure_ascii=False,indent=2)+'\n')
for source,target in [(final/'geometry-report.json','v05-geometry.json'),(final/'export-quality.json','v05-mesh-quality.json'),(final/'assets/ao-bake.json','v05-ao-bake.json'),(character/'animation-report.json','v05-animation.json')]:shutil.copy2(source,ROOT/'reports'/target)
D=ROOT/'game/dist/assets/v05';D.mkdir(exist_ok=True)
for f in (final/'assets').iterdir():
 if f.is_file():shutil.copy2(f,D/f.name)
print('V05_GATED_ASSETS_PROMOTED',len(spec['buildings']))
