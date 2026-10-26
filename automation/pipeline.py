"""Manifest DAG + content-addressed cache + staged gates, using Python stdlib.

No shell evaluation, arbitrary downloaded scripts, automatic installs or silent
weakening of validators. Failed candidates cannot replace the active release.
"""
import argparse,json,os,sys,time,tempfile,shutil,hashlib,contextlib
from pathlib import Path
from datetime import datetime,timezone
from .quality import sha256
from . import drivers

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(canonical(value)+b'\n');os.replace(tmp,path)
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def expand_tasks(config):
 """Expand typed parameters without eval or shell/string command templates."""
 result=list(config.get('tasks',[]))
 def replace(value,params):
  if isinstance(value,dict):return {k:replace(v,params) for k,v in value.items()}
  if isinstance(value,list):return [replace(v,params) for v in value]
  if not isinstance(value,str):return value
  if value.startswith('${') and value.endswith('}') and value.count('${')==1:
   key=value[2:-1]
   if key not in params:raise drivers.Failure('CONFIGURATION','UNBOUND_PARAMETER',key)
   return params[key]
  for key,param in params.items():value=value.replace('${'+key+'}',str(param))
  if '${' in value:raise drivers.Failure('CONFIGURATION','UNBOUND_PARAMETER',value)
  return value
 for batch in config.get('batches',[]):
  template=config.get('task_templates',{}).get(batch['template'])
  if template is None:raise drivers.Failure('CONFIGURATION','UNKNOWN_TEMPLATE',batch['template'])
  for item in batch['items']:
   result.extend(replace(template,item))
 return result

