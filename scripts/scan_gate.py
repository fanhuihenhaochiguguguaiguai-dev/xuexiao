#!/usr/bin/env python3
"""Conservative readiness gate: do not treat six cube faces as six viewpoints."""
import json,sys
from pathlib import Path
m=json.loads((Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'manifest.json').read_text('utf8'))
scenes=m.get('scenes',[])
viewpoints=[s for s in scenes if s.get('panorama') or s.get('cube_faces')]
geo=[s for s in viewpoints if isinstance(s.get('position_m'),list) and len(s['position_m'])==3]
scan=[s for s in scenes if s.get('scan_glb')]
readiness={'official_panoramic_viewpoints':len(viewpoints),'cube_faces_are_not_extra_viewpoints':True,'viewpoints_with_measured_positions':len(geo),'scanned_models_declared':len(scan),'full_campus_metric_reconstruction_proven':False,'reason':[]}
if len(viewpoints)<2:readiness['reason'].append('Need 2+ independent overlapping camera viewpoints')
if len(geo)<2:readiness['reason'].append('Camera positions/orientations need verified measurement or successful SfM estimates')
if not scan:readiness['reason'].append('No actual scanned terrain/building geometry is registered')
readiness['reason'].append('Geometry must be tested for scale, holes, navigation and licensing before a true replica claim')
print(json.dumps(readiness,ensure_ascii=False,indent=2))
