"""Build and evaluate the staggered remains of the East Quay screen walls."""
from collections import Counter
from pathlib import Path
import json
import math
import unreal as u
import arena
import editor as e

FOLDER = "Deathmatch/East Quay"
WALLS = [
    ("SpillwayBay", "Causeway Scupper Pier", (-18.60, 18.71, 3.95), 8.2, (.61,.330,.367)),
    ("BatteredBay", "Quay North Recessed Wall", (-6.25, 23.32, 3.95), 3.0, (.59,.300,.33)),
    ("TerraceBay", "Quay South Processional Wall", (3.12, 20.05, 3.95), 181.0, (.57,.332,.30)),
]
G = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "Review"


def build(stage=None):
    world=arena.current()
    actors=e.all_named()
    for asset,name,at,yaw,sc in WALLS:
        actor=actors.get(name) or e.place(u.StaticMeshActor,name,FOLDER,at,yaw)
        actor.set_actor_location_and_rotation(e.vector(at),e.rotation(yaw),False,True)
        actor.set_actor_scale3d(u.Vector(*sc))
        comp=actor.static_mesh_component
        comp.set_static_mesh(e.assets.load_asset(e.BASE+"/Architecture/Meshes/SM_Astra_"+asset))
        comp.set_collision_profile_name("BlockAll")
    blue_home()
    exclude_retaining_crowns()
    if stage:
        save_copy(stage)
    elif not u.EditorLoadingAndSavingUtils.save_current_level():raise RuntimeError("Quay walls could not be saved")
    return [name for _,name,_,_,_ in WALLS]


def save_copy(stage):
    directory=G/"Saved/Deathmatch"/stage
    directory.mkdir(exist_ok=True)
    target=directory/"L_CanopyDeathmatch.umap"
    command=f'OBJ SAVEPACKAGE PACKAGE="{arena.ARENA}" FILE="{target.as_posix()}" SILENT=true KEEPDIRTY=true'
    u.SystemLibrary.execute_console_command(arena.current(),command)
    if not target.is_file():raise RuntimeError("Native map snapshot is missing")
    return str(target)


def compare(label,filename,kind,original_starts=True):
    world=arena.current()
    names=e.all_named()
    walls=[names[name] for _,name,_,_,_ in WALLS]
    labels={w.get_actor_label() for w in walls}
    centres=[]
    for team in ("Red","Blue"):
        starts=[a.get_actor_location() for a in e.actors.get_all_level_actors() if isinstance(a,u.PlayerStart) and str(a.player_start_tag)==team]
        centres.append((sum(p.x for p in starts)/len(starts)/100,sum(p.y for p in starts)/len(starts)/100))
    if original_starts:
        centres=[(-84.35,12.41667),(14.,25.68333)]
    def trace(a,b,ignore):
        hit=u.SystemLibrary.line_trace_single(world,e.vector(a),e.vector(b),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,ignore,u.DrawDebugTrace.NONE)
        if not hit:return ""
        comp=hit.to_dict()["hit_component"]
        return comp.get_owner().get_actor_label() if comp else "world"
    counts={}
    events=[]
    rows=Path(filename).read_text(errors="replace").splitlines()
    for line in rows:
        token="CB|"+kind+"|"
        if token not in line:continue
        r=line.split(token)[1].split("|")
        team=int(r[1])
        if kind=="impact":
            fatal=int(r[2])
            p=list(map(float,r[3:]))
        else:
            fatal=1
            p=list(map(float,r[2:]))
            p[2]+=.66
            p[5]+=.27
        start,end=p[:3],p[3:]
        if abs(start[0])>1000 or abs(end[0])>1000:continue
        near=math.dist(centres[1-team],end[:2])<20.
        long=math.dist(start,end)>60.
        scopes=["all",("blue" if team==0 else "red")+"_victims"]
        if near:
            scopes.append(("blue" if team==0 else "red")+"_home_20m")
            if long:scopes.append(("blue" if team==0 else "red")+"_home_20m_over_60m")
        events.append((start,end,scopes,fatal))
    # Restore the old screen and standard for the original geometry pass.
    legacy=[(names["Blue Quay Screen"],(8.10,26.4,3.61),180,(.74,.86,.38)),
            (names["Blue Woven Standard"],(8.94,27.84,3.99),180,None)]
    previous=[actor.get_actor_transform() for actor,_,_,_ in legacy]
    try:
        for actor,pos,yaw,scale in legacy:
            actor.set_actor_location_and_rotation(e.vector(pos),e.rotation(yaw),False,True)
            if scale:actor.set_actor_scale3d(u.Vector(*scale))
        original=[trace(start,end,walls) for start,end,_,_ in events]
    finally:
        for (actor,_,_,_),transform in zip(legacy,previous):
            actor.set_actor_transform(transform,False,True)
    labels.update(actor.get_actor_label() for actor,_,_,_ in legacy)
    for (start,end,scopes,fatal),before in zip(events,original):
        after=trace(start,end,[])
        for scope in scopes:
            counter=counts.setdefault(scope,Counter())
            counter["samples"]+=1
            if not before:counter["open_before"]+=1
            if not after:counter["open_after"]+=1
            if not before and after in labels:
                counter["newly_intercepted"]+=1
                counter[after]+=1
                if fatal:counter["fatal_segments_intercepted"]+=1
    counts={k:dict(v) for k,v in counts.items()}
    path=OUT/("QuaySightlines"+label+".json")
    path.write_text(json.dumps({"source":str(Path(filename).relative_to(G)),"mode":kind,
        "method":"Exact authoritative point-damage trace start and hit point" if kind=="impact" else
        "Reconstructed eye to torso at recorded elimination positions. Historical logs rounded pawn centres to 0.1 m.",
        "before_geometry":"Original screen and banner transforms, three added architectural pieces ignored. After uses the installed map transforms and includes all three pieces.",
        "events":counts},indent=2))
    return counts


