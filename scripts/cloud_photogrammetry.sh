#!/usr/bin/env bash
# Usage: bash scripts/cloud_photogrammetry.sh /absolute/authorized_dataset
# The following software must already exist on the cloud runner; no downloads occur.
set -euo pipefail
DATASET="${1:-}"
if [[ -z "$DATASET" || ! -d "$DATASET/images" ]]; then
  echo 'ERROR: expected dataset/images with legally obtained 2:1 spherical panoramas (independent camera viewpoints).' >&2
  exit 2
fi
if ! command -v opensfm >/dev/null 2>&1; then
  echo 'ERROR: OpenSfM CLI is not installed on this cloud runner; no fallback invented.' >&2
  exit 3
fi
mapfile -d '' panoramas < <(find "$DATASET/images" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) -print0)
if (( ${#panoramas[@]} < 2 )); then
  echo 'ERROR: need overlapping images from two or more DIFFERENT panorama viewpoints.' >&2
  exit 4
fi
if [[ ! -f "$DATASET/camera_models.json" ]]; then
  echo 'ERROR: camera_models.json with verified spherical camera convention is required.' >&2
  echo 'Do not let unknown camera orientation/projection silently become a pinhole model.' >&2
  exit 5
fi
if [[ ! -f "$DATASET/config.yaml" ]] || ! grep -Eq '^[[:space:]]*use_exif_size:' "$DATASET/config.yaml"; then
  echo 'CAUTION: validate spherical camera and SfM dataset config before running.' >&2
fi
mkdir -p "$DATASET/validation"
printf 'Stage: feature extraction / matching / sparse reconstruction. NOT a ready-to-walk campus model.\n' | tee "$DATASET/validation/STATUS.txt"
opensfm extract_metadata "$DATASET"
opensfm detect_features "$DATASET"
opensfm match_features "$DATASET"
opensfm create_tracks "$DATASET"
opensfm reconstruct "$DATASET"
if [[ ! -s "$DATASET/reconstruction.json" ]]; then
  echo 'NO SUCCESSFUL SFM RECONSTRUCTION: camera overlap/geometry insufficient or poses could not be recovered.' | tee -a "$DATASET/validation/STATUS.txt"
  exit 6
fi
opensfm export_ply "$DATASET"
cat >> "$DATASET/validation/STATUS.txt" <<'STATUS'
Sparse reconstruction exists. This is a point cloud, not a collision-ready building mesh.
Next stages (not automated): verify camera poses, add metric scale control points,
obtain dense point cloud and mesh, eliminate holes, ground test, license review,
then export an actual scanned GLB and register it in manifest.json.
STATUS
