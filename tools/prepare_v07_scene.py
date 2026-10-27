"""Stage incremental metric changes from one immutable v0.6 baseline."""
import argparse, copy, hashlib, json, shutil, math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from shapely.geometry import Polygon, Point
from shapely import affinity
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.campus-cache/v07'
P=ROOT/'assets/henan_campus/project'


def prepare(campaign):
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=OUT/'baseline';baseline.mkdir(exist_ok=True)
    cfg=json.loads((ROOT/'configs/v07-scene.json').read_text())
    # A fresh cloud checkout already contains v0.7. Recover the exact historic
    # source through Git, rather than treating a processed mesh as raw input.
    commit=cfg['baseline_commit']
    if subprocess.run(['git','cat-file','-e',commit],cwd=ROOT,capture_output=True).returncode:
        subprocess.run(['git','fetch','origin',commit],cwd=ROOT,check=True)
    for src,name in [(P/'HenanCampus.blend','HenanCampus.blend'),(P/'scene_specification.json','scene_specification.json'),(ROOT/'game/dist/assets/world.json','world.json'),(ROOT/'game/dist/assets/zones.json','zones.json')]:
        dest=baseline/name
        if not dest.exists():
            data=subprocess.run(['git','show',commit+':'+str(src.relative_to(ROOT))],cwd=ROOT,check=True,capture_output=True).stdout
            if name=='scene_specification.json':assert json.loads(data)['version']=='0.6'
            dest.write_bytes(data)
    old=json.loads((baseline/'scene_specification.json').read_text());assert old['version']=='0.6'
    spec=copy.deepcopy(old);ids={'pilot':[13],'small':[13,5,15],'all':list(range(1,20))}[campaign]
    policy={};new_floor=cfg['floor_height_m']
    for b in spec['buildings']:
        idx=b['map_index']
        if idx not in ids:continue
        body=next(o for o in old['objects'] if o.get('building_index')==idx and o['group']=='Buildings' and o.get('display_name'))
        policy[idx]={'base':body['z'],'old_height':body['height'],'new_height':b['floor_count']*new_floor,'factor':new_floor/b['floor_height_m']}
        b.update(height_m=b['floor_count']*new_floor,floor_height_m=new_floor,height_status='USER_3_9M_RULE_NOT_SURVEY',model_reuse='EXISTING_BODY_FACADE_FOOTPRINT_PRESERVED')
    for o in spec['objects']:
        p=policy.get(o.get('building_index'))
        if not p or o['group']=='Foundation':continue
        if o['group']=='Buildings':
            o.update(height=p['new_height'],floor_height_estimated=new_floor,facade_tile_height=new_floor)
        elif o['group']=='Roof_details':o['z']+=p['new_height']-p['old_height']
    spec.update(version='0.7' if campaign=='all' else '0.7-'+campaign,v07_policy=cfg,v07_selected_buildings=ids)
    (OUT/'scene_specification.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    (OUT/'transform-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    world=json.loads((baseline/'world.json').read_text())
    for c in world['colliders']:
        p=policy.get(c.get('building'))
        if not p or c['kind']!='Buildings':continue
        for i in range(1,len(c['vertices']),3):
            z=c['vertices'][i];c['vertices'][i]=p['base']+(z-p['base'])*p['factor']
    for b in world['buildings']:
        if b['id'] in policy:b.update(height=policy[b['id']]['new_height'],floorHeightMeters=new_floor,heightSource='USER_RULE_NOT_SURVEY')
    world.update(version=spec['version'],floorHeightMeters=new_floor,buildingFloorHeightRule='Regular storeys only; stadium tiers, railings and steps retain physical dimensions.')
    profile=json.loads((ROOT/'assets/henan_campus/metadata/library_refinement.json').read_text())['front_profile_uv'];uc=(profile[0][0]+profile[-1][0])/2
    front=next(a[1]+(b[1]-a[1])*(uc-a[0])/(b[0]-a[0]) for a,b in zip(profile,profile[1:]) if a[0]<=uc<=b[0])
    u=(math.cos(math.radians(35)),math.sin(math.radians(35)));v=(-u[1],u[0]);px=u[0]*uc+v[0]*(front-7.5);py=u[1]*uc+v[1]*(front-7.5)
    world['landmarks']['libraryEntrance']={'approach':[px,.3,-py],'direction':[v[0],-v[1]],'landing_top_m':1.96,'door_height_m':2.1,'status':'PHOTO_GUIDED_ESTIMATE_NOT_SURVEY'}
    (OUT/'world.json').write_text(json.dumps(world,ensure_ascii=False,separators=(',',':')))
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    # Add modest air-conditioner grilles to the existing authored dorm atlas;
    # originals, people, signs and photographs are not pasted onto buildings.
    dorm=Image.open(P/'assets/dorm_facade.png').convert('RGB');d=ImageDraw.Draw(dorm)
    for x in range(0,dorm.width,256):
        d.rectangle((x+209,168,x+250,203),fill=(187,185,170),outline=(124,129,121),width=2)
        d.ellipse((x+219,173,x+246,199),fill=(95,105,100),outline=(153,159,151),width=2)
        for y in range(176,198,4):d.line((x+220,y,x+245,y),fill=(162,166,156),width=1)
        d.line((x+208,197,x+203,197,x+203,235),fill=(151,150,139),width=2)
    dorm.save(assets/'dorm-facade-v07.png')
    # Reproject static shadows for the taller bodies; near-field AO (6m) is
    # retained because footprints and the lower six metres of solids are fixed.
    bounds=json.loads((P/'assets/lighting-water.json').read_text())['ground_blender_bounds'];xmin,ymin,xmax,ymax=bounds;size=4096
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
    shadow=Image.eval(mask.filter(ImageFilter.GaussianBlur(2)),lambda v:255-round(v*.62));shadow.save(assets/'ground-shadow-v07.png')
    ao=Image.open(P/'assets/v06/ground-ao-2048.png').convert('L')
    ImageChops.multiply(ao,shadow.resize(ao.size,Image.Resampling.LANCZOS)).save(assets/'ground-occlusion-v07.png')
    return {'campaign':campaign,'selected':ids,'rule_m':new_floor,'photogrammetry_run':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',choices=['pilot','small','all'],default='pilot')
    print(json.dumps(prepare(parser.parse_args().campaign)))
