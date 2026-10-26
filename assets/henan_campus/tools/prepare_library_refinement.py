from pathlib import Path
import os
import json,sys,math,random
sys.path.insert(0,str(Path(__file__).resolve().parent/'geometry_deps'))
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely import constrained_delaunay_triangles
from PIL import Image,ImageDraw
R=Path(os.environ.get('CAMPUS_ASSET_ROOT', str(Path(__file__).resolve().parents[1])));P=R/'project';A=P/'assets'
s=json.loads((P/'scene_specification.json').read_text());lib=next(o for o in s['objects'] if o['name']=='B13_library')
lib['height']=28.8;lib['levels_estimated']=8;lib['floor_height_estimated']=3.6
lib['confidence']='SOURCE_XY__2017_PHOTO_GUIDED_APPROXIMATE_EIGHT_LEVEL_FACADE__HEIGHT_NOT_SURVEYED'
u=(math.cos(math.radians(35)),math.sin(math.radians(35)));v=(-u[1],u[0]);ring=lib['polygon']['rings'][0]
profile=sorted([(x*u[0]+y*u[1],x*v[0]+y*v[1]) for x,y in ring[1:5]])
def front(x):
 for a,b in zip(profile,profile[1:]):
  if a[0]<=x<=b[0]:return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
 return profile[0][1] if x<profile[0][0] else profile[-1][1]
def point(x,y):return (x*u[0]+y*v[0],x*u[1]+y*v[1])
def pack(p):
 p=orient(p,sign=1);return {'rings':[list(p.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in p.interiors], 'triangles':[list(t.exterior.coords)[:3] for t in constrained_delaunay_triangles(p).geoms]}
plaza=next(o for o in s['objects'] if o['name']=='Library_south_plaza')
# The first draft subtracted the road from the plaza. Restore that paved strip
# using the photo-observed broad square, then trim the asphalt against it.
pp=Polygon([point(x,y) for x,y in [(-63,-93),(78,-93),(78,-17),(-63,-17)]])
for o in s['objects']:
 if o['group']=='Buildings':pp=pp.difference(Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]).buffer(.8))
 if o['material']=='water':pp=pp.difference(Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]).buffer(1.9))
parts=[pp] if pp.geom_type=='Polygon' else list(pp.geoms);pp=max(parts,key=lambda p:p.area);plaza['polygon']=pack(pp)
new=[]
for o in s['objects']:
 if o['name'].startswith(('Library_stair_','Library_entry_terrace','Library_south_plaza_','B13_library_parapet','B13_library_plant')):continue
 if o['name'].startswith('Campus_roads'):
  p=Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]).difference(pp)
  parts=[p] if p.geom_type=='Polygon' else list(p.geoms)
  for i,q in enumerate(parts):
   if q.area>.01:new.append({**o,'name':o['name']+('_ref'+str(i) if i else ''),'polygon':pack(q)})
 else:new.append(o)
uc=sum(p[0] for p in [profile[0],profile[-1]])/2;xs=[uc-25+i*50/48 for i in range(49)]
def band(inner,outer):return Polygon([point(x,front(x)-outer) for x in xs]+[point(x,front(x)-inner) for x in reversed(xs)])
for j in range(8):
 inner=.7+(7-j)*.55;outer=inner+.55
 new.append({'name':'Library_stair_'+str(j),'polygon':pack(band(inner,outer)),'z':.16,'height':.15*(j+1),'material':'paving','group':'Roads','source':'Cached library south-plaza photographs','confidence':'PHOTO_GUIDED_ESTIMATED_STAIR_DIMENSIONS'})
new.append({'name':'Library_entry_terrace','polygon':pack(band(0,.7)),'z':.16,'height':1.2,'material':'paving','group':'Roads','source':'Cached library south-plaza photographs','confidence':'PHOTO_GUIDED_ESTIMATED_DIMENSIONS'})
s['objects']=new
for b in s['buildings']:
 if b['map_index']==13:b.update({'height_m':28.8,'floor_count':8,'height_status':'PHOTO_GUIDED_ESTIMATE_NOT_MEASURED','visual_revision':'Horizontal blue bands, stone piers, curved eaves, signed entrance and broad stairs from cached 2017 photographs'})
s['library_refinement']={'method':'PHOTO_GUIDED_LOCAL_GEOMETRY_CORRECTION','references':['scene_ef8a1b1d35eefd7f/b.jpg','scene_ef8a1b1d35eefd7f/l.jpg','scene_c5fd9763ca141592/l.jpg'],'source_date':'2017-08-11','measurement_status':'ALL_NEW_DIMENSIONS_ESTIMATED'}
(P/'scene_specification.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
(R/'metadata/library_refinement.json').write_text(json.dumps({'front_profile_uv':profile,**s['library_refinement']},ensure_ascii=False,indent=2)+'\n')
(R/'metadata/building_model_parameters.json').write_text(json.dumps(s['buildings'],ensure_ascii=False,indent=2)+'\n')
# Self-authored tiling textures use photo-observed colours and joint proportions.
rng=random.Random(42)
for name,base,grid in [('library_stone',(193,177,165),(128,64)),('library_paving',(182,143,132),(128,128))]:
 im=Image.new('RGB',(512,512));px=im.load()
 for y in range(512):
  for x in range(512):
   n=rng.randint(-7,7);px[x,y]=tuple(max(0,min(255,c+n)) for c in base)
 d=ImageDraw.Draw(im)
 for y in range(0,512,grid[1]):d.line((0,y,511,y),fill=tuple(c-22 for c in base),width=2)
 for row,y in enumerate(range(0,512,grid[1])):
  for x in range((-grid[0]//2 if row%2 and name=='library_stone' else 0),512,grid[0]):d.line((x,y,x,y+grid[1]),fill=tuple(c-22 for c in base),width=2)
 if name=='library_paving':d.rectangle((0,0,31,511),fill=(198,190,170));d.rectangle((0,0,511,31),fill=(198,190,170))
 im.save(A/(name+'.png'))
print('LIBRARY_SPEC_PREPARED',len(new))
