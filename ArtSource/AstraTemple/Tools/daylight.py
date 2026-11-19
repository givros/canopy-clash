"""A measured, fixed outdoor sky radiance distribution. The sunlight is supplied by UE."""
from editor import *

def install():
    require_world()
    f=ROOT/"Terrain/T_SkyDiffuse.hdr"
    path=BASE+"/Lighting"
    sky=import_texture(f,path)
    if not isinstance(sky,u.TextureCube):raise TypeError("HDR panorama was not imported as a native cubemap")
    sky.set_editor_property("max_texture_size",2048)
    assets.save_loaded_asset(sky,False)
    sky_mat=backdrop()
    names=all_named()
    dome=names.get("Cloud canopy over the valley") or place(u.StaticMeshActor,"Cloud canopy over the valley","Lighting",(0,0,0))
    comp=dome.static_mesh_component
    comp.set_static_mesh(assets.load_asset("/Engine/EngineSky/SM_SkySphere"))
    comp.set_material(0,sky_mat);comp.set_cast_shadow(False)
    dome.set_actor_enable_collision(False)
    comp.set_collision_profile_name("NoCollision")
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    radius=comp.static_mesh.get_bounds().sphere_radius
    scale=3500000./radius
    dome.set_actor_scale3d(u.Vector(scale,scale,scale))
    comp.set_editor_properties({"affect_distance_field_lighting":False,"affect_dynamic_indirect_lighting":False,"visible_in_ray_tracing":False,"receives_decals":False})
    cloud=names.get("High cumulus")
    if cloud:actors.destroy_actor(cloud)
    skycomp=names["Open Sky"].light_component
    skycomp.set_editor_properties({"source_type":u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP,"cubemap":sky,"real_time_capture":False,"intensity":7400.,"lower_hemisphere_is_black":True,"lower_hemisphere_color":u.LinearColor(.035,.032,.023,1)})
    skycomp.recapture_sky()
    fog=names["River Valley Air"].get_component_by_class(u.ExponentialHeightFogComponent)
    fog.set_editor_properties({"fog_density":.024,"fog_height_falloff":.115,"start_distance":4500.,"fog_inscattering_luminance":u.LinearColor(2500,3240,3600,1),"directional_inscattering_luminance":u.LinearColor(.20,.17,.14,1),"directional_inscattering_start_distance":10500.})
    return save()

def backdrop():
    path=BASE+"/Lighting"
    sky=import_texture(ROOT/"Terrain/T_CanopySky.hdr",path)
    sky.set_editor_property("max_texture_size",2048)
    assets.save_loaded_asset(sky,False)
    g=Graph(material("M_CloudCeiling",path))
    g.m.set_editor_properties({"shading_model":u.MaterialShadingModel.MSM_UNLIT,"two_sided":True,"is_sky":True})
    view=g.pair("Multiply",g.node("CameraVectorWS"),g.const(-1))
    sample=g.node("TextureSample",texture=sky,sampler_type=u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    g.connect(sample,view,"Coordinates")
    g.result(g.pair("Multiply",sample,g.const(10600)),"EMISSIVE_COLOR")
    return g.finish()

def local_bounce():
    names=all_named()
    def source(label,pos,yaw,pitch,flux,width,height,reach,color):
        a=names.get(label) or place(u.RectLight,label,"Lighting/Reflected daylight",pos,yaw,pitch)
        a.set_actor_location_and_rotation(vector(pos),rotation(yaw,pitch),False,True)
        c=a.get_component_by_class(u.RectLightComponent)
        c.set_mobility(u.ComponentMobility.MOVABLE)
        c.set_editor_properties({"intensity_units":u.LightUnits.LUMENS,"intensity":float(flux),"source_width":width*100.,"source_height":height*100.,"attenuation_radius":reach*100.,"light_color":u.Color(*color,255),"cast_shadows":False,"specular_scale":.15,"indirect_lighting_intensity":.45})
    source("Waterlight on the near arch",(-50,14.6,11),-39,-8,900000,8,6,23,(212,231,229))
    source("Daylight through the nave roof",(81.8,-.4,37.5),168,-78,1040000,6.0,6.8,17,(238,241,224))
    source("Plaza bounce through the threshold",(69.9,-1.1,33),7,-15,725000,5.2,4.1,19,(255,232,200))
    source("Open sky over the causeway",(-38,21,17),3,-79,1350000,16,11,29,(222,236,236))
    source("Sanctuary limestone bounce",(58,-4.2,42),19,16,1050000,8.7,6.6,22,(255,237,209))
    return save()
