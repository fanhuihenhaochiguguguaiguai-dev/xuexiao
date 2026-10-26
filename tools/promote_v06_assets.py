"""Promote the gated v0.6 assets on the development branch; no re-export."""
from pathlib import Path
import json,shutil,sys,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from automation.quality import glb_gate
S=ROOT/'.campus-cache/v06';P=ROOT/'assets/henan_campus/project';C=ROOT/'assets/henan_campus/character/output';D=ROOT/'game/dist/assets'
checks={'campus':glb_gate(S/'HenanCampus.glb',10),'base':glb_gate(S/'campus-base.glb',10),'character':glb_gate(S/'character/CampusExplorer.glb',1,True)}
assert json.loads((S/'interactions.json').read_text())['passed'];assert json.loads((S/'character/report.json').read_text())['passed']
for name in ['HenanCampus.blend','HenanCampus.fbx','HenanCampus.glb']:shutil.copy2(S/name,P/name)
for name in ['CampusExplorer.blend','CampusExplorer.fbx','CampusExplorer.glb','fabric-normal.png']:shutil.copy2(S/'character'/name,C/name)
shutil.copy2(S/'scene_specification.json',P/'scene_specification.json');spec=json.loads((P/'scene_specification.json').read_text())
for path in [P/'source_data/building_model_parameters.json',ROOT/'assets/henan_campus/metadata/building_model_parameters.json']:path.write_text(json.dumps(spec['buildings'],ensure_ascii=False,indent=2)+'\n')
shutil.copytree(S/'assets',P/'assets/v06',dirs_exist_ok=True);shutil.copytree(S/'runtime',D,dirs_exist_ok=True);shutil.copy2(C/'CampusExplorer.glb',D/'character.glb');(D/'v06').mkdir(exist_ok=True)
for p in (S/'assets').glob('*-2048.png'):shutil.copy2(p,D/'v06'/p.name)
for src,dst in [('geometry-report.json','v06-geometry.json'),('interactions.json','v06-interactions.json'),('character/report.json','v06-character.json')]:shutil.copy2(S/src,ROOT/'reports'/dst)
checks['status']='MODELS_AND_PHYSICS_PROMOTED_BROWSER_QA_REQUIRED';(ROOT/'reports/v06-stage-gates.json').write_text(json.dumps(checks,indent=2)+'\n');print('V06_ASSETS_PROMOTED')
