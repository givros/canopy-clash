"""Walk the saved temple in offscreen PIE using its own Enhanced Input actions.
All waypoints are world metres. No teleport, transform move or AI navigation bypass is used.
"""
import json
import math
import time
import traceback
from datetime import datetime
from pathlib import Path

import unreal as u
import valley

REVIEW=Path(__file__).resolve().parents[1]/"Review"
ROOT=Path(__file__).resolve().parents[3]
MAP="/Game/AstraTemple/Maps/L_TempleOfTheCanopy"
ACTIVE=None

def routes():
    groups=[]
    def add(name,pts,tolerance=1.45):
        groups.append((name,[(x,y,z,tolerance) for x,y,z in pts]))
    approach=valley.TRAILS["Pilgrims approach"][4:]
    add("Jungle approach",approach)
    ax,ay=valley.BRIDGE_START;bx,by=valley.BRIDGE_END
    crossing=[(ax+(bx-ax)*t,ay+(by-ay)*t,4.0) for t in (.10,.30,.50,.70,.90,1.)]
    quay=[(-.5,21.7,4),(7.65,21.70,4),(11.72,21.70,4),(11.72,11,4),(13,0,4),(15.65,0,4)]
    add("Causeway and quay",crossing+quay,.68)
    stair=[]
    for i,(x,z) in enumerate(valley.STAIRS):
        steps=[(x+off,0,z+up) for off,up in [(0,0),(3.85,2.4),(7.92,4.8),(12.90,7.85),(14.6,8)]]
        stair+=steps;add("Stair flight "+str(i+1),steps,.75)
    chamber=[(68.6,0,28),(72.7,0,28),(77.5,0,28),(83,0,28),(89.3,0,28),(94.5,0,28)]
    add("Deity portal and ritual hall",chamber,.72)
    core=list(groups)
    add("Return through hall, down all stairs",list(reversed(chamber[:-1]))+list(reversed(stair))+[(13,0,4)],.85)
    add("Return across causeway",list(reversed(quay[:-2]))+list(reversed(crossing))+[(-48,16,4)],1.05)
    add("Return to jungle PlayerStart",list(reversed(approach[:-1]))+[(-83.8,13.4,6)],1.6)
    options={"main":groups}
    # Each excursion starts in a fresh PIE run at the real PlayerStart and
    # physically walks the connecting section before the designated side trail.
    def ground(points):
        return [(x,y,valley.terrain(x,y)) for x,y in points]
    # Enter uphill shrines through their real doors. The terrain trail datum
    # marks a site; its centreline alone can cross an occupied side wall.
    east=valley.TRAILS["East jungle gallery"]
    eastern_shrine=ground([(-38,54),(-32.1,55),(-30.2,55.4),(-27.3,55.7)])+[(-27,54,5.46),(-26.8,52.4,5.46)]+ground([(-27.3,55.7),(-21,55)])
    options["east"]=[("Jungle approach to gallery",[(-76,24,6,1.7),(-69,29,5,1.7)]),
                     ("East jungle gallery",[(*q,1.8) for q in east[1:3]+eastern_shrine+east[4:]])]
    cloister=valley.TRAILS["Broken cloister"][:-1]
    chapel=ground([(24.9,-54.4)])+[(24,-57,10),(23.2,-58.4,10)]
    options["cloister"]=[("Broken cloister walk",[(*q,2.0) for q in cloister+chapel])]
    rain=valley.TRAILS["Rain court"][1:]
    options["spring"]=core+[("Rain court",[(*q,1.6) for q in rain[:3]]),("Spring trail",[(*q,2.15) for q in valley.TRAILS["Spring trail"]])]
    west=valley.TRAILS["West canopy trail"][3:]
    grotto=ground([(105,-7),(107,-10),(109,-14),(114.5,-18),(120,-22),(122,-27),(123,-30)])
    hidden_entry=[(111.6,-68.6,55),(107.4,-69.7,55)]
    high=valley.TRAILS["High shrine ridge"]
    summit=valley.TRAILS["Crown watch spur"]+[(134.7,-72.5,75)]
    split=high.index((91,-90,55))+1
    ridge=high[1:split]+[(90.8,-88.3,55)]+high[split:-1]+summit
    options["ridge"]=core+[("Rear terrace to canopy",[(98,0,28,1.5),(101,0,28,1.7)]),("Spring grotto",[(*q,1.55) for q in grotto]),("West canopy trail",[(*q,2.1) for q in west+hidden_entry]),
                          ("High shrine ridge",[(*q,2.2) for q in ridge])]
    return options

