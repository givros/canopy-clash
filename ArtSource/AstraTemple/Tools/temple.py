"""Build the plaza, galleries, structural terraces, valley shrines and stone crossings."""
from stonework import *

def build():
    require_world()
    for a in actors.get_all_level_actors():
        if str(a.get_folder_path()).split("/")[0] in ("Composition Study","Temple","Bridges","Secondary Ruins","Outer Gate"):
            actors.destroy_actor(a)
    count=0
    def put(mesh,pos,yaw=0,scale=(1,1,1),folder="Temple",label=None,roll=0):
        nonlocal count
        count+=1
        label=label or f"{folder.split('/')[-1]} {mesh} {count:03}"
        return piece(mesh,label,pos,yaw,scale,folder,roll=roll)
    def paving(x0,x1,y0,y1,z,folder):
        cols=max(1,math.ceil((x1-x0)/8.01)); rows=max(1,math.ceil((y1-y0)/8.01))
        dx,dy=(x1-x0)/cols,(y1-y0)/rows
        for i in range(cols):
            for j in range(rows):
                put("Paving",(x0+(i+.5)*dx,y0+(j+.5)*dy,z),0,(dx/8,dy/8,1),folder)
    def wall(a,b,z,h,yaw,group,mesh="BatteredBay"):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        n=max(1,round(length/8))
        for j in range(n):put(mesh,(a[0]+dx*(j+.5)/n,a[1]+dy*(j+.5)/n,z),yaw,(1,length/n/8,h/8),group)
    def fence(a,b,z,group):
        dx,dy=b[0]-a[0],b[1]-a[1];l=math.hypot(dx,dy);n=max(1,round(l/8));yaw=math.degrees(math.atan2(dy,dx))-90
        for j in range(n):put("Balustrade",(a[0]+dx*(j+.5)/n,a[1]+dy*(j+.5)/n,z),yaw,(1,l/n/8,1),group)

    for i,(x,z) in enumerate(v.STAIRS):
        put("StairFlight",(x,0,z),label=["Steps of the Basin","Processional Stair","Sanctuary Ascent"][i],folder="Temple/Grand Stair")
        end=[34,52,73][i]
        paving(x+13.2,end,-6.1,6.1,z+8,"Temple/Grand Stair")
    put("Portal",(68.5,0,28),scale=(1,1,1.11),label="Face of the Spring Keeper",folder="Temple/Sanctuary")
    put("RitualHall",(73.42,0,28),label="Hall of the Open Sky",folder="Temple/Sanctuary")
    for i,(front,rear,half,bottom,top) in enumerate(v.TIERS):
        group=f"Temple/Terrace {i+1}"
        for side in [-1,1]:
            wall((front,side*6.2),(front,side*half),bottom,top-bottom,0,group,"TerraceBay" if i==0 else "BatteredBay")
            wall((front,side*half),(rear,side*half),bottom,top-bottom,-90*side,group)
            # Wide side walks over the terrace, continuing behind the stair landings.
            inside=[27,19,9][i]
            paving(front+.45,rear-.3,min(side*(half-.3),side*inside),max(side*(half-.3),side*inside),top,group)
            end_front=[39,57,69][i]
            paving(front+.45,end_front,min(side*6.15,side*inside),max(side*6.15,side*inside),top,group)
            fence((front+1.55,side*(half-3)),(front+1.55,side*(half-10)),top,group)
        if i==2:
            paving(91.2,99,-9,9,28,"Temple/Rain Court")
            for sy in [-1,1]:
                put("Colonnade",(93.9,sy*7.7,28),scale=(.83,.83,.84),folder="Temple/Rain Court")
    for y in [-8.15,8.15]:
        put("Serpent",(26.3,y,12),yaw=-34*(1 if y>0 else -1),scale=(.96,.96,1),folder="Temple/Serpent Wardens")
        put("Colonnade",(57.2,y,28),scale=(.85,.85,.78),folder="Temple/Knotted Landing")
    paving(7.3,16,-29,29,4,"Temple/Basin Plaza")
    for y0,y1 in [(-29,-3.8),(-2,15),(25.8,29)]:
        wall((7.25,y0),(7.25,y1),-3.15,7.15,0,"Temple/Basin Plaza")
    for sy in [-1,1]:
        fence((8.15,sy*4.2),(8.15,sy*13.2),4,"Temple/Basin Plaza")
        for y in (sy*19,sy*26):put("Colonnade",(14.1,y,4),scale=(.76,.76,.88),folder="Temple/Basin Plaza")
    put("StairFlight",(-.25,0,.42),0,(.573,1.10,.4475),"Temple/Basin Plaza","Basin landing steps")

    ax,ay=v.BRIDGE_START;bx,by=v.BRIDGE_END
    yaw=math.degrees(math.atan2(by-ay,bx-ax))
    for i in range(4):
        t=(i+.5)/4
        put("BridgeSpan",(v.mix(ax,bx,t),v.mix(ay,by,t),4),yaw,(math.hypot(bx-ax,by-ay)/40,1,1.06),"Bridges/Pilgrim Causeway")
    # The returning arcade runs along the margin of the large open basin.
    for i in range(2):put("BridgeSpan",(bx+(7.6-bx)*(i+.5)/2,by,4),0,((7.6-bx)/20,1,1.05),"Bridges/East Quay")
    put("Paving",(bx,by,4.035),yaw*.5,(.46,.72,.75),"Bridges/East Quay")
    for i in range(3):put("Paving",(-51.85-i*6.8,15.44-i*.96,4.02),yaw,(.86,1.13,1),"Outer Gate/Approach")
    put("RuinedGate",(-40.4,5.65,4.64),12,(.85,-.69,.88),"Outer Gate","Arch of the First Spring")
    paving(-46.2,-38.4,.25,10.45,4.64,"Outer Gate/Foundation")
    for a,b,yawwall in [((-46.2,.25),(-38.4,.25),90),((-38.4,.25),(-38.4,10.45),180)]:
        wall(a,b,-2.4,7.04,yawwall,"Outer Gate/Foundation")
    put("StairFlight",(-52.4,12.2,3.72),20,(.40,.52,.115),"Outer Gate/Approach")

    for name,x,y,z,yaw,s in [
        ("Shrine of the Split Leaf",91,-90,55,98,1.05),("Shrine Above the Mist",136,-71,75,-132,1.35),
        ("Court of the Eastern Spring",123,17,31,-156,.88),("The West Chapel",24,-57,10,-119,.73),
        ("Shrine of the Lower Ford",-27,54,5.46,-84,.68),("Temple of the Hidden Spring",110,-69,55,15,1.13)]:
        put("Shrine",(x,y,z),yaw,(s,s,s),"Secondary Ruins/Shrines",name)
    for i,(x,y,yaw) in enumerate([(-57,-46,30),(-30,-54,-14),(-17,-56,-26),(122,49,-45)]):
        put("CollapsedCloister",(x,y,v.terrain(x,y)-.23),yaw,(1,1,.9+i*.03),"Secondary Ruins/Collapsed Cloister")
    for x,y,yaw,s in [(-51,-21,0,.87),(-41,-27,7,.91),(-23,-29,0,.65),(-9,-28,21,.57),(-4,-22,8,.36),(1,-22,8,.41),(-9,40,22,.5)]:
        z=max(.38,v.terrain(x,y)-.08)
        bed=v.terrain(x,y)-.16
        if bed<z-.2:put("Colonnade",(x,y,bed),yaw,(1.27,1.27,(z-bed)/6.48),"Secondary Ruins/Flooded Colonnade")
        put("Paving",(x,y,z),yaw,(.38,.38,1.2),"Secondary Ruins/Flooded Colonnade")
        put("Colonnade",(x,y,z+.05),yaw,(s,s,s*1.24),"Secondary Ruins/Flooded Colonnade")
    # The roofed lateral passage reappears on the west ruin trail.
    put("RitualHall",(-83,-24.5,6.83),-44,(.65,.60,.58),"Secondary Ruins/Root Passage","The Root Passage")
    return count,save()

def friezes():
    placed=all_named()
    for label,source,y in [("The Jaguar Procession","JaguarProcession",-9.925),("Offering to the Rainbird","RainbirdOffering",17.375)]:
        mesh=assets.load_asset(BASE+"/Reliefs/SM_"+source+"Frieze")
        if not mesh:raise RuntimeError(source)
        actor=placed.get(label) or place(u.StaticMeshActor,label,"Temple/Grand Reliefs",(19.80,y,8.16))
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.static_mesh_component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    return save()
