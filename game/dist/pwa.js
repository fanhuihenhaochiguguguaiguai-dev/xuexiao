const status=document.querySelector('#install-status'),button=document.querySelector('#install-button');
const dialog=document.querySelector('#install-dialog');let pendingPrompt;
// Entering browser fullscreen does not mean the application was installed.
const launchedStandalone=matchMedia('(display-mode:standalone)').matches||navigator.standalone||
 (matchMedia('(display-mode:fullscreen)').matches&&!document.fullscreenElement);
const installed=()=>!!launchedStandalone||!!window.__campusApp?.installConfirmed;
window.__campusApp={installed:!!installed(),serviceWorker:false,orientation:'landscape',installPromptAvailable:false};
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();pendingPrompt=e;window.__campusApp.installPromptAvailable=true;status.textContent='浏览器已允许安装，可添加桌面图标并独立运行。';});
window.addEventListener('appinstalled',()=>{pendingPrompt=null;window.__campusApp.installed=true;window.__campusApp.installConfirmed=true;window.__campusApp.installPromptAvailable=false;button.textContent='已安装';status.textContent='已添加到手机桌面。';});
document.querySelectorAll('[data-install]').forEach(b=>b.addEventListener('click',()=>{status.textContent=installed()?'当前已在独立应用窗口运行。':pendingPrompt?'已准备好安装到手机桌面。':'若浏览器未弹出安装按钮，请用安卓 Chrome 打开本页，再选择浏览器菜单中的“安装应用”或“添加到主屏幕”。';dialog.showModal();}));
button.addEventListener('click',async()=>{if(!pendingPrompt){status.textContent=installed()?'当前已在独立窗口运行。':'请使用浏览器菜单中的“安装应用”或“添加到主屏幕”。内置聊天浏览器可能不提供安装。';return;}const prompt=pendingPrompt;pendingPrompt=null;await prompt.prompt();const choice=await prompt.userChoice;window.__campusApp.installChoice=choice.outcome;status.textContent=choice.outcome==='accepted'?'安装请求已提交，完成后可从桌面打开。':'你仍可在浏览器中横屏游玩。';});
export async function enterLandscape(){
 try{if(!document.fullscreenElement&&document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen({navigationUI:'hide'});}catch{}
 try{if(screen.orientation?.lock){await screen.orientation.lock('landscape');window.__campusApp.orientationLock='granted';}else window.__campusApp.orientationLock='unsupported';}catch{window.__campusApp.orientationLock='browser_not_granted';}
}
document.querySelector('#rotate-fullscreen').addEventListener('click',enterLandscape);
if('serviceWorker' in navigator){
 navigator.serviceWorker.register('/sw.js',{scope:'/'}).then(async reg=>{await navigator.serviceWorker.ready;window.__campusApp.serviceWorker=true;window.__campusApp.scope=reg.scope;}).catch(e=>{window.__campusApp.serviceWorkerError=String(e);});
}
