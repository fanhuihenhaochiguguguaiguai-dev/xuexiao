"""Reuse cached evidence and prepare only v0.6 geometric corrections."""
from pathlib import Path
import json,math,copy,hashlib,shutil
from shapely.geometry import Polygon,Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import constrained_delaunay_triangles
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.campus-cache/v06';OUT.mkdir(parents=True,exist_ok=True)
baseline=OUT/'baseline';baseline.mkdir(exist_ok=True)
for source,name in [('assets/henan_campus/project/HenanCampus.blend','HenanCampus.blend'),('assets/henan_campus/project/scene_specification.json','scene_specification.json'),('assets/henan_campus/character/output/CampusExplorer.blend','CampusExplorer.blend')]:
 if not (baseline/name).exists():shutil.copy2(ROOT/source,baseline/name)
spec=json.loads((baseline/'scene_specification.json').read_text());cfg=json.loads((ROOT/'configs/v06-scene.json').read_text())
assert spec.get('version')=='0.5','Requires the verified v0.5 baseline; do not apply transforms twice'
def pack(poly):
 poly=orient(poly,sign=1)
 return {'rings':[list(poly.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in poly.interiors],'triangles':[list(t.exterior.coords)[:3] for t in constrained_delaunay_triangles(poly).geoms]}
def shape(obj):return Polygon(obj['polygon']['rings'][0],obj['polygon']['rings'][1:])
def rectangle(center,length,width,angle):
 a=math.radians(angle);u=(math.cos(a),math.sin(a));v=(-u[1],u[0])
 return Polygon([(center[0]+u[0]*x+v[0]*y,center[1]+u[1]*x+v[1]*y) for x,y in [(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)]])
def add(name,poly,z,height,material,group,**extra):
 obj={'name':name,'polygon':pack(poly),'z':z,'height':height,'material':material,'group':group,'source':'Cached published panoramas; see configs/v06-scene.json','confidence':'PHOTO_GUIDED_ESTIMATED_DIMENSIONS',**extra};spec['objects'].append(obj);return obj
spec['objects']=[o for o in spec['objects'] if not o['name'].startswith(('Library_stair_','Library_entry_terrace','Grandstand_seat_row_')) and o['name']!='B20_grandstand_parapet']
for o in spec['objects']:
 if o['name']=='B13_library':o.update(height=27,levels_estimated=9,floor_height_estimated=3,facade_tile_height=3,confidence='DOCUMENTED_NINTH_FLOOR__USER_3M_RULE_NOT_SURVEY')
 if 'facade_tile_height' in o:o['facade_tile_height']=3
for b in spec['buildings']:
 if b['map_index']==13:b.update(height_m=27,floor_count=9,floor_count_source='2025 public procurement, ninth floor; corroborating lake article',height_status='DOCUMENTED_FLOOR_COUNT_USER_3M_HEIGHT_RULE')
# Reuse the established curved entrance profile and its map position.
profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];u=(math.cos(math.radians(35)),math.sin(math.radians(35)));v=(-u[1],u[0]);uc=(profile[0][0]+profile[-1][0])/2
def front(x):
 for a,b in zip(profile,profile[1:]):
  if a[0]<=x<=b[0]:return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
 return profile[0][1] if x<profile[0][0] else profile[-1][1]
def point(x,offset):
 y=front(x)-offset;return (u[0]*x+v[0]*y,u[1]*x+v[1]*y)
xs=[uc-25+i*50/48 for i in range(49)]
def band(inner,outer):return Polygon([point(x,outer) for x in xs]+[point(x,inner) for x in reversed(xs)])
l=cfg['library'];total=l['stairs']*l['riser_m']
for j in range(l['stairs']):
 inner=.7+(l['stairs']-1-j)*l['tread_m'];add('Library_stair_'+str(j),band(inner,inner+l['tread_m']),.16,(j+1)*l['riser_m'],'paving','Roads',riser_m=l['riser_m'])
