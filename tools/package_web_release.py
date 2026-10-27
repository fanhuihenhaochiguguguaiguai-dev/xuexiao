"""Package the existing static app for any authorized HTTPS host; no source fork."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def package(output):
    dist=ROOT/'game/dist';browser=json.loads((ROOT/'reports/v07-browser.json').read_text())
    assert browser['passed'] and browser['allRequestsSameOrigin']
    assert all(sha(ROOT/p)==h for p,h in browser['sourceHashes'].items()),'Browser acceptance is stale'
    paths=sorted(p for p in dist.rglob('*') if p.is_file());fingerprint=hashlib.sha256(''.join(str(p.relative_to(dist))+sha(p) for p in paths).encode()).hexdigest()
    report_path=ROOT/'reports/static-release.json';old=json.loads(report_path.read_text()) if report_path.exists() else {}
    if old.get('content_fingerprint')==fingerprint and output.exists() and sha(output)==old.get('zip_sha256'):
        print(json.dumps({'status':'CACHED','files':len(paths),'sha256':old['zip_sha256']}));return
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in paths:archive.write(p,str(p.relative_to(dist)))
        archive.write(ROOT/'docs/china-hosting.md','部署说明.md')
        archive.write(ROOT/'docs/static-host-nginx.conf','nginx-example.conf')
    with zipfile.ZipFile(output) as archive:assert archive.testzip() is None
    result={'build':'campus-v07-20261027-1','content_fingerprint':fingerprint,'zip_sha256':sha(output),'zip_bytes':output.stat().st_size,'runtime_files':len(paths),'original_reference_photos_included':False,'browser_all_requests_same_origin':True,'china_network_verified':False,'deployment_status':'READY_FOR_AUTHORIZED_HTTPS_HOST_NOT_DEPLOYED_IN_CHINA'}
    report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');output.with_suffix(output.suffix+'.sha256').write_text(result['zip_sha256']+'  '+output.name+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('/workspace/output/河南经贸_国内静态部署.zip'));package(parser.parse_args().output)
