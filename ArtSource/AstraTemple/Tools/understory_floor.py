"""Spatially limited scanned riverbank material and small native foliage groups."""
from pathlib import Path
import json
import math
import unreal as u
import editor as e

SOURCE=e.ROOT/'BankUnderstory'
PACKAGE=e.BASE+'/BankUnderstory'
PROPERTIES=['BASE_COLOR','NORMAL','ROUGHNESS']

def projected_uv(g,world,footprint):
    xy=g.mask(world,True,True);z=g.mask(world,False,False,True)
    slope=g.pair('Multiply',z,g.node('Constant2Vector',r=.08,g=.60))
    metric=g.pair('Divide',g.pair('Add',xy,slope),g.const(460))
    variation=g.mask(footprint,False,True,True)
    uv=g.pair('Add',metric,g.pair('Multiply',variation,g.const(.44)))
    uv.set_editor_property('desc','Low bank slope projection')
    return uv

def apply_layer(g):
    previous=[]
    for p in PROPERTIES:
        prop=getattr(u.MaterialProperty,'MP_'+p)
        old=e.edit.get_material_property_input_node(g.m,prop)
        if not old:raise RuntimeError('Missing original terrain expression '+p)
        previous.append((old,str(e.edit.get_material_property_input_node_output_name(g.m,prop))))
    if all(n.get_editor_property('desc')=='Eastern bank and approach shoulders' for n,_ in previous):return
    textures={}
    for name,linear,normal in [('T_DampForest_ColorRough',False,False),('T_DampForest_NormalDX',False,True),('T_LowBankFootprint',True,False)]:
        t=e.import_texture(SOURCE/(name+'.png'),PACKAGE,linear=linear,normal=normal)
        if name=='T_DampForest_ColorRough':t.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_BC7)
        if name=='T_LowBankFootprint':t.set_editor_properties({'address_x':u.TextureAddress.TA_CLAMP,'address_y':u.TextureAddress.TA_CLAMP})
        e.assets.save_loaded_asset(t,False);textures[name]=t
    world=g.node('WorldPosition');xy=g.mask(world,True,True)
    region_uv=g.pair('Divide',g.pair('Add',xy,g.node('Constant2Vector',r=10100.,g=0.)),g.node('Constant2Vector',r=12000.,g=7500.))
    footprint=g.texture(textures['T_LowBankFootprint'],region_uv,linear=True)
    footprint.set_editor_property('sampler_source',u.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS)
    uv=projected_uv(g,world,footprint)
    coverage=g.mask(footprint);patch=g.mask(footprint,False,True)
    pigment=g.texture(textures['T_DampForest_ColorRough'],uv)
    normal=g.texture(textures['T_DampForest_NormalDX'],uv,normal=True)
    for node in [pigment,normal]:node.set_editor_property('sampler_source',u.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
    brightness=g.pair('Add',g.const(.79),g.pair('Multiply',g.const(.39),patch))
    color=g.pair('Multiply',pigment,brightness)
    for i,(src,pin) in enumerate([(color,''),(normal,''),(pigment,'A')]):
        old,oldpin=previous[i]
        blend=g.node('LinearInterpolate',desc='Eastern bank and approach shoulders')
        g.connect(blend,old,'A','' if oldpin=='None' else oldpin);g.connect(blend,src,'B',pin);g.connect(blend,coverage,'Alpha');g.result(blend,PROPERTIES[i])

def update_material():
    m=e.assets.load_asset(e.BASE+'/Terrain/M_CatchmentFloor')
    g=e.Graph(m);apply_layer(g);g.finish()
    return [t.get_name() for t in e.edit.get_used_textures(m)]

def refresh_scans():
    for name,linear,normal in [('T_DampForest_ColorRough',False,False),('T_DampForest_NormalDX',False,True),('T_LowBankFootprint',True,False)]:
        t=e.import_texture(SOURCE/(name+'.png'),PACKAGE,linear=linear,normal=normal,refresh=True)
        if name=='T_DampForest_ColorRough':t.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_BC7)
        if name=='T_LowBankFootprint':t.set_editor_properties({'address_x':u.TextureAddress.TA_CLAMP,'address_y':u.TextureAddress.TA_CLAMP})
        e.assets.save_loaded_asset(t,False)
    m=e.assets.load_asset(e.BASE+'/Terrain/M_CatchmentFloor');g=e.Graph(m)
    def sample(prop):
        root=e.edit.get_material_property_input_node(m,getattr(u.MaterialProperty,'MP_'+prop));nodes=e.edit.get_inputs_for_material_expression(m,root)
        return next(n for n in nodes if isinstance(n,u.MaterialExpressionTextureSample)),next(n for n in nodes if isinstance(n,u.MaterialExpressionComponentMask))
    normal,coverage=sample('NORMAL');color,_=sample('ROUGHNESS');foot=e.edit.get_inputs_for_material_expression(m,coverage)[0]
    old=e.edit.get_inputs_for_material_expression(m,normal)[0]
    if old.get_editor_property('desc')!='Low bank slope projection':
        uv=projected_uv(g,g.node('WorldPosition'),foot)
        g.connect(normal,uv,'Coordinates');g.connect(color,uv,'Coordinates')
    g.finish()
    return m.get_path_name()

def plant():
    world=e.require_world();named=e.all_named();ground=named['Valley of the Two Springs'];poses={};accepted=[]
    for name,x,y,s,yaw in json.loads((SOURCE/'Clumps.json').read_text()):
        hit=u.SystemLibrary.line_trace_single(world,e.vector((x,y,20)),e.vector((x,y,-2)),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
        if not hit:continue
        d=hit.to_dict();n=d['impact_normal'];p=d['impact_point']
        if d['hit_actor']!=ground or n.z<.50 or p.z<38:continue
        up=u.Vector(n.x*.48,n.y*.48,.52+n.z*.48);ang=math.radians(yaw)
        rot=u.MathLibrary.make_rot_from_zx(up,u.Vector(math.cos(ang),math.sin(ang),0))
        pose=u.Transform(p-u.Vector(0,0,2.8),rot,u.Vector(s,s,s));poses.setdefault(name,[]).append(pose);accepted.append([name,x,y,round(p.z/100,2)])
    if len(accepted)<20:raise RuntimeError(('Insufficient suitable understory sites',len(accepted)))
    for name,locations in poses.items():
        key='FT_Bank'+name;path=PACKAGE+'/'+key
        foliage=e.assets.load_asset(path) if e.assets.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset(key,PACKAGE,u.FoliageType_InstancedStaticMesh,u.FoliageType_InstancedStaticMeshFactory())
        u.InstancedFoliageActor.remove_all_instances(world,foliage)
        body=foliage.get_editor_property('body_instance');body.set_editor_property('collision_profile_name','NoCollision')
        foliage.set_editor_properties({'mesh':e.assets.load_asset(e.BASE+'/FloraStudies/SM_'+name),'body_instance':body,'cast_shadow':False,'cast_dynamic_shadow':False,'cast_static_shadow':False,'affect_distance_field_lighting':False,'cull_distance':u.Int32Interval(8300,9900)})
        e.assets.save_loaded_asset(foliage,False);u.InstancedFoliageActor.add_instances(world,foliage,locations)
    return accepted
