"""Promote the single staged source only after geometry, navigation and reimport."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from automation.quality import glb_gate
S=ROOT/'.campus-cache/v07';P=ROOT/'assets/henan_campus/project';D=ROOT/'game/dist/assets'
spec=json.loads((S/'scene_specification.json').read_text());report=json.loads((S/'geometry-report.json').read_text());nav=json.loads((S/'all-interactions.json').read_text());reimport=json.loads((S/'reimport.json').read_text())
assert spec['version']=='0.7' and set(report['selected'])==set(range(1,20))
assert report['passed'] and nav['passed'] and nav['libraryEntrance']['passed'] and reimport['passed']
gates={'campus':glb_gate(S/'HenanCampus.glb',10),'base':glb_gate(S/'campus-base.glb',10)}
for name in ['HenanCampus.blend','HenanCampus.glb','HenanCampus.fbx','scene_specification.json']:shutil.copy2(S/name,P/name)
for name in ['world.json','zones.json']:shutil.copy2(S/name,D/name)
shutil.copy2(S/'campus-base.glb',D/'campus.glb');shutil.copytree(S/'zones',D/'zones',dirs_exist_ok=True);shutil.copytree(S/'assets',P/'assets/v07',dirs_exist_ok=True)
shutil.copy2(S/'reimport.json',P/'verification/reimport_validation.json')
for p in [P/'source_data/building_model_parameters.json',ROOT/'assets/henan_campus/metadata/building_model_parameters.json']:p.write_text(json.dumps(spec['buildings'],ensure_ascii=False,indent=2)+'\n')
p=ROOT/'configs/buildings.json';config=json.loads(p.read_text())
for b in config:
    b['floor_rule_applied']=b['building_id']!=20
    if b['floor_rule_applied']:b['floor_height_m']=3.9
    else:b['structure_type']='TIERED_STAND_NOT_REGULAR_STOREYS'
p.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
for src,dst in [('geometry-report.json','v07-geometry.json'),('all-interactions.json','v07-interactions.json'),('reimport.json','v07-reimport.json')]:shutil.copy2(S/src,ROOT/'reports'/dst)
gates.update(status='GEOMETRY_NAVIGATION_REIMPORT_PASSED_BROWSER_QA_PENDING',source_sha256=hashlib.sha256((P/'HenanCampus.blend').read_bytes()).hexdigest())
(ROOT/'reports/v07-stage-gates.json').write_text(json.dumps(gates,indent=2)+'\n');print('V07_ASSETS_PROMOTED')
