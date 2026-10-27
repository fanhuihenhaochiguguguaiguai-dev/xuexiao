"""Align the raised entrance with a separate plinth and 3m storeys."""
def align_library(scene,height=1.8,body_already_shifted=False):
 import bpy
 if scene.get('v06_library_entry_aligned'):return
 body=bpy.data.objects['B13_library'];foundation=body.copy();foundation.data=body.data.copy();foundation.name='B13_library_plinth';scene.collection.objects.link(foundation);low=min(v.co.z for v in foundation.data.vertices);span=max(v.co.z for v in foundation.data.vertices)-low
 for vert in foundation.data.vertices:vert.co.z=.16+(vert.co.z-low)*height/span
 foundation['building_index']=13;foundation['dimension_status']='ESTIMATED_RAISED_ENTRANCE_BASE_NOT_A_STOREY'
 if not body_already_shifted:
  for vert in body.data.vertices:vert.co.z+=height
 detail=bpy.data.objects['Library_refined_details']
 for face in detail.data.polygons:
  vertices=[detail.data.vertices[i] for i in face.vertices];lo=min(v.co.z for v in vertices);hi=max(v.co.z for v in vertices)
  if abs(lo-1.96)<.015 and abs(hi-4.06)<.015:continue
  if abs(lo-1.96)<.015 and hi>26:
   for vert in vertices:
    if vert.co.z>26:vert.co.z+=height
  else:
   for vert in vertices:vert.co.z+=height
 sign=bpy.data.objects.get('Library_v06_name')
 if sign:sign.location.z+=height
 scene['v06_library_entry_aligned']=True
