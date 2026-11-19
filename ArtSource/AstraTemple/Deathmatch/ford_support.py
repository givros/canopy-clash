from pathlib import Path
import math,json
import unreal as u
import arena,editor as e

def measured_bank_boulder():
    w=arena.current()
    fol=[a for a in e.actors.get_all_level_actors() if isinstance(a,u.InstancedFoliageActor)]
    rocks=[]
    for a in fol:
        for comp in a.get_components_by_class(u.FoliageInstancedStaticMeshComponent):
            if not comp.static_mesh or comp.static_mesh.get_name()!="SM_MossBoulder05":continue
            for i in range(comp.get_instance_count()):
                pose=comp.get_instance_transform(i,True)
                if (pose.translation-e.vector((3.85,45.40,2.27))).length()<60:rocks.append((comp,i,pose))
    if len(rocks)!=1:raise RuntimeError("Ambiguous ford rock")
    component,index,pose=rocks[0]
    mesh,ok=u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(component.static_mesh,u.DynamicMesh(),
        u.GeometryScriptCopyMeshFromAssetOptions(),u.GeometryScriptMeshReadLOD())
    if ok!=u.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError("Could not read original rock mesh")
    spacing=10
    grid={}
    for i in range(mesh.get_triangle_count()):
        valid,*points=u.GeometryScript_MeshQueries.get_triangle_positions(mesh,i)
        if not valid:continue
        a,b,c=[pose.transform_location(v) for v in points]
        den=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y)
        if abs(den)<1e-7:continue
        for ix in range(math.ceil(min(a.x,b.x,c.x)/spacing),math.floor(max(a.x,b.x,c.x)/spacing)+1):
            for iy in range(math.ceil(min(a.y,b.y,c.y)/spacing),math.floor(max(a.y,b.y,c.y)/spacing)+1):
                x,y=ix*spacing,iy*spacing
                l=((b.y-c.y)*(x-c.x)+(c.x-b.x)*(y-c.y))/den
                m=((c.y-a.y)*(x-c.x)+(a.x-c.x)*(y-c.y))/den
                if min(l,m,1-l-m)<-1e-5:continue
                z=l*a.z+m*b.z+(1-l-m)*c.z
                g=grid.setdefault((x,y),[z,z])
                g[0]=min(g[0],z);g[1]=max(g[1],z)
    r=[]
    for (x,y),(bottom,top) in grid.items():
        h=u.SystemLibrary.line_trace_single(w,u.Vector(x,y,1300),u.Vector(x,y,-700),u.TraceTypeQuery.ECC_VISIBILITY,True,fol,u.DrawDebugTrace.NONE)
        if not h:raise RuntimeError("No support surface")
        hit=h.to_dict();label=hit["hit_component"].get_owner().get_actor_label()
        r.append(dict(x_m=x/100,y_m=y/100,mesh_bottom_cm=round(bottom,2),mesh_top_cm=round(top,2),
            surface_cm=round(hit["impact_point"].z,2),clearance_cm=round(bottom-hit["impact_point"].z,2),surface_actor=label))
    r.sort(key=lambda e:(e['x_m'],e['y_m']))
    cx=sum(v['x_m'] for v in r)/len(r);cy=sum(v['y_m'] for v in r)/len(r)
    mid=min(r,key=lambda d:(d['x_m']-cx)**2+(d['y_m']-cy)**2)
    centre=[d for d in r if math.hypot(d['x_m']-cx,d['y_m']-cy)<=.45]
    summary=dict(mesh=component.static_mesh.get_path_name(),instance=index,source_triangles=mesh.get_triangle_count(),grid_spacing_cm=spacing,samples=len(r),central_footprint_samples=len(centre),central_contact=sum(v['clearance_cm']<=2 for v in centre),contact_area_m2=round(sum(v['clearance_cm']<=2 for v in r)*spacing**2/10000,2),
        surface_crossing_area_m2=round(sum(v["mesh_bottom_cm"]<=v["surface_cm"]<=v["mesh_top_cm"] for v in r)*spacing**2/10000,2),
        centroid_m=[round(cx,2),round(cy,2)],centre_sample=mid,minimum_underside_clearance_cm=min(v['clearance_cm'] for v in r),maximum_underside_clearance_cm=max(v['clearance_cm'] for v in r),actual_surfaces=sorted({v['surface_actor'] for v in r}))
    out=Path(e.ROOT)/"Deathmatch"/"Review"/"FordBoulderSupport.json"
    out.write_text(json.dumps({'summary':summary,'grid':r},indent=2))
    return summary
