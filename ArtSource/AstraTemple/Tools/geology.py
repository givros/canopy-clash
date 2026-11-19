"""Seat the exposed faces of actual photogrammetry scans in the valley's eroded banks."""
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import random
import struct

import valley as v

SCANS=Path(__file__).resolve().parents[1]/"Nature"/"Sources"

def percentile(values,fraction):
    data=sorted(values)
    return data[round((len(data)-1)*fraction)]

@lru_cache(maxsize=None)
def profile(kind):
    source="rock_face_01" if kind=="SandstoneCliff" else "namaqualand_cliff_01"
    folder=SCANS/source
    data=json.loads((folder/(source+".gltf")).read_text())
    buf=(folder/data["buffers"][0]["uri"]).read_bytes()
    primitive=data["meshes"][0]["primitives"][0]
    def read(index,fmt):
        accessor=data["accessors"][index]
        view=data["bufferViews"][accessor["bufferView"]]
        base=view.get("byteOffset",0)+accessor.get("byteOffset",0)
        stride=view.get("byteStride",struct.calcsize(fmt))
        return [struct.unpack_from(fmt,buf,base+i*stride) for i in range(accessor["count"])]
    position=primitive["attributes"]["POSITION"]
    accessor=data["accessors"][position]
    low,high=accessor["min"],accessor["max"]
    # Match Blender pivot rebasing and the FBX -> Unreal Y reflection.
    ox,oy,oz=(low[0]+high[0])*.5,(low[2]+high[2])*.5,low[1]+.045*(high[1]-low[1])
    vertices=[(x-ox,z-oy,y-oz) for x,y,z in read(position,"<fff")]
    key=lambda point:tuple(round(c,4) for c in point)
    points=list(dict.fromkeys(key(p) for p in vertices))
    fmt="<I" if data["accessors"][primitive["indices"]]["componentType"]==5125 else "<H"
    indices=[u[0] for u in read(primitive["indices"],fmt)]
    edge_count=Counter()
    keys=[key(p) for p in vertices]
    for i in range(0,len(indices),3):
        a,b,c=(keys[id] for id in indices[i:i+3])
        for p,q in ((a,b),(b,c),(c,a)):
            if p!=q:edge_count[tuple(sorted((p,q)))]+=1
    rim=sorted({p for edge,count in edge_count.items() if count==1 for p in edge})
    # Use diverse samples in all directions; the bottom strip is examined separately.
    sample=random.Random(438)
    lower=percentile([p[2] for p in points],.10)
    foot=[p for p in points if p[2]<=lower]
    return [sample.sample(group,min(len(group),count)) for group,count in ((points,90),(foot,32),(rim,45))]

