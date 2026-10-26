const {chromium}=require('playwright');const fs=require('fs');
const out=require('node:path').resolve('reports');let browser;
(async()=>{
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
 const result={};
 for(const [name,opts]of [['desktop',{viewport:{width:960,height:640}}],['mobile',{viewport:{width:915,height:412},deviceScaleFactor:1,isMobile:true,hasTouch:true}]]){
  const c=await browser.newContext(opts);const p=await c.newPage();p.setDefaultTimeout(60000);const errors=[],consoleMessages=[];console.log('START',name);
  p.on('pageerror',e=>errors.push(String(e)));p.on('console',m=>{if(['error','warning'].includes(m.type()))consoleMessages.push(m.text().slice(0,500));});
  await p.goto('http://127.0.0.1:8141/?qa=1&quality=low',{waitUntil:'domcontentloaded'});
  await p.waitForFunction(()=>window.__campusGameState?.ready||window.__campusGameState?.errors.length,null,{timeout:90000});
  if(!(await p.evaluate(()=>window.__campusGameState.ready))){console.log(JSON.stringify({state:await p.evaluate(()=>window.__campusGameState),errors,consoleMessages},null,2));throw Error('Game initialization failed');}
  await p.locator('#start').evaluate(b=>b.click());await p.waitForTimeout(1300);console.log('PLAYING',name);
  await p.screenshot({path:'/workspace/henan_campus/project/preview/game_'+name+'.png'});
  const before=await p.evaluate(()=>window.__campusTest.state());
  const poseBefore=await p.evaluate(()=>window.__campusTest.pose());
  await p.keyboard.down('KeyW');await p.waitForTimeout(1000);
  const movingAnimation=await p.evaluate(()=>window.__campusTest.state().animation),poseMoving=await p.evaluate(()=>window.__campusTest.pose());
  await p.keyboard.up('KeyW');
  const after=await p.evaluate(()=>window.__campusTest.state());
  await p.getByRole('button',{name:'打开校园地图'}).click();const mapWorks=await p.locator('#map-dialog').isVisible();
  await p.getByRole('button',{name:/体育场东侧道路/}).click();await p.waitForTimeout(400);
  const poiState=await p.evaluate(()=>window.__campusTest.state());
  await p.getByRole('button',{name:'返回出生点'}).click();await p.waitForTimeout(350);
  const resetState=await p.evaluate(()=>window.__campusTest.state());
  const camBefore=await p.evaluate(()=>window.__campusTest.camera());
  if(name==='mobile'){
   const session=await c.newCDPSession(p);const box=await p.locator('#joystick').boundingBox();const x=box.x+box.width/2,y=box.y+box.height/2;
   await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y,id:1}]});
   await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y-35,id:1}]});
   const touchInput=await p.evaluate(()=>({...window.__campusTest.input}));
   await p.waitForTimeout(500);
   await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y:y-35,id:1},{x:670,y:180,id:2}]});
   await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y-35,id:1},{x:730,y:200,id:2}]});
   await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   result.mobile_touch={joystick_forward_value:touchInput.y,afterRelease:await p.evaluate(()=>({...window.__campusTest.input})),cameraBefore:camBefore,cameraAfter:await p.evaluate(()=>window.__campusTest.camera())};
   await session.detach();
  }else{
   await p.mouse.move(800,400);await p.mouse.down();await p.mouse.move(960,445,{steps:10});await p.mouse.up();
  }
  result[name]={state:await p.evaluate(()=>window.__campusTest.state()),keyboardDisplacement:Math.hypot(after.feet.x-before.feet.x,after.feet.z-before.feet.z),movingAnimation,poseBefore,poseMoving,skeletalPoseChanges:JSON.stringify(poseBefore)!==JSON.stringify(poseMoving),mapWorks,poiState:poiState.feet,resetState:resetState.feet,cameraBefore:camBefore,cameraAfter:await p.evaluate(()=>window.__campusTest.camera()),pageErrors:errors,consoleMessages,
   verificationLimit:'Chromium software renderer; phone viewport/touch emulation is not a physical Android or hardware WebGPU performance test.'};
  if(name==='mobile'){
   await p.getByRole('button',{name:'安装到手机',exact:true}).first().click();result.pwa={installDialogOpens:await p.locator('#install-dialog').isVisible()};await p.getByRole('button',{name:'关闭安装说明'}).click();
   await p.waitForFunction(()=>window.__campusApp?.serviceWorker,null,{timeout:30000});
   const session=await c.newCDPSession(p);result.pwa.installability=await session.send('Page.getInstallabilityErrors');result.pwa.manifest=await p.evaluate(async()=>{const r=await fetch('/manifest.webmanifest');return r.json();});
   result.pwa.cachedPaths=await p.evaluate(async()=>{const names=await caches.keys();const cache=await caches.open(names.find(n=>n.startsWith('henan-campus-')));return (await cache.keys()).map(r=>new URL(r.url).pathname);});
   await p.setViewportSize({width:412,height:915});result.pwa.portraitGateVisible=await p.locator('#rotate-gate').isVisible();await p.screenshot({path:'/workspace/henan_campus/project/preview/game_portrait_gate.png'});await p.setViewportSize({width:915,height:412});
   await c.setOffline(true);await p.reload({waitUntil:'domcontentloaded'});await p.waitForFunction(()=>window.__campusGameState?.ready||window.__campusGameState?.errors.length,null,{timeout:90000});result.pwa.offlineLoadsGame=await p.evaluate(()=>window.__campusGameState.ready);await c.setOffline(false);await session.detach();
  }
  await c.close();
 }
 fs.writeFileSync(out+'/playable-regression.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));await browser.close();
})().catch(async e=>{console.error(e);await browser?.close();process.exitCode=1;});
