"""Local Sites-helper fallback: installed Sites helper scripts are unavailable.
Accept only the Site-issued credential through hidden stdin; never store secrets.
Push exact clean source and package only the tracked static output/manifest.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tarfile,termios
from sync_progress import ProgressSync
ROOT=Path(__file__).resolve().parents[1]
try:
 settings=termios.tcgetattr(sys.stdin);settings[3]&=~termios.ECHO;termios.tcsetattr(sys.stdin,termios.TCSANOW,settings)
except (termios.error,OSError):pass
print('Ready for Sites credential JSON on stdin (input is hidden).',flush=True)
request=json.loads(sys.stdin.readline());credential=request['credential'];token=credential.get('token','');env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
mode=credential.get('auth_mode')
if mode=='http_extra_header':
 count=int(env.get('GIT_CONFIG_COUNT','0'));env['GIT_CONFIG_COUNT']=str(count+1);env[f'GIT_CONFIG_KEY_{count}']='http.'+credential['remote_url']+'.extraHeader';env[f'GIT_CONFIG_VALUE_{count}']='Authorization: Bearer '+token
elif mode!='work_proxy':raise SystemExit('Unsupported returned authentication mode; no alternate identity attempted.')
def run(args,timeout=60):
 r=subprocess.run(args,cwd=ROOT,env=env,text=True,capture_output=True,timeout=timeout)
 if r.returncode:
  message=r.stderr.replace(token,'[redacted]') if token else r.stderr
  raise RuntimeError(message[-1600:])
 return r.stdout.strip()
try:
 sync=ProgressSync(ROOT)
 with sync.lock():
  if run(['git','status','--porcelain']):raise RuntimeError('Source checkout is dirty; checkpoint and verify before publication.')
  hosting=json.loads((ROOT/'.openai/hosting.json').read_text());project=request['project_id']
  if hosting['project_id']!=project:raise RuntimeError('Site identity mismatch')
  head=run(['git','rev-parse','HEAD']);remote=credential['remote_url'];branch=credential['branch']
  existing=run(['git','remote'])
  if 'sites' not in existing.splitlines():run(['git','remote','add','sites',remote])
  elif run(['git','remote','get-url','sites'])!=remote:raise RuntimeError('Existing Sites remote does not match issued credential')
  # Normal fast-forward-only push; no token in arguments, configuration files or logs.
  run(['git','ls-remote','sites','refs/heads/'+branch]);run(['git','push','sites','HEAD:refs/heads/'+branch],timeout=90)
  observed=run(['git','ls-remote','sites','refs/heads/'+branch]).split()[0]
  if observed!=head:raise RuntimeError('Pushed Sites source ref mismatch')
  path=Path(request['archivePath']).resolve();path.parent.mkdir(parents=True,exist_ok=True)
  # Each packaged file must be identical to the just-pushed commit.
  selected=[ROOT/'.openai/hosting.json',*(ROOT/hosting['static']['directory']).rglob('*')]
  for file in selected:
   if file.is_file():
    tracked=subprocess.check_output(['git','show',f'{head}:{file.relative_to(ROOT)}'],cwd=ROOT)
    if tracked!=file.read_bytes():raise RuntimeError('Packaged output is not the pushed source: '+str(file.relative_to(ROOT)))
  with tarfile.open(path,'w:gz') as archive:
   archive.add(ROOT/'.openai/hosting.json',arcname='.openai/hosting.json');archive.add(ROOT/hosting['static']['directory'],arcname=hosting['static']['directory'])
  print(json.dumps({'project_id':project,'commit_sha':head,'archive':str(path),'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_ref_verified':True,'fallback_reason':'Official local Sites helper scripts are absent from this execution image; ordinary Git and explicit static packaging used.'}),flush=True)
except Exception as e:print(json.dumps({'status':'FAIL','error':str(e)}),flush=True);raise SystemExit(1)
