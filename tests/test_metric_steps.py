import unittest
from collections import Counter
from tools.metric_steps import stepped_stand

class MetricStepsTests(unittest.TestCase):
 def test_closed_stand_has_no_coincident_internal_faces_or_open_edges(self):
  v,faces=stepped_stand((0,0,0),(1,0,0),(0,1,0),137.485,11.249)
  edges=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
  self.assertEqual(set(edges.values()),{2})
  self.assertEqual(len({tuple(p) for p in v}),len(v))
  self.assertEqual(len({tuple(sorted(f)) for f in faces}),len(faces))
  self.assertAlmostEqual(max(p[2] for p in v)-min(p[2] for p in v),3)
 def test_central_aisle_risers_stay_within_character_autostep_budget(self):
  v,_=stepped_stand((0,0,0),(1,0,0),(0,1,0),137.485,11.249)
  heights=sorted({round(p[2],8) for p in v if abs(p[0])<2})
  self.assertGreater(len(heights),10)
  self.assertLess(max(b-a for a,b in zip(heights,heights[1:])),.3)
