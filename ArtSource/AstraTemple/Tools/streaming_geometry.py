"""Build Nanite representations of the opaque waterbed, bank growth and headland fig."""
import editor as e
import stonework
import unreal as u


def build():
    e.require_world()
    if e.levels.is_in_play_in_editor():raise RuntimeError("Wait for the current play session")
    system=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    names=("M_FigBark","M_RainLeaf","M_RainLeafShade","M_RainLeafLight")
    folder=e.BASE+"/Terrain/Meshes"
    wood=e.ROOT/"Terrain/SM_GateFigLimb.fbx"
    stonework.import_mesh(wood,folder,replace=True,nanite=True,binding={k:e.assets.load_asset(e.BASE+"/Nature/Materials/"+k) for k in names})
    paths=[str(p) for p in e.assets.list_assets(e.BASE+"/Water",False,False) if any(n in str(p) for n in ("PoolBed","LotusShelves")) and "/SM_" in str(p)]
    paths.append(folder+"/SM_GateFigLimb")
    for path in paths:
        mesh=e.assets.load_asset(path)
        settings=system.get_nanite_settings(mesh)
        settings.enabled=True
        if "Lotus" in path or "FigLimb" in path:
            settings.shape_preservation=u.NaniteShapePreservation.PRESERVE_AREA
        system.set_nanite_settings(mesh,settings,True)
        e.assets.save_loaded_asset(mesh,False)
    return {"assets":paths,"saved":e.save()}
