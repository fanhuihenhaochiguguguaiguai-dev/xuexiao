"""Extract only clear architectural components, rectify and cache their textures."""
import hashlib,json,sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];CFG=ROOT/'configs/photo-fit-library.json';OUT=ROOT/'.campus-cache/photo-fit';A=OUT/'assets';A.mkdir(parents=True,exist_ok=True)
cfg=json.loads(CFG.read_text());source=ROOT/'.resource-cache/user-photos'/cfg['source_archive_sha256']/cfg['photo']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)==cfg['source_sha256'],'Wrong source photograph'
im=np.array(Image.open(source).convert('RGB'));assert list(im.shape[1::-1])==cfg['source_dimensions']
paving_source=Path('/workspace/henan_campus/resources/panorama_cubefaces')/cfg['paving']['scene']/(cfg['paving']['face']+'.jpg');assert sha(paving_source)==cfg['paving']['source_sha256']
fingerprint=hashlib.sha256((sha(CFG)+sha(Path(__file__))+sha(source)+sha(paving_source)+cv2.__version__).encode()).hexdigest();receipt=OUT/'materials.json'
if receipt.exists():
    old=json.loads(receipt.read_text())
    if old.get('fingerprint')==fingerprint and all((A/n).is_file() and sha(A/n)==h for n,h in old['texture_hashes'].items()):
        print(json.dumps({'status':'CACHED','fingerprint':fingerprint,'textures':len(old['texture_hashes'])}));sys.exit(0)

def rectify(quad,width,height,pixels=None):
    pixels=im if pixels is None else pixels
    q=np.float32(quad);assert q.shape==(4,2) and cv2.isContourConvex(q.astype(np.int32))
    assert all(0<=x<pixels.shape[1] and 0<=y<pixels.shape[0] for x,y in q)
    target=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    H=cv2.getPerspectiveTransform(q,target);assert np.isfinite(H).all() and abs(np.linalg.det(H))>1e-8
    error=float(np.max(np.linalg.norm(cv2.perspectiveTransform(q[None],H)[0]-target,axis=1)));assert error<.01
    patch=cv2.warpPerspective(pixels,H,(width,height),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
    lengths=[float(np.linalg.norm(q[(i+1)%4]-q[i])) for i in range(4)]
    return patch,{'homography':H.tolist(),'corner_error_px':error,'source_edge_pixels':lengths,'output_dimensions':[width,height]}

tiles=[];checks=[]
for q in cfg['window_quads']:
    patch,check=rectify(q,96,96);tiles.append(patch);checks.append(check)
# A gutter prevents mipmap bleeding between independent photographic variants.
atlas=np.zeros((128,512,3),dtype=np.uint8)
for i,patch in enumerate(tiles):atlas[:,i*128:(i+1)*128]=np.pad(patch,((16,16),(16,16),(0,0)),mode='edge')
Image.fromarray(atlas).save(A/'library-photo-windows.png',optimize=True)
wall,wall_check=rectify(cfg['wall_quad'],128,128)
# Remove broad illumination variation without fabricating any hidden content.
luma=np.maximum(1,np.dot(wall,[.2126,.7152,.0722]));low=cv2.GaussianBlur(luma,(0,0),22);ratio=np.clip(np.median(luma)/np.maximum(low,1),.88,1.14)
wall=np.uint8(np.clip(wall.astype(float)*ratio[:,:,None],0,255))
Image.fromarray(wall).save(A/'library-photo-cladding.png',optimize=True)
# Texture-derived micro-normal is an appearance estimate, not measured depth.
height=cv2.cvtColor(wall,cv2.COLOR_RGB2GRAY).astype(np.float32)/255;dx=cv2.Sobel(height,cv2.CV_32F,1,0,ksize=3)*.2;dy=cv2.Sobel(height,cv2.CV_32F,0,1,ksize=3)*.2;norm=np.sqrt(dx*dx+dy*dy+1)
normal=np.uint8(np.clip(np.stack([-dx/norm,-dy/norm,1/norm],axis=-1)*127.5+127.5,0,255));Image.fromarray(normal).save(A/'library-photo-normal.png',optimize=True)
paving,paving_check=rectify(cfg['paving']['quad'],256,256,np.array(Image.open(paving_source).convert('RGB')))
Image.fromarray(paving).save(A/'library-photo-pavers.png',optimize=True)
textures=sorted(A.glob('*.png'));assert sum(p.stat().st_size for p in textures)<=cfg['budget']['maximum_added_texture_bytes']
for p in textures:
    with Image.open(p) as image:image.verify()
contact=Image.new('RGB',(768,400),'#dedbd4');d=ImageDraw.Draw(contact)
for i,t in enumerate(tiles):contact.paste(Image.fromarray(t).resize((160,160)),(i*192,40));d.text((i*192,15),'PHOTO WINDOW '+str(i+1),fill='#262c2a')
contact.paste(Image.fromarray(wall).resize((160,160)),(0,220));d.text((185,245),'Actual photo patches; no people, foliage or invented infill.',fill='#262c2a');contact.save('/workspace/output/photo-material-pilot.png')
result={'passed':True,'fingerprint':fingerprint,'source_photo_sha256':sha(source),'source_dimensions':cfg['source_dimensions'],'permission':cfg['source_permission'],'method':'PLANAR_HOMOGRAPHY_COMPONENT_TEXTURES_NOT_PHOTOGRAMMETRY','window_checks':checks,'wall_check':wall_check,'paving_check':paving_check,'paving_source_sha256':sha(paving_source),'texture_hashes':{p.name:sha(p) for p in textures},'texture_bytes':sum(p.stat().st_size for p in textures),'original_photo_included':False,'source_detail_limit':'Actual usable window corners span about 40 pixels; output resolution does not create new captured detail','normal_status':'PHOTO_DERIVED_MICRO_NORMAL_ESTIMATE_NOT_MEASURED_DEPTH'}
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'BUILT','passed':True,'textures':len(textures),'bytes':result['texture_bytes'],'maximum_corner_error':max(c['corner_error_px'] for c in checks)}))
