from pathlib import Path
import os
import sys,json,math,shutil,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent/'geometry_deps'))
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely import constrained_delaunay_triangles
R=Path(os.environ.get('CAMPUS_ASSET_ROOT', str(Path(__file__).resolve().parents[1])));P=R/'project';D=Path(os.environ.get('CAMPUS_GAME_ROOT', str(Path(__file__).resolve().parents[3]/'game')))/'dist/assets'
D.mkdir(parents=True,exist_ok=True)
s=json.loads((P/'scene_specification.json').read_text());colliders=[]
def make_mesh(obj,top_only=False):
 v=[];inds=[]
 def vert(x,y,z):v.extend([x,z,-y]);return len(v)//3-1
 z=obj['z'];h=obj['height'];p=obj['polygon']
 for t in p['triangles']:
  a,b,c=t
  if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<0:t=list(reversed(t))
  inds.extend(vert(*a,z+h) for a in t)
  if not top_only:inds.extend(vert(*a,z) for a in reversed(t))
 if not top_only:
  for ring in p['rings']:
   for a,b in zip(ring,ring[1:]+ring[:1]):
    k=[vert(*a,z),vert(*b,z),vert(*b,z+h),vert(*a,z+h)];inds.extend([k[0],k[1],k[2],k[0],k[2],k[3]])
 return {'name':obj['name'],'building':obj.get('building_index'),'kind':obj['group'],'vertices':v,'indices':inds}
for o in s['objects']:
 if o['group'] in ['Buildings','Gate']:
  colliders.append(make_mesh(o))
 elif o['group']=='Ground' or o['group']=='Roads' or o['name']=='Library_south_plaza':
  colliders.append(make_mesh(o,True))
 elif o['material']=='water':
  o={**o,'height':2};colliders.append(make_mesh(o));colliders[-1]['kind']='WaterBarrier'
ground=next(o for o in s['objects'] if o['name']=='Campus_ground')
boundary=Polygon(ground['polygon']['rings'][0]);wall=orient(boundary.buffer(.25).difference(boundary.buffer(-.25)),sign=1)
wall_poly={'rings':[list(wall.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in wall.interiors],
           'triangles':[list(t.exterior.coords)[:3] for t in constrained_delaunay_triangles(wall).geoms]}
colliders.append(make_mesh({'name':'Campus_perimeter','z':0,'height':4,'group':'Boundary','polygon':wall_poly}))
buildings=[]
for b in s['buildings']:
 x,y=b['centroid_local_m'];buildings.append({'id':b['map_index'],'name':b['label'],'x':x,'z':-y,'height':b['height_m'],'estimated':True})
pois=[{'id':'library','name':'图书馆南广场','x':32,'z':78,'yaw':.55},
      {'id':'stadium','name':'体育场东侧道路','x':-170,'z':-95,'yaw':1.2},
      {'id':'dorm','name':'宿舍楼群外道路','x':38,'z':-138,'yaw':-1.1},
      {'id':'gate','name':'南侧办公楼前','x':100,'z':195,'yaw':.5}]
outline=[(p[0],-p[1]) for p in ground['polygon']['rings'][0]]
mapdata={'boundary':outline,'buildings':[],'roads':[]}
for o in s['objects']:
 if o['group']=='Buildings' and o.get('building_index') and '_parapet' not in o['name']:
  mapdata['buildings'].append({'id':o['building_index'],'rings':[[(p[0],-p[1]) for p in ring] for ring in o['polygon']['rings']]})
 if o['group']=='Roads' and o['material']=='asphalt':mapdata['roads'].extend([[(p[0],-p[1]) for p in ring] for ring in o['polygon']['rings']])
data={'colliders':colliders,'buildings':buildings,'pois':pois,'map':mapdata,'spawn':pois[0],
 'campus_geometry':'Existing 20-footprint image-guided draft. Heights and details estimated.',
 'model_attribution':'© OpenStreetMap contributors / ODbL 1.0',
 'source_model_sha256':hashlib.sha256((P/'HenanCampus.glb').read_bytes()).hexdigest()}
(D/'world.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
shutil.copy2(P/'HenanCampus.glb',D/'campus.glb')
shutil.copy2(R/'character/output/CampusExplorer.glb',D/'character.glb')
shutil.copy2(R/'character/source/LICENSE.ASSETS.md',D/'character-base-CC0.txt')
print(json.dumps({'colliders':len(colliders),'collision_triangles':sum(len(c['indices'])//3 for c in colliders),'world_bytes':(D/'world.json').stat().st_size},ensure_ascii=False))
