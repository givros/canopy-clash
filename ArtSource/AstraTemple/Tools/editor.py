"""Native editor construction, invoked through Epic's Unreal MCP Python toolset."""
from pathlib import Path
import array
import math
import unreal as u
import valley as v

ROOT=Path(__file__).resolve().parents[1]
BASE="/Game/AstraTemple"
MAP=BASE+"/Maps/L_TempleOfTheCanopy"
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
assets=u.EditorAssetLibrary
edit=u.MaterialEditingLibrary

def require_world():
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0]!=MAP:
        raise RuntimeError("The authoring level must be open")
    return world

def vector(p): return u.Vector(*(100*t for t in p))
def rotation(yaw=0,pitch=0,roll=0): return u.Rotator(roll,pitch,yaw)
def all_named():return {a.get_actor_label():a for a in actors.get_all_level_actors()}

def place(cls,label,folder,pos=(0,0,0),yaw=0,pitch=0,scale=(1,1,1)):
    actor=actors.spawn_actor_from_class(cls,vector(pos),rotation(yaw,pitch))
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    actor.set_actor_scale3d(u.Vector(*scale))
    return actor

def save():
    require_world()
    return u.EditorLoadingAndSavingUtils.save_current_level()

def rig():
    world=require_world()
    existing=all_named()
    def actor(cls,label,folder,*args,**kwargs):
        return existing.get(label) or place(cls,label,folder,*args,**kwargs)
    sun=actor(u.DirectionalLight,"Afternoon Sun","Lighting",(18,-24,60),15,-56)
    sun.set_actor_rotation(rotation(15,-56),False)
    sun.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    sun.light_component.set_editor_properties({"intensity":65000.0,"light_color":u.Color(255,241,213,255),"atmosphere_sun_light":True,"light_source_angle":1.15})
    actor(u.SkyAtmosphere,"Tropical Atmosphere","Lighting",(0,0,0))
    clouds=actor(u.VolumetricCloud,"High cumulus","Lighting")
    cloud=clouds.get_component_by_class(u.VolumetricCloudComponent)
    cloud.set_editor_properties({"material":assets.load_asset("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst"),"layer_bottom_altitude":2.3,"layer_height":4.1})
    sky=actor(u.SkyLight,"Open Sky","Lighting",(0,0,15))
    sky.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_properties({"real_time_capture":True,"intensity":2.25,"lower_hemisphere_is_black":False})
    fog=actor(u.ExponentialHeightFog,"River Valley Air","Lighting",(0,0,0))
    fog.get_component_by_class(u.ExponentialHeightFogComponent).set_editor_properties({"fog_density":.027,"fog_height_falloff":.14,"start_distance":3600.})
    pp=actor(u.PostProcessVolume,"Fixed daylight exposure","Lighting")
    pp.set_editor_property("unbound",True)
    settings=pp.get_editor_property("settings")
    for name,val in {"auto_exposure_min_brightness":13.25,"auto_exposure_max_brightness":13.25,"auto_exposure_bias":0.1,"bloom_intensity":.09,"vignette_intensity":0.02,"motion_blur_amount":0.0}.items():
        settings.set_editor_property("override_"+name,True)
        settings.set_editor_property(name,val)
    pp.set_editor_property("settings",settings)
    for name,(pos,(yaw,pitch),fov) in v.CAMERAS.items():
        cam=actor(u.CameraActor,"View_"+name,"Cameras",pos,yaw,pitch)
        cam.set_actor_location_and_rotation(vector(pos),rotation(yaw,pitch),False,True)
        cam.camera_component.set_editor_properties({"field_of_view":fov,"aspect_ratio":4/3,"constrain_aspect_ratio":True})
    start=actor(u.PlayerStart,"Jungle approach","Navigation",(-83.8,13.4,7.05),48)
    start.set_actor_rotation(rotation(48),False)
    world.get_world_settings().set_editor_property("default_game_mode",assets.load_blueprint_class("/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode"))
    camera=all_named()["View_Reference"]
    u.get_editor_subsystem(u.UnrealEditorSubsystem).set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
    return save()

def import_texture(file,package,linear=False,normal=False,refresh=False):
    path=package+"/"+file.stem
    tex=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not tex or refresh:
        task=u.AssetImportTask()
        task.set_editor_properties({"filename":str(file),"destination_path":package,"automated":True,"replace_existing":refresh,"save":True})
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        tex=assets.load_asset(path)
    if not tex:raise RuntimeError("Texture import failed "+str(file))
    if normal:tex.set_editor_property("compression_settings",u.TextureCompressionSettings.TC_NORMALMAP)
    if normal or linear:tex.set_editor_property("srgb",False)
    assets.save_loaded_asset(tex)
    return tex

def material(name,folder):
    path=folder+"/"+name
    m=assets.load_asset(path) if assets.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,u.Material,u.MaterialFactoryNew())
    edit.delete_all_material_expressions(m)
    return m

