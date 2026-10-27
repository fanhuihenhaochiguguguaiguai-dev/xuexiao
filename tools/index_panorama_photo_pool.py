"""Index existing face caches by capture point; never redownload or inflate viewpoints."""
import hashlib,json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BASE=Path('/workspace/henan_campus');scenes=json.loads((BASE/'metadata/scene_index.json').read_text())['scenes'];entries=[];missing=[]
for scene in scenes:
    for face in ['f','b','l','r','u','d']:
        path=BASE/'resources/panorama_cubefaces'/scene['scene_id']/(face+'.jpg')
        alias=False
        if not path.is_file() and scene['scene_id']=='scene_a449101eb4c7b224' and face=='f':path=Path('/workspace/campus_source_cache/public_panorama/south_gate_cube_front.jpg');alias=True
        if not path.is_file():missing.append({'scene':scene['scene_id'],'face':face});continue
        with Image.open(path) as im:kind,size=im.format,list(im.size)
        assert kind=='JPEG' and min(size)>=768
        entries.append({'capture_point':scene['scene_id'],'title':scene['title'],'face':face,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'format':kind,'dimensions':size,'existing_cache_alias':alias,'source_url':scene['panorama_template'].replace('%s',face),'role':'REFERENCE_OR_REQUESTED_DERIVATIVE_TEXTURE_INPUT_NOT_INDEPENDENT_CAMERA'})
report={'source':'https://www.ivrpano.com/p/2b89e1f8b87d40ad','capture_points':len(scenes),'expected_faces':len(scenes)*6,'cached_faces':len(entries),'missing':missing,'new_downloads':0,'images_are_not_324_independent_photogrammetry_views':True,'originals_redistributed':False,'pano_reference_date':'2017-08-11; do not assume current planting or renovations','entries':entries}
(ROOT/'reports/panorama-photo-pool.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='entries'},ensure_ascii=False))
