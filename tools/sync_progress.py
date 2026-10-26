"""Verified stage checkpoints and safe bidirectional Git synchronization.
No reset/clean, force-push, automatic stash, or guessed conflict resolution.
"""
import argparse,contextlib,fcntl,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone

class SyncError(Exception):pass

def redact(value):
 value=re.sub(r'https://[^/@\s]+:[^/@\s]+@','https://[redacted]@',value)
 return re.sub(r'(?:gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)','[redacted]',value)

class ProgressSync:
 def __init__(self,root,config=None):
  self.root=Path(root).resolve();self.config=config if config is not None else json.loads((self.root/'configs/sync.json').read_text())
  self.remote=self.config.get('remote','origin');self.main=self.config.get('main_branch','main')
  git_dir=Path(self.git('rev-parse','--git-path','campus-sync'));self.directory=git_dir if git_dir.is_absolute() else self.root/git_dir;self.directory.mkdir(parents=True,exist_ok=True)
  self.state_file=self.directory/'state.json';self.state=json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
 def git_result(self,*args,timeout=25):
  env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0'
  try:return subprocess.run(['git',*map(str,args)],cwd=self.root,env=env,text=True,capture_output=True,timeout=timeout)
  except subprocess.TimeoutExpired:raise SyncError('Git operation timed out; local files retained')
 def git(self,*args):
  r=self.git_result(*args)
  if r.returncode:raise SyncError(redact(r.stderr or r.stdout)[-1500:])
  return r.stdout.strip()
 @property
 def branch(self):return self.git('symbolic-ref','--short','HEAD')
 @property
 def head(self):return self.git('rev-parse','HEAD')
 def save(self,status,**details):
  self.state.update({'status':status,'updated_utc':datetime.now(timezone.utc).isoformat(),**details});tmp=self.state_file.with_suffix('.tmp');tmp.write_text(json.dumps(self.state,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,self.state_file)
  return {'status':status,'branch':self.branch,'head':self.head,**details}
 @contextlib.contextmanager
 def lock(self):
  path=self.directory/'run.lock'
  with path.open('a+') as handle:
   try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise SyncError('SYNC_BUSY: another sync is active; retry later')
   try:
    handle.seek(0);handle.truncate();handle.write(str(os.getpid()));handle.flush()
    self.state=json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
    yield
   finally:fcntl.flock(handle,fcntl.LOCK_UN)
 def changed(self):
  names=self.git('diff','--name-only','HEAD').splitlines()+self.git('ls-files','--others','--exclude-standard').splitlines()
  return sorted(set(names))
 def fingerprint(self):
  names=sorted(set(self.git('ls-files','-c','-o','--exclude-standard','-z').split('\0')));h=hashlib.sha256()
  for name in names:
   p=self.root/name
   if not name or not (p.exists() or p.is_symlink()):continue
   h.update(name.encode()+b'\0')
   h.update(str(p.lstat().st_mode & 0o777).encode()+b'\0')
   if p.is_symlink():h.update(os.readlink(p).encode())
   elif p.is_file():
    with p.open('rb') as f:
     for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
  return h.hexdigest()
 def validate(self,paths=None):
  fingerprint=self.fingerprint()
  if self.state.get('validated_fingerprint')==fingerprint:return {'cached':True,'fingerprint':fingerprint}
  paths=paths if paths is not None else self.changed()
  for name in paths:
   p=self.root/name
   if not p.is_file() or p.is_symlink():continue
   if p.suffix=='.json':json.loads(p.read_text())
   if p.suffix not in ['.png','.jpg','.blend','.fbx','.glb','.wasm'] and p.stat().st_size<8*1024*1024:
    if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',p.read_bytes()):raise SyncError('Credential-like content detected in '+name+'; nothing committed')
  docs_only=bool(paths) and all(n.startswith(('docs/','reports/')) or n in ['README.md','AGENTS.md'] for n in paths)
  commands=[] if docs_only else self.config.get('validation_commands',[])
  for i,command in enumerate(commands):
   if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise SyncError('Validation commands must be argument arrays')
   try:r=subprocess.run(command,cwd=self.root,text=True,capture_output=True,timeout=self.config.get('validation_timeout_seconds',180))
   except (OSError,subprocess.TimeoutExpired) as e:raise SyncError('Validation unavailable: '+str(e))
   (self.directory/f'validation-{i}.log').write_text(redact(r.stdout+'\n'+r.stderr)[-300000:])
   if r.returncode:raise SyncError('Validation failed: '+command[0]+'; see local validation log')
  if self.fingerprint()!=fingerprint:raise SyncError('Inputs changed during validation; no checkpoint committed')
  self.state.update({'validated_fingerprint':fingerprint,'validated_sha':self.head});return {'cached':False,'fingerprint':fingerprint,'commands':len(commands),'docs_only':docs_only}
 def fetch(self):
  r=self.git_result('fetch',self.remote)
  if r.returncode:raise SyncError('FETCH_FAILED: '+redact(r.stderr)[-700:])
 def exists(self,ref):return self.git_result('rev-parse','--verify','--quiet',ref).returncode==0
 def ancestor(self,a,b):return self.git_result('merge-base','--is-ancestor',a,b).returncode==0
 def integrate(self):
  branch=self.branch;ref=f'{self.remote}/{branch}'
  if not self.exists(ref):return {'relation':'NEW_LOCAL_BRANCH','merged':False}
  local=self.head;remote=self.git('rev-parse',ref)
  if local==remote:return {'relation':'UP_TO_DATE','merged':False}
  if self.ancestor(remote,local):return {'relation':'LOCAL_AHEAD','merged':False}
  if self.ancestor(local,remote):
   # Git itself checks for dirty-path overlap before a fast-forward writes files.
   r=self.git_result('merge','--ff-only',ref)
   if r.returncode:raise SyncError('REMOTE_UPDATE_DEFERRED_DIRTY: '+redact(r.stderr)[-700:])
   return {'relation':'FAST_FORWARDED','merged':False}
  if self.changed():raise SyncError('DIVERGED_DIRTY: local files retained; checkpoint before integration')
  preview=self.git_result('merge-tree','--write-tree','HEAD',ref)
  if preview.returncode:raise SyncError('MERGE_CONFLICT: preflight refused; working files were not changed')
  self.git('-c','user.name=Campus AI Development','-c','user.email=campus-build@users.noreply.github.com','merge','--no-edit',ref)
  return {'relation':'MERGED_CLEANLY','merged':True}
 def push(self,destination=None,sha=None):
  destination=destination or self.branch;sha=sha or self.head;last=''
  for attempt in range(1,min(3,self.config.get('max_push_attempts',3))+1):
   try:r=self.git_result('push',self.remote,f'{sha}:refs/heads/{destination}')
   except SyncError as e:last=str(e);r=None
   if r is not None and not r.returncode:return {'attempts':attempt,'destination':destination}
   if r is not None:last=redact(r.stderr)[-700:]
   if re.search('non-fast-forward|fetch first|rejected',last,re.I):break
   if attempt<min(3,self.config.get('max_push_attempts',3)):time.sleep(min(attempt,2)*self.config.get('retry_delay_seconds',1))
  raise SyncError('PUSH_PENDING: '+last)
 def begin(self):
  with self.lock():
   try:
    self.fetch();result=self.integrate()
    if result['merged']:
     proof=self.validate();self.state['validated_sha']=self.head;self.push();return self.save('MERGED_VALIDATED_AND_PUSHED',pending=False,proof=proof)
    return self.save(result['relation'],pending=self.state.get('pending',False),development_continues=True)
   except (SyncError,ValueError) as e:return self.save('SYNC_DEFERRED',reason=redact(str(e)),development_continues=True)
 def checkpoint(self,stage):
  with self.lock():
   committed=None
   try:
    proof=self.validate()
    if self.changed():
     self.git('add','-A');self.git('-c','user.name=Campus AI Development','-c','user.email=campus-build@users.noreply.github.com','commit','-m','阶段同步：'+stage,'-m','Campus-Verified-Stage: '+stage);committed=self.head
    self.state.update({'validated_sha':self.head,'pending':True,'pending_stage':stage,'validated_fingerprint':self.fingerprint()});self.save('LOCAL_CHECKPOINT_SAVED',pending=True)
    self.fetch()
    try:integrated=self.integrate()
    except SyncError as e:
     if 'MERGE_CONFLICT' in str(e):
      slug=re.sub('[^a-z0-9-]','-',stage.lower()).strip('-')[:30] or 'stage'
      backup='codex/saved-'+slug+'-'+self.head[:8]
      uploaded=self.push(backup,self.state['validated_sha']);return self.save('CONFLICT_SAVED_TO_BRANCH',pending=True,conflict_head=self.head,backup_branch=backup,push=uploaded,reason=str(e),development_continues=True)
     raise
    if integrated['merged'] or self.head!=self.state['validated_sha']:
     proof=self.validate();self.state['validated_sha']=self.head
    # A network retry must never publish edits made after the validation receipt.
    if self.fingerprint()!=self.state['validated_fingerprint']:raise SyncError('Workspace changed; pending checkpoint retained for revalidation')
    result=self.push();return self.save('SYNCED',pending=False,conflict_head=None,last_pushed_sha=self.head,proof=proof,push=result,created_commit=committed,development_continues=True)
   except (SyncError,ValueError) as e:return self.save('CHECKPOINT_PENDING' if committed or self.state.get('pending') else 'VALIDATION_FAILED',pending=bool(committed or self.state.get('pending')),reason=redact(str(e)),development_continues=True)
 def retry(self):
  # A timer may publish a previously verified commit, but must not commit edits
  # belonging to an unfinished development phase or resolve a conflict itself.
  with self.lock():
   if not self.state.get('pending'):action='begin'
   elif self.state.get('conflict_head')==self.head:
    return self.save('CONFLICT_REQUIRES_RESOLUTION',pending=True,development_continues=True)
   elif self.changed() or self.fingerprint()!=self.state.get('validated_fingerprint'):
    sha=self.state.get('validated_sha')
    if not sha:return self.save('PENDING_REVALIDATION_REQUIRED',pending=True,development_continues=True)
    try:
     self.fetch();result=self.push(sha=sha)
     return self.save('VERIFIED_COMMIT_PUSHED_WORKSPACE_RETAINED',pending=False,last_pushed_sha=sha,push=result,development_continues=True)
    except SyncError as e:return self.save('CHECKPOINT_PENDING',pending=True,reason=redact(str(e)),development_continues=True)
   else:action='checkpoint'
  return self.checkpoint(self.state.get('pending_stage','retry-verified-progress')) if action=='checkpoint' else self.begin()
 def worktree(self,task):
  slug=re.sub('[^a-z0-9-]','-',task.lower()).strip('-')[:48]
  if not slug:raise SyncError('Task requires a non-empty branch-safe name')
  self.fetch();branch='codex/'+slug;path=self.root.parent/(self.root.name+'-tasks')/slug;path.parent.mkdir(exist_ok=True)
  if path.exists():raise SyncError('Worktree already exists; reuse it without overwriting: '+str(path))
  if self.git_result('show-ref','--verify','--quiet','refs/heads/'+branch).returncode==0:self.git('worktree','add',str(path),branch)
  else:self.git('worktree','add','-b',branch,str(path),f'{self.remote}/{self.main}')
  return {'status':'TASK_WORKTREE_READY','branch':branch,'path':str(path)}

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['begin','checkpoint','retry','status','watch','worktree']);p.add_argument('--stage',default='validated-progress');p.add_argument('--root',default='.');p.add_argument('--task');p.add_argument('--interval',type=int,default=60);p.add_argument('--cycles',type=int,default=0);a=p.parse_args();sync=ProgressSync(a.root)
 try:
  if a.action=='watch':
   pid=sync.directory/'watcher.pid'
   if pid.exists():
    try:os.kill(int(pid.read_text()),0);print(json.dumps({'status':'WATCHER_ALREADY_RUNNING'}));return
    except (ProcessLookupError,ValueError):pass
   pid.write_text(str(os.getpid()))
   try:
    count=0
    while True:
     try:result=sync.retry()
     except SyncError as e:result={'status':'SYNC_DEFERRED','reason':redact(str(e)),'development_continues':True}
     print(json.dumps(result,ensure_ascii=False),flush=True);count+=1
     if a.cycles and count>=a.cycles:break
     time.sleep(max(10,a.interval));sync.state=json.loads(sync.state_file.read_text()) if sync.state_file.exists() else {}
   finally:pid.unlink(missing_ok=True)
   return
  if a.action=='status':result={**sync.state,'branch':sync.branch,'head':sync.head,'changed_files':sync.changed()}
  elif a.action=='worktree':result=sync.worktree(a.task or '')
  else:result=getattr(sync,a.action)(a.stage) if a.action=='checkpoint' else getattr(sync,a.action)()
  print(json.dumps(result,ensure_ascii=False,indent=2))
 except SyncError as e:print(json.dumps({'status':'SYNC_DEFERRED','reason':redact(str(e)),'development_continues':True},ensure_ascii=False))
if __name__=='__main__':main()
