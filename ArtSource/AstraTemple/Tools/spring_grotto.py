"""Install the jointed West Canopy passage and inspect its clear walking strip."""
import json
import math
from editor import *
from stonework import import_mesh

SOURCE=ROOT/"SpringGrotto"
FOLDER=BASE+"/SpringGrotto"
SHELL="West Canopy Spring Grotto"

def finishes():
    defs=[
        ("M_GrottoJoint","JointedRock",.78,(.94,.91,.83)),
        ("M_GrottoWet","JointedRock",.46,(.71,.79,.72)),
        ("M_GrottoStrata","SedimentaryBand",.83,(.74,.76,.70)),
        ("M_GrottoMoss","mossy_rock",.83,(.58,.76,.51)),
        ("M_GrottoBed","brown_mud_rocks_01",.71,(.72,.72,.62)),
    ]
    result={}
    for name,src,rough,tint in defs:
        if src in ("JointedRock","SedimentaryBand"):
            t=[import_texture(SOURCE/"Textures"/f"T_{src}_{suffix}.jpg",FOLDER+"/Textures",suffix=="Roughness",suffix=="NormalGL") for suffix in ("Color","NormalGL","Roughness")]
            t[1].set_editor_property("flip_green_channel",True);assets.save_loaded_asset(t[1])
        else:
            t=[assets.load_asset(BASE+f"/Terrain/Textures/T_{src}_"+suffix) for suffix in ("Color","Normal","Rough")]
        if not all(t):raise RuntimeError(f"Missing grotto finish maps {src}")
        g=Graph(material(name,FOLDER+"/Materials"))
        pos=g.pair("Divide",g.node("WorldPosition"),g.const(215))
        normal=g.node("PixelNormalWS");weights=g.pair("Multiply",normal,normal)
        yz=g.mask(pos,False,True,True);xz=g.mask(pos,True,False,True);xy=g.mask(pos,True,True,False)
        a=g.pair("Multiply",g.texture(t[0],yz),g.mask(weights))
        b=g.pair("Multiply",g.texture(t[0],xz),g.mask(weights,False,True))
        c=g.pair("Multiply",g.texture(t[0],xy),g.mask(weights,False,False,True))
        photo=g.pair("Add",g.pair("Add",a,b),c)
        g.result(g.pair("Multiply",photo,g.node("Constant3Vector",constant=u.LinearColor(*tint,1))),"BASE_COLOR")
        g.result(g.texture(t[1],normal=True),"NORMAL")
        g.result(g.pair("Multiply",g.mask(g.texture(t[2],linear=True)),g.const(rough)),"ROUGHNESS")
        result[name]=g.finish()
    return result

