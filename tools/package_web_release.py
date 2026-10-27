"""Package the existing static app for any authorized HTTPS host; no source fork."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verified_browser_hashes():
    photo_path=ROOT/'reports/photo-projection-browser.json'
    if photo_path.exists():
        photo=json.loads(photo_path.read_text())
        if photo.get('passed') and all(sha(ROOT/p)==h for p,h in photo['sourceHashes'].items()):
            assert photo['allRequestsSameOrigin'] and photo['collisionDataIdentical']
            assert photo['unchangedControlCameraWaterDetectorAlgorithms']
            for name in ['photo-projection-physical','photo-projection-reimport']:
                assert json.loads((ROOT/'reports'/f'{name}.json').read_text())['passed']
            gates=json.loads((ROOT/'reports/photo-projection-gates.json').read_text())
            for name,path in [('HenanCampus.glb',ROOT/'assets/henan_campus/project/HenanCampus.glb'),('library.glb',ROOT/'game/dist/assets/zones/b13.glb'),('campus-base.glb',ROOT/'game/dist/assets/campus.glb')]:
                assert gates[name]['passed'] and sha(path)==gates[name]['sha256']
            # The browser exercised the changed library. The remaining zones must
            # still be the exact previously accepted inputs, not unchecked edits.
            others=sorted((ROOT/'game/dist/assets/zones').glob('*.glb'))
            assert len(others)==20
            for path in others:
                if path.name=='b13.glb':continue
                prior=subprocess.run(['git','show',photo['baseline']+':'+str(path.relative_to(ROOT))],cwd=ROOT,check=True,capture_output=True).stdout
                assert hashlib.sha256(prior).hexdigest()==sha(path),'Unverified zone change: '+path.name
            return photo['sourceHashes']
    browser=json.loads((ROOT/'reports/v07-browser.json').read_text())
    assert browser['passed'] and browser['allRequestsSameOrigin']
    accepted=browser['sourceHashes']
    if not all(sha(ROOT/p)==h for p,h in accepted.items()):
        followup=json.loads((ROOT/'reports/v07-visual-revalidation.json').read_text())
        assert followup['passed'] and followup['baseSourceHashes']==accepted
        assert followup['geometryAndRoundtripPassed'] and followup['navigationPassed']
        assert set(followup['changedInputs']) <= {'game/dist/assets/world.json','game/dist/assets/zones/b13.glb','game/dist/assets/campus.glb'}
        accepted=followup['sourceHashes']
    return accepted
def package(output):
    dist=ROOT/'game/dist';accepted=verified_browser_hashes()
    assert all(sha(ROOT/p)==h for p,h in accepted.items()),'Browser acceptance is stale'
    manifest=json.loads((dist/'assets/asset-manifest.json').read_text())
    assert all(sha(dist/'assets'/f['path'])==f['sha256'] for f in manifest['files']),'Asset manifest is stale'
    paths=sorted(p for p in dist.rglob('*') if p.is_file());docs=[ROOT/'docs/china-hosting.md',ROOT/'docs/static-host-nginx.conf'];fingerprint=hashlib.sha256((''.join(str(p.relative_to(dist))+sha(p) for p in paths)+''.join(sha(p) for p in docs)).encode()).hexdigest()
    report_path=ROOT/'reports/static-release.json';old=json.loads(report_path.read_text()) if report_path.exists() else {}
    if old.get('content_fingerprint')==fingerprint and output.exists() and sha(output)==old.get('zip_sha256'):
        print(json.dumps({'status':'CACHED','files':len(paths),'sha256':old['zip_sha256']}));return
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in paths:archive.write(p,str(p.relative_to(dist)))
        archive.write(ROOT/'docs/china-hosting.md','部署说明.md')
        archive.write(ROOT/'docs/static-host-nginx.conf','nginx-example.conf')
    with zipfile.ZipFile(output) as archive:assert archive.testzip() is None
    build=re.search(r"export const BUILD_ID='([^']+)'",(ROOT/'game/performance-core.js').read_text()).group(1)
    result={'build':build,'content_fingerprint':fingerprint,'zip_sha256':sha(output),'zip_bytes':output.stat().st_size,'runtime_files':len(paths),'original_reference_photos_included':False,'browser_all_requests_same_origin':True,'china_network_verified':False,'deployment_status':'READY_FOR_AUTHORIZED_HTTPS_HOST_NOT_DEPLOYED_IN_CHINA'}
    report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');output.with_suffix(output.suffix+'.sha256').write_text(result['zip_sha256']+'  '+output.name+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('/workspace/output/河南经贸_国内静态部署.zip'));package(parser.parse_args().output)
