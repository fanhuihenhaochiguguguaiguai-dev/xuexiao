from pathlib import Path
import os
import bpy,json
P=Path(os.environ.get('CAMPUS_ASSET_ROOT', str(Path(__file__).resolve().parents[1])))/'character/output'
bpy.ops.wm.open_mainfile(filepath=str(P/'CampusExplorer.blend'));bpy.context.preferences.filepaths.save_version=0
rig=bpy.data.objects['Campus_character_rig'];scene=bpy.context.scene
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1)
ob=bpy.data.objects['Clothing_straight_jeans'];triangles=sum(len(f.vertices)-2 for f in ob.data.polygons)
if triangles<=12000:
 print('PANTS_ALREADY_WITHIN_BUDGET',triangles,flush=True)
 raise SystemExit(0)
bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
mod=ob.modifiers.new('Pants_mobile_budget','DECIMATE');mod.ratio=min(1,10000/triangles);mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
 if o.type in ['MESH','ARMATURE']:o.select_set(True)
bpy.context.view_layer.objects.active=rig
for tr in rig.animation_data.nla_tracks:tr.mute=False
rig.animation_data.action=None
bpy.ops.export_scene.gltf(filepath=str(P/'CampusExplorer.glb'),export_format='GLB',use_selection=True,export_skins=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(P/'CampusExplorer.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},bake_anim=True,add_leaf_bones=False,path_mode='COPY',embed_textures=True)
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(P/'CampusExplorer.blend'),compress=True)
r=json.loads((P/'character_report.json').read_text());r['mesh_triangles_total']=sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in scene.objects if o.type=='MESH');r['pants_triangles']=sum(len(f.vertices)-2 for f in ob.data.polygons);(P/'character_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
scene.render.filepath=str(P/'character_preview.png');bpy.ops.render.render(write_still=True)
print('CHARACTER_LOD',r['mesh_triangles_total'],r['pants_triangles'],flush=True)
