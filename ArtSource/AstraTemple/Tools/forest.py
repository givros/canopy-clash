from editor import *
from stonework import import_mesh
import json

def root_meshes(refresh=False):
    rootmat=assets.load_asset(BASE+"/Nature/Materials/M_FigBark")
    if not rootmat:raise RuntimeError("Missing fig bark")
    result=[]
    for name,point in [("SM_SanctuaryRootCascade",(71.1,14.7,28)),("SM_ForegateRootCrawl",(-56.2,5.8,4.8))]:
        folder=BASE+"/Terrain/Meshes"
        result.append(import_mesh(ROOT/"Terrain"/(name+".fbx"),folder,replace=refresh and "Foregate" in name,nanite=True,binding={"M_FigBark":rootmat}))
        actor=all_named().get(name) or place(u.StaticMeshActor,name,"Hero Trees/Architectural Roots",point)
        actor.set_actor_location(vector(point),False,True)
        actor.static_mesh_component.set_static_mesh(assets.load_asset(folder+"/"+name))
    return result

def flora(kinds=None):
    world=require_world()
    layout=json.loads((ROOT/"Terrain/Vegetation.json").read_text())
    counts={}
    for name,records in layout.items():
        if kinds and name not in kinds:continue
        mesh=assets.load_asset(BASE+"/Nature/Meshes/SM_"+name)
        if not mesh:raise RuntimeError("No mesh "+name)
        folder=BASE+"/Nature/Foliage"
        type_name="FT_"+name
        if assets.does_asset_exist(folder+"/"+type_name):
            foliage=assets.load_asset(folder+"/"+type_name)
            u.InstancedFoliageActor.remove_all_instances(world,foliage)
        else:
            foliage=u.AssetToolsHelpers.get_asset_tools().create_asset(type_name,folder,u.FoliageType_InstancedStaticMesh,u.FoliageType_InstancedStaticMeshFactory())
        foliage.set_editor_property("mesh",mesh)
        distance=0
        if name in ("Fern","Monstera","Heliconia","LianaCurtain","MossCushion"):
            distance=19000 if name in ("Fern","Monstera","LianaCurtain") else 15500
        if distance:foliage.set_editor_property("cull_distance",u.Int32Interval(int(distance*.92),distance))
        woody=name in ("StranglerFig","JungleCanopy","ArecaPalm","SandstoneCliff","FracturedCliff","WallRoots") or name.startswith("MossBoulder")
        # Foliage uses the mesh's authored trunk hull or solid cliff surface.
        if woody:
            body=foliage.get_editor_property("body_instance")
            body.set_editor_property("collision_profile_name","BlockAll")
            foliage.set_editor_property("body_instance",body)
        assets.save_loaded_asset(foliage,False)
        poses=[u.Transform(vector((x,y,z)),rotation(yaw,pitch,roll),u.Vector(sx,sy,sz)) for x,y,z,yaw,pitch,roll,sx,sy,sz in records]
        u.InstancedFoliageActor.add_instances(world,foliage,poses)
        counts[name]=len(records)
    # Replanting a visible tree also moves its matching shadow geometry.
    from foliage_runtime import TREE_NAMES, shadow_geometry
    paired=[name for name in TREE_NAMES if name.removeprefix('SM_') in counts
            and not assets.load_asset(BASE+'/Nature/Foliage/FT_'+name.removeprefix('SM_')).get_editor_property('cast_dynamic_shadow')]
    if paired:shadow_geometry(names=paired)
    return counts,save()

def escarpments():
    folder=BASE+"/Terrain"
    g=Graph(material("M_RiverGorge",folder))
    uv=g.node("TextureCoordinate")
    world=g.node("WorldPosition"); xy=g.mask(world,True,True)
    pat=assets.load_asset(BASE+"/Architecture/Materials/T_MasonryWeathering")
    broad=g.texture(pat,g.pair("Divide",xy,g.const(710)),linear=True)
    lich=g.mask(broad)
    def photo(role,normal=False,linear=False):
        return g.texture(assets.load_asset(folder+"/Textures/T_mossy_rock_"+role),uv,normal,linear)
    color=photo("Color")
    stone=g.pair("Multiply",color,g.node("Constant3Vector",constant=u.LinearColor(.72,.83,.71,1)))
    moss=g.pair("Multiply",color,g.node("Constant3Vector",constant=u.LinearColor(.38,.66,.27,1)))
    g.result(g.blend(stone,moss,lich),"BASE_COLOR")
    g.result(photo("Normal",True),"NORMAL");g.result(photo("Rough",linear=True),"ROUGHNESS","R")
    mat=g.finish()
    labels=all_named()
    for name in ("SM_WestSpringEscarpment","SM_EastSpringEscarpment"):
        import_mesh(ROOT/"Terrain"/(name+".fbx"),folder+"/Meshes",nanite=True,binding={"M_RiverGorge":mat})
        actor=labels.get(name) or place(u.StaticMeshActor,name,"Terrain/Escarpments")
        actor.static_mesh_component.set_static_mesh(assets.load_asset(folder+"/Meshes/"+name))
    return save()
