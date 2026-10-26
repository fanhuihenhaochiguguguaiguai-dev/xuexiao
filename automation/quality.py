"""Small executable gates; full glTF schema validation remains an optional tool.

The geometry gate reads position/index buffers, rather than trusting extensions,
file names, bounding boxes in JSON, or a previous 'passed' string.
"""
import json,struct,math,hashlib
from pathlib import Path

def sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def glb_gate(path,min_height=.1,require_skin=False):
 raw=Path(path).read_bytes()
 if len(raw)<28 or raw[:4]!=b'glTF':raise ValueError('Not a binary glTF file')
 magic,version,size=struct.unpack_from('<4sII',raw)
 if version!=2 or size!=len(raw):raise ValueError('Invalid GLB header/length')
 offset=12;chunks=[]
 while offset<len(raw):
  if offset+8>len(raw):raise ValueError('Truncated chunk header')
  length,kind=struct.unpack_from('<II',raw,offset);offset+=8
  if length%4 or offset+length>len(raw):raise ValueError('Invalid chunk length')
  chunks.append((kind,raw[offset:offset+length]));offset+=length
 if chunks[0][0]!=0x4e4f534a:raise ValueError('JSON must be first chunk')
 doc=json.loads(chunks[0][1].rstrip(b' \0'));binary=next((c for k,c in chunks if k==0x004e4942),None)
 if binary is None or not doc.get('meshes'):raise ValueError('No mesh geometry')
 if any(b.get('uri') for b in doc.get('buffers',[])):raise ValueError('External buffers are not self-contained')
 if len(doc.get('buffers',[]))!=1 or doc['buffers'][0]['byteLength']>len(binary):raise ValueError('Invalid buffer declaration')
 views=doc.get('bufferViews',[]);accessors=doc.get('accessors',[])
 for v in views:
  if v.get('buffer',0)!=0 or v.get('byteOffset',0)<0 or v['byteLength']<0 or v.get('byteOffset',0)+v['byteLength']>len(binary):raise ValueError('Buffer view out of range')
 sizes={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
 components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
 def read_accessor(index):
  a=accessors[index]
  if 'sparse' in a or 'bufferView' not in a:raise ValueError('Sparse/implicit accessors need the full validator')
  fmt,width=sizes[a['componentType']];n=components[a['type']];v=views[a['bufferView']];stride=v.get('byteStride',n*width);local=a.get('byteOffset',0)
  if a['count']<0 or stride<n*width:raise ValueError('Invalid accessor shape')
  end=local+(a['count']-1)*stride+n*width if a['count'] else local
  if local<0 or end>v['byteLength']:raise ValueError('Accessor exceeds its view')
  start=v.get('byteOffset',0)+local
  return [struct.unpack_from('<'+fmt*n,binary,start+i*stride) for i in range(a['count'])]
 lo=[float('inf')]*3;hi=[float('-inf')]*3;vertices=triangles=0
 for mesh in doc['meshes']:
  for p in mesh.get('primitives',[]):
   if p.get('mode',4)!=4:raise ValueError('Non-triangle primitive is outside this model gate')
   pos_index=p.get('attributes',{}).get('POSITION')
   if pos_index is None or accessors[pos_index]['type']!='VEC3':raise ValueError('Missing VEC3 positions')
   xyz=read_accessor(pos_index)
   if not xyz:raise ValueError('Empty vertex buffer')
   for point in xyz:
    if any(not math.isfinite(v) for v in point):raise ValueError('Non-finite vertex')
    for k in range(3):lo[k]=min(lo[k],point[k]);hi[k]=max(hi[k],point[k])
   vertices+=len(xyz)
   indices=[x[0] for x in read_accessor(p['indices'])] if 'indices' in p else list(range(len(xyz)))
   if len(indices)%3 or not indices or min(indices)<0 or max(indices)>=len(xyz):raise ValueError('Invalid triangle indices')
   triangles+=len(indices)//3
 for image in doc.get('images',[]):
  if 'uri' in image:raise ValueError('External image URI is not self-contained')
  if 'bufferView' not in image:raise ValueError('Image has no data')
  view=views[image['bufferView']];blob=binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
  if not (blob.startswith(b'\x89PNG\r\n\x1a\n') or blob.startswith(b'\xff\xd8\xff')):raise ValueError('Unrecognized embedded texture encoding')
 extent=[hi[k]-lo[k] for k in range(3)]
 if triangles<4 or extent[1]<min_height or extent[0]<.05 or extent[2]<.05:raise ValueError('Not a volumetric-scale 3D model')
 animations=[a.get('name','') for a in doc.get('animations',[])]
 if require_skin and (not doc.get('skins') or not {'Idle','Walk','Run','Jump'}.issubset(animations)):raise ValueError('Required rig/animation clips missing')
 return {'passed':True,'sha256':sha256(path),'triangles':triangles,'vertices':vertices,'position_extent_m':extent,'embedded_images':len(doc.get('images',[])),'animations':animations,
         'scope':'Geometry, buffers, finiteness and embedded texture signatures; not a likeness, survey, render or full glTF schema certification.'}

def pwa_gate(directory):
 p=Path(directory);manifest=json.loads((p/'manifest.webmanifest').read_text())
 if manifest.get('orientation')!='landscape' or manifest.get('display')!='standalone':raise ValueError('Landscape standalone manifest required')
 sizes=set()
 for icon in manifest.get('icons',[]):
  path=p/icon['src'].lstrip('/');data=path.read_bytes()
  if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Icon is not PNG')
  w,h=struct.unpack_from('>II',data,16)
  if f'{w}x{h}'!=icon['sizes']:raise ValueError('Icon dimensions mismatch')
  sizes.add(w)
 if not {192,512}.issubset(sizes):raise ValueError('192/512 icons required')
 for name in ['index.html','style.css','game.js','pwa.js','sw.js','assets/world.json','assets/campus.glb','assets/character.glb']:
  if not (p/name).is_file():raise ValueError('Missing app resource: '+name)
 return {'passed':True,'orientation':'landscape','icon_sizes':sorted(sizes),'scope':'Static app prerequisites only; browser installability and phone installation are separate checks.'}