def clear_widths(label):
    """Measure each opening with a 68 cm diameter standing body at every 5 cm sample."""
    world=arena.current()
    result={}
    for name,x,y in [("Scupper",-18.5,20.20),("North",-5.85,21.70),("South",2.7,21.70)]:
        strips=[]
        for j in range(141):
            yy=y-3.5+j*.05
            p=(x,yy,5.08)
            floor=u.SystemLibrary.line_trace_single(world,e.vector((x,yy,4.28)),e.vector((x,yy,3.64)),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
            hit=u.SystemLibrary.capsule_trace_single(world,e.vector((x-.8,yy,5.08)),e.vector((x+.8,yy,5.08)),34,67,u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
            if floor and not hit:
                if not strips or abs(yy-strips[-1][-1])>.051:strips.append([])
                strips[-1].append(yy)
        result[name]=[{"centres_m":[round(a[0],2),round(a[-1],2)],"physical_width_m":round(a[-1]-a[0]+.68,2)} for a in strips if len(a)>2]
    (OUT/("QuayClearance"+label+".json")).write_text(json.dumps(result,indent=2))
    return result

def exclude_retaining_crowns():
    # Keep the flagged exterior cornices as solid scenery. The paving is clear east of x9.2.
    world=arena.current()
    names=e.all_named()
    for label,y0,y1 in (("West Cornice",-29.1,-3.77),("Central Cornice",-2.04,15.04),("North Cornice",25.77,29.06)):
        p=(8.08,(y0+y1)*.5,4.15)
        tag="Quay "+label+" Navigation"
        zone=names.get(tag) or e.place(u.NavModifierVolume,tag,"Deathmatch/Navigation",p)
        zone.set_actor_location(e.vector(p),False,True)
        zone.set_actor_scale3d(u.Vector(1.20,(y1-y0)*.5,.85))
        zone.set_editor_property("area_class",u.NavArea_Null)
    u.SystemLibrary.execute_console_command(world,"RebuildNavigation")


def blue_home():
    """Place the six arrivals behind the existing carved screen on the inner quay."""
    actors=e.all_named()
    screen=actors["Blue Quay Screen"]
    screen.set_actor_location_and_rotation(e.vector(arena.BLUE_SCREEN_POINT),e.rotation(180),False,True)
    screen.set_actor_scale3d(u.Vector(.74,.82,.38))
    banner=actors["Blue Woven Standard"]
    banner.set_actor_location_and_rotation(e.vector((9.06,3.90,4.01)),e.rotation(180),False,True)
    for i,(point,bearing) in enumerate(arena.BLUE_ARRIVALS,1):
        ground=arena.floor((point[0],point[1],4))
        if not ground or abs(ground[2]+1.04-point[2])>.25:
            raise RuntimeError(f"Missing quay paving under Blue Arrival {i}")
        actors[f"Blue Arrival {i}"].set_actor_location_and_rotation(e.vector(point),e.rotation(bearing),False,True)
