"""One bounded normal browser visit to supplied public panorama; no asset harvest."""
from pathlib import Path
import json,time
import numpy as np
from PIL import Image
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from browser_display import display,ARGS
ROOT=Path(__file__).resolve().parents[1];report={'status':'UNVERIFIED_PANORAMA_SCENE','raw_images_committed':False,'requests_failed':[],'http_failures':[],'script_errors':[]};url='https://www.ivrpano.com/p/2b89e1f8b87d40ad?from=singlemessage&sid=0&_s=a449101eb4c7b224'
with display() as env,sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=False,args=ARGS,env=env)
 try:
  page=b.new_page(viewport={'width':1280,'height':720});page.on('requestfailed',lambda r:report['requests_failed'].append({'host':urlsplit(r.url).netloc,'path':urlsplit(r.url).path,'reason':r.failure}));page.on('response',lambda r:report['http_failures'].append({'host':urlsplit(r.url).netloc,'path':urlsplit(r.url).path,'status':r.status}) if r.status>=400 else None);page.on('pageerror',lambda e:report['script_errors'].append(str(e)))
  response=page.goto(url,wait_until='domcontentloaded',timeout=40000);report['page_status']=response.status;report['title']=page.title()
  try:page.wait_for_function("document.querySelector('#loadermask') && (getComputedStyle(document.querySelector('#loadermask')).display==='none'||getComputedStyle(document.querySelector('#loadermask')).visibility==='hidden'||Number(getComputedStyle(document.querySelector('#loadermask')).opacity)===0)",timeout=35000)
  except Exception:pass
  report['canvas_count']=page.locator('#pano canvas').count();report['visible_text']=page.locator('body').inner_text()[:500]
  page.screenshot(path=str(ROOT/'.cache/original-panorama-private.png'),timeout=20000)
  pixels=np.array(Image.open(ROOT/'.cache/original-panorama-private.png').convert('RGB'));report['visible_rgb_std']=float(pixels.std(axis=(0,1)).mean());report['loader_hidden']=page.locator('#loadermask').is_hidden()
  if report['canvas_count'] and report['loader_hidden'] and report['visible_rgb_std']>10:report['status']='PASS_ORIGINAL_SCENE_VISUAL_ONLY'
  else:report['reason']='HTML/canvas presence does not prove visible panorama; bounded capture still has loading overlay or no varied scene.'
 except Exception as e:report['reason']=str(e)
 finally:b.close()
(ROOT/'reports/reference-viewer.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
