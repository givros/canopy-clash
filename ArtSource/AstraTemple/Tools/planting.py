"""Deterministic, zone-specific foliage and geology for the native foliage editor."""
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import valley as v

def layout():
    rng=random.Random(746832)
    out=defaultdict(list)
    def add(kind,x,y,z=None,s=1,yaw=None,pitch=0,roll=0):
        if z is None:z=v.terrain(x,y)-.07
        if yaw is None:yaw=rng.uniform(-180,180)
        if isinstance(s,(float,int)):s=(s,s,s)
        if kind in ("JungleCanopy","StranglerFig","ArecaPalm") and x>47 and y<0:
            for tx,ty,roof in [(136,-71,87.2),(110,-69,65.4)]:
                t=(x+60.5)/(tx+60.5)
                if t<1.07 and abs(y-(22+(ty-22)*t))<3.0+7.7*t:
                    h={"JungleCanopy":18.8,"StranglerFig":25.7,"ArecaPalm":10.1}[kind]
                    allowed=(8+(roof-8)*t-z-1.4)/h
                    if allowed<.24:return
                    if s[2]>allowed:s=tuple(axis*allowed/s[2] for axis in s)
        out[kind].append([round(q,4) for q in (x,y,z,yaw,pitch,roll,*s)])
    def inside_temple(x,y):
        return 7<x<102 and abs(y)<38
    def special(x,y):
        return any(math.hypot(x-a,y-b)<r for a,b,r in [(91,-90,9),(136,-71,12),(123,17,9),(24,-57,8),(-27,54,8),(110,-69,10),(-45,8,11),(-60.5,22,7)])
    def paved(x,y):
        return inside_temple(x,y) or v.line_sample(x,y,v.BRIDGE_START,v.BRIDGE_END)[0]<4 or (-13<x<9 and 17<y<26)
    def bed(x,y):
        z=v.terrain(x,y);river,water_level,_=v.river_sample(x,y)
        return z, (z<.30 and v.within_bank(x,y)>-2) or (river<.45 and z<water_level+.8)
    # Branched crowns overlap in sheltered ravines and separate on the ridge skyline.
    for gy in range(-193,197,8):
        for gx in range(-148,242,8):
            x=gx+rng.uniform(-3.4,3.4);y=gy+rng.uniform(-3.4,3.4)
            td,_=v.trail_sample(x,y)
            if paved(x,y) or td<6.3 or special(x,y):continue
            if -71<x<22 and -39<y<45:continue
            if 42<x<100 and abs(y)<42:continue
            z,wet=bed(x,y)
            if wet:continue
            bank,level,_=v.river_sample(x,y)
            if bank<2.6:continue
            clump=.52+.20*math.sin(x*.082+math.cos(y*.069))+.24*math.sin(y*.095-.031*x)
            if rng.random()>.38+.59*clump:continue
            p=rng.random()
            kind="ArecaPalm" if p<(.31 if bank<18 else .17) else ("StranglerFig" if p<.41 else "JungleCanopy")
            s=rng.uniform(.52,1.13)
            if kind=="StranglerFig":s*=.84
            if z>62:s*=.68
            if -77<x<0 and -54<y<-32:s*=.61
            add(kind,x,y,z-.15,(s*rng.uniform(.88,1.12),s,s*rng.uniform(.86,1.12)),pitch=rng.uniform(-3,3))
            if kind!="ArecaPalm" and rng.random()<.21:
                off=rng.uniform(3.1,5.3);az=rng.random()*6.28
                px=x+math.cos(az)*off;py=y+math.sin(az)*off
                if v.trail_sample(px,py)[0]>3 and not bed(px,py)[1]:add("ArecaPalm",px,py,s=rng.uniform(.39,.78))
    for x,y,s,yaw in [(-56.2,5.8,1.27,-75),(71.1,14.7,1.59,31),(-86,-3,1.05,27),(105,24,1.02,-67),(-33,-49,1.03,113),(28,53,1.14,154)]:
        z={(71.1,14.7):27.88,(-56.2,5.8):4.48}.get((x,y),v.terrain(x,y)-.20)
        shape=(s*.84,s*.82,s) if (x,y) in ((-56.2,5.8),(71.1,14.7)) else s
        add("StranglerFig",x,y,z,shape,yaw)
    # Denser maiden canopy hugs the background ridges and masks patches of exposed soil.
    for j in range(1350):
        x=rng.uniform(-18,179);y=rng.uniform(-125,108)
        if -37<y<38 or paved(x,y) or special(x,y) or v.trail_sample(x,y)[0]<4:continue
        if v.river_sample(x,y)[0]<2.8:continue
        z=v.terrain(x,y)
        if z<22:continue
        sd=rng.uniform(.34,.70)
        if rng.random()<.4:
            add("CecropiaSapling",x,y,z-.1,sd*2.4)
        else:
            add("JungleCanopy",x,y,z-.20,(sd*1.14,sd*1.10,sd*rng.uniform(.77,1.24)))
    # Cliff faces sit in the banks and on the strike of the weathered strata.
    from geology import exposed_strata
    exposed_strata(add,special)
    boulders=["MossBoulder"]+[f"MossBoulder0{i}" for i in range(2,7)]
    for j in range(6400):
        x=rng.uniform(-119,183);y=rng.uniform(-110,113)
        td,_=v.trail_sample(x,y)
        if paved(x,y) or special(x,y) or td<1.65:continue
        z,wet=bed(x,y)
        if wet:continue
        bank,_,_=v.river_sample(x,y)
        intimacy=.5+.5*math.sin(.13*x+math.cos(y*.11))*math.cos(y*.14)
        if rng.random()>.12+.59*intimacy+(.24 if 1.65<td<7 else 0):continue
        kind=rng.choices(["Fern","Monstera","ArecaPalm","Heliconia","Rock"],[38,36,10,3,13])[0]
        s=rng.uniform(.58,1.48)
        if kind=="ArecaPalm":s*=.47
        if kind=="Rock":
            kind=rng.choice(boulders);z-=s*.31;s*=rng.uniform(.55,1.3)
        add(kind,x,y,z-.035,s)
        if kind in ("Fern","Monstera") and rng.random()<.32:
            for _ in range(rng.randint(1,3)):
                xx=x+rng.uniform(-1.6,1.6);yy=y+rng.uniform(-1.5,1.5)
                if v.trail_sample(xx,yy)[0]>1.75 and not bed(xx,yy)[1] and not paved(xx,yy):add("Fern",xx,yy,s=rng.uniform(.38,.88))
    # Waterline rocks, on banks rather than floating upon the pool's surface.
    for i in range(140):
        x=rng.uniform(-62,13);y=rng.uniform(-46,44)
        bank=v.within_bank(x,y)
        if abs(bank)>3.7 or paved(x,y) or v.trail_sample(x,y)[0]<2.1:continue
        z=v.terrain(x,y);s=rng.uniform(.55,1.8)
        add(rng.choice(boulders),x,y,z-.25*s,(s*1.28,s,s*.8))
    # Crown plantings grow on the sides and splash cuts, preserving the stair aisle.
    for i,(front,rear,half,base,level) in enumerate(v.TIERS):
        ymin=[28,20,10.8][i]
        imax=[88,66,46][i]
        for j in range(imax):
            sx=rng.uniform(front+1,rear-2);sy=rng.choice([-1,1])*rng.uniform(ymin,half-1.5)
            if (.5+.5*math.sin(sx*.34+sy*.28))<rng.uniform(0,.68):continue
            kind=rng.choices(["Fern","Monstera","ArecaPalm"],[50,41,9])[0]
            s=rng.uniform(.63,1.43)*(.63 if kind=="ArecaPalm" else 1)
            add(kind,sx,sy,level-.16,s)
        for side in [-1,1]:
            for j in range(8-i):
                y=side*rng.uniform(7.6,half-.6)
                add("LianaCurtain",front-.24,y,level+.12,(.87,rng.uniform(.8,1.4),rng.uniform(.65,1.15)),rng.uniform(-7,7))
            for j in range(9-i):
                x=rng.uniform(front+2,rear-2)
                add("LianaCurtain",x,side*(half+.12),level+.06,(1,rng.uniform(.65,1.15),rng.uniform(.7,1.24)),-90*side+rng.uniform(-13,13))
    for x,y,z,s in [(-56.7,13,4.9,1.38),(-60.7,17.4,4.8,1.24),(-52.4,12,4.88,1.2),(-45.3,3.4,4.64,1.4),(-40.5,11.7,4.7,1.06),(-62,17.8,4.83,1.66),(27.8,-10.5,12,1.03),(30.4,12.8,12,1.18),(16.4,-26,4,1.20)]:
        add("Monstera",x,y,z-.10,s)
        add("Heliconia",x-.48,y+.52,z-.06,.85*s)
    # Isolated roots at structural interfaces, rooted from the visible upper foliage.
    for x,y,z,yaw,s in [(57.55,15.5,28,0,1.32),(68.8,19,28,-90,1.32),(40.3,26.1,20,-20,.97),(23.5,35.95,12,-82,.93)]:
        add("WallRoots",x,y,z,s,yaw)
    for x,y,z,a,s in [(-40.8,5.5,16.3,12,.95),(-40.9,3.1,16.1,12,.81),(-40.6,7.9,15.2,12,.82),(-38.4,9.9,4.93,180,.92),(-26.6,21.8,4.14,-82,.70),(70.8,-8.2,38.8,0,1.1),(82.6,8.1,35.1,-90,.95)]:
        add("LianaCurtain",x,y,z,s,a)
    for x,y in [(-41.5,9.2),(-66,15.3),(-63.2,6.3),(-59.4,7.3),(-43,4),(-54.1,13.4),(-48.8,8.3)]:
        add("Fern",x,y,v.terrain(x,y)-.05,rng.uniform(1.13,1.75))
    # A planted bank and pilaster foot frame both lower corners of the reference view.
    for x,y,s in [(-52.8,14.1,1.6),(-51.9,13.1,1.35),(-50.5,13.2,1.01),(-45.9,24.25,1.92),(-47.2,25.8,1.58),(-51.8,21.7,1.2),(-51.5,21.9,1.18),(-39.4,4.1,.97)]:
        z=v.terrain(x,y)
        add("Monstera",x,y,z-.15*s,s)
        add("Fern",x-.55,y+.64,v.terrain(x-.55,y+.64)-.10,s*.76)
    for x,y,s in [(-52.6,13.85,1.85),(-45.7,24.05,1.83),(-50.6,22.9,1.25),(-42.2,2.2,1.34)]:
        add("Heliconia",x,y,v.terrain(x,y)-.1,s)
    for j in range(640):
        x=rng.uniform(-115,172);y=rng.uniform(-110,110)
        if paved(x,y) or special(x,y):continue
        z,wet=bed(x,y);dist=v.trail_sample(x,y)[0]
        if wet or dist<2.4 or v.river_sample(x,y)[0]<1.2:continue
        if rng.random()<.36 or dist<9:
            add("CecropiaSapling",x,y,z-.08,rng.uniform(.65,1.7))
    for i,(front,rear,half,base,level) in enumerate(v.TIERS):
        for j in range(70-i*12):
            sign=rng.choice([-1,1]);edge=rng.random()
            if edge<.50:
                x=front+rng.uniform(.0,1.5); y=sign*rng.uniform(7.1,half-.3)
            else:
                x=rng.uniform(front+.5,rear-.9); y=sign*(half-rng.uniform(.2,1.6))
            add("MossCushion",x,y,level+.015,(rng.uniform(.8,2.15),rng.uniform(.85,1.55),rng.uniform(.66,1.2)))
    for x,y,z,s in [(26,-24,12,.70),(27,21,12,.63),(36,-13,12,.56),(43,20,20,.55),(47,-17,20,.72),(62,-11.6,28,.63),(63.7,16.7,28,.49),(83,-16,28,.61),(86,12,28,.45),(21,28,12,.57),(68,-25.5,20,.51)]:
        add("ArecaPalm",x,y,z-.12,s)
        for k in range(5):
            t=k*1.26+.24
            add("Monstera" if k%2 else "Fern",x+math.cos(t)*1.12,y+math.sin(t)*1.04,z-.11,rng.uniform(.88,1.40))
    # Rooted palms mark the ledges at the elbows of the two waterfall circuits.
    for river in v.RIVERS:
        for a,b in zip(river,river[1:]):
            if a[2]!=b[2]:continue
            dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy)
            for sign in [-1,1]:
                for j in range(max(2,round(length*.56))):
                    t=rng.uniform(.09,.91);off=v.mix(a[3],b[3],t)*.5+rng.uniform(.75,3.7)
                    x=v.mix(a[0],b[0],t)-dy/length*off*sign;y=v.mix(a[1],b[1],t)+dx/length*off*sign
                    if (10<x<95 and abs(y)<36.8) or v.trail_sample(x,y)[0]<2.3:continue
                    h=v.terrain(x,y);gr=math.hypot(v.terrain(x+.4,y)-v.terrain(x-.4,y),v.terrain(x,y+.4)-v.terrain(x,y-.4))/.8
                    if h<a[2]+.1 or gr>1.45:continue
                    kind=rng.choice(["Fern","Monstera","ArecaPalm","CecropiaSapling"])
                    add(kind,x,y,h-.12,rng.uniform(.64,1.28))
    return dict(out)

if __name__=="__main__":
    result=layout()
    root=Path(__file__).resolve().parents[1]
    (root/"Terrain/Vegetation.json").write_text(json.dumps(result,separators=(",",":")))
    print({k:len(v) for k,v in result.items()})