def expected_support(group,gx,gy):
    if group.startswith('Stair flight') or group.startswith('Return through'):
        for (foot,_),name in zip(valley.STAIRS,['Steps of the Basin','Processional Stair','Sanctuary Ascent']):
            if foot+.9<gx<foot+12.65 and abs(gy)<1:return [name]
    if group.startswith('Causeway') or group.startswith('Return across'):
        if -47.2<gx<-9.4:return ['BridgeSpan','Causeway']
        if -7.0<gx<7.1 and gy>18.:return ['BridgeSpan','Quay']
    if ('hall' in group or 'portal' in group) and 75.<gx<90.:return ['Hall of the Open Sky','RitualHall']
    return []

def serial(p):return [round(n/100.,3) for n in (p.x,p.y,p.z)]
def human(obj):
    if not obj:return None
    try:return obj.get_actor_label()
    except Exception:return obj.get_name()
def quantile(seq,f):
    ordered=sorted(seq);p=f*(len(ordered)-1);lo=int(p)
    return round(ordered[lo]+(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(p-lo),3)
def controller_subsystem(controller,world):
    getattr_cls=getattr(u,"SubsystemBlueprintLibrary",None)
    fn=getattr(getattr_cls,"get_local_player_sub_system_from_player_controller",None)
    if fn:return fn(controller,u.EnhancedInputLocalPlayerSubsystem)
    # LocalPlayer is owned by Engine. Its world context resolves the active PIE client.
    for lp in u.ObjectIterator(u.LocalPlayer):
        if not lp.get_name().startswith("Default__") and u.GameplayStatics.get_player_controller(lp,0)==controller:
            return u.get_local_player_subsystem(lp,u.EnhancedInputLocalPlayerSubsystem)
    raise RuntimeError("No LocalPlayer owned by this PIE game instance")

class Walk:
    def __init__(self,route):
        self.editor_log=ROOT/'Saved/Logs/AstraAuthoringMcp.log';self.log_start=self.editor_log.stat().st_size if self.editor_log.exists() else 0;self.renderer_warnings=[]
        self.route=route;self.itinerary=routes()[route]
        self.goals=[(group,i+1,p) for group,pts in self.itinerary for i,p in enumerate(pts)]
        self.idx=0;self.phase="waiting";self.now=time.perf_counter();self.spawn_requested=self.now
        self.best=float("inf");self.last_progress=self.now;self.last_write=0;self.last_sample=0
        self.last_frame=None;self.wall_ms=[];self.trace=[];self.visits=[];self.startup={}
        self.walk_m=0.;self.last_pos=None;self.csv=False;self.native_profile=False;self.detour=None;self.attempt=0
        self.stepped=0;self.air_frames=0;self.max_air=0.;self.air_since=None
        self.world=None;self.controller=None;self.pawn=None;self.input=None;self.handle=None
        self.first_yaw=0;self.first_pos=None;self.first_camera_yaw=None;self.stop_time=None
        self.last_section=None;self.tick_stalls=[];self.status="starting";self.error=None
        self.file=REVIEW/("Traversal_"+route+".json");REVIEW.mkdir(parents=True,exist_ok=True)
    def save(self):
        data={"renderer_warnings":self.renderer_warnings,"route":self.route,"status":self.status,"phase":self.phase,"startup":self.startup,"at_goal":self.idx,"total_goals":len(self.goals),"walked_m":round(self.walk_m,2),"checkpoints":self.visits,"samples":self.trace,"failure":self.error,"detours":self.tick_stalls,"airborne_samples":self.air_frames,"max_continuous_air_seconds":round(self.max_air,3),"wall_time_cadence":{},"native_csv_basename":getattr(self,"csv_name",None)}
        if self.wall_ms:
            data["wall_time_cadence"]={"scope":"Offscreen PIE engine ticker wall clock while walking. Includes editor and driver overhead. This measures main-loop cadence, not presentation or GPU completion.","frames":len(self.wall_ms),"mean_fps":round(1000*len(self.wall_ms)/sum(self.wall_ms),2),"median_ms":quantile(self.wall_ms,.5),"p95_ms":quantile(self.wall_ms,.95),"p99_ms":quantile(self.wall_ms,.99),"max_ms":round(max(self.wall_ms),2)}
        temp=self.file.with_suffix(".tmp");temp.write_text(json.dumps(data,indent=2),encoding="utf-8");temp.replace(self.file);self.last_write=self.now
    def finish(self,status,reason=None):
        self.status=status;self.error=reason;self.phase="finished"
        if self.world:
            safekeys=getattr(self,"keys",["W"])
            for key in safekeys:u.SystemLibrary.execute_console_command(self.world,"Input.-key "+key)
        if self.input and self.pawn:
            self.input.inject_input_vector_for_action(self.move,u.Vector(0,0,0),[],[])
        if self.csv and self.world:
            u.SystemLibrary.execute_console_command(self.world,"CsvProfile STOP")
            u.SystemLibrary.execute_console_command(self.world,"r.GPUCsvStatsEnabled "+str(self.prior_gpu_csv))
            self.csv=False
        if self.editor_log.exists():
            with self.editor_log.open('rb') as log:
                log.seek(self.log_start)
                self.renderer_warnings=[row for row in log.read().decode('utf-8',errors='replace').splitlines() if 'LogRenderer: Warning:' in row]
        self.save()
        u.log("Astra traversal "+self.route+": "+status+" - "+str(reason or ""))
        u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
        return False
    def boot(self):
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:
            if self.now-self.spawn_requested>180:raise RuntimeError("No PIE world after startup request")
            return
        w=worlds[0];pawn=u.GameplayStatics.get_player_character(w,0);pc=u.GameplayStatics.get_player_controller(w,0)
        if not pawn or not pc:
            if self.now-self.spawn_requested>180:raise RuntimeError("No possessed first-person character")
            return
        self.world=w;self.controller=pc;self.pawn=pawn;self.cm=pawn.character_movement
        self.cap=pawn.capsule_component
        self.move=u.load_asset("/Game/Input/Actions/IA_Move");self.look=u.load_asset("/Game/Input/Actions/IA_Look")
        self.input=controller_subsystem(pc,w)
        if not self.input:raise RuntimeError("Missing Enhanced Input subsystem")
        action_context=u.load_asset("/Game/Input/IMC_Default")
        mappings=action_context.get_editor_property("default_key_mappings").get_editor_property("mappings")
        position=pawn.get_actor_location();p=serial(position)
        self.startup={"map_instance":w.get_path_name(),"pawn":pawn.get_class().get_path_name(),"player_controller":pc.get_class().get_path_name(),"position_m":p,"viewport_px":list(pc.get_viewport_size()),"capsule_radius_cm":self.cap.get_scaled_capsule_radius(),"capsule_half_height_cm":self.cap.get_scaled_capsule_half_height(),"max_step_cm":self.cm.get_editor_property("max_step_height"),"max_walk_cm_s":self.cm.get_editor_property("max_walk_speed"),"walkable_slope_deg":self.cm.get_walkable_floor_angle(),"default_input_context_priority":self.input.has_mapping_context(action_context),"action_keys":[[m.key.export_text().removeprefix("(KeyName=").removesuffix(")"),m.action.get_name()] for m in mappings if m.action],"engine_version":u.SystemLibrary.get_engine_version(),"r_screen_percentage":u.SystemLibrary.get_console_variable_float_value("r.ScreenPercentage"),"t_max_fps":u.SystemLibrary.get_console_variable_float_value("t.MaxFPS")}
        self.startup['render_cvars']={key:u.SystemLibrary.get_console_variable_int_value(key) for key in (
            'r.Shadow.Virtual.NonNanite.IncludeInCoarsePages','r.Shadow.Virtual.Cache','r.VelocityOutputPass','r.Velocity.EnableVertexDeformation','r.EyeAdaptation.CachedLightingPreExposure','r.Water.SingleLayer.Reflection')}
        for key in ('r.Shadow.Virtual.ResolutionLodBiasDirectional','r.TSR.History.ScreenPercentage'):
            self.startup['render_cvars'][key]=u.SystemLibrary.get_console_variable_float_value(key)
        if math.hypot(p[0]+83.8,p[1]-13.4)>2.5:raise RuntimeError("PlayerStart mismatch: "+str(p))
        if self.startup["default_input_context_priority"] is None and self.now-self.spawn_requested<4.0:return
        self.first_pos=position;self.first_rotation=pc.get_control_rotation();self.first_yaw=self.first_rotation.yaw;self.startup["initial_camera_yaw"]=self.first_yaw;self.phase="look";self.phase_time=self.now;self.status="running";self.save()
    def support(self,pos):
        result=self.cm.find_floor(pos)
        hit=result.hit_result.to_dict() if result.blocking_hit else {}
        actor=hit.get("hit_actor");pt=hit.get("impact_point");normal=hit.get("impact_normal")
        if not actor:
            try:actor=self.pawn.get_movement_base_actor()
            except Exception:pass
        return {"walkable":bool(result.walkable_floor),"on_ground":bool(self.cm.is_moving_on_ground()),"floor":human(actor),"floor_dist_cm":round(result.floor_dist,2),"impact_m":serial(pt) if pt else None,"slope_deg":round(math.degrees(math.acos(max(-1,min(1,normal.z)))),2) if normal else None}
    def blockers(self,pos,aim):
        dx,dy=aim;direction=u.Vector(dx,dy,0)
        results=[]
        for h in (4.,48.,110.):
            start=pos+u.Vector(0,0,h-self.cap.get_scaled_capsule_half_height());end=start+direction*230
            hit=u.SystemLibrary.line_trace_single(self.world,start,end,u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[self.pawn],u.DrawDebugTrace.NONE)
            if hit:
                d=hit.to_dict();results.append({"height_cm":h,"actor":human(d.get("hit_actor")),"point_m":serial(d["impact_point"])})
        return results
    def tick(self,dt):
        try:
            self.now=time.perf_counter()
            if self.phase=="waiting":
                self.boot();return True
            if not self.pawn or not u.SystemLibrary.is_valid(self.pawn):
                raise RuntimeError("First-person pawn destroyed before route completion")
            if self.phase=="look":
                self.input.inject_input_vector_for_action(self.look,u.Vector(1.0,0,0),[],[])
                if self.now-self.phase_time<.48:return True
                final=self.controller.get_control_rotation().yaw;turn=abs((final-self.first_yaw+180)%360-180)
                self.startup["look_action_yaw_delta_deg"]=round(turn,3)
                if turn<.06:raise RuntimeError("IA_Look did not rotate player's view")
                self.controller.set_control_rotation(self.first_rotation)
                self.keys=["W","Z","Q"] if self.route=="main" else ["W"];self.key_index=0
                self.startup["verified_key_deltas_m"]={}
                self.startup["azerty_context_priority"]=self.input.has_mapping_context(u.load_asset("/Game/AstraTemple/Input/IMC_TempleAZERTY"))
                self.phase="capture" if self.route in ("main","ridge") else "key_ready"
                self.capture_step=0;self.phase_time=self.now;return True
            if self.phase=="capture":
                if self.now-self.phase_time<.30:return True
                suffix="FirstPerson" if self.capture_step==0 else "FirstPersonWithUI"
                prefix="PIE_Ridge_" if self.route=="ridge" else "PIE_"
                path=(REVIEW/(prefix+suffix+".png")).as_posix()
                flags="-nosuffix" if self.capture_step==0 else "-showui -nosuffix"
                u.SystemLibrary.execute_console_command(self.world,"shot "+flags+" filename="+path)
                if self.capture_step==1:
                    widget_type=getattr(u,"UserWidget",None)
                    widgets=[] if not widget_type else [w for w in u.ObjectIterator(widget_type) if w.is_in_viewport() and u.GameplayStatics.get_player_controller(w,0)==self.controller]
                    self.startup["visible_user_widgets"]=[w.get_class().get_path_name() for w in widgets if w.is_visible()] if widget_type else None
                    self.startup["camera_component_names"]=[c.get_name() for c in self.pawn.get_components_by_class(u.CameraComponent) if c.is_active()]
                    self.phase="key_ready"
                self.capture_step+=1;self.phase_time=self.now;return True
            if self.phase=="key_ready":
                if self.now-self.phase_time<.22:return True
                self.key_start=self.pawn.get_actor_location();self.phase="key";self.phase_time=self.now
                u.SystemLibrary.execute_console_command(self.world,"Input.+key "+self.keys[self.key_index]);return True
            if self.phase=="key":
                if self.now-self.phase_time<.40:return True
                key=self.keys[self.key_index];u.SystemLibrary.execute_console_command(self.world,"Input.-key "+key)
                key_delta=self.pawn.get_actor_location()-self.key_start;coords=serial(key_delta)
                self.startup["verified_key_deltas_m"][key]=coords
                heading=math.radians(self.first_yaw);forward=key_delta.x*math.cos(heading)+key_delta.y*math.sin(heading);right=-key_delta.x*math.sin(heading)+key_delta.y*math.cos(heading)
                if key in ("W","Z") and forward<18:raise RuntimeError(key+" did not move the possessed character forward")
                if key=="Q" and right>-18:raise RuntimeError("Q did not strafe the possessed character left")
                self.key_index+=1
                if self.key_index<len(self.keys):
                    self.phase="key_ready";self.phase_time=self.now;return True
                self.phase="walk";self.last_progress=self.now;self.last_frame=self.now;self.last_pos=self.pawn.get_actor_location()
                self.csv_name="Astra_"+self.route+"_"+datetime.now().strftime("%Y%m%d_%H%M%S")
                self.prior_gpu_csv=u.SystemLibrary.get_console_variable_int_value("r.GPUCsvStatsEnabled")
                u.SystemLibrary.execute_console_command(self.world,"r.GPUCsvStatsEnabled 1")
                u.SystemLibrary.execute_console_command(self.world,"CsvProfile STARTFILE="+self.csv_name)
                u.SystemLibrary.execute_console_command(self.world,"CsvProfile START")
                self.csv=True;self.save();return True
            wall=self.now-self.last_frame;self.last_frame=self.now
            self.wall_ms.append(wall*1000)
            pos=self.pawn.get_actor_location();xyz=serial(pos);dxy=math.hypot(pos.x-self.last_pos.x,pos.y-self.last_pos.y)/100
            if dxy>max(2.5,dt*self.cm.max_walk_speed*.016):raise RuntimeError("Unexpected discontinuity in pawn movement")
            self.walk_m+=dxy;self.last_pos=pos;self.stepped+=1
            if not self.cm.is_moving_on_ground():
                self.air_frames+=1
                if self.air_since is None:self.air_since=self.now
                self.max_air=max(self.max_air,self.now-self.air_since)
            else:self.air_since=None
            group,checkpoint,(gx,gy,gz,ztol)=self.goals[self.idx]
            if self.last_section!=group:
                u.SystemLibrary.execute_console_command(self.world,"Trace.Bookmark AstraWalk_"+group.replace(" ","_").replace(",",""))
                self.last_section=group
            ax,ay=(gx,gy) if self.detour is None else self.detour
            vx,vy=ax-xyz[0],ay-xyz[1];dist=math.hypot(vx,vy)
            floor_z=xyz[2]-self.cap.get_scaled_capsule_half_height()/100.
            if self.now-self.last_sample>=.40:
                self.trace.append({"t":round(self.now-self.spawn_requested,2),"section":group,"position_m":xyz,"ground_z_m":round(floor_z,3),"speed_mps":round(self.pawn.get_velocity().length()/100,2),**self.support(pos)})
                self.last_sample=self.now
            if self.now-self.last_write>4:self.save()
            if dist<.45:
                if self.detour is not None:
                    self.detour=None;self.best=float("inf");self.last_progress=self.now;return True
                support=self.support(pos)
                if not support["on_ground"] and self.now-self.last_progress<1.2:return True
                if abs(floor_z-gz)>ztol or not support["walkable"]:
                    return self.finish("failed",{"reason":"Incorrect support elevation or unwalkable surface","section":group,"target_m":[gx,gy,gz],"position_m":xyz,"measured_foot_z_m":floor_z,"support":support})
                expected=expected_support(group,xyz[0],xyz[1])
                if expected and not any(term in (support['floor'] or '') for term in expected):
                    return self.finish('failed',{'reason':'Required architectural surface does not support the capsule','section':group,'target_m':[gx,gy,gz],'position_m':xyz,'expected':expected,'support':support})
                if self.route=="main" and ((group=="Causeway and quay" and checkpoint==3) or (group=="Deity portal and ritual hall" and checkpoint==4)):
                    name="Bridge" if group=="Causeway and quay" else "Sanctuary"
                    path=(REVIEW/("PIE_Player_"+name+".png")).as_posix()
                    u.SystemLibrary.execute_console_command(self.world,"shot -nosuffix filename="+path)
                if self.route=="ridge" and group=="Spring grotto" and checkpoint==4:
                    path=(REVIEW/"PIE_Player_Grotto.png").as_posix()
                    u.SystemLibrary.execute_console_command(self.world,"shot -nosuffix filename="+path)
                if self.route=="east" and group=="East jungle gallery" and (gx,gy) in ((-38,54),(-27,54)):
                    filename,flags=("PIE_East_WithUI.png","-showui -nosuffix") if gx==-38 else ("PIE_Player_LowerFord.png","-nosuffix")
                    u.SystemLibrary.execute_console_command(self.world,"shot "+flags+" filename="+(REVIEW/filename).as_posix())
                self.visits.append({"section":group,"waypoint":checkpoint,"goal_m":[gx,gy,gz],"position_m":xyz,"foot_z_m":round(floor_z,3),**support})
                self.idx+=1;self.best=float("inf");self.attempt=0;self.last_progress=self.now
                if self.idx>=len(self.goals):return self.finish("passed")
                return True
            if dist<self.best-.10:self.best=dist;self.last_progress=self.now
            if self.now-self.last_progress>2.6:
                aim=(vx/dist,vy/dist);blocking=self.blockers(pos,aim)
                if (self.route!="main" and group not in ("Jungle approach","Causeway and quay","Deity portal and ritual hall") and not group.startswith("Stair") and self.attempt<4):
                    self.attempt+=1;side=1 if self.attempt%2==1 else -1;offset=1.05 if self.attempt<3 else 2.05
                    self.detour=(xyz[0]+aim[0]*.34-aim[1]*side*offset,xyz[1]+aim[1]*.34+aim[0]*side*offset)
                    self.tick_stalls.append({"section":group,"position_m":xyz,"blockers":blocking,"walked_detour_target":self.detour})
                    self.best=float("inf");self.last_progress=self.now;return True
                return self.finish("failed",{"reason":"Movement stalled","section":group,"station":checkpoint,"target_m":[gx,gy,gz],"position_m":xyz,"support":self.support(pos),"forward_blockers":blocking})
            self.controller.set_control_rotation(u.Rotator(0,0,math.degrees(math.atan2(vy,vx))))
            speed=self.cm.max_walk_speed/100.;strength=min(1.,max(.16,dist/(max(.045,dt)*speed*1.6)))
            self.input.inject_input_vector_for_action(self.move,u.Vector(0,strength,0),[],[])
            return True
        except Exception:
            return self.finish("failed",{"reason":"Driver exception","traceback":traceback.format_exc()})
def start(route="main"):
    global ACTIVE
    level=u.get_editor_subsystem(u.LevelEditorSubsystem)
    if level.is_in_play_in_editor():raise RuntimeError("A play session is already running")
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0]!=MAP:raise RuntimeError("Open the authored temple first")
    ACTIVE=Walk(route);ACTIVE.save()
    level.editor_request_begin_play()
    ACTIVE.handle=u.register_ticker_callback(ACTIVE.tick)
    return str(ACTIVE.file)
