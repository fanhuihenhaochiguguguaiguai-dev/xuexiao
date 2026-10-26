import json,tempfile,unittest,struct,hashlib
from unittest.mock import patch
from pathlib import Path
from automation.pipeline import Pipeline,expand_tasks
from automation import drivers
from automation.quality import glb_gate

class FixtureDrivers:
 def __init__(self):self.calls=[];self.version='v1';self.fail={};self.mutate=False
 def fingerprint(self,job,root,tools):return {'version':self.version if job['driver']=='probe_fixture' else 'stable'}
 def run(self,job,root,stage,inputs,deps,tools):
  self.calls.append(job['id'])
  if job['id'] in self.fail:raise self.fail[job['id']]
  text=self.version if job['driver']=='probe_fixture' else job.get('params',{}).get('text','constant')
  if job.get('params',{}).get('echo_input'):text=inputs['source'].read_text()
  (stage/'result.txt').write_text(text)
  if self.mutate and inputs:next(iter(inputs.values())).write_text('unexpected source mutation')

class PipelineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'configs').mkdir();(self.root/'source.txt').write_text('original');self.registry=FixtureDrivers()
 def tearDown(self):self.tmp.cleanup()
 def task(self,id='one',**kwargs):return {'id':id,'driver':'fixture','outputs':['result.txt'],**kwargs}
 def runner(self,tasks,**extra):
  p=self.root/'configs/pipeline.json';p.write_text(json.dumps({'schema_version':1,'tasks':tasks,'policy':{'max_attempts':2},**extra}));return Pipeline(p,registry=self.registry)
 def test_input_digest_and_cache_hit(self):
  tasks=[self.task(inputs={'source':'source.txt'},params={'echo_input':True})]
  r=self.runner(tasks).run();first=r['tasks']['one']['key'];self.assertEqual(r['counts']['SUCCESS'],1)
  r=self.runner(tasks).run();self.assertEqual(r['counts']['CACHED'],1);self.assertEqual(len(self.registry.calls),1)
  (self.root/'source.txt').write_text('changed');r=self.runner(tasks).run();self.assertNotEqual(first,r['tasks']['one']['key']);self.assertEqual(len(self.registry.calls),2)
 def test_tampered_cache_is_quarantined_and_rebuilt(self):
  tasks=[self.task()];r=self.runner(tasks).run();p=Path(r['tasks']['one']['artifact'])/'result.txt';p.write_text('tampered')
  r=self.runner(tasks).run();self.assertEqual(r['tasks']['one']['status'],'SUCCESS');self.assertTrue(r['tasks']['one']['repaired_corrupt_cache']);self.assertEqual(p.read_text(),'constant')
 def test_tool_version_invalidates_dependants(self):
  tasks=[self.task('tool',driver='probe_fixture'),self.task('one',needs=['tool'])]
  a=self.runner(tasks).run();self.registry.version='v2';b=self.runner(tasks).run();self.assertNotEqual(a['tasks']['one']['key'],b['tasks']['one']['key']);self.assertEqual(b['counts']['SUCCESS'],2)
 def test_same_dependency_output_avoids_unnecessary_downstream_recompute(self):
  tasks=[self.task('up',inputs={'source':'source.txt'}),self.task('down',needs=['up'])]
  self.runner(tasks).run();(self.root/'source.txt').write_text('new annotation, same result');r=self.runner(tasks).run();self.assertEqual(r['tasks']['up']['status'],'SUCCESS');self.assertEqual(r['tasks']['down']['status'],'CACHED')
 def test_cycle_rejected_before_execution(self):
  with self.assertRaises(drivers.Failure) as c:self.runner([self.task('a',needs=['b']),self.task('b',needs=['a'])])
  self.assertEqual(c.exception.code,'CYCLE');self.assertEqual(self.registry.calls,[])
 def test_shared_root_cause_blocks_only_dependants(self):
  tasks=[self.task('tool'),self.task('a',needs=['tool']),self.task('b',needs=['tool']),self.task('independent')];self.registry.fail['tool']=drivers.Failure('ENVIRONMENT','TOOL_MISSING','missing Blender')
  r=self.runner(tasks).run();self.assertEqual(r['tasks']['independent']['status'],'SUCCESS');self.assertNotIn('a',self.registry.calls);self.assertEqual(r['failure_groups']['ENVIRONMENT']['root_tasks'],['tool']);self.assertEqual(r['tasks']['a']['attempts'] if 'attempts' in r['tasks']['a'] else 0,0)
 def test_quality_failure_halts_batch_without_replacing_last_release(self):
  tasks=[self.task('a',group='batch',inputs={'source':'source.txt'}),self.task('b',group='batch')]
  previous=self.runner(tasks).run();active=(self.root/'.campus-cache/active.json').read_bytes();(self.root/'source.txt').write_text('new input');self.registry.fail['a']=drivers.Failure('QUALITY','MODEL_GATE','bad geometry')
  r=self.runner(tasks).run();self.assertFalse(r['passed']);self.assertEqual(r['tasks']['a']['attempts'],1);self.assertEqual(r['tasks']['b']['status'],'BLOCKED');self.assertEqual((self.root/'.campus-cache/active.json').read_bytes(),active)
  self.runner(tasks).rollback(previous['run_id']);self.assertEqual(json.loads((self.root/'.campus-cache/active.json').read_text())['run_id'],previous['run_id'])
 def test_timeout_retries_are_bounded(self):
  self.registry.fail['one']=drivers.Failure('ENVIRONMENT','TIMEOUT','simulated timeout');r=self.runner([self.task()]).run();self.assertEqual(r['tasks']['one']['attempts'],2);self.assertEqual(len(self.registry.calls),2)
 def test_source_mutation_is_rejected(self):
  self.registry.mutate=True;r=self.runner([self.task(inputs={'source':'source.txt'})]).run();self.assertEqual(r['tasks']['one']['category'],'INTEGRITY');self.assertFalse(r['promoted'])
 def test_partial_pilot_cannot_replace_full_release(self):
  tasks=[self.task('a',inputs={'source':'source.txt'}),self.task('b')]
  runner=self.runner(tasks,release_targets=['a','b']);runner.run();active=(self.root/'.campus-cache/active.json').read_bytes();(self.root/'source.txt').write_text('changed');r=runner.run(['a']);self.assertTrue(r['passed']);self.assertFalse(r['promoted']);self.assertEqual((self.root/'.campus-cache/active.json').read_bytes(),active)
 def test_rollback_refuses_corrupt_prior_artifact(self):
  runner=self.runner([self.task()]);r=runner.run();(Path(r['tasks']['one']['artifact'])/'result.txt').write_text('corrupt')
  with self.assertRaises(drivers.Failure):runner.rollback(r['run_id'])
 def test_rollback_cannot_bypass_partial_release_gate(self):
  runner=self.runner([self.task('a'),self.task('b')],release_targets=['a','b']);runner.run();active=(self.root/'.campus-cache/active.json').read_bytes();partial=runner.run(['a'])
  with self.assertRaises(drivers.Failure) as error:runner.rollback(partial['run_id'])
  self.assertEqual(error.exception.code,'ROLLBACK_PARTIAL');self.assertEqual((self.root/'.campus-cache/active.json').read_bytes(),active)
 def test_single_panorama_station_is_not_multiview_input(self):
  p=self.root/'photos.json';p.write_text(json.dumps({'independent_capture_positions':['same_station']*6,'overlap_verified':True,'projection_adapter_verified':True}));self.assertEqual(drivers.route(None,p)['decision'],'NEED_DATA')
  p.write_text(json.dumps({'independent_capture_positions':['a','b','c'],'overlap_verified':True,'projection_adapter_verified':True}));self.assertEqual(drivers.route(None,p)['decision'],'NEED_DATA')
 def test_image_bytes_are_required_and_only_route_to_a_candidate(self):
  images=[]
  for i in range(3):
   data=b'\x89PNG\r\n\x1a\n'+bytes([i])*30;f=self.root/f'{i}.png';f.write_bytes(data);images.append({'path':f.name,'sha256':hashlib.sha256(data).hexdigest(),'capture_position':str(i)})
  p=self.root/'photos.json';p.write_text(json.dumps({'images':images,'overlap_verified':True,'projection_adapter_verified':True}));r=drivers.route(None,p);self.assertEqual(r['decision'],'RECONSTRUCTION_CANDIDATE');self.assertFalse(r['automatic_execution_enabled'])
 def test_integrity_batch_block_is_grouped_under_the_same_root_cause(self):
  self.registry.fail['a']=drivers.Failure('INTEGRITY','HASH_MISMATCH','bad bytes');r=self.runner([self.task('a',group='batch'),self.task('b',group='batch')]).run();self.assertEqual(set(r['failure_groups']),{'INTEGRITY'});self.assertEqual(r['failure_groups']['INTEGRITY']['root_tasks'],['a'])
 def test_known_source_copy_avoids_network(self):
  source=self.root/'source.txt';stage=self.root/'stage';stage.mkdir();job={'driver':'fetch_asset','params':{'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'url':'https://raw.githubusercontent.com/example/file','license':'CC0'}}
  with patch('urllib.request.build_opener',side_effect=AssertionError('network must not be used')):drivers.run(job,self.root,stage,{'existing':source},{},{})
  self.assertEqual((stage/'asset.bin').read_bytes(),source.read_bytes());self.assertEqual(json.loads((stage/'provenance.json').read_text())['origin'],'VERIFIED_EXISTING_COPY')
 def test_download_requires_known_hash_and_allowed_public_host(self):
  stage=self.root/'stage';stage.mkdir()
  for params in [{'sha256':'unknown'},{'sha256':'0'*64,'url':'http://127.0.0.1/private'}]:
   with self.assertRaises(drivers.Failure):drivers.run({'driver':'fetch_asset','params':params},self.root,stage,{}, {},{})
 def test_batch_template_preserves_typed_numbers_and_arrays(self):
  config={'tasks':[],'task_templates':{'model':[{'id':'model.${id}','params':{'building_id':'${number}','extra':'${extra}'}}]},'batches':[{'template':'model','items':[{'id':'13','number':13,'extra':['canopy']}]}]}
  tasks=expand_tasks(config);self.assertEqual(tasks[0]['id'],'model.13');self.assertEqual(tasks[0]['params']['building_id'],13);self.assertEqual(tasks[0]['params']['extra'],['canopy'])
 def test_unbound_template_parameter_fails_before_execution(self):
  with self.assertRaises(drivers.Failure):expand_tasks({'task_templates':{'t':[{'id':'${missing}'}]},'batches':[{'template':'t','items':[{}]}]})

def make_glb(points,indices=None):
 indices=indices or [0,1,2,0,3,1,0,2,3,1,3,2];position=struct.pack('<12f',*(v for point in points for v in point));index=struct.pack('<12H',*indices);binary=position+index
 doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(binary)}],'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':len(position)},{'buffer':0,'byteOffset':len(position),'byteLength':len(index)}],
 'accessors':[{'bufferView':0,'componentType':5126,'count':4,'type':'VEC3','min':[-999,-999,-999],'max':[999,999,999]},{'bufferView':1,'componentType':5123,'count':12,'type':'SCALAR'}],
 'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}]}
 data=json.dumps(doc).encode();data+=b' '*((-len(data))%4);total=12+8+len(data)+8+len(binary)
 return struct.pack('<4sII',b'glTF',2,total)+struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(binary),0x004e4942)+binary

class GeometryGateTests(unittest.TestCase):
 def check(self,data):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'test.glb';p.write_bytes(data);return glb_gate(p)
 def test_real_position_buffer_is_used_instead_of_claimed_json_bounds(self):
  self.assertTrue(self.check(make_glb([(0,0,0),(1,0,0),(0,1,0),(0,0,1)]))['passed'])
  with self.assertRaises(ValueError):self.check(make_glb([(0,0,0)]*4))
 def test_nan_indices_and_truncation_are_rejected(self):
  for data in [make_glb([(float('nan'),0,0),(1,0,0),(0,1,0),(0,0,1)]),make_glb([(0,0,0),(1,0,0),(0,1,0),(0,0,1)],[0,1,99]*4),make_glb([(0,0,0),(1,0,0),(0,1,0),(0,0,1)])[:-1]]:
   with self.subTest():
    with self.assertRaises(ValueError):self.check(data)

if __name__=='__main__':unittest.main()
