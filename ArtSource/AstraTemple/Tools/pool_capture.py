"""Bake local radiance for the reflection pool from the finished Unreal level."""
import editor as e
import unreal as u


def bake(refresh=False):
    name=e.BASE+"/Lighting/T_PoolRadiance"
    exists=e.assets.does_asset_exist(name)
    if exists and not refresh:return name
    if e.levels.is_in_play_in_editor():raise RuntimeError("Wait for traversal to end")
    rt=u.new_object(u.TextureRenderTargetCube)
    rt.set_editor_property("size_x",512)
    target=e.place(u.SceneCaptureCube,"Basin radiance capture","Lighting/Baking",(-17.6,1.2,1.22))
    try:
        cap=target.get_component_by_class(u.SceneCaptureComponentCube)
        cap.set_editor_properties({"capture_every_frame":False,"capture_on_movement":False,"texture_target":rt,"capture_source":u.SceneCaptureSource.SCS_SCENE_COLOR_HDR})
        for actor in e.actors.get_all_level_actors():
            if str(actor.get_folder_path()) in ("AstraTemple/Water/Basins","AstraTemple/Water/Whitewater","AstraTemple/Water/Spray"):
                cap.hide_actor_components(actor)
        cap.capture_scene()
        if exists:
            cube=e.assets.load_asset(name)
            u.RenderingLibrary.convert_render_target_to_texture_cube_editor_only(e.require_world(),rt,cube)
        else:
            cube=u.RenderingLibrary.render_target_create_static_texture_cube_editor_only(rt,name,u.TextureCompressionSettings.TC_HDR)
        if not cube:raise RuntimeError("Unreal did not bake the cube")
        e.assets.save_loaded_asset(cube,False)
        return cube.get_path_name()
    finally:
        e.actors.destroy_actor(target)
