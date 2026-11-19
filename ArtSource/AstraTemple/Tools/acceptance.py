"""Inspect the saved Unreal world and its physical support through Epic's MCP."""
from collections import Counter
import json
import math
import editor as e
import unreal as u


def write(name, data):
    (e.ROOT/name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def point(vec):
    return [round(x/100, 3) for x in (vec.x, vec.y, vec.z)]


def review_cameras():
    names=e.all_named()
    for label,pos,yaw,pitch,fov in [
        ("PortalDetail",(41.0,-11.0,27.8),21,23,48),
        ("CrownShrine",(112,-83,66.8),26,14,69),
        ("Grotto",(108,-12,31.4),-45,5,76),
    ]:
        a=names.get("View_"+label) or e.place(u.CameraActor,"View_"+label,"Cameras/Details",pos,yaw,pitch)
        a.set_actor_location_and_rotation(e.vector(pos),e.rotation(yaw,pitch),False,True)
        a.camera_component.set_editor_properties({"field_of_view":fov,"aspect_ratio":4/3,"constrain_aspect_ratio":True})
    return e.save()


def shrine_support():
    world=e.require_world()
    actors=list(e.actors.get_all_level_actors())
    ignore=[a for a in actors if not isinstance(a,u.LandscapeProxy)]
    samples={}
    for a in actors:
        if str(a.get_folder_path())!="Secondary Ruins/Shrines":continue
        heights=[]
        for x in [-1.15,1.2,4.1,7.75]:
            for y in [-4.72,0,4.72]:
                p=u.MathLibrary.transform_location(a.get_actor_transform(),e.vector((x,y,0)))
                hit=u.SystemLibrary.line_trace_single(world,p+u.Vector(0,0,5000),p-u.Vector(0,0,12000),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,ignore,u.DrawDebugTrace.NONE)
                h=hit.to_dict()["impact_point"].z if hit else None
                heights.append({"point":point(p),"soil_m":round(h/100,2) if h is not None else None,"paving_to_ground_m":round((p.z-h)/100,2) if h is not None else None})
        samples[a.get_actor_label()]=heights
    write("Review/ShrineSupport.json",samples)


def registry():
    world=e.require_world()
    acts=list(e.actors.get_all_level_actors())
    assets=u.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(e.BASE,recursive=True)
    packages={}
    for item in assets:
        packages.setdefault(str(item.asset_class_path.asset_name),[]).append(str(item.package_name))
    instances=Counter()
    meshes=Counter()
    external=[]
    cameras={}
    for a in acts:
        name=a.get_actor_label()
        if isinstance(a,u.CameraActor):
            r=a.get_actor_rotation()
            cameras[name]={"point_m":point(a.get_actor_location()),"yaw":r.yaw,"pitch":r.pitch,"horizontal_fov":a.camera_component.field_of_view}
        for comp in a.get_components_by_class(u.StaticMeshComponent):
            mesh=comp.static_mesh
            if not mesh:continue
            path=mesh.get_path_name().split(".")[0]
            if isinstance(comp,u.InstancedStaticMeshComponent):
                instances[path]+=comp.get_instance_count()
            else:meshes[path]+=1
            if not path.startswith(e.BASE+"/"):
                external.append({"actor":name,"mesh":path})
    write("asset_registry.json",{"world":world.get_path_name(),"actor_count":len(acts),"folders":dict(sorted(Counter(str(a.get_folder_path()) for a in acts).items())),"native_assets":{k:sorted(v) for k,v in sorted(packages.items())},"placed_mesh_components":dict(sorted(meshes.items())),"instanced_meshes":dict(sorted(instances.items())),"external_mesh_audit":external,"saved_cameras":cameras})
    shrine_support()


def finalize_materials_and_cameras():
    names=e.all_named()
    for key,(pos,rot,fov) in e.v.CAMERAS.items():
        camera=names["View_"+key]
        camera.set_actor_location_and_rotation(e.vector(pos),e.rotation(*rot),False,True)
        camera.camera_component.field_of_view=fov
    import import_nature
    inventory=import_nature._registry()["materials"]
    for name in ("M_RainLeaf","M_RainLeafLight","M_RainLeafShade","M_CanopySpray","M_PalmBlade"):
        if name in inventory:import_nature.make_material(name,inventory[name],True)
    import sys
    sys.path.insert(0,str(e.ROOT/"Water"))
    import water_materials, importlib
    importlib.reload(water_materials).spring()
    save_material_usage()
    return e.save()


def save_material_usage():
    required={}
    for a in e.actors.get_all_level_actors():
        for c in a.get_components_by_class(u.StaticMeshComponent):
            mesh=c.static_mesh
            if not mesh:continue
            flags=set()
            if isinstance(c,u.InstancedStaticMeshComponent):
                flags.add("MATUSAGE_INSTANCED_STATIC_MESHES")
            if mesh.get_editor_property("nanite_settings").enabled:
                flags.add("MATUSAGE_NANITE")
            for i in range(c.get_num_materials()):
                m=c.get_material(i)
                if m and isinstance(m,u.Material) and m.get_path_name().startswith(e.BASE+"/"):
                    required.setdefault(m,set()).update(flags)
    for m,flags in required.items():
        for name in flags:
            u.MaterialEditingLibrary.set_base_material_usage(m,getattr(u.MaterialUsage,name),True)
        e.assets.save_loaded_asset(m,False)
    return len(required)


def reopen_and_check():
    if e.levels.is_in_play_in_editor():raise RuntimeError("Stop play before reloading")
    e.require_world()
    views=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    camera=e.all_named()["View_Reference"]
    views.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
    if not e.save():raise RuntimeError("World save failed")
    if not e.levels.load_level("/Engine/Maps/Entry"):raise RuntimeError("Could not switch away from temple")
    if not e.levels.load_level(e.MAP):raise RuntimeError("Could not load saved temple")
    world=e.require_world()
    checked={}
    for asset in u.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(e.BASE,recursive=True):
        if str(asset.asset_class_path.asset_name)=="Material":
            mat=asset.get_asset()
            checked[str(asset.package_name)]=[str(message) for message in u.MaterialEditingLibrary.recompile_material(mat)]
    camera=e.all_named()["View_Reference"]
    views.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
    u.SystemLibrary.execute_console_command(world,"MAP CHECK")
    settings=u.get_default_object(u.load_class(None,"/Script/ModelContextProtocol.ModelContextProtocolSettings"))
    write("Review/SavedWorldCheck.json",{"reloaded_world":world.get_path_name(),"actors":len(e.actors.get_all_level_actors()),"material_compile_errors":checked,
          "editor_mcp":{"automatic_start":settings.get_editor_property("bAutoStartServer"),"configured_port":settings.get_editor_property("ServerPortNumber"),"path":settings.get_editor_property("ServerUrlPath")},
          "game_mode":world.get_world_settings().get_editor_property("default_game_mode").get_path_name()})
    return {"materials":len(checked),"errors":sum(len(v) for v in checked.values()),"world":world.get_path_name()}
