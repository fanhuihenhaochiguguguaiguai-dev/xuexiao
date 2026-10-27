// One source for the default, settings menu and automatic resolution floor.
// Costs are configured work budgets, never estimates of a device's actual FPS.
export const QUALITY_PROFILES=Object.freeze({
 low:Object.freeze({label:'省电',scale:.85,minScale:.75,shadowSize:1024,cascades:1,pcf:3,targetFps:30,loadDistance:110,unloadDistance:160,maxZones:4,concurrency:1,refraction:false,dynamicReflections:false,ssao:false,bloom:false}),
 balanced:Object.freeze({label:'均衡',scale:1,minScale:.85,shadowSize:1024,cascades:1,pcf:3,targetFps:30,loadDistance:140,unloadDistance:195,maxZones:6,concurrency:1,refraction:false,dynamicReflections:false,ssao:false,bloom:false}),
 high:Object.freeze({label:'高清',scale:1.25,minScale:1,shadowSize:2048,cascades:2,pcf:5,targetFps:45,loadDistance:170,unloadDistance:230,maxZones:10,concurrency:2,refraction:true,dynamicReflections:true,ssao:true,bloom:true}),
 ultra:Object.freeze({label:'超清',scale:1.5,minScale:1.25,shadowSize:2048,cascades:2,pcf:5,targetFps:60,loadDistance:190,unloadDistance:250,maxZones:20,concurrency:2,refraction:true,dynamicReflections:true,ssao:true,bloom:true})
});
export const normalizeQuality=value=>Object.hasOwn(QUALITY_PROFILES,value)?value:'balanced';
export const qualityProfile=value=>QUALITY_PROFILES[normalizeQuality(value)];
export const defaultEffects=value=>({ssao:qualityProfile(value).ssao,bloom:qualityProfile(value).bloom,pcss:false,fog:false});
export function reducedScale(current,quality){return Math.max(qualityProfile(quality).minScale,Math.round((current-.1)*100)/100);}
