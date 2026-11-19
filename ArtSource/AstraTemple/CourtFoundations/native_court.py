"""Mount and inspect the three sandstone structures under the existing courts."""
from pathlib import Path
import json
import sys
import unreal as u

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'Tools'))
import editor as e
from stonework import import_mesh

PACKAGE='/Game/AstraTemple/CourtFoundations'
FOLDER='Temple/Rain Court Foundations'
LABELS=['Rain court rear foundation','West terrace return foundations','East terrace return foundations']

def mount():
    e.require_world();named=e.all_named()
    materials={}
    for role in ['Sandstone','Ochre','CarvedStone','ShadeStone','MossStone','Pinestone']:
        name='M_Astra_'+role
        materials[name]=e.assets.load_asset('/Game/AstraTemple/Architecture/Materials/'+name)
    out=[]
    for label,item in zip(LABELS,json.loads((ROOT/'Modules.json').read_text())):
        name=item['mesh']
        info=import_mesh(ROOT/(name+'.fbx'),PACKAGE,False,True,materials,collision=True)
        mesh=e.assets.load_asset(PACKAGE+'/'+name)
        if not mesh.get_editor_property('nanite_settings').enabled:raise RuntimeError(info)
        pos=e.vector(item['pivot_m']);ob=named.get(label) or e.actors.spawn_actor_from_object(mesh,pos,e.rotation())
        ob.set_actor_label(label);ob.set_folder_path(FOLDER)
        if ob.static_mesh_component.static_mesh!=mesh:raise RuntimeError(label)
        out.append([label,item['triangles'],mesh.get_path_name()])
    return [e.save(),out]

def audit():
    world=e.require_world();named=e.all_named();ground=named['Valley of the Two Springs']
    supports=[named[name] for name in LABELS];regional=[]
    for a in named.values():
        c,r=a.get_actor_bounds(False)
        if c.x+r.x>8500 and c.x-r.x<11100 and c.y+r.y>-3900 and c.y-r.y<3900:regional.append(a)
    slabs=[a for a in regional if 'Paving' in a.get_actor_label()]
    def exclude(keep):return [a for a in regional if a not in keep]
    ground_only=exclude([ground]);foundations_only=exclude(supports);paving_only=exclude(slabs)
    def ray(start,end,ignore):
        hit=u.SystemLibrary.line_trace_single(world,e.vector(start),e.vector(end),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,ignore,u.DrawDebugTrace.NONE)
        if hit:
            d=hit.to_dict();return d['hit_actor'].get_actor_label(),d['impact_point'].z/100
    section=[]
    probes=[('rear court west',98.60,-7.39,28),('rear court east',98.55,7.43,28),('west side return',98.19,-8.52,28),('east side return',98.17,8.47,28)]
    for sign,title in [(-1,'west'),(1,'east')]:
        for x,y,z,tier in [(94.23,13.62,28,'upper'),(95.30,22.48,20,'middle'),(96.23,29.65,12,'lower')]:probes.append((title+' '+tier,x,sign*y,z))
    for label,x,y,z in probes:
        actual=ray((x,y,70),(x,y,-15),ground_only)
        foot=ray((x,y,-15),(x,y,z+.3),foundations_only)
        seat=ray((x,y,z+.7),(x,y,-15),foundations_only)
        soffit=ray((x,y,z-1.8),(x,y,z+.16),paving_only)
        if not all([actual,foot,seat,soffit]):raise RuntimeError(str((label,actual,foot,seat,soffit)))
        if actual[1]<foot[1]+.03 or seat[1]<soffit[1]-.015 or seat[1]>z-.12:
            raise RuntimeError(str(('bearing tolerance',label,actual,foot,seat,soffit)))
        section.append({'edge':label,'xy_m':[x,y],'landscape_m':round(actual[1],3),'masonry_base_m':round(foot[1],3),'masonry_top_m':round(seat[1],3),'paving_underside_m':round(soffit[1],3),'embed_m':round(actual[1]-foot[1],3),'paving_overlap_m':round(seat[1]-soffit[1],3),'from_below':foot[0],'from_above':seat[0]})
    route=[]
    for x,y in [(90,0),(92,0),(94,0),(96,0),(98,0),(98.8,.5),(99.3,.8),(100.1,1.25),(101.2,2.00),(102.2,2.85),(103.4,3.75)]:
        hit=ray((x,y,29.65),(x,y,25),[])
        if not hit or hit[0] in LABELS:raise RuntimeError(str(('route',x,y,hit)))
        route.append([x,y,hit[0],round(hit[1],3)])
    toe=[]
    for side,direction in [('west',-1),('east',1)]:
        for label,x0,y0 in [('court',98.8,7.5),('upper',94.58,14.1),('middle',95.58,22.7),('lower',96.58,29.8)]:
            candidates=[]
            for dx in [.15,.38,.61,.84,1.07,1.30,1.53,1.76,1.99,2.22]:
                for dy in [-.74,-.27,.15,.65,1.25]:
                    x=x0+dx;y=(y0+dy)*direction
                    h=ray((x,y,70),(x,y,-15),ground_only);bottom=ray((x,y,-15),(x,y,32),foundations_only)
                    if h and bottom and .08<h[1]-bottom[1]<2.7:
                        candidates.append((abs(h[1]-bottom[1]-.78),x,y,h[1],bottom[1],bottom[0]))
            if not candidates:raise RuntimeError(('No embedment on the outermost toe',side,label))
            _,x,y,soil,z,actor=min(candidates)
            toe.append({'edge':side+' '+label,'xy_m':[round(x,2),round(y,2)],'landscape_m':round(soil,3),'masonry_base_m':round(z,3),'embed_m':round(soil-z,3),'foundation':actor})
    return {'edges':section,'exterior_toes':toe,'center_route':route}
