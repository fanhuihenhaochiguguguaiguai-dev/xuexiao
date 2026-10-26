"""Photo acquisition template: 1 -> 3 -> 8, verified byte cache, no raw redistribution."""
import argparse,json,hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from resource_inventory import fetch,CACHE,ROOT

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--campaign',choices=['pilot','small','all'],default='all');args=parser.parse_args()
 config=json.loads((ROOT/'configs/photo-reference-inputs.json').read_text());count={'pilot':1,'small':3,'all':len(config['images'])}[args.campaign]
 observations=json.loads((ROOT/'reports/reference-observations.json').read_text()) if (ROOT/'reports/reference-observations.json').is_file() else {'observations':[]}
 known={o['sha256']:o for o in observations['observations']}
 def acquire(url):
  try:
   data,info=fetch(url,limit=8*1024*1024);local=CACHE/hashlib.sha256(url.encode()).hexdigest()/'reference.jpg';local.write_bytes(data)
   with Image.open(local) as im:im.verify()
   with Image.open(local) as im:size=list(im.size)
   if min(size)<300:raise ValueError('INSUFFICIENT_RESOLUTION')
   return {'source_url':url,'source_page':config['source_page'],'sha256':info['sha256'],'bytes':len(data),'dimensions':size,'decoded':True,'local_path':str(local.relative_to(ROOT)),'capture_date':config['capture_date'],'upload_path_hint':config['upload_path_hint'],'rights':config['rights'],'semantic_review':'VISUALLY_INSPECTED_SEE_OBSERVATIONS' if info['sha256'] in known else 'PENDING_VISUAL_CHECK','cache_hit':info['cache_hit']}
  except Exception as e:return {'source_url':url,'decoded':False,'reason':str(e)[:160],'retry_planned':False}
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(acquire,config['images'][:count]))
 report={'campaign':args.campaign,'photos':results,'passed':all(r['decoded'] for r in results),'not_photogrammetry_qualified':True}
 (ROOT/'reports'/('photo-candidates.json' if args.campaign=='all' else 'photo-'+args.campaign+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'campaign':args.campaign,'images':count,'passed':report['passed'],'cached':sum(r.get('cache_hit',False) for r in results)}))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
