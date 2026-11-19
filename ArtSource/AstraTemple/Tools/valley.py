"""Spatial authoring datums. Distances are metres in Unreal's X-forward, Y-right frame."""
import math

CENTRE = (48, 0)
RESOLUTION = 505
SPACING = .8
BANKS = [(-63,-13,14),(-59,-30,29),(-51,-39,38),(-42,-45,43),(-25,-46,44),(-9,-42,43),(4,-42,44),(14,-40,43),(19,-39,41)]
RIVERS = [
    [(110,-55,54,13),(98,-53,54,16),(93,-51,54,19),(86,-49,27,18),(78,-49,27,19),(68,-47,27,13),(61,-45,27,12),(55,-44,18,12),(46,-41,18,15),(32,-40,18,11),(27,-39,18,9),(21,-38,1.8,10),(16,-37,1.8,10),(13,-36,1.8,8),(10,-35,0,10)],
    [(98,52,42,9),(84,51,42,13),(77,49,42,12),(71,48,18,14),(60,47,18,13),(48,44,18,10),(38,42,18,9),(32,41,4.6,11),(25,39,4.6,11),(18,38,4.6,8),(14,37,0,10)],
    [(151,-41,64,20),(135,-39,64,24),(123,-36,64,23),(116,-38,54,22),(113,-45,54,14),(110,-55,54,13)],
]
STAIRS = [(16,4),(34,12),(52,20)]
TIERS = [(20,97,36,4,12),(39,96,27,12,20),(57,95,19,20,28)]
BRIDGE_START = (-48,16)
BRIDGE_END = (-8.41,21.70)
TRAILS = {
    "Pilgrims approach":[(-116,7,9),(-105,1,8),(-94,4,7),(-84,13,6),(-76,24,6),(-64,25,5),(-53,18,4),(-48,16,4)],
    "East jungle gallery":[(-69,29,5),(-65,42,5.2),(-49,52,5.2),(-25,55,5.5),(-9,54,5),(7,48,5),(14,29,4),(16,7,4)],
    "Rain court":[(87,0,28),(98,0,28),(105,5,28),(114,13,29),(123,17,31),(133,13,32)],
    "Spring trail":[(113,12,29),(123,26,31),(133,39,34),(133,55,37),(124,65,40),(110,67,43),(99,63,44)],
    "West canopy trail":[(101,0,28),(109,-14,30),(120,-22,34),(124,-35,38),(133,-47,43),(132,-54,46.2),(129.5,-58,48.5),(125.5,-61,50.9),(122,-61,52.35),(120.6,-60.8,53),(118.5,-59.9,54.05),(116.6,-60,54.8),(111,-61.55,55),(107.4,-62.4,55),(105.1,-64.3,55),(105.2,-67.2,55),(107.4,-69.7,55),(110,-69,55)],
    "Broken cloister":[(-88,12,6),(-91,-7,7),(-85,-23,7),(-71,-38,6),(-54,-48,5),(-31,-53,6),(-14,-56,7),(0,-54,7.5),(13,-53,8),(24,-57,10)],
    "High shrine ridge":[(110,-69,55),(101,-73,55),(97,-77.1,54.8),(96.75,-78.75,54.8),(96.95,-80.81,54.85),(97.65,-85.2,55),(98.15,-89.3,55),(98.37,-91.4,55),(97.1,-92,55),(94.7,-92.3,55),(91.4,-92.4,55),(91,-90,55),(91.4,-92.4,55),(97.4,-93.3,55.65),(99.8,-93.65,56.9),(102,-94,58),(115,-96,61),(123,-103,65),(134,-110,68),(148,-113,71),(159,-105,74),(154,-94,77),(144,-92,79)],
    "Crown watch spur":[(144,-92,79),(141,-85,78.1),(140.8,-80,75.9),(142,-77.8,75.3),(142.8,-73.9,75.15),(141.7,-69.7,75.05),(138.2,-68.7,75),(136,-71,75)],
}
CAMERAS = {
    "Reference":((-61.25,22.4,9.15),(-20.3,.28),55.6),
    "PilgrimsApproach":((-83.8,13.4,7.6),(48,1.0),76),
    "Bridge":((-42.8,18.2,5.68),(15,5),76),
    "Stairs":((13,1,5.7),(-2,22),76),
    "Sanctuary":((72,0,29.65),(0,3),72),
    "SpringCourt":((111,13,30.7),(-146,5),76),
    "WestCloister":((-28,-53,7.75),(30,8),77),
    "Basin":((-39.8,41.2,5.3),(-52,-3),73),
    "Aerial":((-81,112,104),(-38,-28),80),
}

def clamp(v, low=0, high=1):
    return max(low,min(high,v))

def sm(v):
    v=clamp(v)
    return v*v*(3-2*v)

def mix(a,b,t):
    return a+(b-a)*t

