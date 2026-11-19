"""Limit wind evaluation to playable distances while preserving authored foliage instances."""
import unreal as u
from editor import BASE, assets, actors, require_world

WIND_DISTANCE_CM={
    'SM_StranglerFig':4500,'SM_JungleCanopy':4500,'SM_ArecaPalm':4000,
    'SM_CecropiaSapling':3500,'SM_LianaCurtain':3200,'SM_Monstera':3000,
    'SM_Fern':2800,'SM_Heliconia':2500,'SM_MossCushion':2500,'SM_WaterLily':2500,
}

def foliage_components():
    return [component for actor in actors.get_all_level_actors() if isinstance(actor,u.InstancedFoliageActor)
            for component in actor.get_components_by_class(u.InstancedStaticMeshComponent) if component.static_mesh]

def wind():
    require_world();results=[]
    for component in foliage_components():
        name=component.static_mesh.get_name()
        path=BASE+'/Nature/Foliage/FT_'+name.removeprefix('SM_')
        if not assets.does_asset_exist(path):continue
        ft=assets.load_asset(path)
        # Wood-only roots and rock surfaces do not reference animated vertex inputs.
        distance=WIND_DISTANCE_CM.get(name,0);enabled=bool(distance)
        ft.set_editor_properties({'bEvaluateWorldPositionOffset':enabled,'WorldPositionOffsetDisableDistance':distance})
        component.set_evaluate_world_position_offset(enabled)
        component.set_world_position_offset_disable_distance(distance)
        if not assets.save_loaded_asset(ft,False):raise RuntimeError('Failed to save '+path)
        if component.get_editor_property('WorldPositionOffsetDisableDistance')!=distance:raise RuntimeError('Foliage wind radius did not update: '+name)
        results.append([name,component.get_instance_count(),distance])
    return results

def shadow_coarse(enabled):
    world=require_world()
    u.SystemLibrary.execute_console_command(world,'r.Shadow.Virtual.NonNanite.IncludeInCoarsePages '+str(int(enabled)))
    return u.SystemLibrary.get_console_variable_int_value('r.Shadow.Virtual.NonNanite.IncludeInCoarsePages')

TREE_NAMES=('SM_JungleCanopy','SM_StranglerFig')
SHADOW_FOLDER=BASE+'/Nature/ShadowGeometry'

def _shadow_mesh(original):
    path=SHADOW_FOLDER+'/'+original.get_name()+'_Shadow'
    mesh=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_loaded_asset(original,path)
    if not mesh:raise RuntimeError('Could not create the shadow mesh '+path)
    system=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    settings=system.get_nanite_settings(mesh)
    if not settings.enabled:
        settings.enabled=True
        settings.shape_preservation=u.NaniteShapePreservation.PRESERVE_AREA
        # This mesh contributes solely to Nanite virtual shadows. The visual
        # asset retains its own full-resolution fallback and all authored LODs.
        system.set_nanite_settings(mesh,settings,True)
        if not assets.save_loaded_asset(mesh,False):raise RuntimeError('Could not save '+path)
    return mesh

def _shadow_type(mesh):
    name='FT_'+mesh.get_name().removeprefix('SM_')
    path=SHADOW_FOLDER+'/'+name
    ft=assets.load_asset(path) if assets.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset(
        name,SHADOW_FOLDER,u.FoliageType_InstancedStaticMesh,u.FoliageType_InstancedStaticMeshFactory())
    body=ft.get_editor_property('body_instance')
    body.set_editor_property('collision_profile_name','NoCollision')
    ft.set_editor_properties({'mesh':mesh,'body_instance':body,'cast_shadow':True,'cast_dynamic_shadow':True,
        'affect_distance_field_lighting':False,'affect_dynamic_indirect_lighting':False,
        'visible_in_ray_tracing':False,'visible_in_reflections':False,'use_as_occluder':False,
        'evaluate_world_position_offset':True,'world_position_offset_disable_distance':4500})
    if not assets.save_loaded_asset(ft,False):raise RuntimeError('Could not save '+path)
    return ft

