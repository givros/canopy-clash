"""Material and mesh import for the meter-scale Astra Temple nature collection."""
import json

import unreal as u
from editor import BASE, ROOT, Graph, assets, import_texture, material, require_world
from stonework import import_mesh

SOURCE = ROOT / "Nature"
NATIVE = BASE + "/Nature"
TEXTURES = NATIVE + "/Textures"
MATERIALS = NATIVE + "/Materials"
MESHES = NATIVE + "/Meshes"
FOLIAGE_NANITE = {"SM_ArecaPalm","SM_Fern","SM_Monstera",
                  "SM_LianaCurtain","SM_CecropiaSapling","SM_MossCushion"}

def _registry():
    return json.loads((SOURCE / "nature_assets.json").read_text())

def _texture(path, normal=False, linear=False):
    tex = import_texture(SOURCE / path, TEXTURES, linear=linear, normal=normal)
    if normal and not tex.get_editor_property("flip_green_channel"):
        tex.set_editor_property("flip_green_channel", True)
        assets.save_loaded_asset(tex, False)
    return tex

def _foliage(g, name, color):
    g.m.set_editor_property("two_sided", True)
    foliage=next(getattr(u.MaterialShadingModel,key) for key in dir(u.MaterialShadingModel) if key.endswith("FOLIAGE"))
    g.m.set_editor_property("shading_model",foliage)
    g.result(g.pair("Multiply",color,g.const(.58)),"SUBSURFACE_COLOR")
    if "Stem" in name:
        return
    # A continuous, spatially travelling wave; bladetips carry motion, petioles stay attached.
    p = g.node("WorldPosition")
    position = g.pair("Add",g.pair("Multiply",g.mask(p),g.const(.0024)),
                      g.pair("Multiply",g.mask(p,False,True),g.const(.0011)))
    phase = g.pair("Add",position,g.pair("Multiply",g.node("Time"),g.const(.185)))
    sine = g.node("Sine")
    g.connect(sine,phase,"Input")
    uv = g.node("TextureCoordinate")
    tip = g.node("Saturate")
    g.connect(tip,g.pair("Subtract",g.const(1),g.mask(uv,False,True)),"Input")
    weight = g.pair("Multiply",tip,tip)
    motion = g.pair("Multiply",sine,weight)
    amount = .16 if "Lily" in name or "Petal" in name else (.31 if "Bract" in name else 1.15)
    direction = g.node("Constant3Vector",constant=u.LinearColor(amount,.38*amount,.10*amount,1))
    g.result(g.pair("Multiply",motion,direction),"WORLD_POSITION_OFFSET")
    g.m.set_editor_property("used_with_instanced_static_meshes",True)

def make_material(name, desc, refresh=False):
    path=MATERIALS+"/"+name
    if not refresh and assets.does_asset_exist(path):
        return assets.load_asset(path)
    g=Graph(material(name,MATERIALS))
    sampler=g.texture(_texture(desc["base_color"]))
    color=sampler
    if desc.get("alpha_cutout"):
        g.m.set_editor_property("blend_mode",u.BlendMode.BLEND_MASKED)
        g.m.set_editor_property("opacity_mask_clip_value",.30)
        g.result(sampler,"OPACITY_MASK","A")
    if desc.get("linear_tint"):
        tint=g.node("Constant3Vector",constant=u.LinearColor(*desc["linear_tint"],1))
        color=g.pair("Multiply",color,tint)
    if desc["two_sided"]:
        # Pigment varies modestly between instances across groves and thickets.
        if name in ("M_RainLeaf","M_RainLeafLight","M_RainLeafShade","M_CanopySpray","M_PalmBlade"):
            old_leaf=g.node("Constant3Vector",constant=u.LinearColor(.70,.82,.80,1))
            sun_leaf=g.node("Constant3Vector",constant=u.LinearColor(1.26,1.07,.73,1))
            tint=g.blend(old_leaf,sun_leaf,g.node("PerInstanceRandom"))
        else:
            tint=g.pair("Add",g.const(.98),g.pair("Multiply",g.node("PerInstanceRandom"),g.const(.09)))
        color=g.pair("Multiply",color,tint)
        _foliage(g,name,color)
    g.result(color,"BASE_COLOR")
    if desc.get("normal_gl"):
        g.result(g.texture(_texture(desc["normal_gl"],normal=True),normal=True),"NORMAL")
    if desc.get("arm"):
        arm=g.texture(_texture(desc["arm"],linear=True),linear=True)
        g.result(arm,"ROUGHNESS","G")
        g.result(arm,"AMBIENT_OCCLUSION","R")
    elif desc.get("roughness_map"):
        g.result(g.texture(_texture(desc["roughness_map"],linear=True),linear=True),"ROUGHNESS","R")
    else:
        g.result(g.const(desc["roughness"]),"ROUGHNESS")
    return g.finish()

