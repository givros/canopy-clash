"""Author the playable temple variant and inspect the original shooter example in Unreal."""
from collections import Counter
from pathlib import Path
import json
import hashlib
import math
import unreal as u
import editor as e

ROOT = Path(__file__).resolve().parent
REFERENCE = "/Game/Variant_Shooter/Lvl_ArenaShooter"
ARENA = "/Game/AstraTemple/Maps/L_CanopyDeathmatch"

def xyz(p):
    return [round(v / 100, 2) for v in (p.x, p.y, p.z)]

def load(path):
    if not e.levels.load_level(path):
        raise RuntimeError("Could not load " + path)
    return u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()

def inspect_reference():
    world = load(REFERENCE)
    actors = list(e.actors.get_all_level_actors())
    notable = []
    for actor in actors:
        cls = actor.get_class().get_name()
        if isinstance(actor, u.PlayerStart) or any(s in cls for s in ("NPC","NavMesh","Pickup","Spawner","JumpPad")):
            origin, extent = actor.get_actor_bounds(False)
            notable.append(dict(name=actor.get_actor_label(), cls=cls, location_m=xyz(actor.get_actor_location()), extent_m=xyz(extent)))
    assets = u.AssetRegistryHelpers.get_asset_registry().get_assets_by_path("/Game/Variant_Shooter",recursive=True)
    roles = [str(a.package_name) for a in assets if str(a.asset_class_path.asset_name) in ("Blueprint","WidgetBlueprint","StateTree","EnvQuery")]
    result = dict(map=world.get_path_name(), game_mode=world.get_world_settings().get_editor_property("default_game_mode").get_name(), actors=dict(Counter(a.get_class().get_name() for a in actors)), notable=notable, native_systems=sorted(roles))
    (ROOT / "ArenaStudy.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    load(e.MAP)
    return result["actors"]

def open_variant():
    creating=not e.assets.does_asset_exist(ARENA)
    if creating:
        if not u.EditorLoadingAndSavingUtils.save_map(e.require_world(), ARENA):
            raise RuntimeError("Could not save temple variant")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != ARENA:
        world = load(ARENA)
    if creating and e.assets.does_asset_exist("/Game/TempleTDM/Rules/BP_CanopyDeathmatch"):
        mode=e.assets.load_blueprint_class("/Game/TempleTDM/Rules/BP_CanopyDeathmatch")
        world.get_world_settings().set_editor_property("default_game_mode",mode)
        if not e.levels.save_current_level():
            raise RuntimeError("Could not save the match rules on the new level")
    return world.get_path_name()

def current():
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != ARENA:
        raise RuntimeError("Open the deathmatch variant first.")
    return world

def navpos(point, extent=(1.5,1.5,2.5)):
    return u.NavigationSystemV1.project_point_to_navigation(current(),e.vector(point),None,None,e.vector(extent))

def floor(point):
    p=e.vector(point)
    hit=u.SystemLibrary.line_trace_single(current(),p+u.Vector(0,0,190),p-u.Vector(0,0,440),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
    if not hit: return None
    v=hit.to_dict()
    return xyz(v["impact_point"])

RED_ARRIVALS=[
    ((-83,12,7.04),55), ((-82,9.4,7.04),-37), ((-85.6,9.6,7.27),-33),
    ((-86.8,12.8,7.09),31), ((-86.1,15,7.41),23), ((-82.6,15.7,7.01),19),
]
BLUE_ARRIVALS=[
    ((9.50,-4.75,5.058),-79.4), ((9.75,-.75,5.047),-88.2),
    ((9.75,1.25,5.053),86.8), ((10.50,3.00,5.052),90.2),
    ((9.75,5.25,5.055),88.4), ((11.00,-5.50,5.056),-86.7),
]
BLUE_SCREEN_POINT=(8.10,2.50,3.61)
NODES={
    "Roots Gate":(-63,20,5.13),"Gate Steps":(-54,16,4.46),"Causeway":(-34,18,4.45),"East Quay":(-7,21.7,4.49),
    "Basin Plaza":(12,4,4.44),"First Landing":(31,0,12.13),"Sanctuary Steps":(49,0,20.13),"Keeper Landing":(66.8,0,28.25),
    "Garden Fork":(-64,40,5.63),"Litter Walk":(-47,52,5.69),"Ford Chapel":(-30.46,49.84,5.76),
    "Forest Gallery":(-12,53,5.56),"Orchid Bend":(3,49.5,5.44),"Ford Landing":(11,39,4.98),
    "Cloister Threshold":(-88,-10,6.99),"West Court Bend":(-74,-34,7.01),"Cloister Court":(-54,-48,5.51),
    "Cloister Terrace":(-14,-55,7.42),"West Chapel Path":(10,-51,8.38),
    "West Spring Bridge":(13,-36,4.44),"West Plaza":(12,-23,4.45)
}

def landmarks():
    positions=[p for p,bearing in RED_ARRIVALS+BLUE_ARRIVALS]+list(NODES.values())
    return {str(p):{"floor":floor(p),"nav":xyz(v) if (v:=navpos(p)) else None} for p in positions}

def build_navigation():
    w=current()
    v=e.all_named().get("Canopy Navigation") or e.place(u.NavMeshBoundsVolume,"Canopy Navigation","Deathmatch/Navigation",(35,0,40))
    v.set_actor_location(e.vector((35,0,40)),False,True)
    v.set_actor_scale3d(u.Vector(169,130,52))
    nav=u.NavigationSystemV1.get_navigation_system(w)
    nav.on_navigation_bounds_updated(v)
    import team_navigation
    starts=[a for a in e.actors.get_all_level_actors() if isinstance(a,u.PlayerStart)]
    if all(sum(str(a.player_start_tag)==team for a in starts)==6 for team in ("Red","Blue")):
        team_navigation.install()
    else:
        team_navigation.install_west_spring_exclusion(e.actors)
        u.SystemLibrary.execute_console_command(w,"RebuildNavigation")
    return str(v.get_actor_bounds(False))

def assemble():
    current()
    names=e.all_named()
    for a in list(names.values()):
        if str(a.get_folder_path()).startswith(("Deathmatch/Teams","Deathmatch/Routes","Deathmatch/Cover","Deathmatch/West Crossing","Deathmatch/Water")):e.actors.destroy_actor(a)
    from stonework import piece
    added=[]
    for i, y in enumerate((-40.05,-32.12)):
        piece("BridgeSpan",f"West Spring Arch {i+1}",(13,y,4.0),90,(.794,.88,.76),"Deathmatch/West Crossing")
    for name,center,scale in [("Lower Basin",(-20,0,-5),(65,64,5.7)),("Western Spring",(14.7,-37,-3.2),(8,8,5.22))]:
        water=e.place(u.NavModifierVolume,name+" Navigation Bed","Deathmatch/Water",center,scale=scale)
        water.set_editor_property("area_class",u.NavArea_Null)
    for mesh,label,p,yaw,scale in [
        ("TerraceBay","Red Gate Screen",(-77.9,11.7,6),9,(.78,.82,.37)),
        ("BatteredBay","Red Garden Wing",(-85.3,18.1,6),77,(.51,.54,.30)),
        ("TerraceBay","Blue Quay Screen",(8.1,2.5,4),180,(.74,.82,.38)),
        ("BatteredBay","Blue Garden Wing",(14.5,32.1,4),-85,(.5,.54,.31)),
        ("Colonnade","Garden Milepost",(-45,50.7,5.2),-19,(.88,.88,.47)),
        ("Balustrade","Ford Processional Rail",(-18.7,54.6,5.3),87,(1,.67,1)),
        ("Colonnade","Quay Marker",(8.7,14.3,4),32,(.83,.83,.56)),
        ("Balustrade","Plaza Watch Rail",(14,9.7,4),76,(1,.61,1.06))]:
        hit=floor(p)
        if not hit:raise RuntimeError("No ground for "+label)
        hit[2]-=.13
        if mesh in ("TerraceBay","BatteredBay"):hit[2]-=.25
        if label=="Blue Quay Screen":hit=BLUE_SCREEN_POINT
        piece(mesh,label,hit,yaw,scale,"Deathmatch/Cover")
        added.append(label)
    for team,arrivals in (("Red",RED_ARRIVALS),("Blue",BLUE_ARRIVALS)):
        for i,(point,yaw) in enumerate(arrivals):
            actor=e.place(u.PlayerStart,f"{team} Arrival {i+1}",f"Deathmatch/Teams/{team}",point,yaw)
            actor.set_editor_property("player_start_tag",team)
    for label,p in NODES.items():
        actor=e.place(u.TargetPoint,label,"Deathmatch/Routes",p)
        actor.set_editor_property("tags",["TemplePatrol"])
    for a in e.actors.get_all_level_actors():
        if isinstance(a,u.PlayerStart) and a.get_actor_label()=="Jungle approach":e.actors.destroy_actor(a)
    author_lanes(save=False)
    build_navigation()
    if not u.EditorLoadingAndSavingUtils.save_current_level():raise RuntimeError("Arena save failed")
    return added

def inspect_navigation():
    w=current()
    actors=list(e.actors.get_all_level_actors())
    starts={t:[a for a in actors if isinstance(a,u.PlayerStart) and str(a.player_start_tag)==t] for t in ("Red","Blue")}
    samples={a.get_actor_label():xyz(a.get_actor_location()) for aa in starts.values() for a in aa}
    samples.update({a.get_actor_label():xyz(a.get_actor_location()) for a in actors if a.actor_has_tag("TemplePatrol")})
    on_nav={n:navpos(p,(1.1,1.1,2.1)) for n,p in samples.items()}
    routes={
        "Causeway":["Red Arrival 1","Roots Gate","Gate Steps","Causeway","East Quay","Blue Arrival 1"],
        "Eastern Gallery":["Red Arrival 1","Garden Fork","Litter Walk","Ford Chapel","Forest Gallery","Orchid Bend","Ford Landing","Blue Arrival 1"],
        "Cloister":["Red Arrival 1","Cloister Threshold","West Court Bend","Cloister Court","Cloister Terrace","West Chapel Path","West Spring Bridge","West Plaza","Basin Plaza","Blue Arrival 1"],
        "Terraces":["Basin Plaza","First Landing","Sanctuary Steps","Keeper Landing"]
    }
    legs={}
    for label,names in routes.items():
        legs[label]=[]
        for src,dst in zip(names,names[1:]):
            p,q=on_nav[src],on_nav[dst]
            path=u.NavigationSystemV1.find_path_to_location_synchronously(w,p,q) if p and q else None
            ok=bool(path and path.is_valid() and not path.is_partial())
            legs[label].append(dict(start=src,end=dst,complete=ok,length_m=round(path.get_path_length()/100,2) if ok else None,points_m=[xyz(v) for v in path.path_points] if ok else []))
    clear=[]
    sightlines=[]
    for a in starts["Red"]:
        for b in starts["Blue"]:
            offset=u.Vector(0,0,57)
            hit=u.SystemLibrary.line_trace_single(w,a.get_actor_location()+offset,b.get_actor_location()+offset,u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
            source=a.get_actor_label();destination=b.get_actor_label()
            if not hit:clear.append([source,destination])
            comp=hit.to_dict()["hit_component"] if hit else None
            sightlines.append({"red":source,"blue":destination,"blocked":bool(hit),"blocking_actor":comp.get_owner().get_actor_label() if comp else None})
    file=ROOT/"ArenaNavigation.json"
    output={"map":ARENA,"spawns":{a.get_actor_label():{"point_m":samples[a.get_actor_label()],"nav_m":xyz(on_nav[a.get_actor_label()]) if on_nav[a.get_actor_label()] else None} for aa in starts.values() for a in aa},"direct_spawn_sightlines":clear,"legs":legs}
    disk=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))/"Content"/(ARENA[6:]+".umap")
    output["map_sha256"]=hashlib.sha256(disk.read_bytes()).hexdigest()
    output["pair_sightlines"]=sightlines
    all_starts=starts["Red"]+starts["Blue"]
    for start in all_starts:
        point=start.get_actor_location()
        blocked=u.SystemLibrary.capsule_trace_single(w,point,point+u.Vector(0,0,2),34,96,u.TraceTypeQuery.ECC_VISIBILITY,True,all_starts,u.DrawDebugTrace.NONE)
        datum=output["spawns"][start.get_actor_label()]
        datum["clear_character_capsule"]=blocked is None
        datum["orientation_yaw"]=round(start.get_actor_rotation().yaw,1)
        datum["forward_ground_coverage"]=[]
        for dist in (225,450):
            foot=point+start.get_actor_forward_vector()*dist-u.Vector(0,0,98)
            projected=navpos(xyz(foot),(.9,.9,1.7))
            datum["forward_ground_coverage"].append({"distance_m":dist/100,"nearest_nav_offset_m":round((projected-foot).length()/100,2) if projected else None})
    file.write_text(json.dumps(output,indent=2),encoding="utf8")
    return {k:[(l["complete"],l["length_m"]) for l in parts] for k,parts in legs.items()}|{"visible_spawn_pairs":clear}

def review_camera(label,eye,target,filename):
    w=current()
    if e.levels.is_in_play_in_editor():raise RuntimeError("Stop play before capturing the authored level")
    view = e.all_named().get(label)
    if not view:
        view=e.place(u.CameraActor,label,"Deathmatch/Composition",eye)
    eye=e.vector(eye)
    direction=u.MathLibrary.find_look_at_rotation(eye,e.vector(target))
    view.set_actor_location_and_rotation(eye,direction,False,True)
    view.camera_component.field_of_view=70
    output=ROOT/"Review"
    output.mkdir(exist_ok=True)
    u.AutomationLibrary.take_high_res_screenshot(1280,720,str(output/(filename+".png")),view,delay=2.1)


def verify_saved_arena():
    world=current()
    for actor in e.actors.get_all_level_actors():
        if isinstance(actor,u.CameraActor) and str(actor.get_folder_path())=="Deathmatch/Composition":
            e.actors.destroy_actor(actor)
    if not u.EditorLoadingAndSavingUtils.save_current_level():
        raise RuntimeError("Could not save playable map")
    load(ARENA)
    return inspect_saved_arena()

def inspect_saved_arena():
    """Inspect the loaded saved map without saving or modifying its package."""
    world=current()
    mode=world.get_world_settings().get_editor_property("default_game_mode")
    rules=u.get_default_object(mode)
    classes={"game_mode":mode.get_path_name()}
    for key in ("default_pawn_class","bot_controller_class"):
        classes[key]=rules.get_editor_property(key).get_path_name()
    nav=inspect_navigation()
    placed=e.all_named()
    expected=[f"Ford Path {kind} {i}" for kind in ("Steps","Footing") for i in range(1,5)]
    if not all(name in placed for name in expected):raise RuntimeError("Missing ford masonry")
    actors=list(e.actors.get_all_level_actors())
    families={"patrol_nodes":sum(a.actor_has_tag("TemplePatrol") for a in actors),
              "player_starts":sum(isinstance(a,u.PlayerStart) for a in actors),
              "review_cameras":sum(isinstance(a,u.CameraActor) and str(a.get_folder_path())=="Deathmatch/Composition" for a in actors)}
    u.SystemLibrary.execute_console_command(world,"MAP CHECK")
    spatial=json.loads((ROOT/"ArenaNavigation.json").read_text())
    families.update(total=len(actors),team_navigation_areas=sum("DeploymentNavigation" in actor.get_class().get_name() for actor in actors),
                    quay_threshold_pieces=sum(actor.get_actor_label().startswith("South Quay Threshold") for actor in actors))
    ordered={}
    for a in actors:
        if isinstance(a,u.TargetPoint):
            for tag in a.tags:
                parts=str(tag).split(".")
                if len(parts)==3 and parts[0]=="Patrol":ordered.setdefault(parts[1],[]).append((int(parts[2]),a.get_actor_label()))
    starts={team:[spatial["spawns"][f"{team} Arrival {i}"]["point_m"] for i in range(1,7)] for team in ("Red","Blue")}
    (ROOT/"Review"/"SavedArena.json").write_text(json.dumps({"map":world.get_path_name(),"map_sha256":spatial["map_sha256"],
        "classes":classes,"actors":families,"navigation":nav,"ordered_team_starts_m":starts,
        "spawn_pairs_checked":len(spatial["pair_sightlines"]),"occluded_spawn_pairs":sum(q["blocked"] for q in spatial["pair_sightlines"]),
        "clear_starting_capsules":sum(q["clear_character_capsule"] for q in spatial["spawns"].values()),
        "tagged_patrol_routes":{k:[n for _,n in sorted(vals)] for k,vals in sorted(ordered.items())}},indent=2),encoding="utf-8")
    return classes

def playable_blueprints():
    world=current()
    package="/Game/TempleTDM/Rules"
    e.assets.make_directory(package)
    classes={}
    for name,parent in [("BP_CanopyRanger","TempleFighter"),("BP_CanopyBot","TempleBotController"),("BP_CanopyDeathmatch","TempleMatchMode")]:
        parent_class=u.load_class(None,"/Script/gameAstraForest."+parent)
        if not parent_class:raise RuntimeError("The native project module must be loaded")
        path=package+"/"+name
        asset=e.assets.load_asset(path) if e.assets.does_asset_exist(path) else None
        if not asset:
            factory=u.BlueprintFactory()
            factory.set_editor_property("parent_class",parent_class)
            asset=u.AssetToolsHelpers.get_asset_tools().create_asset(name,package,u.Blueprint,factory)
        if not asset:raise RuntimeError(path)
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        cls=asset.generated_class()
        if name=="BP_CanopyDeathmatch":
            defaults=u.get_default_object(cls)
            defaults.set_editor_property("default_pawn_class",classes["BP_CanopyRanger"])
            defaults.set_editor_property("bot_controller_class",classes["BP_CanopyBot"])
        e.assets.save_loaded_asset(asset,False)
        classes[name]=cls
    mode=classes["BP_CanopyDeathmatch"]
    world.get_world_settings().set_editor_property("default_game_mode",mode)
    if not u.EditorLoadingAndSavingUtils.save_current_level():raise RuntimeError("Failed to save assigned mode")
    return [v.get_path_name() for v in classes.values()]

def spawn_orientation(apply=False):
    w=current()
    rows=[]
    def distance(eye,yaw):
        a=math.radians(yaw)
        target=eye+u.Vector(math.cos(a)*6500,math.sin(a)*6500,0)
        h=u.SystemLibrary.line_trace_single(w,eye,target,u.TraceTypeQuery.ECC_VISIBILITY,True,[],u.DrawDebugTrace.NONE)
        return round(u.MathLibrary.vector_distance(eye,h.to_dict()["impact_point"])/100,2) if h else 65
    for a in e.actors.get_all_level_actors():
        if not isinstance(a,u.PlayerStart):continue
        team=str(a.player_start_tag)
        pt=a.get_actor_location()
        eye=pt+u.Vector(0,0,60)
        before=a.get_actor_rotation().yaw
        ideal=26 if team=="Red" else 170
        def yaw_delta(y):return abs((y-ideal+180)%360-180)
        def cost(y):
            lengths=[distance(eye,y+d) for d in (-21,-10,0,10,21)]
            return min(lengths)*.53+sum(min(32,z) for z in lengths)*.27+min(48,lengths[2])*.45-yaw_delta(y)*.33
        if team=="Blue":
            index=int(a.get_actor_label().rsplit(" ",1)[-1])-1
            best=BLUE_ARRIVALS[index][1]
        else:best=max(range(ideal-75,ideal+76,4),key=cost)
        if apply:a.set_actor_rotation(e.rotation(best),False)
        rows.append(dict(spawn=a.get_actor_label(),previous=before,yaw=best,previous_clear_m=distance(eye,before),clear_m=distance(eye,best),min_central_fan_m=min(distance(eye,best+d) for d in (-10,0,10))))
    if apply:
        u.EditorLoadingAndSavingUtils.save_current_level()
        (ROOT/"SpawnOrientation.json").write_text(json.dumps(rows,indent=2))
    return rows

def author_lanes(save=True):
    world=current()
    names=e.all_named()
    for label,p in NODES.items():
        if label not in names:
            names[label]=e.place(u.TargetPoint,label,"Deathmatch/Routes",p)
    lanes=[
        ["Roots Gate","Gate Steps","Causeway","East Quay","Basin Plaza"],
        ["Garden Fork","Litter Walk","Ford Chapel","Forest Gallery","Orchid Bend","Ford Landing"],
        ["Cloister Threshold","West Court Bend","Cloister Court","Cloister Terrace","West Chapel Path","West Spring Bridge","West Plaza"],
        ["Cloister Threshold","West Court Bend","Cloister Court","Cloister Terrace","West Chapel Path","West Spring Bridge","West Plaza","First Landing"]
    ]
    for name in {label for lane in lanes for label in lane} | {"Sanctuary Steps","Keeper Landing"}:
        tags=["TemplePatrol"]
        tags += [f"Patrol.{i}.{j}" for i,lane in enumerate(lanes) for j,label in enumerate(lane) if label==name]
        names[name].set_editor_property("tags",tags)
    if save and not u.EditorLoadingAndSavingUtils.save_current_level(): raise RuntimeError("Failed to save patrol routes")
    return lanes


def set_terrace_route(labels):
    """Replace only the ordered terrace patrol tags on the existing native waypoints."""
    current()
    if len(labels)!=len(set(labels)) or len(labels)<2:
        raise ValueError("The terrace route requires distinct ordered waypoints")
    actors={p.get_actor_label():p for p in e.actors.get_all_level_actors() if isinstance(p,u.TargetPoint) and p.actor_has_tag("TemplePatrol")}
    missing=set(labels)-set(actors)
    if missing:raise RuntimeError("Missing patrol points: "+", ".join(sorted(missing)))
    stations={name:i for i,name in enumerate(labels)}
    changed=[]
    for name,actor in actors.items():
        previous=[str(t) for t in actor.tags]
        tags=[t for t in previous if not t.startswith("Patrol.3.")]
        if name in stations:tags.append(f"Patrol.3.{stations[name]}")
        if tags!=previous:
            actor.modify()
            actor.set_editor_property("tags",tags)
            changed.append(name)
    return changed
