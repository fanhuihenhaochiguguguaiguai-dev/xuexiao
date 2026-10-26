import json,sys,subprocess,shutil,platform,struct,urllib.request,urllib.error,urllib.parse,socket,hashlib
from pathlib import Path
from .quality import glb_gate,pwa_gate

CATEGORIES={'ENVIRONMENT','INPUT','INTEGRITY','CONFIGURATION','QUALITY'}
class Failure(Exception):
 def __init__(self,category,code,message):super().__init__(message);self.category=category;self.code=code

def command(argv,cwd,out,timeout=180,env=None):
 try:
  p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
 except FileNotFoundError as e:raise Failure('ENVIRONMENT','TOOL_MISSING',str(e))
 except subprocess.TimeoutExpired as e:raise Failure('ENVIRONMENT','TIMEOUT',f'Command exceeded {timeout}s: {argv[0]}')
 (out/'command.log').write_text((p.stdout+'\n'+p.stderr)[-400000:])
 if p.returncode:raise Failure('ENVIRONMENT' if p.returncode<0 else 'QUALITY','COMMAND_FAILED',f'{Path(str(argv[0])).name} exited {p.returncode}: '+p.stderr[-800:])
 return p.stdout

def route(model,photos=None):
 if model and Path(model).is_file():
  p=Path(model);header=p.read_bytes()[:8]
  if p.suffix=='.blend' and (header.startswith(b'BLENDER') or header.startswith((b'\x1f\x8b',b'\x28\xb5\x2f\xfd'))):return {'decision':'REUSE','geometry_accuracy':'EXISTING_DRAFT_NOT_SURVEY_VERIFIED'}
  if p.suffix=='.glb':
   try:glb_gate(p);return {'decision':'REUSE','geometry_accuracy':'MESH_VERIFIED_NOT_SURVEY_VERIFIED'}
   except (ValueError,KeyError,IndexError,struct.error,UnicodeDecodeError) as e:raise Failure('INTEGRITY','INVALID_MODEL',str(e))
  raise Failure('INPUT','UNSUPPORTED_MODEL','No allowed decoder for the provided model format/header')
 try:info=json.loads(Path(photos).read_text()) if photos and Path(photos).is_file() else {}
 except (OSError,ValueError) as e:raise Failure('INPUT','INVALID_PHOTO_MANIFEST',str(e))
 positions=set();valid_files=0
 for image in info.get('images',[]):
  path=(Path(photos).parent/image.get('path','')).resolve()
  # Names/flags alone do not make a reconstruction data set. Bind actual image
  # bytes to recorded capture positions, then require a separate sparse test.
  if not path.is_relative_to(Path(photos).parent.resolve()) or not path.is_file():continue
  data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=image.get('sha256'):continue
  if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')):continue
  if image.get('capture_position'):positions.add(image['capture_position']);valid_files+=1
 if valid_files>=3 and len(positions)>=3 and info.get('overlap_verified') and info.get('projection_adapter_verified'):
  return {'decision':'RECONSTRUCTION_CANDIDATE','automatic_execution_enabled':False,'reason':'Image bytes and capture annotations exist; decoder, stable COLMAP sparse registration and geometry gates are still required before reconstruction is accepted.'}
 return {'decision':'NEED_DATA','reason':'No usable mesh and no qualified multi-position reconstruction input; panorama faces at one station are not independent camera positions.'}

def fingerprint(job,root,tools):
 kind=job['driver']
 if kind=='tool':
  name=job['params']['name']
  if name not in tools:
   binary=shutil.which(name)
   if not binary:raise Failure('ENVIRONMENT','TOOL_MISSING',name+' is not available')
   try:r=subprocess.run([binary,'--version'],capture_output=True,text=True,timeout=15)
   except subprocess.TimeoutExpired:raise Failure('ENVIRONMENT','TOOL_PROBE_TIMEOUT',name+' version probe timed out')
   if r.returncode:raise Failure('ENVIRONMENT','TOOL_UNHEALTHY',name+' version probe failed')
   tools[name]={'version':(r.stdout or r.stderr).splitlines()[0],'platform':platform.platform()}
  return tools[name]
 return {'python':platform.python_version()}

