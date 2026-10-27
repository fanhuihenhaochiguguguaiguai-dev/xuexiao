const {chromium}=require('playwright');const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:915,height:412},deviceScaleFactor:1,isMobile:true,hasTouch:true,acceptDownloads:true});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.setDefaultTimeout(90000);
  await page.goto('http://127.0.0.1:8141/?qa=1&quality=low&renderer=webgl2',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__campusGameState?.ready||window.__campusGameState?.errors.length);
  const initial=await page.evaluate(()=>window.__campusGameState);if(!initial.ready)throw Error(JSON.stringify(initial));
  console.log('GAME_READY',JSON.stringify({renderer:initial.actualRenderer,water:initial.water}));
  await page.locator('#start').evaluate(b=>b.click());
  // Exercise restoration after the adaptive resolution floor was reached while
  // the user's selected preset still says balanced.
  await page.evaluate(()=>{const s=document.querySelector('#quality-preset');s.value='balanced';s.dispatchEvent(new Event('change'));});
  await page.waitForFunction(()=>window.__campusTest.settings().renderScale===1.25,null,{timeout:25000});
  const settingsBefore=await page.evaluate(()=>window.__campusTest.settings());
  await page.locator('[aria-label="设备性能检测"]').click();
  const positionBefore=await page.evaluate(()=>window.__campusGameState.position);
  await page.locator('#benchmark-start').click();
  await page.waitForFunction(()=>window.__campusDiagnostics.running);
  console.log('BENCHMARK_STARTED');
  await page.waitForTimeout(27500);await page.screenshot({path:path.resolve('docs/images/water-benchmark.png')});
  await page.waitForFunction(()=>!window.__campusDiagnostics.running,null,{timeout:40000});
  const report=await page.evaluate(()=>window.__campusDiagnostics.report);
  if(report.status!=='completed')throw Error('Benchmark failed: '+report.reason);
  if(report.assessment.webgpuPerformancePass)throw Error('Software WebGL2 incorrectly passed WebGPU');
  await page.screenshot({path:path.resolve('docs/images/device-report-mobile.png')});
  const downloadPromise=page.waitForEvent('download');await page.locator('#benchmark-export').click();const download=await downloadPromise;
  const downloaded=JSON.parse(fs.readFileSync(await download.path(),'utf8'));if(downloaded.buildId!==report.buildId)throw Error('Export report mismatch');
  await page.locator('[aria-label="关闭设备检测"]').click();
  const positionAfter=await page.evaluate(()=>window.__campusGameState.position);
  const unchanged=Math.hypot(positionBefore.x-positionAfter.x,positionBefore.z-positionAfter.z)<.01;
  if(!unchanged)throw Error('Benchmark moved the player');
  const settingsAfter=await page.evaluate(()=>window.__campusTest.settings());if(settingsAfter.textures.limit!==settingsBefore.textures.limit)throw Error('Benchmark failed to restore the adaptive texture budget');
  await page.evaluate(()=>window.__campusDiagnostics.start());await page.waitForFunction(()=>window.__campusDiagnostics.running);
  await page.locator('#benchmark-cancel').click();
  const cancelled=await page.evaluate(()=>window.__campusDiagnostics.report);
  if(cancelled.status!=='cancelled'||cancelled.assessment.webgpuPerformancePass)throw Error('Cancel incorrectly passed');
  await page.evaluate(()=>window.__campusDiagnostics.start());await page.waitForFunction(()=>window.__campusDiagnostics.running);
  await page.setViewportSize({width:900,height:412});
  await page.waitForFunction(()=>!window.__campusDiagnostics.running);
  const interrupted=await page.evaluate(()=>window.__campusDiagnostics.report);
  if(interrupted.status!=='interrupted')throw Error('Resize did not invalidate sampling');
  await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.__campusGameState?.ready||window.__campusGameState?.errors.length);
  const persisted=await page.evaluate(()=>window.__campusDiagnostics.report.status);
  if(persisted!=='interrupted')throw Error('Local report did not persist');
  if(errors.length)throw Error('Browser errors: '+errors.join('; '));
  const hash=file=>require('crypto').createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  fs.writeFileSync('reports/browser-device-check.json',JSON.stringify({passed:true,deviceContext:'Chromium software rendering with mobile viewport; NOT physical Android or hardware WebGPU',sourceHashes:Object.fromEntries(['game/game.js','game/diagnostics.js','game/performance-core.js','game/water.js','game/dist/game.js'].map(f=>[f,hash(f)])),report,exportPassed:true,playerPositionRestored:unchanged,adaptiveTextureBudgetRestored:true,settingsBefore,settingsAfter,cancelledReportStatus:cancelled.status,resizedReportStatus:interrupted.status,localReportPersisted:true,errors},null,2)+'\n');
  console.log('BROWSER_CHECK_PASSED',JSON.stringify(report.stages.map(s=>({id:s.id,...s.metrics}))));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