add('Library_entry_terrace',band(0,.7),.16,total,'paving','Roads')
b=cfg['bridge'];deck=add('Stone_bridge_deck',rectangle(b['center_blender_xy'],b['length_m'],b['width_m'],b['angle_degrees']),.16,b['deck_top_m']-.16,'stone','Bridge');deck['placement_status']=b['placement_status']
angle=math.radians(b['angle_degrees']);axis=(math.cos(angle),math.sin(angle))
for side in [-1,1]:
 for i,height in enumerate([.20,.10]):
  offset=side*(b['length_m']/2+.35+i*.7);center=[b['center_blender_xy'][j]+axis[j]*offset for j in range(2)];add(f'Stone_bridge_approach_{side}_{i}',rectangle(center,.7,b['width_m'],b['angle_degrees']),0,height,'stone','Bridge')
# Remove terrain underneath water rather than covering a flat lawn with a water plane.
waters=[o for o in spec['objects'] if o['material']=='water'];wet=unary_union([shape(o) for o in waters]);new=[]
for o in spec['objects']:
 if o['group'] in ['Ground','Roads'] and shape(o).intersects(wet):
  difference=shape(o).difference(wet)
  for i,poly in enumerate([difference] if difference.geom_type=='Polygon' else getattr(difference,'geoms',[])):
   if poly.geom_type=='Polygon' and poly.area>.01:new.append({**o,'name':o['name']+('' if i==0 else '_watercut'+str(i)),'polygon':pack(poly)})
 else:new.append(o)
spec['objects']=new
# A smooth estimated bed follows the same bank-distance rule as physics.
beds=[]
for water in waters:
 poly=shape(water);vertices=[];faces=[];lookup={}
 def vert(p):
  key=(round(p[0],7),round(p[1],7))
  if key not in lookup:
   lookup[key]=len(vertices);depth=min(cfg['water']['maximum_depth_m'],poly.boundary.distance(Point(p))*cfg['water']['depth_per_bank_distance']);vertices.append([p[0],p[1],cfg['water']['surface_m']-depth])
  return lookup[key]
 def subdivide(t):
  if max(math.dist(a,b) for a,b in zip(t,t[1:]+t[:1]))>1.8:
   a,b,c=t;ab=[(a[i]+b[i])/2 for i in range(2)];bc=[(b[i]+c[i])/2 for i in range(2)];ca=[(c[i]+a[i])/2 for i in range(2)]
   for q in [[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]]:subdivide(q)
  else:faces.append([vert(p) for p in t])
 for tri in water['polygon']['triangles']:subdivide(tri)
 beds.append({'name':water['name']+'_bed','vertices':vertices,'faces':faces,'material':'V06_lake_bed'})
spec['version']='0.6';spec['v06_policy']=cfg
(OUT/'scene_specification.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n');(OUT/'lake-beds.json').write_text(json.dumps(beds,separators=(',',':')))
report={'cached_panorama_reused':True,'panorama_network_requests':0,'reference_scenes':['scene_9c55ae29d225b8b9','scene_34656fcf113110f3','scene_28ea3e6c013eab33','scene_ef8a1b1d35eefd7f','scene_c5fd9763ca141592'],'library_floor_evidence':[{'url':'https://zhoukou.zfcg.henan.gov.cn/cmsweb81e27e/nas/webfile2024/henan/rootfiles/2025/05/28/05467834d19d4cae8fe862265d7b34a9.pdf','finding':'Procurement explicitly lists library first and ninth floors; not an elevation survey'},{'url':'https://article.xuexi.cn/articles/index.html?art_id=9310557443033534932&item_id=9310557443033534932','finding':'Indexed lake article describes nine-storey library; full article is a JS page'}],'observations':['Stone bridge has pale stone piers, horizontal openings and broad paving','Grandstand central viewing platform, stairs, guardrails and canopy are visible','Library has a broad raised entrance with multiple shallow risers'],'rights':'Public imagery for reference only; raw panorama photos not redistributed','estimated_dimensions':cfg,'lake_bed_triangles':sum(len(b['faces']) for b in beds),'survey_1_to_1_verified':False}
(ROOT/'reports/v06-reference-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('V06_SPEC_READY',len(spec['objects']),'bed triangles',report['lake_bed_triangles'])
