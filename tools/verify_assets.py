"""Validate actual retained bytes and repair the inherited stale runtime manifest."""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[1];ASSETS=ROOT/'dist/assets'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((ROOT/'reports/baseline.json').read_text())
for row in baseline['retained_assets']:
 p=ROOT/row['path']
 if not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise SystemExit('Retained baseline changed: '+row['path'])
for name in ['campus.glb','character.glb']:
 p=ASSETS/name;b=p.read_bytes()[:12]
 if b[:4]!=b'glTF' or struct.unpack_from('<I',b,4)[0]!=2 or struct.unpack_from('<I',b,8)[0]!=p.stat().st_size:raise SystemExit('Invalid real GLB: '+name)
nav=json.loads((ASSETS/'navigation.json').read_text())
if nav['source_sha256']!=sha(ASSETS/'world.json'):raise SystemExit('Stale collision navigation')
world=json.loads((ASSETS/'world.json').read_text())
if world['source_model_sha256']!=sha(ASSETS/'campus.glb'):raise SystemExit('Physics source identity mismatch')
rows=[{'path':str(p.relative_to(ASSETS)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(ASSETS.rglob('*')) if p.is_file() and p.name!='asset-manifest.json']
if '--write-manifest' in sys.argv:
 prior=json.loads((ASSETS/'asset-manifest.json').read_text());prior.update(revision='campus-experiment-navigation-1',files=rows,scope='Independent experiment; retained approximate source models; current actual asset bytes and collision-derived navigation');(ASSETS/'asset-manifest.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n')
manifest=json.loads((ASSETS/'asset-manifest.json').read_text())
if manifest['files']!=rows:raise SystemExit('Runtime asset manifest differs from actual files; repair explicitly with --write-manifest')
print(json.dumps({'status':'PASS','retained_models_and_world_unchanged':True,'navigation_source_matches':True,'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'scope':'Byte identity and boundary checks; no repeat modeling or native reimport'}))