def line_sample(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=clamp(((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy))
    return math.hypot(x-a[0]-dx*t,y-a[1]-dy*t),t

def trail_sample(x,y):
    near=(999,0)
    for path in TRAILS.values():
        for a,b in zip(path,path[1:]):
            d,t=line_sample(x,y,a,b)
            if d<near[0]:
                near=(d,mix(a[2],b[2],t))
    return near

def within_bank(x,y):
    if x<=BANKS[0][0]:
        return min(y+13,14-y,x+63)
    if x>=BANKS[-1][0]:
        return min(y+39,41-y,19-x)
    for a,b in zip(BANKS,BANKS[1:]):
        if x<=b[0]:
            t=(x-a[0])/(b[0]-a[0])
            return min(y-mix(a[1],b[1],t),mix(a[2],b[2],t)-y,x+63,19-x)

def river_sample(x,y):
    near=(999,0,0)
    for river in RIVERS:
        for a,b in zip(river,river[1:]):
            d,t=line_sample(x,y,a,b)
            width=mix(a[3],b[3],t)*.5
            if d-width<near[0]:
                near=(d-width,mix(a[2],b[2],t),width)
    return near

def hill(x,y,cx,cy,rx,ry,height):
    return height*math.exp(-((x-cx)/rx)**2-((y-cy)/ry)**2)

def terrain(x,y):
    si,co=math.sin,math.cos
    folds=si(x*.094+co(y*.057)*1.6)*co(y*.084+.4)+.47*si(x*.21-y*.15)+.18*co(y*.52+x*.37)
    z=5+1.1*folds+1.1*si(y*.11)
    for h in [(75,-85,37,25,40),(106,-66,40,29,46),(154,-79,32,36,79),(151,-125,23,35,63),(126,84,48,33,52),(136,36,46,35,33),(197,2,45,72,67),(5,-118,38,38,49),(-46,-109,31,30,28),(-50,104,55,35,24),(-132,3,28,76,20)]:
        z+=hill(x,y,*h)
    z+=max(0,z-12)*(.065*folds+.027*si(.47*y+.14*x))
    z-=max(0,z-50)*.43*sm((-y-50)/30)*sm((x-76)/35)
    d=within_bank(x,y)
    if d>-8:
        z=mix(z,-.24-min(4.1,max(d,0)*.31)+.16*folds,sm((d+8)/9))
    # A rooted stone headland under the near arch and the approaching player's feet.
    headland=((x+61)/20.5)**2+((y-10)/11.8)**2
    if headland<1.5:
        z=mix(z,4.85+.36*folds,1-sm((headland-.61)/.89))
    shoulder=((x+53)/9.5)**2+((y-17)/6.5)**2
    if shoulder<1.65:z=mix(z,3.83+.13*folds,1-sm((shoulder-.50)/1.15))
    gate_seat=((x+42.25)/6.4)**2+((y-5.55)/5.9)**2
    if gate_seat<1.45:z=mix(z,4.39+.09*folds,1-sm((gate_seat-.58)/.87))
    bank_dist,bank_t=line_sample(x,y,(-67,39),(-45.6,24.9))
    bank_width=mix(10,4.25,bank_t)
    if bank_dist<bank_width+2.6:
        z=max(z,mix(-1.5,mix(4.7,2.95,bank_t)+.30*folds,1-sm((bank_dist-bank_width*.48)/(bank_width*.52+2.6))))
    enclosure=min(x-15,102-x,36.5-abs(y))
    if enclosure>-4:z=mix(z,3.66,sm((enclosure+4)/4))
    for front,rear,half,base,top in TIERS:
        interior=min(x-front,rear-x,half-abs(y))
        if interior>.18:
            height=top-.24
            z=mix(z,height,sm((interior-.18)/1.45))
    if 8<x<101 and abs(y)<11:
        stair=4.
        for foot,base in STAIRS:
            stair=base+clamp((x-foot)/13.2)*8 if x>=foot else stair
        z=mix(z,stair-.32,sm((11-abs(y))/2)*sm(min((x-8)/3,(101-x)/4)))
    # A continuous cut-stone plaza terminates the curved east-bank approach.
    if 6<x<22 and abs(y)<36:
        mask=sm(min((x-6)/3,(22-x)/3,(36-abs(y))/4))
        z=mix(z,3.60,mask)
    edge,level,width=river_sample(x,y)
    if edge<10 and (x>16 or abs(y)>30):
        bank=level+clamp((edge+1.25)/5)*4.2-1.1+.28*folds
        z=mix(z,bank,1-sm((edge-2)/8))
    td,tz=trail_sample(x,y)
    if td<5.2:
        z=mix(z,tz+.06*folds,1-sm((td-1.35)/3.85))
    # Flatten the actual founded footprints while retaining the adjacent rising trail.
    for cx,cy,grade,yaw,scale in [(91,-90,55,98,1.05),(136,-71,75,-132,1.35),(123,17,31,-156,.88),(24,-57,10,-119,.73),(-27,54,5.46,-84,.68),(110,-69,55,15,1.13)]:
        if abs(x-cx)>16 or abs(y-cy)>16:continue
        ang=math.radians(yaw);lx=((x-cx)*co(ang)+(y-cy)*si(ang))/scale;ly=(-(x-cx)*si(ang)+(y-cy)*co(ang))/scale
        edge=max(-1.85-lx,lx-8.3,abs(ly)-5.3)
        if edge<3:z=mix(z,grade-.14,1-sm(max(0,edge)/3))
    dist,_=line_sample(x,y,(-83,-24.5),(-74.5,-32.7))
    if dist<5.5:z=mix(z,6.70,1-sm((dist-3.05)/2.45))
    return z
