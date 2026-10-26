"""Real headed software browser checks. No Android hardware/FPS acceptance claims."""
from pathlib import Path
from contextlib import contextmanager
import ast,json,os,secrets,signal,subprocess,sys,tempfile,time
import numpy as np
from PIL import Image
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports';WORK=ROOT/'.cache';WORK.mkdir(exist_ok=True)
from browser_display import display,ARGS
renderer=sys.argv[1] if len(sys.argv)>1 else 'webgpu';mobile=len(sys.argv)>2 and sys.argv[2]=='mobile';portrait=len(sys.argv)>3 and sys.argv[3]=='portrait';name=renderer+('-portrait' if portrait else '-mobile' if mobile else '-desktop');width,height=(393,852) if portrait else (844,390) if mobile else (1280,720)
report={'status':'FAIL','renderer_requested':renderer,'viewport':[width,height],'headed':True,'software':True,'android_hardware_tested':False,'checks':[],'page_errors':[],'console_errors':[],'external_requests':[]}
def check(name,ok,details=None):
    report['checks'].append({'name':name,'status':'PASS' if ok else 'FAIL','details':details})
    if not ok:raise RuntimeError(name)
with display() as env,sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=False,args=ARGS,env=env)
    try:
        context=browser.new_context(viewport={'width':width,'height':height},has_touch=mobile,device_scale_factor=1)
        page=context.new_page();
        if renderer=='auto-fallback':page.add_init_script("Object.defineProperty(navigator,'gpu',{get:()=>undefined,configurable:true})")
        page.on('request',lambda r:report['external_requests'].append(r.url) if urlsplit(r.url).scheme in ['http','https'] and urlsplit(r.url).netloc!='127.0.0.1:8080' else None)
        page.on('pageerror',lambda e:report['page_errors'].append(str(e)+' '+(e.stack or '')[:1200]));page.on('console',lambda e:report['console_errors'].append(e.text) if e.type=='error' else None)
        page.goto(f'http://127.0.0.1:8080/?qa=1&renderer={renderer}',wait_until='domcontentloaded',timeout=45000)
        page.wait_for_function('window.__campusGameState?.ready===true',timeout=90000)
        page.wait_for_function('window.__campusGameState.frames>2',timeout=40000)
        check('Actual requested rendering backend',page.evaluate('window.__campusGameState.actualRenderer')==('webgl2' if renderer=='auto-fallback' else renderer))
        page.screenshot(path=str(OUT/(name+'-welcome.png')),timeout=30000)
        page.locator('#start').click();page.wait_for_function('window.__campusGameState.started===true',timeout=15000)
        check('Portrait is playable without mandatory rotation',page.locator('#rotate-gate').is_hidden())
        if mobile:
            page.locator('#open-explorer').click();page.locator('#campus-search').fill('运动');check('Search filters destination cards',page.locator('.place-card').count()==1)
            page.locator('#campus-search').fill('');page.locator('[data-place="stadium"]').click()
        else:page.locator('[data-place="stadium"]').click()
        page.locator('#destination-walk').click();page.wait_for_function('window.__campusTest.guide().status==="walking"',timeout=5000)
        start=page.evaluate('window.__campusTest.state().feet');page.wait_for_timeout(1200);after=page.evaluate('window.__campusTest.state()')
        travelled=((after['feet']['x']-start['x'])**2+(after['feet']['z']-start['z'])**2)**.5
        check('Normal render/update loop walks the real actor',travelled>.5,{'metres':travelled,'animation':after['animation']})
        check('Three-dimensional guidance and SVG route bound',page.locator('.walking-route').count()==2)
        page.screenshot(path=str(OUT/(name+'-walking.png')),timeout=30000)
        pixels=np.array(Image.open(OUT/(name+'-walking.png')).convert('RGB'))[int(height*.25):int(height*.66),int(width*.3):int(width*.68)]
        variation=float(pixels.std(axis=(0,1)).mean());check('Actual visible 3D scene area is nonblank',variation>8,variation)
        if mobile:
            joy=page.locator('#joystick').bounding_box();check('Joystick is in the viewport',joy and joy['x']>=0 and joy['y']+joy['height']<=height)
            cdp=context.new_cdp_session(page);x=joy['x']+joy['width']/2;y=joy['y']+joy['height']/2
            cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y,'id':1}]});cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+25,'y':y,'id':1}]});page.wait_for_timeout(650);cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        else:page.keyboard.down('d');page.wait_for_timeout(500);page.keyboard.up('d')
        check('Manual controls pause autonomous walking',page.evaluate('window.__campusTest.guide().status')=='paused')
        before=page.evaluate('window.__campusTest.state().feet');page.locator('#guide-resume').click();check('Resume retains the intended destination',page.evaluate('window.__campusTest.guide().destination')=='stadium')
        # Accelerate only normal fixed physics steps, without setFeet or teleport.
        walked=page.evaluate('window.__campusTest.walkSteps(15000)');check('Same actual collision controller reaches the destination',walked['guide']['status']=='arrived',walked)
        page.wait_for_timeout(500);check('Arrival is visible and explorable',page.locator('#guide-state').inner_text().startswith('已到达'))
        check('Pause/resume never teleports the actor',walked['guide']['history'][-1]['offset']<1.9)
        if mobile and page.locator('#destination').is_visible():page.locator('#destination-close').click()
        page.evaluate('window.__campusTest.building(13)');check('Building information references the actual library',page.locator('#place-title').inner_text()=='图书馆')
        page.locator('#place-dialog [data-close]').click()
        page.evaluate('window.__campusTest.tour()');check('One-click tour has remaining stops',len(page.evaluate('window.__campusTest.guide().tourRemaining'))==3)
        page.locator('#guide-pause').click();check('Tour can pause for exploration',page.evaluate('window.__campusTest.guide().status')=='paused')
        check('Real panorama stays on the original source',page.locator('#reference-source').get_attribute('href').startswith('https://www.ivrpano.com/p/2b89e1f8b87d40ad'))
        check('No main-page runtime or graphics errors',not report['page_errors'] and not report['console_errors'] and not page.evaluate('window.__campusGameState.errors.length'),{'page':report['page_errors'],'console':report['console_errors']})
        check('Game loading needs no external CDN requests',not report['external_requests'],report['external_requests'])
        check('No horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        report['state']=page.evaluate('window.__campusTest.state()');report['navigation']=page.evaluate('window.__campusTest.guide()');report['quality']=page.evaluate('window.__campusTest.qualityBudget()');report['status']='PASS_BROWSER_EXPERIMENT_ONLY'
        page.screenshot(path=str(OUT/(name+'-arrived.png')),timeout=30000)
    except Exception as e:
        report['error']=str(e)
        try:report['last_state']=page.evaluate('window.__campusGameState');page.screenshot(path=str(WORK/(name+'-failure.png')),timeout=15000)
        except Exception:pass
    finally:browser.close()
(OUT/(name+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':len(report['checks']),'error':report.get('error'),'page_errors':report['page_errors']}),flush=True);sys.exit(0 if report['status'].startswith('PASS') else 1)
