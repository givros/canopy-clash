"""Inspect the eastern ford where the bot movement review flagged a ledge."""
import json
import math
import unreal as u
import arena
import editor as e

DIAGNOSTICS=e.ROOT.parents[1]/"Saved"/"Deathmatch"/"FordDiagnosis"


def describe(hit):
    if not hit:
        return None
    fields = hit.to_dict()
    actor = fields.get("hit_actor") or fields.get("actor")
    component = fields.get("hit_component")
    if not actor and component:
        actor = component.get_owner()
    return dict(actor=actor.get_actor_label() if actor else "",
                component=component.get_name() if component else "",
                point=arena.xyz(fields["impact_point"]), normal=str(fields["impact_normal"]))


def inspect(tag):
    world = arena.current()
    rows = []
    for y in [37.5, 38.5, 39.5, 40.5, 41.5]:
        for x in [3, 4, 4.6, 5, 5.5, 6, 6.5, 7, 8, 9, 10]:
            start = e.vector((x, y, 7.5))
            end = e.vector((x, y, -1))
            hit = u.SystemLibrary.line_trace_single(world,start,end,u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
            floor = describe(hit)
            nav = arena.navpos((x,y,3.3),(1.,1.,2.4))
            row = dict(x=x,y=y,floor=floor,nav=arena.xyz(nav) if nav else None)
            if floor:
                here=e.vector((x,y,floor["point"][2]+.98))
                there=here+u.Vector(110,0,0)
                row["forward_capsule"] = describe(u.SystemLibrary.capsule_trace_single(world,here,there,34,96,u.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[],u.DrawDebugTrace.NONE))
            rows.append(row)
    DIAGNOSTICS.mkdir(parents=True,exist_ok=True)
    filename=DIAGNOSTICS/("Ford"+tag+".json")
    filename.write_text(json.dumps(rows,indent=2),encoding="utf-8")


def bank_profile():
    world=arena.current()
    vegetation=[a for a in e.actors.get_all_level_actors() if "FoliageActor" in a.get_class().get_name()]
    data=[]
    for y in (37.4,39.6,41.8):
        row=[]
        for x in range(-1,12):
            hit=u.SystemLibrary.line_trace_single(world,e.vector((x,y,9)),e.vector((x,y,-5)),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,vegetation,u.DrawDebugTrace.NONE)
            sample=describe(hit)
            row.append(sample["point"][2] if sample else None)
        data.append(row)
    return data


def build_steps():
    world=arena.current()
    names=e.all_named()
    group="Deathmatch/East Ford"
    y=39.65
    # Rise per flight follows the surveyed bank. The bottom tread meets the water
    # and the last course opens directly onto the route behind the blue quay.
    edges=[(1.50,.20),(3.55,1.80),(5.40,3.24),(7.12,4.56),(9.05,4.79)]
    def walking_surface(label,x0,z0,x1,z1):
        angle=math.atan2(z1-z0,x1-x0)
        half_depth=.54
        ox=math.sin(angle)*half_depth
        oz=-math.cos(angle)*half_depth
        center=((x0+x1)*.5+ox,y,(z0+z1)*.5+oz)
        scale=(math.hypot(x1-x0,z1-z0)*.5+.075,1.94,half_depth)
        volume=names.get(label) or e.place(u.BlockingVolume,label,group,center)
        volume.set_actor_location_and_rotation(e.vector(center),e.rotation(pitch=math.degrees(angle)),False,True)
        volume.set_actor_scale3d(u.Vector(*scale))
        volume.brush_component.set_collision_profile_name("BlockAll")
    # Fighter capsules climb a continuous walk surface along the tread noses.
    # The same solid surface receives the weapon trace and contact effects.
    def stone(model,name,p,s):
        actor=names.get(name) or e.place(u.StaticMeshActor,name,group,p,scale=s)
        actor.set_actor_location_and_rotation(e.vector(p),e.rotation(),False,True)
        actor.set_actor_scale3d(u.Vector(*s))
        comp=actor.static_mesh_component
        comp.set_static_mesh(e.assets.load_asset(e.BASE+"/Architecture/Meshes/SM_Astra_"+model))
        actor.set_actor_enable_collision(False)
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    stone("ApproachSteps","Ford Submerged Steps",(-.55,y,-1.27),(2.05/2.1,.66,1.47/.8))
    walking_surface("Ford Submerged Walk Surface",-.55,-1.21,1.50,.28)
    for index,((start,z),(end,top)) in enumerate(zip(edges,edges[1:]),1):
        for model,name,p,s in [
            ("ApproachSteps",f"Ford Path Steps {index}",(start,y,z),((end-start)/2.1,.66,(top-z)/.8)),
            ("Paving",f"Ford Path Footing {index}",((start+end)*.5,y,z-.105),((end-start)/8.,.466,6.6))]:
            stone(model,name,p,s)
        walking_surface(f"Ford Walk Surface {index}",start,z+.08,end,top+.08)
    # Preserve the basin exclusion around a narrow strip of wading steps.
    areas=[
        ("Lower Basin Navigation Bed",-85,45,-64,37.64),
        ("North Basin Navigation Bed",-85,45,41.66,64),
        ("Ford Water Edge West",-85,-1.20,37.64,41.66),
        ("Ford Water Edge East",9.80,45,37.64,41.66)]
    for name,x0,x1,y0,y1 in areas:
        p=((x0+x1)*.5,(y0+y1)*.5,-5)
        zone=names.get(name) or e.place(u.NavModifierVolume,name,"Deathmatch/Water",p)
        zone.set_actor_location(e.vector(p),False,True)
        zone.set_actor_scale3d(u.Vector((x1-x0)*.5,(y1-y0)*.5,5.7))
        zone.set_editor_property("area_class",u.NavArea_Null)
    u.SystemLibrary.execute_console_command(world,"RebuildNavigation")
    if not u.EditorLoadingAndSavingUtils.save_current_level():
        raise RuntimeError("Could not save the east ford")


def decoration_candidates():
    arena.current()
    rows=[]
    for actor in e.actors.get_all_level_actors():
        if not isinstance(actor,u.InstancedFoliageActor):
            continue
        for comp in actor.get_components_by_class(u.FoliageInstancedStaticMeshComponent):
            box=u.Box(e.vector((1,37.65,0)),e.vector((9.1,41.65,6)))
            for i in comp.get_instances_overlapping_box(box,True):
                t=comp.get_instance_transform(i,True)
                p=arena.xyz(t.translation)
                if 0<p[0]<10 and 36<p[1]<43:
                    rows.append([comp.get_name(),comp.static_mesh.get_name(),i,p])
    return rows


def clear_treads():
    world=arena.current()
    foliage=[a for a in e.actors.get_all_level_actors() if isinstance(a,u.InstancedFoliageActor)]
    stairs=[a for a in e.actors.get_all_level_actors() if str(a.get_folder_path())=="Deathmatch/East Ford"]
    moves={"SM_Fern":((5.32,37.90),(5.0,35.9)),
           "SM_MossBoulder05":((4.12,41.60),(3.85,45.4))}
    changes=[]
    def ground(x,y):
        hit=u.SystemLibrary.line_trace_single(world,e.vector((x,y,12)),e.vector((x,y,-8)),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,foliage+stairs,u.DrawDebugTrace.NONE)
        if not hit: raise RuntimeError(f"No terrain at {x}, {y}")
        return describe(hit)["point"][2]
    def components(mesh_name):
        return [comp for actor in foliage for comp in actor.get_components_by_class(u.FoliageInstancedStaticMeshComponent) if comp.static_mesh.get_name()==mesh_name]
    def signature(transform):
        p=transform.translation
        q=transform.rotation
        s=transform.scale3d
        return tuple(round(v,3) for v in (p.x,p.y,p.z,q.x,q.y,q.z,q.w,s.x,s.y,s.z))
    for name,((x,y),(nx,ny)) in moves.items():
        poses=[c.get_instance_transform(i,True) for c in components(name) for i in range(c.get_instance_count())]
        matching=[i for i,t in enumerate(poses) if abs(t.translation.x/100-x)<.12 and abs(t.translation.y/100-y)<.12]
        if not matching:
            continue
        if len(matching)!=1:
            raise RuntimeError("Ambiguous instance: "+name)
        target=poses[matching[0]]
        before=arena.xyz(target.translation)
        target.translation=e.vector((nx,ny,before[2]+ground(nx,ny)-ground(x,y)))
        expected=sorted(signature(t) for t in poses)
        foliage_type=e.assets.load_asset(e.BASE+"/Nature/Foliage/FT_"+name.removeprefix("SM_"))
        if not foliage_type or foliage_type.get_editor_property("mesh").get_name()!=name:
            raise RuntimeError("Foliage type does not match "+name)
        # Use the native foliage store so editor and cooked transforms agree.
        u.InstancedFoliageActor.remove_all_instances(world,foliage_type)
        u.InstancedFoliageActor.add_instances(world,foliage_type,poses)
        actual=sorted(signature(c.get_instance_transform(i,True)) for c in components(name) for i in range(c.get_instance_count()))
        if expected!=actual:
            raise RuntimeError("Foliage transforms differ after replanting "+name)
        changes.append(dict(mesh=name,old_position=before,new_position=arena.xyz(target.translation),other_instances_preserved=len(poses)-1))
    if changes:
        u.SystemLibrary.execute_console_command(world,"RebuildNavigation")
        if not u.EditorLoadingAndSavingUtils.save_current_level():raise RuntimeError("Could not save moved decoration")
        (e.ROOT/"Deathmatch"/"Review"/"FordPlanting.json").write_text(json.dumps(changes,indent=2),encoding="utf-8")
    return changes
