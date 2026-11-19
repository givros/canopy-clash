"""Seat a measured rock relief on the main falls and build the Crown corner footing."""
from pathlib import Path
import json,math
import editor as e
import unreal as u
from stonework import import_mesh
SOURCE=e.ROOT/'FallsGeology'
BASE=e.BASE+'/FallsGeology'
def material():
    g=e.Graph(e.material('M_SprayLedges',BASE+'/Materials'));uv=g.node("TextureCoordinate");vertex=g.node('VertexColor')
    def maps(package,stem,names):
        return [e.assets.load_asset(package+'/'+stem+s) for s in names]
    grot=e.BASE+'/SpringGrotto/Textures';ter=e.BASE+'/Terrain/Textures'
    basalt=maps(grot,'T_JointedRock_',('Color','NormalGL','Roughness'))
    moss=maps(ter,'T_mossy_rock_',('Color','Normal','Rough'))
    if not all(basalt+moss):raise RuntimeError('Unresolved geological textures')
    base=g.texture(basalt[0],uv);lichen=g.texture(moss[0],g.pair('Multiply',uv,g.const(1.22)))
    colony=g.pair('Multiply',g.mask(vertex),g.const(.76))
    stone=g.blend(base,lichen,colony)
    # Mineral layers retain a restrained warm tint with dark damp seams near the water curtain.
    ochre=g.pair('Multiply',stone,g.node('Constant3Vector',constant=u.LinearColor(1.16,1.04,.82,1)))
    color=g.blend(stone,ochre,g.mask(vertex,False,False,True))
    wet=g.mask(vertex,False,True)
    after=g.blend(color,g.pair('Multiply',color,g.node('Constant3Vector',constant=u.LinearColor(.63,.72,.68,1))),wet)
    g.result(after,'BASE_COLOR');g.result(g.texture(basalt[1],uv,normal=True),'NORMAL')
    g.result(g.pair('Multiply',g.mask(g.texture(basalt[2],uv,linear=True)),g.blend(g.const(.95),g.const(.48),wet)),'ROUGHNESS')
    return g.finish()
def trace(start,end,ignore=()):
    hit=u.SystemLibrary.line_trace_single(e.require_world(),e.vector(start),e.vector(end),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,list(ignore),u.DrawDebugTrace.NONE)
    return hit.to_dict() if hit and hit.to_dict()['blocking_hit'] else None
def install(rebuild=False):
    spec=json.loads((SOURCE/'escarpment.json').read_text())
    bindings={'M_SprayLedges':material()}
    for n in ('M_Astra_ShadeStone','M_Astra_MossStone'):
        bindings[n]=e.assets.load_asset(e.BASE+'/Architecture/Materials/'+n)
    for name in ('SM_SpringSprayCliff','SM_CrownCornerFoundation'):
        import_mesh(SOURCE/(name+'.fbx'),BASE+'/Meshes',replace=rebuild,nanite=True,binding=bindings)
    active=e.all_named()
    def piece(name,mesh,folder,pos,yaw=0,scale=1.,decoration=False):
        m=e.assets.load_asset(mesh)
        if not m:raise RuntimeError(mesh)
        a=active.get(name) or e.place(u.StaticMeshActor,name,folder,pos)
        a.set_actor_location_and_rotation(e.vector(pos),e.rotation(yaw),False,True)
        a.set_actor_scale3d(u.Vector(scale,scale,scale));a.static_mesh_component.set_static_mesh(m)
        a.static_mesh_component.set_collision_profile_name('NoCollision' if decoration else 'BlockAll')
        return a
    cliff=piece("Spray-polished ledges of the high falls",BASE+'/Meshes/SM_SpringSprayCliff',"Terrain/Escarpments/Upper Falls",spec['origin'])
    crown=piece("Footing beneath Crown shrine hillside corner",BASE+'/Meshes/SM_CrownCornerFoundation',"Secondary Ruins/Foundations",(124.264,-74.511,75),-132)
    roots=[];retained=set()
    for i,(kind,p,scale,yaw) in enumerate(spec['plants']):
        x,y,z=p
        # A vertical world trace seats every rooted clump onto the visible surface itself.
        h=trace((x+.10,y,z+.57),(x+.10,y,z-.58))
        if not h:continue
        q=h['impact_point'];n=h['impact_normal']
        if n.z<.24 or h['hit_actor']!=cliff:continue
        pos=(q.x/100,q.y/100,q.z/100-.036);roots.append(pos)
        a=piece("Upper falls "+kind+" "+str(i+1).zfill(2),e.BASE+'/Nature/Meshes/SM_'+kind,"Vegetation/Upper Falls",pos,yaw,scale,True)
        retained.add(a.get_actor_label())
        if kind=='MossCushion':
            a.set_actor_rotation(u.MathLibrary.compose_rotators(e.rotation(yaw),u.MathLibrary.make_rot_from_z(n)),False)
    for label,a in active.items():
        if str(a.get_folder_path())=='Vegetation/Upper Falls' and label not in retained:
            e.actors.destroy_actor(a)
    result=e.save()
    return result,len(roots)
def support():
    hit=trace((124.264,-74.511,74.89),(124.264,-74.511,72))
    landscape=next(a for a in e.actors.get_all_level_actors() if isinstance(a,u.LandscapeProxy))
    crown=e.all_named()["Footing beneath Crown shrine hillside corner"]
    ignore=[a for a in e.actors.get_all_level_actors() if a!=landscape]
    ground=trace((124.264,-74.511,75.4),(124.264,-74.511,70),ignore)
    cf=trace((124.264,-74.511,75.5),(124.264,-74.511,71),[a for a in e.actors.get_all_level_actors() if a!=crown])
    result=dict(corner_xy_m=(124.264,-74.511),landscape_m=ground['impact_point'].z/100,foundation_top_m=cf['impact_point'].z/100,footing_bottom_m=71.52,paving_m=75.)
    (e.ROOT/'Review/CrownFooting.json').write_text(json.dumps(result,indent=2));return result