class Pipeline:
 def __init__(self,manifest,root=None,registry=None,cache=None):
  self.manifest=Path(manifest).resolve();self.root=Path(root or self.manifest.parent.parent).resolve()
  self.config=json.loads(self.manifest.read_text());self.jobs={};self.tools={};self.registry=registry or drivers
  self.cache=Path(cache or self.root/self.config.get('cache_dir','.campus-cache')).resolve()
  if self.config.get('schema_version')!=1:raise drivers.Failure('CONFIGURATION','SCHEMA','Unsupported manifest schema')
  for j in expand_tasks(self.config):
   if j['id'] in self.jobs:raise drivers.Failure('CONFIGURATION','DUPLICATE_TASK',j['id'])
   if not j['id'].replace('.','').replace('_','').replace('-','').isalnum():raise drivers.Failure('CONFIGURATION','UNSAFE_TASK_ID',j['id'])
   self.jobs[j['id']]=j
  self.order=self.sort(set(self.jobs))
  self.driver_hash=digest({p.name:sha256(p) for p in (Path(__file__).parent).glob('*.py')})
  self.results={}

 def sort(self,selected):
  output=[];seen=set();active=set()
  def visit(name):
   if name not in self.jobs:raise drivers.Failure('CONFIGURATION','MISSING_DEPENDENCY',name)
   if name in active:raise drivers.Failure('CONFIGURATION','CYCLE','Dependency cycle at '+name)
   if name in seen:return
   active.add(name)
   for d in self.jobs[name].get('needs',[]):visit(d)
   active.remove(name);seen.add(name);output.append(name)
  for name in self.jobs:
   if name in selected:visit(name)
  return output

 def input_paths(self,job):
  result={};fp={}
  for role,spec in job.get('inputs',{}).items():
   spec={'path':spec} if isinstance(spec,str) else spec
   p=(self.root/spec['path']).resolve()
   if not p.is_relative_to(self.root):raise drivers.Failure('CONFIGURATION','INPUT_OUTSIDE_ROOT',role)
   if not p.is_file():
    if spec.get('optional'):result[role]=None;fp[role]=None;continue
    raise drivers.Failure('INPUT','MISSING_FILE',str(p.relative_to(self.root)))
   result[role]=p;fp[role]={'sha256':sha256(p),'bytes':p.stat().st_size}
  return result,fp

 def cached(self,key):
  directory=self.cache/'objects'/key;manifest=directory/'artifact.json'
  if not manifest.is_file():return None
  try:
   data=json.loads(manifest.read_text())
   if data['key']!=key or data.get('gate')!='PASSED' or not data['outputs']:return None
   for f in data['outputs']:
    p=(directory/f['path']).resolve()
    if not p.is_relative_to(directory.resolve()) or not p.is_file() or p.stat().st_size!=f['bytes'] or sha256(p)!=f['sha256']:return None
   return data
  except (OSError,ValueError,KeyError):return None

 def execute(self,job):
  paths,inputs=self.input_paths(job);tool=self.registry.fingerprint(job,self.root,self.tools)
  dependency_cache_keys={d:self.results[d]['key'] for d in job.get('needs',[])}
  # Depend on semantic output hashes, not a parent's unrelated input changes.
  # Adding photos that leave a REUSE decision unchanged need not re-export a model.
  depkeys={d:digest(self.cached(k)['outputs']) for d,k in dependency_cache_keys.items()}
  key=digest({'schema':1,'driver':job['driver'],'driver_hash':self.driver_hash,'inputs':inputs,'params':job.get('params',{}),'tool':tool,'dependencies':depkeys})
  hit=self.cached(key)
  if hit:return {'status':'CACHED','key':key,'artifact':str(self.cache/'objects'/key),'attempts':0,'validation':'INPUT_PARAMETERS_TOOLS_AND_OUTPUT_HASHES_MATCH'}
  target=self.cache/'objects'/key
  repaired_cache=False
  if target.exists():
   dest=self.cache/'quarantine'/('cache-'+key+'-'+str(time.time_ns()));dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(target),str(dest));repaired_cache=True
  policy=self.config.get('policy',{});max_attempts=min(2,max(1,int(job.get('max_attempts',policy.get('max_attempts',1)))))
  for attempt in range(1,max_attempts+1):
   stage=Path(tempfile.mkdtemp(prefix=job['id']+'-',dir=self.cache/'staging'))
   try:
    self.registry.run(job,self.root,stage,paths,{d:self.results[d] for d in depkeys},self.tools)
    after_paths,after=self.input_paths(job)
    if after!=inputs:raise drivers.Failure('INTEGRITY','INPUT_MUTATED','A source input changed during execution')
    files=[]
    for p in sorted(stage.rglob('*')):
     if p.is_symlink():raise drivers.Failure('QUALITY','SYMLINK_OUTPUT','Outputs may not escape staging')
     if p.is_file() and p.suffix!='.log':files.append({'path':str(p.relative_to(stage)),'bytes':p.stat().st_size,'sha256':sha256(p)})
    expected=job.get('outputs',[])
    if not files or any(n not in {f['path'] for f in files} for n in expected):raise drivers.Failure('QUALITY','MISSING_OUTPUT','Expected artifact not produced')
    artifact={'key':key,'task':job['id'],'inputs':inputs,'params':job.get('params',{}),'tool':tool,'dependencies':depkeys,'dependency_cache_keys':dependency_cache_keys,'outputs':files,'gate':'PASSED'}
    atomic(stage/'artifact.json',artifact);target.parent.mkdir(parents=True,exist_ok=True);os.replace(stage,target)
    return {'status':'SUCCESS','key':key,'artifact':str(target),'attempts':attempt,'repaired_corrupt_cache':repaired_cache}
   except Exception as exc:
    failure=exc if isinstance(exc,drivers.Failure) else drivers.Failure('QUALITY','UNEXPECTED_FAILURE',str(exc))
    atomic(stage/'failure.json',{'category':failure.category,'code':failure.code,'message':str(failure),'attempt':attempt})
    dest=self.cache/'quarantine'/(job['id']+'-'+str(time.time_ns()));dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(stage),str(dest))
    retry=failure.category=='ENVIRONMENT' and failure.code in policy.get('retryable_codes',['TIMEOUT','IO_BUSY']) and attempt<max_attempts
    if not retry:return {'status':'FAILED','key':key,'category':failure.category,'code':failure.code,'message':str(failure),'attempts':attempt,'quarantine':str(dest)}

 @contextlib.contextmanager
 def lock(self):
  self.cache.mkdir(parents=True,exist_ok=True);lock=self.cache/'run.lock'
  try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  except FileExistsError:raise drivers.Failure('CONFIGURATION','RUN_LOCKED','Another run/unclean lock exists; inspect its PID rather than overwriting it.')
  os.write(fd,str(os.getpid()).encode());os.close(fd)
  try:yield
  finally:lock.unlink(missing_ok=True)

 def run(self,targets=None,promote=True):
  selected=self.sort(set(targets or self.jobs));self.results={};halted={};start=time.time()
  with self.lock():
   (self.cache/'staging').mkdir(exist_ok=True)
   for name in selected:
    j=self.jobs[name];deps=j.get('needs',[]);group=j.get('group')
    bad=[d for d in deps if self.results[d]['status'] not in ['SUCCESS','CACHED']]
    if bad:self.results[name]={'status':'BLOCKED','category':self.results[bad[0]].get('category','INPUT'),'code':'DEPENDENCY_FAILED','dependencies':bad,'root_tasks':sorted({r for d in bad for r in self.results[d].get('root_tasks',[d])})}
    elif group and group in halted:self.results[name]={'status':'BLOCKED','category':self.results[halted[group]].get('category','QUALITY'),'code':'BATCH_QUALITY_GATE','root_tasks':[halted[group]]}
    else:
     try:self.results[name]=self.execute(j)
     except drivers.Failure as e:self.results[name]={'status':'FAILED','category':e.category,'code':e.code,'message':str(e),'attempts':0}
     if self.results[name]['status']=='FAILED' and self.results[name].get('category') in ['QUALITY','INTEGRITY'] and group and self.config.get('policy',{}).get('halt_group_on_failure',True):halted[group]=name
    print(name,self.results[name]['status'],flush=True)
   passed=all(v['status'] in ['SUCCESS','CACHED'] for v in self.results.values())
   counts={s:sum(v['status']==s for v in self.results.values()) for s in ['SUCCESS','CACHED','FAILED','BLOCKED']}
   groups={}
   for name,result in self.results.items():
    if result['status'] in ['FAILED','BLOCKED']:
     cat=result.get('category','QUALITY');g=groups.setdefault(cat,{'tasks':[],'root_tasks':[],'repair_guidance':drivers.REPAIR_GUIDANCE.get(cat,'Inspect this failure locally.')});g['tasks'].append(name);g['root_tasks']=sorted(set(g['root_tasks']+result.get('root_tasks',[name])))
   report={'schema_version':1,'run_id':datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+str(time.time_ns())[-8:],
      'created_utc':datetime.now(timezone.utc).isoformat(),'passed':passed,'counts':counts,'duration_seconds':round(time.time()-start,3),'tasks':self.results,'failure_groups':groups,'promoted':False}
   required=set(self.config.get('release_targets',selected))
   complete=required.issubset(self.results)
   if passed and promote and complete:
    # Pointer promotion is the only publication mutation. Failed candidates never
    # replace an accepted pointer; previous successful runs remain rollbackable.
    atomic(self.cache/'active.json',{'run_id':report['run_id'],'tasks':{k:v['key'] for k,v in self.results.items()}});report['promoted']=True
   if passed and promote and not complete:report['promotion_blocked_reason']='PARTIAL_CAMPAIGN_NOT_A_COMPLETE_RELEASE'
   atomic(self.cache/'runs'/(report['run_id']+'.json'),report)
  return report

 def rollback(self,run_id):
  with self.lock():
   if Path(run_id).name!=run_id:raise drivers.Failure('CONFIGURATION','INVALID_RUN_ID',run_id)
   report=json.loads((self.cache/'runs'/(run_id+'.json')).read_text())
   required=set(self.config.get('release_targets',self.jobs))
   if not required.issubset(report['tasks']):raise drivers.Failure('CONFIGURATION','ROLLBACK_PARTIAL','A partial pilot cannot replace a complete release, including through rollback')
   if not report['passed'] or any(not self.cached(v['key']) for v in report['tasks'].values()):raise drivers.Failure('INTEGRITY','ROLLBACK_INVALID','Prior artifacts are missing or no longer match their hashes')
   atomic(self.cache/'active.json',{'run_id':run_id,'tasks':{k:v['key'] for k,v in report['tasks'].items()}})

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',default='configs/pipeline.json');p.add_argument('--campaign');p.add_argument('--targets',nargs='+');p.add_argument('--report');p.add_argument('--no-promote',action='store_true');p.add_argument('--rollback');args=p.parse_args()
 try:
  runner=Pipeline(args.manifest)
  if args.rollback:runner.rollback(args.rollback);return
  targets=args.targets
  if args.campaign:
   if args.campaign not in runner.config.get('campaigns',{}):raise drivers.Failure('CONFIGURATION','UNKNOWN_CAMPAIGN',args.campaign)
   targets=runner.config['campaigns'][args.campaign]
  report=runner.run(targets,promote=not args.no_promote)
  if args.report:atomic(Path(args.report),report)
  print(json.dumps({'passed':report['passed'],'counts':report['counts'],'run_id':report['run_id'],'promoted':report['promoted']},ensure_ascii=False))
  if not report['passed']:raise SystemExit(1)
 except drivers.Failure as e:
  print(json.dumps({'passed':False,'category':e.category,'code':e.code,'message':str(e)},ensure_ascii=False));raise SystemExit(2)
if __name__=='__main__':main()
