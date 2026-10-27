"""Validate a user photo ZIP once; cache by content hash, never publish originals."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def ingest(source, report):
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = ROOT / '.resource-cache/user-photos' / digest
    cache.mkdir(parents=True, exist_ok=True)
    photos = []
    with ZipFile(source) as archive:
        entries = [e for e in archive.infolist() if not e.is_dir()]
        if len(entries) > 500 or sum(e.file_size for e in entries) > 250_000_000:
            raise ValueError('Archive exceeds the photo intake budget')
        seen = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in entry.filename:
                raise ValueError('Unsafe archive member')
            if entry.file_size > 20_000_000 or name.name in seen:
                raise ValueError('Oversized or ambiguous photo member')
            seen.add(name.name)
            data = archive.read(entry)  # ZIP CRC checked by ZipFile.
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                kind, size = image.format, list(image.size)
            if kind not in ('JPEG', 'PNG', 'WEBP') or min(size) < 300:
                raise ValueError('Unusable photo format or resolution')
            sha = hashlib.sha256(data).hexdigest()
            local = cache / name.name
            hit = local.is_file() and hashlib.sha256(local.read_bytes()).hexdigest() == sha
            if not hit:
                local.write_bytes(data)
            photos.append({'name': name.name, 'sha256': sha, 'bytes': len(data),
                           'format': kind, 'dimensions': size, 'decoded': True,
                           'cache_hit': hit, 'local_path': str(local.relative_to(ROOT))})
    result = {'archive_name': 'campus_photos_updated.zip', 'archive_sha256': digest,
              'source': 'USER_UPLOAD_2026_10_27', 'rights': 'USER_PROVIDED_REFERENCE_ONLY_ORIGINALS_NOT_REDISTRIBUTED',
              'photogrammetry_qualified': False,
              'reason': 'Sparse viewpoints/screenshots without calibrated overlap; no validated depth.',
              'photos': photos, 'passed': bool(photos)}
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, default=ROOT / 'reports/uploaded-photos-v07.json')
    args = parser.parse_args()
    result = ingest(args.archive, args.report)
    print(json.dumps({'passed': result['passed'], 'photos': len(result['photos']),
                      'cache_hits': sum(p['cache_hit'] for p in result['photos']),
                      'archive_sha256': result['archive_sha256']}))
