"""Preserve the in-project Epic rifle surfaces and detach its original magazine island."""
from pathlib import Path
from collections import defaultdict
import json
import unreal as u

assets=u.EditorAssetLibrary
source=assets.load_asset("/Game/Weapons/Rifle/Meshes/SKM_Rifle")
directory="/Game/TempleTDM/Presentation"
assets.make_directory(directory)


def variant(original,name):
    dest=directory+"/"+name
    return assets.load_asset(dest) if assets.does_asset_exist(dest) else assets.duplicate_asset(original,dest)


def import_lod():
    mesh=u.DynamicMesh()
    _,outcome=u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(source,mesh,u.GeometryScriptCopyMeshFromAssetOptions(),u.GeometryScriptMeshReadLOD())
    if outcome!=u.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError(str(outcome))
    return mesh


def select_island(mesh):
    _,vector_list,_=mesh.get_all_vertex_positions(False)
    _,triangle_list,_=mesh.get_all_triangle_indices(False)
    vertices=[(v.x,v.y,v.z) for v in vector_list.convert_vector_list_to_array()]
    triangles=[(t.x,t.y,t.z) for t in triangle_list.convert_triangle_list_to_array()]
    parents=list(range(len(vertices)))
    def find(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]]
            i=parents[i]
        return i
    def union(a,b):
        parents[find(a)]=find(b)
    seams={}
    for i,pos in enumerate(vertices):
        key=tuple(round(x,3) for x in pos)
        if key in seams:union(i,seams[key])
        seams[key]=i
    groups=defaultdict(list)
    for a,b,c in triangles:
        if a>=0:union(a,b);union(b,c)
    for i,(a,b,c) in enumerate(triangles):
        if a>=0:groups[find(a)].append(i)
    found=[]
    for ids in groups.values():
        positions=[vertices[v] for i in ids for v in triangles[i]]
        low=[min(p[k] for p in positions) for k in range(3)]
        high=[max(p[k] for p in positions) for k in range(3)]
        # This enclosed original island sits directly below the well. The mouth remains on the receiver.
        if -11.5<low[2]<-10 and .2<high[2]<1.3 and 6.8<high[1]-low[1]<9.0 and 2.1<high[0]-low[0]<2.7:
            found.append((ids,low,high))
    if len(found)!=1:raise RuntimeError("Expected exactly one original magazine island, found "+str(len(found)))
    ids,low,high=found[0]
    return set(ids),{i for i,t in enumerate(triangles) if t[0]>=0},low,high


def remove(mesh,indices):
    _,selection=mesh.convert_index_array_to_mesh_selection(sorted(indices),u.GeometryScriptMeshSelectionType.TRIANGLES)
    _,count=mesh.delete_selected_triangles_from_mesh(selection)
    if count!=len(indices):raise RuntimeError("Triangle selection did not survive the split.")


part=import_lod(); ids,whole,minimum,maximum=select_island(part)
receiver=import_lod()
remove(part,whole-ids)
remove(receiver,ids)
body=variant("/Game/Weapons/Rifle/Meshes/SKM_Rifle","SKM_CanopyReceiver")
clip=variant("/Game/Weapons/Rifle/Meshes/SM_Rifle","SM_CanopyMagazine")
nanite=clip.get_editor_property("nanite_settings")
nanite.set_editor_property("enabled",False)
clip.set_editor_property("nanite_settings",nanite)
opts=u.GeometryScriptCopyMeshToAssetOptions()
_,body_ok=u.GeometryScript_AssetUtils.copy_mesh_to_skeletal_mesh(receiver,body,opts,u.GeometryScriptMeshWriteLOD())
_,part_ok=u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(part,clip,opts,u.GeometryScriptMeshWriteLOD())
if body_ok!=u.GeometryScriptOutcomePins.SUCCESS or part_ok!=u.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError("Native mesh rebuild failed")
clip.set_material(0,source.materials[0].material_interface)
for asset in [body,clip]:assets.save_loaded_asset(asset,False)
out=Path(__file__).resolve().parents[3]/"Saved/Deathmatch/ReloadSculpt"
out.mkdir(parents=True,exist_ok=True)
component=u.SkeletalMeshComponent()
component.set_skeletal_mesh_asset(body)
(out/'MeshSplit.json').write_text(json.dumps(dict(original_triangles=len(whole),receiver_triangles=len(whole-ids),magazine_triangles=len(ids),bounds_cm=[minimum,maximum],receiver_lods=component.get_num_lods(),magazine_lods=clip.get_num_lods(),assets=[body.get_path_name(),clip.get_path_name()]),indent=2))
