"""Bounded public-source inventory: cached bytes, source hashes and real mesh gates.

No logins, probing of private endpoints, code execution or access-control bypass.
Reference URLs and page evidence are distinct from acquired/licensed 3D models.
"""
import argparse,hashlib,json,re,time,urllib.request,urllib.parse,urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from automation.quality import glb_gate
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.resource-cache';VERSION=1

def fetch(url,refresh=False,limit=4*1024*1024):
 parsed=urllib.parse.urlsplit(url)
 if parsed.scheme!='https' or parsed.username or parsed.password:raise ValueError('Only public HTTPS URLs without embedded credentials')
 key=hashlib.sha256(url.encode()).hexdigest();folder=CACHE/key;meta=folder/'source.json';body=folder/'body.bin'
 if not refresh and meta.is_file() and body.is_file():
  old=json.loads(meta.read_text());data=body.read_bytes()
  if old['sha256']==hashlib.sha256(data).hexdigest() and time.time()-old['retrieved_epoch']<86400:return data,{**old,'cache_hit':True}
 # Normal public redirects remain HTTPS; 401/403 are recorded, never worked around.
 class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   u=urllib.parse.urlsplit(newurl)
   if u.scheme!='https' or u.username or u.password:raise ValueError('Rejected non-public/HTTPS redirect')
   return super().redirect_request(req,fp,code,msg,headers,newurl)
 opener=urllib.request.build_opener(HTTPSRedirect())
 with opener.open(urllib.request.Request(url,headers={'User-Agent':'CampusResourceInventory/1.0'}),timeout=20) as response:
  data=response.read(limit+1)
  if len(data)>limit:raise ValueError('SIZE_LIMIT')
  info={'url':url,'final_url':response.url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'content_type':response.headers.get('content-type',''),'retrieved_epoch':time.time(),'cache_hit':False}
 folder.mkdir(parents=True,exist_ok=True);body.write_bytes(data);meta.write_text(json.dumps(info));return data,info

def inspect(source,refresh=False):
 result={'id':source['id'],'url':source['url'],'platform':source['platform'],'rights':source.get('rights','REFERENCE_ONLY_REUSE_PERMISSION_UNCONFIRMED'),'status':'PENDING','models':[]}
 try:
  raw,proof=fetch(source['url'],refresh);text=raw.decode('utf-8',errors='replace');result['page']=proof
  refs=set()
  for value in re.findall(r'''["']([^"'<>\s]+)["']''',text):
   if re.search(r'\.(?:glb|gltf|fbx|obj|ply|b3dm|i3dm|jpg|jpeg|png|webp|mp4|js)(?:[?#]|$)',value,re.I) or 'tileset.json' in value:
    url=urllib.parse.urljoin(proof['final_url'],value.replace('&amp;','&'));u=urllib.parse.urlsplit(url)
    # Signed avatar/CDN URLs are unrelated to reusable campus inputs. Do not
    # publish expiring access signatures or treat profile icons as school photos.
    if u.scheme=='https' and not u.username and not u.password and not re.search(r'(?:^|&)(?:ssig|sig|signature|token|access_token|kid|expires)=',u.query,re.I):refs.add(url)
  models=sorted(u for u in refs if re.search(r'\.(?:glb|gltf|fbx|obj|ply|b3dm|i3dm)(?:[?#]|$)|tileset.json',u,re.I))
  images=sorted(u for u in refs if re.search(r'\.(?:jpg|jpeg|png|webp)(?:[?#]|$)',u,re.I))
  result['reference_images']=images[:40];result['reference_images_downloaded']=False;result['image_scope']='Unscreened page image references; may contain logos or unrelated imagery. Not verified campus photos.'
  result['script_references']=sorted(u for u in refs if re.search(r'\.js(?:[?#]|$)',u,re.I))[:20]
  for url in models[:5]:
   candidate={'url':url,'status':'REFERENCE_FOUND_NOT_ACQUIRED','rights':result['rights']}
   host=urllib.parse.urlsplit(url).hostname
   if host in source.get('model_download_hosts',[]) and '.glb' in urllib.parse.urlsplit(url).path.lower():
    model,meta=fetch(url,refresh,32*1024*1024);local=CACHE/hashlib.sha256(url.encode()).hexdigest()/'body.bin'
    try:candidate.update({'status':'GEOMETRY_VERIFIED_PERMISSION_SEPARATE','quality':glb_gate(local),'source':meta})
    except Exception as e:candidate.update({'status':'INVALID_OR_UNSUPPORTED_GEOMETRY','reason':str(e)[:200]})
   result['models'].append(candidate)
  result['status']='PUBLIC_PAGE_INDEXED';result['scope']='Declared page and linked file references only; not an exhaustive platform search.'
 except urllib.error.HTTPError as e:result.update({'status':'ACCESS_RESTRICTED' if e.code in [401,403] else 'HTTP_ERROR','http_status':e.code,'retry_planned':False})
 except Exception as e:result.update({'status':'UNAVAILABLE','reason':str(e)[:180],'retry_planned':False})
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',default='configs/resource-sources.json');p.add_argument('--report',default='reports/resource-inventory.json');p.add_argument('--refresh',action='store_true');args=p.parse_args()
 config=json.loads((ROOT/args.manifest).read_text())
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda s:inspect(s,args.refresh),config['sources']))
 report={'version':VERSION,'created_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'sources':results,'verified_mesh_count':sum(m.get('status')=='GEOMETRY_VERIFIED_PERMISSION_SEPARATE' for s in results for m in s['models']),'policy':'Bounded normal public requests. Access denials stop. Cached bytes verified before reuse. No claim of full-web absence.'}
 (ROOT/args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'sources':len(results),'statuses':{s['id']:s['status'] for s in results},'verified_mesh_count':report['verified_mesh_count']},ensure_ascii=False))
if __name__=='__main__':main()
