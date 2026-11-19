"""Native PIE checks for the two restricted spawn areas, actual movement and input release."""
import json
import time
import traceback
import unreal as u
import arena

def start():
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    pc=u.GameplayStatics.get_player_controller(world,0)
    gs=u.GameplayStatics.get_game_state(world)
    if gs.get_editor_property("phase")==3:pc.replay_match()
    starts=u.GameplayStatics.get_all_actors_of_class(world,u.PlayerStart)
    bases={k:[a.get_actor_location() for a in starts if str(a.player_start_tag)==k] for k in ["Red","Blue"]}
    reference={k:sum(group[1:],group[0])/len(group) for k,group in bases.items()}
    out={"map":world.get_name(),"sample":"Native PIE. Enemy-base intrusion is deliberately staged. The running game performs the restriction and the team respawn.","zones":[]}
    path=arena.ROOT/"SpawnGameplay.json"
    st={"phase":0,"next":0,"started":time.monotonic()}
    move=u.load_asset("/Game/Input/Actions/IA_Move")
    def tick(dt):
        try:
            now=u.GameplayStatics.get_time_seconds(world)
            if gs.get_editor_property("phase")!=2:return True
            pawn=u.GameplayStatics.get_player_pawn(world,0)
            if not pawn or not pawn.is_alive():return True
            team=pawn.get_team()
            own="Red" if team==0 else "Blue"
            enemy="Blue" if team==0 else "Red"
            if st["phase"] in (0,2):
                if st["phase"]==2 and team==st["first"]:return True
                if st["phase"]==0:st["first"]=team
                spot=reference[enemy]+u.Vector(50,0,70)
                pawn.set_actor_location(spot,False,True)
                st.update(phase=st["phase"]+1,next=now+.4)
                out["zones"].append({"team":own,"intrusion_position_m":arena.xyz(spot)})
            elif st["phase"] in (1,3) and now>st["next"]:
                actual=pawn.get_actor_location()
                distance=float((actual-reference[own]).length())/100
                out["zones"][-1].update(return_position_m=arena.xyz(actual),distance_to_own_base_m=round(distance,2),passed=distance<7.5)
                if st["phase"]==1:
                    pc.join_team(1-team)
                    st["phase"]=2
                else:
                    st.update(phase=4,next=now+.6,origin=actual)
                    # Face the open plaza exit along the blue parapet; this is a real Enhanced Input action.
                    pc.set_control_rotation(u.Rotator(0,0,-88 if team==1 else 43))
                    for lp in u.ObjectIterator(u.LocalPlayer):
                        if not lp.get_name().startswith("Default__") and u.GameplayStatics.get_player_controller(lp,0)==pc:
                            st["input"]=u.get_local_player_subsystem(lp,u.EnhancedInputLocalPlayerSubsystem)
            elif st["phase"]==4:
                st["input"].inject_input_vector_for_action(move,u.Vector(0,1,0),[],[])
                if now>st["next"]:
                    st.update(phase=5,next=now+.36)
            elif st["phase"]==5 and now>st["next"]:
                at=pawn.get_actor_location()
                out["walk_m"]=round(float((at-st["origin"]).length())/100,2)
                out["released_speed_m_s"]=round(pawn.get_velocity().length()/100,3)
                pawn.jump()
                st.update(phase=6,next=now+.28,jump_z=at.z)
            elif st["phase"]==6 and now>st["next"]:
                out["jump_rise_m"]=round((pawn.get_actor_location().z-st["jump_z"])/100,2)
                pawn.stop_jumping()
                out["passed"]=all(v["passed"] for v in out["zones"]) and out["walk_m"]>1 and out["released_speed_m_s"]<.15 and out["jump_rise_m"]>.25
                path.write_text(json.dumps(out,indent=2),encoding="utf8")
                return False
            if time.monotonic()-st["started"]>45:raise RuntimeError("Timed out")
            return True
        except Exception:
            out["error"]=traceback.format_exc()
            path.write_text(json.dumps(out,indent=2),encoding="utf8")
            return False
    return str(u.register_ticker_callback(tick))

def shield_and_sides():
    w=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    pc=u.GameplayStatics.get_player_controller(w,0)
    mode=u.GameplayStatics.get_game_mode(w)
    gs=u.GameplayStatics.get_game_state(w)
    out={"sample":"Native PIE. A real team change and respawn are followed by isolated server damage probes. Ordinary match scores are validated separately."}
    path=arena.ROOT/"ProtectionAndDamage.json"
    state={"phase":0,"start":time.monotonic()}
    def tick(dt):
        try:
            if time.monotonic()-state["start"]>38:raise RuntimeError("Respawn probe timed out")
            if gs.get_editor_property("phase")!=2:return True
            pawn=u.GameplayStatics.get_player_pawn(w,0)
            if not pawn or not pawn.is_alive():return True
            if state["phase"]==0:
                state["side"]=1-pawn.get_team()
                pc.join_team(state["side"])
                state["phase"]=1
                return True
            if pawn.get_team()!=state["side"]:return True
            all_f=u.GameplayStatics.get_all_actors_of_class(w,u.load_class(None,"/Script/gameAstraForest.TempleFighter"))
            allies=[p for p in all_f if p!=pawn and p.is_alive() and p.get_team()==pawn.get_team()]
            foes=[p for p in all_f if p.is_alive() and p.get_team()!=pawn.get_team()]
            if not foes or not allies:return True
            def damage(source):
                before=pawn.get_health()
                applied=u.GameplayStatics.apply_damage(pawn,2.0,source.get_controller(),source,u.DamageType)
                return dict(before=before,after=pawn.get_health(),applied=applied)
            if state["phase"]==1:
                if not pawn.is_spawn_protected():raise RuntimeError("Fresh pawn was not protected")
                out["new_pawn_start_health"]=pawn.get_health()
                out["new_pawn_start_ammo"]=[pawn.get_magazine_ammo(),pawn.get_reserve_ammo()]
                out["protected_opponent_damage"]=damage(foes[0])
                pawn.set_trigger_held(True)
                pawn.set_trigger_held(False)
                out["protected_after_first_shot"]=pawn.is_spawn_protected()
                out["opponent_after_first_shot"]=damage(foes[0])
                out["default_friendly_fire"]=damage(allies[0])
                # Exercise expiry independently of the earlier fire cancellation.
                duration=mode.get_editor_property("spawn_protection_seconds")
                pawn.grant_spawn_protection(duration)
                state.update(phase=2,pawn=pawn,clock=u.GameplayStatics.get_time_seconds(w),duration=duration)
                return True
            elapsed=u.GameplayStatics.get_time_seconds(w)-state["clock"]
            if elapsed<state["duration"]-.15:
                if not pawn.is_spawn_protected():raise RuntimeError("Shield expired early")
                return True
            if pawn.is_spawn_protected():return True
            out["passive_expiry_seconds"]=round(elapsed,3)
            out["passed"]=out["new_pawn_start_health"]==100 and out["new_pawn_start_ammo"]==[30,120] and out["protected_opponent_damage"]["applied"]==0 and not out["protected_after_first_shot"] and out["opponent_after_first_shot"]["applied"]==2 and out["default_friendly_fire"]["applied"]==0 and abs(elapsed-state["duration"])<.3
            path.write_text(json.dumps(out,indent=2),encoding="utf8")
            return False
        except Exception:
            out["error"]=traceback.format_exc()
            path.write_text(json.dumps(out,indent=2),encoding="utf8")
            return False
    return str(u.register_ticker_callback(tick))
