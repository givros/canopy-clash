"""Build, update and place the authored water features in the current Unreal level."""
import math
import unreal as ue
import water_geometry as geo
from water_materials import ROOT


def mesh_buffer(feature):
    source=feature.shape
    buffers=ue.GeometryScriptSimpleMeshBuffers()
    n=len(source.positions)
    normals=[[0.,0.,0.] for _ in range(n)]
    for a,b,c in source.faces:
        pa,pb,pc=[source.positions[i] for i in (a,b,c)]
        x,y,z=[pc[j]-pa[j] for j in range(3)]
        u,v,w=[pb[j]-pa[j] for j in range(3)]
        nx,ny,nz=y*w-z*v,z*u-x*w,x*v-y*u
        for k in (a,b,c):
            normal=normals[k]
            normal[0]+=nx; normal[1]+=ny; normal[2]+=nz
    unit=[]
    for x,y,z in normals:
        length=math.sqrt(x*x+y*y+z*z)
        unit.append(ue.Vector(x/length,y/length,z/length) if length>1e-10 else ue.Vector(0,0,1))
    px,py,pz=feature.pivot
    buffers.set_editor_properties({
        "vertices":[ue.Vector(100*(x-px),100*(y-py),100*(z-pz)) for x,y,z in source.positions],
        "triangles":[ue.IntVector(a,b,c) for a,b,c in source.faces],
        "uv0":[ue.Vector2D(u,v) for u,v in source.uvs],
        "normals":unit,
        "vertex_colors":[ue.LinearColor(*c) for c in source.colors]
    })
    return buffers


def save_feature(feature):
    path=ROOT+"/SM_"+feature.name
    dm=ue.new_object(ue.DynamicMesh)
    dm.append_buffers_to_mesh(mesh_buffer(feature))
    expected=len(feature.shape.faces)
    if dm.get_triangle_count()!=expected:
        raise RuntimeError((path,dm.get_triangle_count(),expected))
    lib=ue.EditorAssetLibrary
    mat=ue.load_asset(ROOT+"/"+feature.material)
    if not mat:
        raise RuntimeError(feature.material)
    if lib.does_asset_exist(path):
        asset=ue.load_asset(path)
        opts=ue.GeometryScriptCopyMeshToAssetOptions()
        opts.set_editor_properties({"enable_recompute_normals":False,"enable_recompute_tangents":True})
        _,outcome=ue.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
            dm,asset,opts,ue.GeometryScriptMeshWriteLOD(),True)
    else:
        opts=ue.GeometryScriptCreateNewStaticMeshAssetOptions()
        opts.set_editor_properties({"enable_collision":False,"enable_nanite":False,
                                    "enable_recompute_normals":False,"enable_recompute_tangents":True})
        asset,outcome=ue.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dm,path,opts)
    if not asset or outcome!=ue.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError((path,str(outcome)))
    asset.set_material(0,mat)
    if not lib.save_loaded_asset(asset,False):
        raise RuntimeError(path)
    return (feature.name,expected)


async def build(only=None):
    import asyncio
    ret=[]
    for feature in geo.features(only):
        ret.append(save_feature(feature))
        await asyncio.sleep(0)
    return ret


def placement():
    yield "ReflectionPool",(-22,0,0),"Basins"
    yield "ReflectionPoolBed",(-22,0,-2),"Basins"
    yield "LotusShelves",(-34,4,0),"Flora"
    for side,points in geo.CHANNELS.items():
        yield side+"TierPools",points[3][:3],"Basins"
        yield side+"PoolBeds",points[3][:3],"Basins"
        n=0
        for a,b in zip(points,points[1:]):
            if a[2]==b[2]:
                continue
            n+=1
            name=f"{side}Falls{n:02}"
            yield name,a[:3],"Cascades"
            yield name+"Whitewater",b[:3],"Whitewater"
            yield name+"Spray",b[:3],"Spray"


def assemble(only=None):
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    existing={a.get_actor_label():a for a in actors.get_all_level_actors()
              if str(a.get_folder_path()).startswith("AstraTemple/Water")}
    names=[]
    for name,pivot,group in placement():
        if only and not name.startswith(only):
            continue
        mesh=ue.load_asset(ROOT+"/SM_"+name)
        if not mesh:
            raise RuntimeError("Missing water mesh "+name)
        label="Water_"+name
        location=ue.Vector(*(v*100. for v in pivot))
        actor=existing.get(label)
        if actor is None:
            actor=actors.spawn_actor_from_object(mesh,location)
        else:
            actor.set_actor_location(location,False,False)
            actor.static_mesh_component.set_static_mesh(mesh)
        actor.set_actor_label(label)
        actor.set_folder_path("AstraTemple/Water/"+group)
        comp=actor.static_mesh_component
        comp.set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
        comp.set_cast_shadow(group=="Flora" or name.endswith("Bed") or name.endswith("Beds"))
        if group in ("Cascades","Whitewater","Spray"):
            comp.set_editor_property("translucency_sort_priority",{"Cascades":0,"Whitewater":1,"Spray":2}[group])
        names.append(label)
    return names