def _configure_shadow_component(component):
    component.modify()
    component.set_cast_hidden_shadow(True)
    component.set_render_in_main_pass(False)
    component.set_render_in_depth_pass(False)
    component.set_visibility(False)
    component.set_hidden_in_game(True)
    component.set_editor_property('world_position_offset_writes_velocity',False)

def verify_tree_pairs():
    components={c.static_mesh.get_name():c for c in foliage_components()}
    def poses(c):
        result=[]
        for i in range(c.get_instance_count()):
            t=c.get_instance_transform(i,True);p=t.translation;q=t.rotation;s=t.scale3d
            result.append((p.x,p.y,p.z,q.x,q.y,q.z,q.w,s.x,s.y,s.z))
        return sorted(result)
    report={}
    for name in TREE_NAMES:
        original=components[name];proxy=components[name+'_Shadow']
        visible,shadow=poses(original),poses(proxy)
        if len(visible)!=len(shadow) or any(abs(a-b)>1e-5 for t,k in zip(visible,shadow) for a,b in zip(t,k)):
            raise RuntimeError('Unmatched shadow instance transform: '+name)
        if (original.get_editor_property('cast_dynamic_shadow') or not original.get_editor_property('visible')
                or not proxy.get_editor_property('cast_dynamic_shadow') or not proxy.get_editor_property('cast_hidden_shadow')
                or proxy.get_editor_property('visible') or proxy.get_editor_property('render_in_main_pass')
                or proxy.get_editor_property('render_in_depth_pass') or not proxy.get_editor_property('hidden_in_game')):
            raise RuntimeError('Invalid shadow or visibility ownership: '+name)
        report[name]=original.get_instance_count()
    return report

def shadow_geometry(enable=True,names=TREE_NAMES):
    world=require_world()
    if u.get_editor_subsystem(u.LevelEditorSubsystem).is_in_play_in_editor():raise RuntimeError('Stop PIE before changing shadow geometry')
    if not set(names).issubset(TREE_NAMES):raise ValueError(names)
    visible=[c for c in foliage_components() if c.static_mesh.get_name() in names];report=[]
    if not visible:raise RuntimeError('Original foliage is unavailable')
    for component in visible:
        mesh=component.static_mesh;name=mesh.get_name()
        original=assets.load_asset(BASE+'/Nature/Foliage/FT_'+name.removeprefix('SM_'))
        shadow_type_path=SHADOW_FOLDER+'/FT_'+name.removeprefix('SM_')+'_Shadow'
        if enable:
            proxy=_shadow_mesh(mesh);ft=_shadow_type(proxy)
            transforms=[component.get_instance_transform(i,True) for i in range(component.get_instance_count())]
            if any(t is None for t in transforms):raise RuntimeError('Missing original tree transform')
            u.InstancedFoliageActor.remove_all_instances(world,ft)
            u.InstancedFoliageActor.add_instances(world,ft,transforms)
            copies=[c for c in foliage_components() if c.static_mesh==proxy]
            expected=len(transforms);actual=sum(c.get_instance_count() for c in copies)
            if expected!=actual:raise RuntimeError(f'{name} shadow count {actual}, expected {expected}')
            for c in copies:_configure_shadow_component(c)
        elif assets.does_asset_exist(shadow_type_path):
            u.InstancedFoliageActor.remove_all_instances(world,assets.load_asset(shadow_type_path))
        component.modify()
        component.set_editor_property('cast_dynamic_shadow',not enable)
        original.set_editor_property('cast_dynamic_shadow',not enable)
        if not assets.save_loaded_asset(original,False):raise RuntimeError('Could not update shadow ownership '+name)
        report.append([name,component.get_instance_count(),enable])
    return report