def nature(names=None, replace=False, refresh_materials=False):
    require_world()
    registry=_registry()
    selected={k:v for k,v in registry["assets"].items() if not names or k in names}
    if names and len(selected)!=len(set(names)):
        raise KeyError(set(names)-set(selected))
    slots={s for item in selected.values() for s in item["material_slots"]}
    bindings={name:make_material(name,registry["materials"][name],refresh_materials) for name in sorted(slots)}
    result=[]
    for name,item in selected.items():
        stone=any(w in name for w in ("Boulder","Cliff"))
        nanite=stone or name in FOLIAGE_NANITE
        row=import_mesh(SOURCE/item["fbx"],MESHES,replace,nanite,bindings,collision=stone)
        mesh=assets.load_asset(MESHES+"/"+name)
        missing=set(item["material_slots"])-set(row[3])
        if missing:
            raise ValueError(f"{name} lost its source material slots: {sorted(missing)}")
        for slot in mesh.get_editor_property("static_materials"):
            if slot.material_interface is None:
                raise ValueError(f"{name} has an empty material slot")
        lo,hi=item["bounds_m"]
        predicted=100*(hi[2]-lo[2])
        box=mesh.get_bounding_box()
        if abs((box.max.z-box.min.z)-predicted)>max(.1,.005*predicted):
            raise ValueError(f"{name} imported at unexpected size: {box} vs {predicted}cm high")
        result.append(row)
    for name,item in selected.items():
        if item.get("lods"):canopy_lods(name,item,registry,replace)
    vegetation_nanite(set(selected)&FOLIAGE_NANITE)
    return result

def canopy_lods(name,item,registry,replace):
    mesh=assets.load_asset(MESHES+"/"+name)
    system=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    settings=system.get_nanite_settings(mesh)
    if settings.enabled:
        settings.enabled=False
        system.set_nanite_settings(mesh,settings,True)
    mat=make_material("M_CanopySpray",registry["materials"]["M_CanopySpray"])
    slots=list(mesh.get_editor_property("static_materials"))
    indices={str(slot.material_slot_name):i for i,slot in enumerate(slots)}
    if "M_CanopySpray" not in indices:
        slot=u.StaticMaterial(material_interface=mat,material_slot_name="M_CanopySpray")
        indices["M_CanopySpray"]=len(slots);slots.append(slot)
        mesh.set_editor_property("static_materials",slots)
    for lod,source in enumerate(item["lods"],1):
        if replace or system.get_lod_count(mesh)<=lod:
            applied=system.import_lod(mesh,lod,str(SOURCE/source["fbx"]))
            if applied!=lod:raise RuntimeError(f"{name} LOD {lod} failed to import")
        if mesh.get_num_sections(lod)!=2:raise RuntimeError(f"{name} LOD {lod} lost the wood / cutout separation")
        for section,slot_name in enumerate(("M_FigBark","M_CanopySpray")):
            if system.get_lod_material_slot(mesh,lod,section)!=indices[slot_name]:
                system.set_lod_material_slot(mesh,indices[slot_name],lod,section)
    sizes=[1.0,.54,.20,.075]
    current=system.get_lod_screen_sizes(mesh)
    if len(current)!=len(sizes) or any(abs(a-b)>.0001 for a,b in zip(current,sizes)):
        if not system.set_lod_screen_sizes(mesh,sizes):raise RuntimeError("Could not set canopy LOD screen sizes")
    assets.save_loaded_asset(mesh,False)

def vegetation_nanite(names=None):
    subsystem=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    result=[]
    for name in sorted(FOLIAGE_NANITE if names is None else names):
        mesh=assets.load_asset(MESHES+"/"+name)
        if mesh is None:continue
        settings=subsystem.get_nanite_settings(mesh)
        target=u.NaniteFallbackTarget.PERCENT_TRIANGLES
        shape=u.NaniteShapePreservation.PRESERVE_AREA
        if (not settings.enabled or settings.shape_preservation!=shape
                or settings.fallback_target!=target or settings.fallback_percent_triangles!=1.0):
            settings.enabled=True
            settings.shape_preservation=shape
            # Tiny separated blades otherwise collapse into oversized triangles in the
            # fallback (thumbnail renders and hardware paths outside Nanite).
            settings.fallback_target=target
            settings.fallback_percent_triangles=1.0
            subsystem.set_nanite_settings(mesh,settings,True)
            assets.save_loaded_asset(mesh,False)
        actual=subsystem.get_nanite_settings(mesh)
        result.append((name,actual.enabled,str(actual.shape_preservation),subsystem.get_convex_collision_count(mesh)))
    return result