def trace(start,end):
    hit=u.SystemLibrary.line_trace_single(require_world(),vector(start),vector(end),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
    return hit.to_dict() if hit and hit.to_dict().get("blocking_hit") else None

def install(rebuild=False):
    spec=json.loads((SOURCE/"grotto.json").read_text())
    native=import_mesh(SOURCE/"SM_WestSpringGrotto.fbx",FOLDER+"/Meshes",replace=rebuild,nanite=False,binding=finishes(),collision=True)
    active=all_named()
    mesh=assets.load_asset(FOLDER+"/Meshes/SM_WestSpringGrotto")
    shell=active.get(SHELL) or place(u.StaticMeshActor,SHELL,"West Canopy/Spring Grotto",spec["origin"])
    shell.set_actor_location(vector(spec["origin"]),False,True)
    shell.static_mesh_component.set_static_mesh(mesh)
    shell.static_mesh_component.set_collision_profile_name("BlockAll")
    def plant(label,kind,position,scale,yaw,normal=None):
        obj=active.get(label) or place(u.StaticMeshActor,label,"West Canopy/Spring Grotto/Detail",position)
        obj.set_actor_location(vector(position),False,True)
        rot=rotation(yaw)
        if normal and abs(normal.z)>.42:rot=u.MathLibrary.compose_rotators(rot,u.MathLibrary.make_rot_from_z(normal))
        obj.set_actor_rotation(rot,False)
        obj.set_actor_scale3d(u.Vector(scale,scale,scale))
        obj.static_mesh_component.set_static_mesh(assets.load_asset(BASE+"/Nature/Meshes/SM_"+kind))
        obj.static_mesh_component.set_collision_profile_name("NoCollision")
    for i,(kind,anchor,size,yaw) in enumerate(spec["botany"]):
        pos=list(anchor);normal=None
        if kind=="MossCushion":
            hit=trace((pos[0],pos[1],pos[2]+1.1),(pos[0],pos[1],pos[2]-.5))
            if hit:
                pos[2]=hit["impact_point"].z/100-.016
                normal=hit['impact_normal']
        plant(f"Grotto {kind} {i+1:02d}",kind,pos,size,yaw,normal)
    samples=spec["centerline"]
    for j,(k,w,size) in enumerate(((9,-1.8,.19),(14,1.8,.16),(16,-2.4,.23),(18,-2.8,.30),(19,-2.3,.17),(21,-3.25,.26),(23,-2.28,.15),(29,1.72,.12),(36,-1.9,.16),(41,1.76,.18))):
        x,y=samples[k];dx=samples[k+1][0]-samples[k-1][0];dy=samples[k+1][1]-samples[k-1][1];d=math.hypot(dx,dy)
        xx=x-dy/d*w;yy=y+dx/d*w;z=v.terrain(x,y)
        hit=trace((xx,yy,z+1.7),(xx,yy,z-2.2))
        if hit:
            p=hit['impact_point']
            plant(f"Grotto pebble {j+1:02d}","MossBoulder"+(f"0{j%6+1}" if j%6 else ""),[xx,yy,p.z/100-.044],size,23+j*91)
    # Local bounced sky from the two roof breaks, attenuated before the exterior.
    for j,k in enumerate((14,32,3,23,41)):
        x,y=samples[k];z=v.terrain(x,y)+2.32
        label=f"Skylight bounce at joint {j+1}"
        light=active.get(label) or place(u.PointLight,label,"West Canopy/Spring Grotto/Skylights",(x,y,z))
        light.set_actor_location(vector((x,y,z)),False,True)
        comp=light.light_component;comp.set_mobility(u.ComponentMobility.MOVABLE)
        comp.set_editor_properties({"intensity_units":u.LightUnits.CANDELAS,"intensity":(39000.,35500.,18300.,21600.,17500.)[j],
            "light_color":u.Color(209,225,229,255),"source_radius":72.,"attenuation_radius":860.,
            "cast_shadows":False,"indirect_lighting_intensity":.3})
    save()
    return native

def clearances():
    """Measure the built route above its actual collision tread in the loaded world."""
    points=json.loads((SOURCE/"grotto.json").read_text())["centerline"]
    columns=[];wall=[]
    for i in range(2,len(points)-2):
        x,y=points[i];dx=points[i+1][0]-points[i-1][0];dy=points[i+1][1]-points[i-1][1];l=math.hypot(dx,dy)
        nx=-dy/l;ny=dx/l;ground=v.terrain(x,y)
        for d in (-1.1,0,1.1):
            px=x+d*nx;py=y+d*ny
            floor=trace((px,py,ground+1.48),(px,py,ground-.83))
            if not floor:raise RuntimeError(f"Missing trail floor {i}/{d}")
            h=floor["impact_point"].z/100
            roof=trace((px,py,h+.18),(px,py,h+7.1))
            if roof:columns.append(roof['impact_point'].z/100-h)
        for sign in (-1,1):
            side=trace((x,y,ground+1.25),(x+nx*sign*6,y+ny*sign*6,ground+1.25))
            if side:
                p=side['impact_point'];wall.append(math.hypot(p.x/100-x,p.y/100-y))
    result={"stations":len(points)-4,"tested_width_m":2.2,"min_roof_clearance_m":min(columns) if columns else None,"min_wall_center_distance_m":min(wall) if wall else None}
    (ROOT/"Review/GrottoClearance.json").write_text(json.dumps(result,indent=2))
    return result

