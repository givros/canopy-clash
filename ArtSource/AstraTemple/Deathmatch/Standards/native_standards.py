"""Import cloth and hardware and seat the two standards beside their spawn-area walls."""
from pathlib import Path
import sys
import math
import unreal as u
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parents[1]/'Tools'),str(ROOT.parent)]
import editor as e
import arena
PACKAGE='/Game/AstraTemple/Deathmatch/Standards'

def fabrics():
    mats={}
    rough=e.import_texture(ROOT/'T_StandardWeave_R.png',PACKAGE,linear=True)
    for team in ('Red','Blue'):
        key='M_Standard'+team
        color=e.import_texture(ROOT/('T_Standard'+team+'_C.png'),PACKAGE)
        normal=e.import_texture(ROOT/('T_Standard'+team+'_N.png'),PACKAGE,normal=True)
        g=e.Graph(e.material(key,PACKAGE))
        g.m.set_editor_property('two_sided',True)
        g.result(g.texture(color),'BASE_COLOR')
        g.result(g.texture(normal,normal=True),'NORMAL')
        g.result(g.texture(rough,linear=True),'ROUGHNESS','R')
        g.result(g.const(.24),'SPECULAR')
        mats[key]=g.finish()
    # Reuse one channel of the project's existing tree bark scan to vary the wood, binding and metal patina.
    grain=e.assets.load_asset('/Game/AstraTemple/Nature/Textures/T_japanese_hackberry_bark_Color')
    for name,light,dark,roughness,metallic in [
        ('Wood',(.25,.116,.042),(.062,.027,.011),.65,0),
        ('Bronze',(.365,.213,.088),(.155,.123,.065),.45,.64),
        ('Braid',(.39,.28,.147),(.115,.068,.028),.80,0)]:
        key='M_Standard'+name
        g=e.Graph(e.material(key,PACKAGE))
        pos=g.node('WorldPosition')
        x=g.mask(pos);y=g.mask(pos,False,True);z=g.mask(pos,False,False,True)
        uv=g.node('AppendVector')
        g.connect(uv,g.pair('Divide',g.pair('Add',x,g.pair('Multiply',y,g.const(.645))),g.const(58.)),'A')
        g.connect(uv,g.pair('Divide',z,g.const(180. if name=='Wood' else 33.)),'B')
        sample=g.mask(g.texture(grain,uv))
        variation=g.node('Saturate');g.connect(variation,g.pair('Multiply',sample,g.const(3.9)),'Input')
        a=g.node('Constant3Vector',constant=u.LinearColor(*dark,1));b=g.node('Constant3Vector',constant=u.LinearColor(*light,1))
        g.result(g.blend(a,b,variation),'BASE_COLOR')
        g.result(g.blend(g.const(roughness+.08),g.const(roughness-.07),variation),'ROUGHNESS')
        g.result(g.const(metallic),'METALLIC')
        mats[key]=g.finish()
    mats['M_Astra_ShadeStone']=e.assets.load_asset('/Game/AstraTemple/Architecture/Materials/M_Astra_ShadeStone')
    return mats

def import_standard(team,mats,refresh=False):
    name='SM_Standard'+team
    full=PACKAGE+'/'+name
    if refresh or not e.assets.does_asset_exist(full):
        w=arena.current()
        u.SystemLibrary.execute_console_command(w,'Interchange.FeatureFlags.Import.FBX 0')
        task=u.AssetImportTask()
        opts=u.FbxImportUI()
        opts.set_editor_properties(dict(import_mesh=True,import_materials=False,import_textures=False,import_as_skeletal=False,
             import_animations=False,automated_import_should_detect_type=False,mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH))
        opts.static_mesh_import_data.set_editor_properties(dict(combine_meshes=True,auto_generate_collision=False,
                generate_lightmap_u_vs=False,build_nanite=False,convert_scene=True,convert_scene_unit=True,force_front_x_axis=False))
        task.set_editor_properties(dict(filename=str(ROOT/(name+'.fbx')),destination_path=PACKAGE,destination_name=name,automated=True,
                replace_existing=refresh,replace_existing_settings=refresh,save=True,options=opts))
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh=e.assets.load_asset(full)
    slots=list(mesh.get_editor_property('static_materials'))
    for slot in slots:
        key=str(slot.get_editor_property('imported_material_slot_name'))
        slot.set_editor_property('material_interface',mats[key])
    mesh.set_editor_property('static_materials',slots)
    e.assets.save_loaded_asset(mesh,False)
    return mesh

def place(refresh=False):
    w=arena.current()
    names=e.all_named()
    mats=fabrics()
    facts=[]
    for team,point,yaw in [('Red',(-78.97,13.24,5.8),9),('Blue',(8.94,27.84,4.),180)]:
        mesh=import_standard(team,mats,refresh)
        label=team+' Woven Standard'
        actor=names.get(label)
        if actor and str(actor.get_folder_path())!='Deathmatch/Standards':raise ValueError(label)
        ignore=[actor] if actor else []
        p=e.vector(point)
        hit=u.SystemLibrary.line_trace_single(w,p+u.Vector(0,0,105),p-u.Vector(0,0,275),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,ignore,u.DrawDebugTrace.NONE)
        if not hit:raise RuntimeError('No floor: '+team)
        hit=hit.to_dict()
        floor=hit['impact_point']
        if abs(floor.z/100-point[2])>1.2:raise ValueError(str(hit))
        if not actor:actor=e.actors.spawn_actor_from_object(mesh,floor,e.rotation(yaw))
        actor.set_actor_label(label);actor.set_folder_path('Deathmatch/Standards')
        actor.set_actor_location_and_rotation(floor,e.rotation(yaw),False,True)
        actor.set_editor_property('tags',['Deathmatch/Standards',team+'Standard'])
        component=actor.static_mesh_component
        component.set_static_mesh(mesh);component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        navsites=[n for n in names.values() if isinstance(n,u.PlayerStart) and str(n.player_start_tag)==team]
        nearest=min([math.hypot(a.get_actor_location().x-floor.x,a.get_actor_location().y-floor.y)/100 for a in navsites],default=None)
        facts.append(dict(team=team,label=label,floor=hit['hit_actor'].get_actor_label() if hit.get('hit_actor') else str(hit.get('hit_component')),
                location_m=arena.xyz(floor),bounds=str(actor.get_actor_bounds(False)),nearest_player_start_m=nearest,materials=len(mesh.static_materials)))
    if not u.EditorLoadingAndSavingUtils.save_current_level():raise RuntimeError('Save failed')
    return facts
