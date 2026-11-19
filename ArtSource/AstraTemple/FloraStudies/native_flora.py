"""Native masked two-sided plant materials and rooted specimen placement."""
from pathlib import Path
import math
import sys
import unreal as u

SOURCE=Path(__file__).resolve().parent
sys.path.insert(0,str(SOURCE.parent/'Tools'))
from editor import Graph, assets, import_texture, material, require_world
from stonework import import_mesh
from editor import actors, vector
import valley

PACKAGE='/Game/AstraTemple/FloraStudies'
NAMES=['WoodFernFountain','WoodFernFan','WoodFernYoung','ElephantEar']

def build_family(name):
    maps={}
    for channel in ['ColorAlpha','ARM','NormalDX']:
        file=SOURCE/'Maps'/('T_'+name+'_'+channel+'.png')
        texture=import_texture(file,PACKAGE+'/Textures',linear=channel=='ARM',normal=channel=='NormalDX')
        if channel=='ColorAlpha':
            texture.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_BC7)
            texture.set_editor_property('srgb',True)
        assets.save_loaded_asset(texture,False)
        maps[channel]=texture
    g=Graph(material('M_'+name,PACKAGE+'/Materials'))
    foliage=next(getattr(u.MaterialShadingModel,k) for k in dir(u.MaterialShadingModel) if k.endswith('FOLIAGE'))
    g.m.set_editor_properties({'two_sided':True,'blend_mode':u.BlendMode.BLEND_MASKED,'shading_model':foliage,'opacity_mask_clip_value':.34,'used_with_instanced_static_meshes':True})
    pigment=g.texture(maps['ColorAlpha'])
    g.result(pigment,'BASE_COLOR')
    g.result(pigment,'OPACITY_MASK','A')
    g.result(g.pair('Multiply',g.const(.42),pigment),'SUBSURFACE_COLOR')
    arm=g.texture(maps['ARM'],linear=True)
    for pin,out in [('AMBIENT_OCCLUSION','R'),('ROUGHNESS','G'),('METALLIC','B')]:g.result(arm,pin,out)
    g.result(g.texture(maps['NormalDX'],normal=True),'NORMAL')
    m=g.finish()
    names=['ElephantEar'] if name=='ElephantEar' else NAMES[:3]
    report=[]
    for specimen in names:
        leaf=import_mesh(SOURCE/('SM_'+specimen+'.fbx'),PACKAGE,False,False,{'M_'+name:m},collision=False)
        loaded=assets.load_asset(PACKAGE+'/SM_'+specimen)
        if loaded.get_material(0)!=m:raise ValueError(str(leaf))
        report.append(leaf)
    return report


# Species, size multiplier, yaw and preferred rooting location, in Unreal metres.
PLANTINGS={
    'Foregate':[
        ('ElephantEar',2.35,28,-49.5,11.1),('WoodFernFountain',1.65,-30,-50.6,11.02),
        ('WoodFernYoung',1.3,85,-53.2,10.39),('WoodFernFan',1.4,57,-49.32,8.0),
        ('WoodFernYoung',1.13,163,-47.4,7.95)],
    'Near bank':[
        ('ElephantEar',2.48,-67,-45.88,23.18),('WoodFernFan',1.48,128,-45.75,24.62),
        ('WoodFernYoung',1.25,-24,-46.6,25.53),('WoodFernFountain',1.68,3,-48.45,25.25)],
    'Spring margins':[
        ('WoodFernFountain',1.52,-153,50.2,-53.05),('WoodFernYoung',1.16,47,51.47,-53.09),
        ('ElephantEar',1.81,114,-34.8,46.85),('WoodFernFan',1.36,27,-36.05,47.25),
        ('WoodFernYoung',1.38,68,11.25,45.41)]}

def ground(world,x,y):
    h=valley.terrain(x,y)
    hit=u.SystemLibrary.line_trace_single(world,vector((x,y,h+3)),vector((x,y,h-2)),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
    if hit:
        data=hit.to_dict()
        ob=data['hit_actor']
        if ob and ob.get_actor_label()=='Valley of the Two Springs':
            p,n=data['impact_point'],data['impact_normal']
            if abs(p.z/100-h)<.17 and n.z>.63 and p.z>25:return p.z/100,n

def margin_free(world,x,y):
    h=valley.terrain(x,y)
    hit=u.SystemLibrary.line_trace_single(world,vector((x,y,h+3)),vector((x,y,h-2)),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
    if not hit:return False
    actor=hit.to_dict()['hit_actor']
    if not actor:return False
    label=actor.get_actor_label()
    return label=='Valley of the Two Springs' or label=='SM_ForegateRootCrawl'

def planting():
    world=require_world()
    existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
    result=[]
    plan=[]
    for region,group in PLANTINGS.items():
        for i,(sp,size,yaw,x0,y0) in enumerate(group):
            label=f'{region} {sp} {i+1:02d}'
            picked=None
            offsets=[(0,0)]+[(r*math.cos(j*math.pi/8),r*math.sin(j*math.pi/8)) for r in [.27,.62,1.02,1.38,1.78,2.25,2.68,3.10] for j in range(16)]
            for dx,dy in offsets:
                x,y=x0+dx,y0+dy
                h=ground(world,x,y)
                if not h:continue
                radius=size*({'ElephantEar':.36,'WoodFernFountain':.44,'WoodFernFan':.37,'WoodFernYoung':.25}[sp])
                if valley.line_sample(x,y,valley.BRIDGE_START,valley.BRIDGE_END)[0]<2.55+radius:continue
                if valley.trail_sample(x,y)[0]<1.55+radius:continue
                if not all(margin_free(world,x+radius*math.cos(j*math.pi/4),y+radius*math.sin(j*math.pi/4)) for j in range(8)):continue
                if any(math.hypot(x-xx,y-yy)<.70*(r+radius) for _,_,_,xx,yy,_,_,r,_ in plan):continue
                picked=(label,sp,size,x,y,h[0],yaw,radius,region)
                break
            if not picked:raise RuntimeError('No exposed soil around '+label)
            plan.append(picked)
    for label,sp,size,x,y,z,yaw,radius,region in plan:
        mesh=assets.load_asset(PACKAGE+'/SM_'+sp)
        loc=vector((x,y,z-.012))
        rotation=u.Rotator(0,0,yaw)
        actor=existing.get(label) or actors.spawn_actor_from_object(mesh,loc,rotation)
        actor.set_actor_label(label)
        actor.set_folder_path('Flora Studies/'+region)
        actor.set_actor_location_and_rotation(loc,rotation,False,True)
        actor.set_actor_scale3d(u.Vector(size,size,size))
        actor.static_mesh_component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        result.append((label,round(x,2),round(y,2),round(z,3),round(valley.line_sample(x,y,valley.BRIDGE_START,valley.BRIDGE_END)[0]-radius,2)))
    return result
