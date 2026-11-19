"""Measure the built Landscape along the two upper trails and locate waist-height obstacles."""
import json
import math
import unreal as u
from editor import ROOT, actors, require_world, vector
import verify_traversal as walk

def inspect():
    world=require_world()
    terrain=next(a for a in actors.get_all_level_actors() if isinstance(a,u.Landscape))
    other=[a for a in actors.get_all_level_actors() if a!=terrain]
    groups={}
    for name,goals in walk.routes()['ridge'][-2:]:
        stations=[];walls=[]
        for a,b in zip(goals,goals[1:]):
            dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy)
            if not length:continue
            nx=-dy/length;ny=dx/length
            steps=math.ceil(length/.55)
            for i in range(steps+1):
                t=i/steps;x=a[0]+t*dx;y=a[1]+t*dy
                for offset in (-.34,0,.34):
                    px=x+nx*offset;py=y+ny*offset
                    hit=u.SystemLibrary.line_trace_single(world,vector((px,py,130)),vector((px,py,5)),
                        u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,other,u.DrawDebugTrace.NONE)
                    if not hit:raise RuntimeError(f'No Landscape at {px}, {py}')
                    h=hit.to_dict();z=h['impact_point'].z/100
                    slope=math.degrees(math.acos(max(-1.,min(1.,h['impact_normal'].z))))
                    stations.append([round(px,3),round(py,3),round(z,3),round(slope,2)])
                    if offset:continue
                    body=u.SystemLibrary.capsule_trace_single_by_profile(world,vector((px,py,z+1.12)),
                        vector((px,py,z+1.121)),34.,64.,'Pawn',False,[terrain],u.DrawDebugTrace.NONE)
                    if body and body.to_dict()['blocking_hit']:
                        h=body.to_dict();owner=h.get('hit_actor');comp=h.get('hit_component')
                        walls.append([round(px,2),round(py,2),round(z,2),owner.get_actor_label() if owner else None,
                                      comp.get_name() if comp else None,h.get('hit_item'),h.get('item')])
        peak=max(stations,key=lambda s:s[3])
        groups[name]={'samples':len(stations),'radius_m':.34,'peak_slope':peak,'first':stations[1],
                      'last':stations[-2],'above_walkable_deg':[p for p in stations if p[3]>44.77],
                      'nonterrain_pawn_blockers':walls}
    (ROOT/'Review/RidgeClearance.json').write_text(json.dumps(groups,indent=2))
    return {n:[g['samples'],g['peak_slope'],len(g['above_walkable_deg']),g['nonterrain_pawn_blockers'][:5]] for n,g in groups.items()}
