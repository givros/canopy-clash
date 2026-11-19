"""Bonded sandstone retaining walls fitted to the native Landscape survey, in metres."""
from pathlib import Path
from math import ceil, floor
import json
import random
import sys
import bpy
import bmesh

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'Architecture'))
import temple_kit as k

survey=json.loads((ROOT/'LandscapeSurvey.json').read_text())
heights=survey['elevation_m'];ox,oy=survey['origin_m'];step=survey['spacing_m']
lowest_ground=min(min(row) for row in heights)
rng=random.Random(20261119)
k.rng.seed(221019)
actors=[]

def land(x,y):
    u=(x-ox)/step;v=(y-oy)/step;i=floor(u);j=floor(v)
    if i<0 or j<0 or i>=len(heights[0])-1 or j>=len(heights)-1:raise ValueError((x,y))
    s=u-i;t=v-j
    return (heights[j][i]*(1-s)+heights[j][i+1]*s)*(1-t)+(heights[j+1][i]*(1-s)+heights[j+1][i+1]*s)*t

def bed(x,y,dx,dy):
    return min(land(x+dx*a,y+dy*b) for a in [-.48,0,.48] for b in [-.48,0,.48])

def stone_if_exposed(a,x,y,z,dx,dy,dz,mat=None):
    if z+dz<bed(x,y,dx,dy)-.92:return
    k.hewn(a,x,y,z,dx,dy,dz,mat,wear=min(.076,dz*.16))

def profile(depth):
    # Each wider lower lift takes the load of the upper course. The stone wall
    # also contains the fill behind the deep cut at the landscape break.
    return .027*depth+.27*(depth>=3.70)+.40*(depth>=7.45)+.36*(depth>=11.20)+.29*(depth>=14.95)

def wall(a,title,axis,fixed,start,end,sign,top,piers=()):
    a.part(title)
    low,high=sorted((start,end));h=.625
    for row in range(44):
        d=row*h;level=top-(row+1)*h
        if level+h<lowest_ground-.94:break
        cap=row==0 or row in (6,12,18,24)
        face=profile(d)+(.075 if cap else 0)
        width=1.48+face
        center=fixed+sign*(face-width/2)
        stride=rng.uniform(1.27,1.70) if not cap else rng.uniform(1.59,2.07)
        n=max(1,round((high-low)/stride))
        weights=[rng.uniform(.73,1.27) for _ in range(n)];total=sum(weights);bound=low
        for factor in weights:
            nxt=bound+(high-low)*factor/total;along=(bound+nxt)*.5;length=nxt-bound-.009
            x,y,dx,dy=(center,along,width,length) if axis=='X' else (along,center,length,width)
            stone_if_exposed(a,x,y,level,dx,dy,h-.007,None if not cap else rng.choice([0,0,0,1,5]))
            bound=nxt
        for along in piers:
            protrude=.24+min(d,12)*.035
            if cap:protrude+=.11
            x,y,dx,dy=(fixed+sign*(face+protrude*.05),along,protrude*1.91,1.05+.018*min(d,12)) if axis=='X' else (along,fixed+sign*(face+protrude*.05),1.05+.018*min(d,12),protrude*1.91)
            stone_if_exposed(a,x,y,level+.009,dx,dy,h-.027,1 if cap else None)

def corner(a,x,y,sy,top):
    a.part('Bonded corner quoins')
    for row in range(43):
        d=row*.625;f=profile(d)+(.075 if row in [0,6,12,18,24] else 0)+.038
        lx=.93+(row%2)*.37+f;ly=1.29-(row%2)*.37+f
        stone_if_exposed(a,x+f-lx/2,y+sy*(f-ly/2),top-(row+1)*.625+.007,lx,ly,.614)

def core(a,xmin,xmax,ymin,ymax,top):
    a.part('Closed footings keyed into the excavated bank')
    nx=ceil((xmax-xmin)/.52);ny=ceil((ymax-ymin)/.52);cols=ny+1;count=(nx+1)*cols
    xy=[(xmin+i*(xmax-xmin)/nx,ymin+j*(ymax-ymin)/ny) for i in range(nx+1) for j in range(ny+1)]
    verts=[(x,y,top) for x,y in xy]+[(x,y,min(top-.32,land(x,y)-.87)) for x,y in xy]
    faces=[]
    for i in range(nx):
        for j in range(ny):
            b=i*cols+j;quad=(b,b+cols,b+cols+1,b+1)
            faces.append(quad);faces.append(tuple(reversed(tuple(k+count for k in quad))))
    loop=list(range(cols))+[i*cols+ny for i in range(1,nx+1)]+[nx*cols+j for j in range(ny-1,-1,-1)]+[i*cols for i in range(nx-1,0,-1)]
    for i,b in enumerate(loop):
        c=loop[(i+1)%len(loop)];faces.append((b,c,c+count,b+count))
    a.add(verts,faces,3)

def finish(a,pivot):
    ob=a.finish();me=ob.data
    for v in me.vertices:
        x,y,z=v.co;v.co=(x-pivot[0],pivot[1]-y,z-pivot[2])
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();me.update()
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(ROOT/(ob.name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False,mesh_smooth_type='FACE',path_mode='RELATIVE')
    me.calc_loop_triangles();actors.append({'mesh':ob.name,'pivot_m':pivot,'triangles':len(me.loop_triangles)})
    ob.location=(pivot[0],-pivot[1],pivot[2])

court=k.Asset('RainCourtFooting');top=27.795
core(court,91.20,98.62,-8.67,8.67,27.773)
wall(court,'Battered rear court face','X',98.79,-8.90,8.90,1,top,[-6.30,6.42])
for sign in [-1,1]:
    wall(court,'Returning face of the projecting court','Y',sign*8.84,94.34,98.85,sign,top,[97.45])
    corner(court,98.79,sign*8.84,sign,top)
finish(court,[96,0,20])

for sign,name in [(-1,'West'),(1,'East')]:
    wing=k.Asset('RainCourt'+name+'Footing')
    for x0,end,lo,hi,ht in [(89.4,94.58,8.88,19.06,27.795),(90.1,95.58,18.82,27.07,19.795),(91.5,96.58,26.80,36.06,11.795)]:
        yl,yh=sorted([sign*(lo+.10),sign*(hi-.26)])
        core(wing,x0,end-.17,yl,yh,ht-.022)
        wall(wing,'Rear bond and stepped terrace toes','X',end,sign*lo,sign*hi,1,ht,[sign*(lo+(hi-lo)*.59)])
    for x0,x1,offset,ht in [(90.45,95.75,18.83,19.90),(91.70,96.74,26.84,11.90),(92.70,96.96,35.83,3.95)]:
        wall(wing,'Footings beneath the existing longitudinal buttresses','Y',sign*offset,x0,x1,sign,ht)
    finish(wing,[94.5,sign*23.4,12])

bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'RainCourtFoundations.blend'))
(ROOT/'Modules.json').write_text(json.dumps(actors,indent=2))
