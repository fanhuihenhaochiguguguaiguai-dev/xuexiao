"""Build staged collision and streaming manifests without modifying the release."""
from pathlib import Path
import json,hashlib,shutil
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/v06';D=S/'runtime';D.mkdir(exist_ok=True)
spec=json.loads((S/'scene_specification.json').read_text());cfg=spec['v06_policy'];data=json.loads((ROOT/'game/dist/assets/world.json').read_text())
def make_mesh(o,top_only=False):
 verts=[];indices=[]
 def v(x,y,z):verts.extend([x,z,-y]);return len(verts)//3-1
 for tri in o['polygon']['triangles']:
  a,b,c=tri
  if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<0:tri=list(reversed(tri))
  indices.extend(v(*p,o['z']+o['height']) for p in tri)
  if not top_only:indices.extend(v(*p,o['z']) for p in reversed(tri))
 if not top_only:
  for ring in o['polygon']['rings']:
   for a,b in zip(ring,ring[1:]+ring[:1]):
    k=[v(*a,o['z']),v(*b,o['z']),v(*b,o['z']+o['height']),v(*a,o['z']+o['height'])];indices.extend([k[0],k[1],k[2],k[0],k[2],k[3]])
 return {'name':o['name'],'building':o.get('building_index'),'kind':o['group'],'vertices':verts,'indices':indices}
colliders=[]
for o in spec['objects']:
 if o['name']=='B20_grandstand':continue
 if o['group'] in ['Buildings','Gate','Bridge']:colliders.append(make_mesh(o))
 elif o['group'] in ['Ground','Roads'] or o['name']=='Library_south_plaza':colliders.append(make_mesh(o,True))
colliders.extend(json.loads((S/'special-colliders.json').read_text()));colliders.extend(c for c in data['colliders'] if c['kind']=='Boundary');data['colliders']=colliders
data['waterZones']=[]
for o in spec['objects']:
 if o['material']!='water':continue
 poly=Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]);point=poly.representative_point();x0,y0,x1,y1=poly.bounds
 data['waterZones'].append({'id':o['name'],'rings':[[[x,-y] for x,y in ring] for ring in o['polygon']['rings']],'bounds':[x0,-y1,x1,-y0],'surface':cfg['water']['surface_m'],'maximumDepth':cfg['water']['maximum_depth_m'],'depthPerBankDistance':cfg['water']['depth_per_bank_distance'],'testPoint':[point.x,-point.y],'depthStatus':'ESTIMATED_NOT_MEASURED'})
for b in data['buildings']:
 if b['id']==13:b.update(height=27,floorCount=9)
data['version']='0.6';data['floorHeightMeters']=3;data['groundTopMeters']=0;data['landmarks']=json.loads((S/'landmarks.json').read_text());data['source_model_sha256']=hashlib.sha256((S/'HenanCampus.glb').read_bytes()).hexdigest();data['runtime_base_sha256']=hashlib.sha256((S/'campus-base.glb').read_bytes()).hexdigest()
(D/'world.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')));shutil.copy2(S/'campus-base.glb',D/'campus.glb');shutil.copy2(S/'zones.json',D/'zones.json');shutil.copytree(S/'zones',D/'zones',dirs_exist_ok=True)
print('V06_RUNTIME_PREPARED',len(colliders),len(data['waterZones']))