def exposed_strata(add,special):
    rng=random.Random(941719)
    occupied=[]
    validation=[]
    # Match the landscape interpolation at its actual 80cm grid vertices.
    @lru_cache(maxsize=120000)
    def node(i,j):
        return v.terrain(v.CENTRE[0]+i*v.SPACING,v.CENTRE[1]+j*v.SPACING)
    def soil(x,y):
        px=(x-v.CENTRE[0])/v.SPACING;py=(y-v.CENTRE[1])/v.SPACING
        i=math.floor(px);j=math.floor(py);a=px-i;b=py-j
        return v.mix(v.mix(node(i,j),node(i+1,j),a),v.mix(node(i,j+1),node(i+1,j+1),a),b)
    def gradient(x,y):
        step=2
        return ((soil(x+step,y)-soil(x-step,y))/(2*step),(soil(x,y+step)-soil(x,y-step))/(2*step))
    def attempt(x,y,channel=False):
        gx,gy=gradient(x,y);incline=math.hypot(gx,gy)
        if incline<(.37 if channel else .52) or special(x,y) or (6<x<101 and abs(y)<37.4):
            return False
        if v.river_sample(x,y)[0]<2.25 or v.trail_sample(x,y)[0]<3.9:
            return False
        kind="SandstoneCliff" if rng.random()<.78 else "FracturedCliff"
        sx=rng.uniform(.91,1.54) if kind=="SandstoneCliff" else rng.uniform(.68,1.12)
        sy=rng.uniform(.67,.94)*v.clamp(1.30/max(.75,incline),.38,1)
        sz=rng.uniform(.72,1.06)*min(1.18,.82+.22*incline)
        width=sx*(5 if kind=="SandstoneCliff" else 8.3)
        if any(math.hypot(x-px,y-py)<.36*(width+w) for px,py,w in occupied):return False
        # The scan's open / visible face is +Y. Strike follows the local contour.
        yaw=math.atan2(-gy,-gx)-math.pi/2+rng.uniform(-.145,.145)
        ca,sa=math.cos(yaw),math.sin(yaw)
        points,bottom,rim=profile(kind)
        def world(p):
            return (x+ca*sx*p[0]-sa*sy*p[1],y+sa*sx*p[0]+ca*sy*p[1],sz*p[2])
        surface=[world(p) for p in points]
        def support(group):
            return [soil(px,py)-z for px,py,z in group]
        # Check the whole oriented rectangular footprint at sub-metre intervals.
        # This also guards native bounds / fallback faces beyond sampled rim points.
        depth=sy*(3.83 if kind=="SandstoneCliff" else 4.40)
        nx=math.ceil(width/.9);ny=math.ceil(depth/.9)
        footprint=[]
        for i in range(nx+1):
            rx=width*(i/nx-.5)
            for j in range(ny+1):
                ry=depth*(j/ny-.5)
                footprint.append((x+ca*rx-sa*ry,y+sa*rx+ca*ry,0))
        bank=min(v.river_sample(px,py)[0] for px,py,_ in footprint)
        path=min(v.trail_sample(px,py)[0] for px,py,_ in footprint)
        if bank<1.07 or path<2.12:return False
        contact=support(surface)
        footing=support([world(p) for p in bottom])
        boundary=support([world(p) for p in rim])
        # Bury most of the scan, including its lower edge. Use the open outer
        # perimeter as a third constraint to suppress the cut edge of the scan.
        z=min(percentile(contact,rng.uniform(.31,.49)),percentile(footing,.09)-.09)
        if boundary:z=min(z,percentile(boundary,.31)-.08)
        relief=[z-h for h in contact]
        visible=sum(h>.055 for h in relief)/len(relief)
        if not .13<visible<.55 or max(relief)<.36 or max(relief)>3.6:return False
        if any(abs(soil(px,py)-soil(x,y))>6.8 for px,py,_ in footprint):return False
        # Embedded rear and bottom contact pin the scan to an actual upslope surface.
        add(kind,x,y,z,(sx,sy,sz),math.degrees(yaw))
        occupied.append((x,y,width))
        validation.append((kind,visible,max(relief),sum(z-h<=0 for h in footing)/len(footing),bank,path))
        return True
    for channel in v.RIVERS:
        for a,b in zip(channel,channel[1:]):
            length=math.hypot(b[0]-a[0],b[1]-a[1])
            if not length or a[2]-b[2]<1:continue
            side_x=-(b[1]-a[1])/length;side_y=(b[0]-a[0])/length
            for side in (-1,1):
                for t in (.03,.24,.50,.79,.98):
                    width=v.mix(a[3],b[3],t)*.5
                    for step in (3.3,4.4,5.9,7.4,8.9):
                        x=v.mix(a[0],b[0],t)+side*side_x*(width+step)
                        y=v.mix(a[1],b[1],t)+side*side_y*(width+step)
                        if attempt(x,y,True):break
    # Discontinuous bedding on the forested ridges. Trace a single terrain
    # contour locally instead of dressing hilltops with heaps of separate rocks.
    bands=[(91,-66),(120,-89),(147,-74),(137,-107),(158,-113),
           (99,78),(127,69),(153,51),(174,27),(135,98),(81,-98),
           (24,-102),(-9,-103),(-43,-98),(-38,84),(9,97)]
    for cx,cy in bands:
        for line in range(2):
            x=cx+rng.uniform(-4,4);y=cy+rng.uniform(-4,4)
            target=soil(x,y)
            direction=-1 if line else 1
            for j in range(rng.randint(4,7)):
                if j!=2 or rng.random()<.59:attempt(x,y)
                gx,gy=gradient(x,y);m=math.hypot(gx,gy)
                if m<.22:break
                distance=rng.uniform(3.9,6.4)
                x+=direction*(-gy/m)*distance;y+=direction*(gx/m)*distance
                gx,gy=gradient(x,y);den=gx*gx+gy*gy
                if den>.12:
                    correction=v.clamp((target-soil(x,y))/den,-2.2,2.2)
                    x+=gx*correction;y+=gy*correction
    return validation