class Graph:
    def __init__(self,m):self.m=m
    def node(self,kind,**props):
        n=edit.create_material_expression(self.m,getattr(u,"MaterialExpression"+kind),0,0)
        if props:n.set_editor_properties(props)
        return n
    def connect(self,node,inp,slot,out=""):
        if not edit.connect_material_expressions(inp,out,node,slot):raise RuntimeError(f"Unconnected {node.get_name()}.{slot}")
    def pair(self,kind,a,b):
        n=self.node(kind)
        self.connect(n,a,"A");self.connect(n,b,"B")
        return n
    def const(self,value):return self.node("Constant",r=float(value))
    def mask(self,a,r=True,g=False,b=False):
        n=self.node("ComponentMask",r=r,g=g,b=b);self.connect(n,a,"Input");return n
    def texture(self,tex,uv=None,normal=False,linear=False):
        typ=u.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else (u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR if linear else u.MaterialSamplerType.SAMPLERTYPE_COLOR)
        n=self.node("TextureSample",texture=tex,sampler_type=typ)
        if uv:self.connect(n,uv,"Coordinates")
        return n
    def blend(self,a,b,t):
        n=self.node("LinearInterpolate")
        for k,i in [(a,"A"),(b,"B"),(t,"Alpha")]:self.connect(n,k,i)
        return n
    def result(self,node,prop,out=""):
        if not edit.connect_material_property(node,out,getattr(u.MaterialProperty,"MP_"+prop)):raise RuntimeError(prop)
    def finish(self):
        edit.layout_material_expressions(self.m)
        edit.recompile_material(self.m)
        assets.save_loaded_asset(self.m,False)
        return self.m

def ground_material():
    folder=BASE+"/Terrain"
    maps={}
    for stem in ("forest_ground_04","mossy_rock","brown_mud_rocks_01","leafy_grass"):
        maps[stem]=[import_texture(next((ROOT/"Terrain").glob("T_"+stem+"_"+suffix+".*")),folder+"/Textures",suffix=="Rough",suffix=="Normal") for suffix in ("Color","Normal","Rough")]
    zones=import_texture(ROOT/"Terrain/T_ValleyZones.png",folder+"/Textures",True,refresh=True)
    zones.set_editor_property("address_x",u.TextureAddress.TA_CLAMP)
    zones.set_editor_property("address_y",u.TextureAddress.TA_CLAMP)
    assets.save_loaded_asset(zones)
    g=Graph(material("M_CatchmentFloor",folder))
    xy=g.mask(g.node("WorldPosition"),True,True)
    uv=g.pair("Divide",xy,g.const(300))
    shift=g.node("Constant2Vector",r=15360.,g=20160.)
    zoneuv=g.pair("Divide",g.pair("Add",xy,shift),g.const(40320))
    mask=g.texture(zones,zoneuv,linear=True)
    mask.set_editor_property("sampler_source",u.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS)
    rock=g.mask(mask);mud=g.mask(mask,False,True);green=g.mask(mask,False,False,True)
    for idx,prop in enumerate(("BASE_COLOR","NORMAL","ROUGHNESS")):
        tex=[g.texture(m[idx],uv,normal=idx==1,linear=idx==2) for m in maps.values()]
        for sample in tex:
            sample.set_editor_property("sampler_source",u.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
        base=g.blend(tex[0],tex[3],green)
        result=g.blend(g.blend(base,tex[1],rock),tex[2],mud)
        g.result(result,prop)
    from understory_floor import apply_layer
    apply_layer(g)
    return g.finish()

def landscape():
    require_world()
    sys=u.get_editor_subsystem(u.LandscapeEditorSubsystem)
    present=sys.get_landscapes()
    ground=present[0] if present else sys.create_landscape(vector((*v.CENTRE,0)),rotation(),u.Vector(80,80,60),u.IntPoint(8,8),1,63)
    ground.set_actor_label("Valley of the Two Springs");ground.set_folder_path("Terrain")
    with (ROOT/"Terrain/ValleyHeights.f32").open("rb") as src:
        h=array.array("f");h.fromfile(src,505*505)
    sys.set_heightmap_data(ground,"Layer",list(h))
    return save()

def apply_terrain_material():
    g=u.get_editor_subsystem(u.LandscapeEditorSubsystem).get_landscapes()[0]
    g.set_editor_property("landscape_material",ground_material())
    return save()

def capture(name="Reference",filename="Reference",width=1200,height=900):
    require_world()
    c=all_named()["View_"+name]
    u.get_editor_subsystem(u.UnrealEditorSubsystem).set_level_viewport_camera_info(c.get_actor_location(),c.get_actor_rotation())
    p=str(ROOT/"Review"/(filename+".png"))
    u.AutomationLibrary.take_high_res_screenshot(width,height,p,c,delay=2.8)
    return p
