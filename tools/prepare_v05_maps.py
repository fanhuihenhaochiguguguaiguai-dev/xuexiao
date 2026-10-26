"""CPU atlas bake inputs: directional prism shadows and estimated pond depth.
AO itself is ray-traced by Blender in bake_v05_lighting.py.
"""
from pathlib import Path
import json,math,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from shapely.geometry import Polygon,Point
from shapely import affinity,points,distance,contains_xy
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];stage=ROOT/'.campus-cache/v05/final';out=stage/'assets';out.mkdir(exist_ok=True)
spec=json.loads((ROOT/'assets/henan_campus/project/scene_specification.json').read_text());cfg=json.loads((ROOT/'configs/v05-buildings.json').read_text());policy={b['id']:b for b in cfg['buildings']};report=json.loads((stage/'geometry-report.json').read_text());bounds=report['ground_atlas_blender_bounds'];xmin,ymin,xmax,ymax=bounds;size=2048
mask=Image.new('L',(size,size),0);draw=ImageDraw.Draw(mask)
def pixel(x,y):return ((x-xmin)/(xmax-xmin)*(size-1),(ymax-y)/(ymax-ymin)*(size-1))
def polygon_mask(poly,value=255):
 if poly.is_empty:return
 for p in ([poly] if poly.geom_type=='Polygon' else getattr(poly,'geoms',[])):
  if p.geom_type!='Polygon':continue
  draw.polygon([pixel(x,y) for x,y in p.exterior.coords],fill=value)
  for ring in p.interiors:draw.polygon([pixel(x,y) for x,y in ring.coords],fill=0)
shadows=[]
for o in spec['objects']:
 if o['group'] not in ['Buildings','Gate','Roof_details']:continue
 p=Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]);idx=o.get('building_index');z=o['z']+o['height']
 if idx in policy and o.get('height_rule')!='USER_3M_FLOOR_RULE':
  q=policy[idx];old=q['old_body_height_m'];new=q['body_height_m'];z=(.16+(z-.16)*new/old) if z<=.16+old else z+new-old
 dx=z*.6308;dy=z*.8679
 shifted=affinity.translate(p,dx,dy);sweep=[p,shifted]
 for ring in [p.exterior,*p.interiors]:
  c=list(ring.coords)
  for a,b in zip(c,c[1:]):
   quad=Polygon([a,b,(b[0]+dx,b[1]+dy),(a[0]+dx,a[1]+dy)])
   if quad.area>1e-8:sweep.append(quad)
 shadows.append(unary_union(sweep))
for t in spec['trees']:
 h=t['height'];p=Point(t['x']+h*.6308,t['y']+h*.8679).buffer(h*.26,resolution=8);shadows.append(p)
polygon_mask(unary_union(shadows));mask=mask.filter(ImageFilter.GaussianBlur(1.3));shadow=Image.eval(mask,lambda v:255-round(v*.68));shadow.save(out/'ground-static-shadow.png')
waters=[]
for o in spec['objects']:
 if o['material']!='water':continue
 poly=Polygon(o['polygon']['rings'][0],o['polygon']['rings'][1:]);x0,y0,x1,y1=poly.bounds;n=256;xx=np.linspace(x0,x1,n)[None,:];yy=np.linspace(y1,y0,n)[:,None];X=np.broadcast_to(xx,(n,n));Y=np.broadcast_to(yy,(n,n));d=distance(points(X,Y),poly.boundary);inside=contains_xy(poly,X,Y);depth=np.minimum(1.3,d*.6)*inside
 foam=np.exp(-((d-.3)/.22)**2)*(.5+.5*np.sin(X*3+np.sin(Y*4)))*.16*inside
 t=np.clip(depth/1.3,0,1);shallow=np.array([127,149,131]);deep=np.array([67,104,94]);rgb=shallow[None,None,:]*(1-t[...,None])+deep[None,None,:]*t[...,None];rgb=rgb*(1-foam[...,None])+np.array([220,229,210])[None,None,:]*foam[...,None]
 Image.fromarray(np.uint8(np.clip(rgb,0,255))).save(out/(o['name']+'-depth-color.png'))
 encoded=np.stack([depth/1.3,foam/.16,inside.astype(float)],axis=2);Image.fromarray(np.uint8(np.clip(encoded*255,0,255))).save(out/(o['name']+'-depth-foam.png'))
 waters.append({'object':o['name'],'blender_bounds':[x0,y0,x1,y1],'color_image':o['name']+'-depth-color.png','depth_foam_image':o['name']+'-depth-foam.png','max_depth_m':1.3,'depth_source':'ESTIMATED_DISTANCE_FROM_EXISTING_SHORE_NOT_MEASURED','shore_foam_width_m':.22})
metadata={'static_shadow_method':'CPU_GEOMETRIC_DIRECTIONAL_PRISM_PROJECTION_ON_FLAT_GROUND','atlas_size':size,'ground_blender_bounds':bounds,'light_ray_dx_dh':.6308,'light_ray_dy_dh':.8679,'water':waters,'geometry_accuracy':'Existing footprints and heights policy; no measured bathymetry'}
(out/'lighting-water.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n');print('V05_MAPS_PREPARED',len(waters),len(shadows))
