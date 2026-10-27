#!/usr/bin/env python3
"""Check an official-source-only scene manifest without downloading anything."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
p = Path(sys.argv[1]) if len(sys.argv)>1 else root/'manifest.json'
m = json.loads(p.read_text(encoding='utf-8'))
assert m.get('schema') == 1
assert m.get('source_policy') == 'official-source-only'
assert isinstance(m.get('scenes'),list)
seen=set();missing=[];image_scenes=0;meshes=0
for i,s in enumerate(m['scenes']):
    ident=s.get('id'); assert isinstance(ident,str) and ident and ident not in seen, f'bad id at {i}'
    seen.add(ident)
    assert isinstance(s.get('name'),str) and s['name'].strip(), f'bad name at {i}'
    for field in ('panorama','scan_glb'):
        if s.get(field):
            v=s[field]
            if not urlsplit(v).scheme and not (root/v).is_file(): missing.append(v)
    if s.get('cube_faces'):
        assert len(s['cube_faces'])==6
        for v in s['cube_faces']:
            if not urlsplit(v).scheme and not (root/v).is_file(): missing.append(v)
    image_scenes+=bool(s.get('panorama') or s.get('cube_faces'))
    meshes+=bool(s.get('scan_glb'))
    for to in s.get('links',[]):assert isinstance(to,str), 'links must contain scene ids'
for s in m['scenes']:
    for to in s.get('links',[]):assert to in seen, f'unknown destination {to}'
summary={'scenes':len(seen),'image_scenes':image_scenes,'scan_meshes':meshes,'missing_local_files':missing,'official_only':True,'note':'Manifest presence does not prove scan accuracy or licensing.'}
print(json.dumps(summary,ensure_ascii=False,indent=2))
if missing:sys.exit(2)
