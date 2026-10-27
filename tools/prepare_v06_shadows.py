"""4096px directional ground-shadow atlas from the corrected metric scene."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFilter
from shapely.geometry import Polygon,Point
from shapely import affinity
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.campus-cache/v06';out=S/'assets';spec=json.loads((S/'scene_specification.json').read_text());bounds=json.loads((ROOT/'assets/henan_campus/project/assets/lighting-water.json').read_text())['ground_blender_bounds'];xmin,ymin,xmax,ymax=bounds;size=4096
mask=Image.new('L',(size,size),0);draw=ImageDraw.Draw(mask)
def pixel(x,y):return ((x-xmin)/(xmax-xmin)*(size-1),(ymax-y)/(ymax-ymin)*(size-1))
def paint(poly):
 for p in [poly] if poly.geom_type=='Polygon' else getattr(poly,'geoms',[]):
  if p.geom_type!='Polygon':continue
  draw.polygon([pixel(x,y) for x,y in p.exterior.coords],fill=255)
  for r in p.interiors:draw.polygon([pixel(x,y) for x,y in r.coords],fill=0)
for o in spec['objects']:
 if o['group'] not in ['Buildings','Roof_details','Gate','Bridge']:continue
 p=Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]);h=o['z']+o['height'];dx=h*.6308;dy=h*.8679;sweep=[p,affinity.translate(p,dx,dy)]
 for ring in [p.exterior,*p.interiors]:
  c=list(ring.coords)
  for a,b in zip(c,c[1:]):
   q=Polygon([a,b,(b[0]+dx,b[1]+dy),(a[0]+dx,a[1]+dy)])
   if q.area>1e-8:sweep.append(q)
 paint(unary_union(sweep))
for t in spec['trees']:paint(Point(t['x']+t['height']*.6308,t['y']+t['height']*.8679).buffer(t['height']*.26,resolution=8))
mask=mask.filter(ImageFilter.GaussianBlur(2));Image.eval(mask,lambda v:255-round(v*.62)).save(out/'ground-shadow-4096.png')
print('V06_STATIC_SHADOW_READY',size)