def run(job,root,stage,inputs,dependencies,tools):
 kind=job['driver'];p=job.get('params',{})
 if kind=='tool':
  (stage/'tool.json').write_text(json.dumps(fingerprint(job,root,tools),sort_keys=True)+'\n')
 elif kind=='route':
  decision=route(inputs.get('model'),inputs.get('photos'))
  (stage/'route.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
  if decision['decision']!='REUSE':raise Failure('INPUT',decision['decision'],decision.get('reason','Reconstruction requires a configured handler.'))
 elif kind=='building_export':
  command(['blender','--background','--factory-startup','--disable-autoexec','--python',root/'automation/export_building.py','--',inputs['source'],p['building_id'],stage,json.dumps(p.get('include_objects',[]))],root,stage,p.get('timeout',120))
  try:
   gate=glb_gate(stage/'model.glb',min_height=p.get('min_height',1.5))
   report=json.loads((stage/'export.json').read_text())
   if report['building_index']!=p['building_id'] or report['triangles']<4:raise ValueError('Wrong/empty source object selection')
  except (ValueError,KeyError,OSError,json.JSONDecodeError) as e:raise Failure('QUALITY','MODEL_GATE',str(e))
  (stage/'quality.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2)+'\n')
 elif kind=='glb_gate':
  try:gate=glb_gate(inputs['model'],p.get('min_height',.1),p.get('require_skin',False))
  except (ValueError,KeyError,OSError) as e:raise Failure('QUALITY','MODEL_GATE',str(e))
  (stage/'quality.json').write_text(json.dumps(gate,indent=2)+'\n')
 elif kind=='physics':
  import os
  env=os.environ.copy();env['CAMPUS_PHYSICS_REPORT']=str(stage/'physics.json')
  command(['node',root/'game/physics-check.mjs'],root/'game',stage,90,env)
  try:
   report=json.loads((stage/'physics.json').read_text())
   if report.get('passed') is not True:raise ValueError('Actual physics checks failed')
  except (ValueError,OSError) as e:raise Failure('QUALITY','PHYSICS_GATE',str(e))
 elif kind=='pwa_gate':
  try:report=pwa_gate(root/'game/dist')
  except (ValueError,OSError,KeyError) as e:raise Failure('QUALITY','PWA_GATE',str(e))
  (stage/'quality.json').write_text(json.dumps(report,indent=2)+'\n')
 elif kind=='build':
  executable=root/'game/node_modules/.bin/esbuild'
  if not executable.exists():raise Failure('ENVIRONMENT','DEPENDENCIES_MISSING','npm ci is required in game/')
  command([executable,root/'game/game.js','--bundle','--minify','--format=esm','--target=es2022','--legal-comments=inline','--outfile='+str(stage/'game.js')],root/'game',stage,90)
  if (stage/'game.js').stat().st_size<1000:raise Failure('QUALITY','EMPTY_BUILD','Unexpectedly small engine bundle')
 elif kind=='published_proof':
  # Import prior browser evidence as prior evidence, never as a new device test.
  reports={k:json.loads(v.read_text()) for k,v in inputs.items()}
  browser=reports['browser'];normal=reports['install']
  if not all(browser[k]['state']['ready'] and not browser[k]['pageErrors'] and browser[k]['skeletalPoseChanges'] for k in ['desktop','mobile']) or normal.get('passed') is not True:raise Failure('QUALITY','PRIOR_PROOF_INVALID','Existing browser proof is incomplete')
  (stage/'prior-proof.json').write_text(json.dumps({'passed':True,'evidence_kind':'IMPORTED_EXISTING_BROWSER_EVIDENCE_NOT_NEW_TEST','physical_android_tested':False,'hardware_webgpu_tested':False,'source_publication':p['source_commit']},indent=2)+'\n')
 elif kind=='fetch_asset':
  expected=p.get('sha256','')
  if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise Failure('CONFIGURATION','HASH_REQUIRED','Public downloads require a known SHA-256')
  source=inputs.get('existing');output=stage/'asset.bin';origin='VERIFIED_EXISTING_COPY'
  if source and hashlib.sha256(source.read_bytes()).hexdigest()==expected:shutil.copyfile(source,output)
  else:
   url=p['url'];parsed=urllib.parse.urlparse(url);allowed=set(p.get('allowed_hosts',['raw.githubusercontent.com']))
   if parsed.scheme!='https' or parsed.hostname not in allowed or parsed.username or parsed.password:raise Failure('CONFIGURATION','PUBLIC_URL_POLICY','Only declared public HTTPS hosts are allowed')
   class RedirectPolicy(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
     u=urllib.parse.urlparse(newurl)
     if u.scheme!='https' or u.hostname not in allowed:raise Failure('INPUT','REDIRECT_NOT_ALLOWED','Redirect left the declared public host set')
     return super().redirect_request(req,fp,code,msg,headers,newurl)
   try:
    opener=urllib.request.build_opener(RedirectPolicy())
    with opener.open(urllib.request.Request(url,headers={'User-Agent':'HenanCampusAssetPipeline/1.0'}),timeout=25) as response:
     size=0
     with output.open('wb') as f:
      while True:
       data=response.read(1024*1024)
       if not data:break
       size+=len(data)
       if size>p.get('max_bytes',32*1024*1024):raise Failure('INPUT','SIZE_LIMIT','Source exceeded configured download limit')
       f.write(data)
    origin='PUBLIC_HTTPS_DOWNLOAD'
   except urllib.error.HTTPError as e:raise Failure('INPUT','ACCESS_DENIED' if e.code in [401,403] else 'HTTP_ERROR',f'HTTP {e.code}; authentication/access controls are not bypassed')
   except (TimeoutError,socket.timeout):raise Failure('ENVIRONMENT','TIMEOUT','Public download timed out')
   except urllib.error.URLError as e:raise Failure('ENVIRONMENT','NETWORK_UNAVAILABLE',str(e.reason))
  actual=hashlib.sha256(output.read_bytes()).hexdigest()
  if actual!=expected:raise Failure('INTEGRITY','HASH_MISMATCH','Downloaded/source bytes do not match the declared hash')
  (stage/'provenance.json').write_text(json.dumps({'origin':origin,'url':p.get('url'),'sha256':actual,'bytes':output.stat().st_size,'license':p.get('license','UNCONFIRMED')},indent=2)+'\n')
 else:raise Failure('CONFIGURATION','UNKNOWN_DRIVER',kind)

REPAIR_GUIDANCE={
 'ENVIRONMENT':'Fix the missing tool/dependency or runner capacity once; verify one canary before rerunning blocked dependants.',
 'INPUT':'Supply/annotate the missing geometry or valid multi-position imagery. Do not invent dimensions or run reconstruction blindly.',
 'INTEGRITY':'Quarantine corrupted bytes; restore only a known hash-matching source or rebuild from unchanged verified inputs.',
 'CONFIGURATION':'Correct the manifest, dependency cycle, path or parameter; do not mutate unrelated assets.',
 'QUALITY':'Keep the last accepted release. Change only the failing preset/driver and pass a small canary before expanding.'}
