"""Full four-stop tour, repeated-route cleanup, real geometry picking and source link."""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from browser_display import display,ARGS
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports'
report={'status':'FAIL','scope':'Headed desktop software WebGPU; normal collision-steering steps can be accelerated by QA. No teleport calls and no Android hardware claims.','checks':[],'page_errors':[],'console_errors':[],'reference':{'status':'UNVERIFIED'}}
def check(name,ok,detail=None):
 report['checks'].append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
 if not ok:raise RuntimeError(name)
with display() as env,sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=False,args=ARGS,env=env)
 try:
  page=browser.new_page(viewport={'width':1280,'height':720});page.on('pageerror',lambda e:report['page_errors'].append(str(e)));page.on('console',lambda e:report['console_errors'].append(e.text) if e.type=='error' else None)
  page.goto('http://127.0.0.1:8080/?qa=1',wait_until='domcontentloaded',timeout=45000);page.wait_for_function('window.__campusGameState?.ready',timeout=90000)
  page.locator('#start').click();page.locator('#start-tour').click();report['stops']=[]
  for stop in range(4):
   result=page.evaluate('window.__campusTest.walkSteps(18000)');s=result['guide'];check('Tour stop '+str(stop+1)+' physically reached',s['status']=='arrived',{'destination':s['destination'],'history':s['history'][-1],'feet':result['feet']});report['stops'].append(s['history'][-1]);page.wait_for_timeout(100)
   if stop<3:page.locator('#guide-next').click()
  state=page.evaluate('window.__campusTest.state()');check('All four exploration visits recorded',len(page.evaluate('window.__campusTest.guide().visited'))==4 and page.locator('#visit-count').inner_text()=='4')
  check('No player reset/teleport during full tour',state['respawns']==1 and state['distanceTravelled']>1100,{'respawns':state['respawns'],'metres':state['distanceTravelled']})
  if page.locator('#destination').is_visible():page.locator('#destination-close').click()
  page.locator('#guide-cancel').click();check('Cancel releases route visual entities',page.evaluate('window.__campusTest.navigationVisuals()')=={'ribbons':0,'markers':0})
  page.evaluate('''()=>{for(let i=0;i<12;i++){window.__campusTest.navigate(i%2?'gate':'stadium');const v=window.__campusTest.navigationVisuals();if(v.ribbons!==1||v.markers!==1)throw Error('Visuals accumulated');window.__campusTest.cancelGuide();}}''')
  check('Repeated navigation keeps only current route resources',page.evaluate('window.__campusTest.navigationVisuals()')=={'ribbons':0,'markers':0})
  page.evaluate('window.__campusTest.inspectView([65,12,90],[-25,10,0])');frame=page.evaluate('window.__campusGameState.frames');page.wait_for_function('(f)=>window.__campusGameState.frames>f+2',arg=frame,timeout=25000)
  point=page.evaluate('window.__campusTest.projectBuilding(13)');check('Actual library projects into visible canvas',310<point['x']<960 and 95<point['y']<540,point)
  page.mouse.click(point['x'],point['y']);page.locator('#place-dialog').wait_for(state='visible',timeout=10000);check('Clicking real building collision opens the right information',page.locator('#place-title').inner_text()=='图书馆')
  page.screenshot(path=str(OUT/'webgpu-library-interaction.png'),timeout=25000)
  page.locator('#building-walk').click();result=page.evaluate('window.__campusTest.walkSteps(10000)');check('Library interaction connects to physical walk-up navigation',result['guide']['status']=='arrived' and result['guide']['destination']=='building/13',result['guide']['history'][-1])
  page.evaluate('window.__campusTest.cancelGuide();window.__campusTest.inspectView(null,null)');frame=page.evaluate('window.__campusGameState.frames');page.wait_for_function('(f)=>window.__campusGameState.frames>f+2',arg=frame,timeout=25000)
  page.screenshot(path=str(OUT/'webgpu-exploration-complete.png'),timeout=25000)
  pixels=np.array(Image.open(OUT/'webgpu-exploration-complete.png').convert('RGB'))[170:480,350:950];variation=float(pixels.std(axis=(0,1)).mean());check('Current WebGPU build renders visible real model scene',variation>8,variation)
  check('Current game runtime has no graphics or script errors',not report['page_errors'] and not report['console_errors'] and not page.evaluate('window.__campusGameState.errors.length'),{'page':report['page_errors'],'console':report['console_errors']})
  report['runtime']=page.evaluate('window.__campusTest.state()');report['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['game.js','lab-experience.js','navigation.js','quality-budget.js','dist/game.js','dist/index.html','dist/style.css','dist/assets/navigation.json']}
  # Third-party reference is evaluated separately; raw imagery is never committed.
  try:
   page.locator('#open-reference').click();page.locator('#panorama-dialog').wait_for(state='visible',timeout=5000);frame=page.frame_locator('#panorama-frame');frame.locator('#pano').wait_for(state='attached',timeout=35000)
   report['reference']={'status':'PASS_ORIGINAL_PAGE_EMBED','src':page.locator('#panorama-frame').get_attribute('src'),'title':frame.locator('title').inner_text(timeout=5000),'native_canvas_count':frame.locator('canvas').count(),'image_files_republished':False}
   try:page.screenshot(path=str(ROOT/'.cache/reference-view-private.png'),timeout=15000)
   except Exception:pass
  except Exception as e:report['reference']={'status':'UNVERIFIED_ORIGINAL_VIEWER','reason':str(e),'fallback_link':page.locator('#panorama-link').get_attribute('href')}
  report['status']='PASS_EXPERIMENT_TOUR_AND_INTERACTION_ONLY'
 except Exception as e:
  report['error']=str(e)
  try:report['last_state']=page.evaluate('window.__campusTest?.state()');report['last_guide']=page.evaluate('window.__campusTest?.guide()');page.screenshot(path=str(ROOT/'.cache/interaction-failure.png'),timeout=15000)
  except Exception:pass
 finally:browser.close()
(OUT/'interaction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':len(report['checks']),'error':report.get('error'),'reference':report['reference']['status']}),flush=True);sys.exit(0 if report['status'].startswith('PASS') else 1)
