"""World-space water features. Positions are metres in Unreal's X/Y/Z axes."""
import math
import random
from collections import namedtuple


TAU = 2.0 * math.pi
WHITE = (1.,1.,1.,1.)
Feature = namedtuple("Feature", "name material shape pivot")
BANKS = [(-63,-13,14),(-59,-30,29),(-51,-39,38),(-42,-45,43),
         (-25,-46,44),(-9,-42,43),(4,-42,44),(14,-40,43),(19,-39,41)]
CHANNELS = {
    "West": [(110,-55,54,13),(98,-53,54,16),(93,-51,54,19),(86,-49,27,18),
             (78,-49,27,19),(68,-47,27,13),(61,-45,27,12),(55,-44,18,12),
             (46,-41,18,15),(32,-40,18,11),(27,-39,18,9),(21,-38,1.8,10),
             (16,-37,1.8,10),(13,-36,1.8,8),(10,-35,0,10)],
    "East": [(98,52,42,9),(84,51,42,13),(77,49,42,12),(71,48,18,14),
             (60,47,18,13),(48,44,18,10),(38,42,18,9),(32,41,4.6,11),
             (25,39,4.6,11),(18,38,4.6,8),(14,37,0,10)],
    "Crown": [(151,-41,64,20),(135,-39,64,24),(123,-36,64,23),(116,-38,54,22),
              (113,-45,54,14),(110,-55,54,13)]
}
LILY_PATCHES = [(-52,-15,3.5,2.1,14),(-40,-12,2.3,1.7,8),
                (-54,28,4.2,1.8,17),(-44,32,2.7,2.2,13),
                (-31,36,3.9,1.25,12),(-16,-25,3.1,1.65,13),
                (4,29,2.4,1.3,7),(-37,-34,3.4,1.9,9),
                (-43,-2,2.8,1.3,10),(-55,-6,1.8,1.0,6)]


def mix(a,b,t):
    return a+(b-a)*t


class Mesh:
    def __init__(self):
        self.positions, self.uvs, self.colors, self.faces = [], [], [], []

    def vertex(self, pos, uv=(0.,0.), color=WHITE):
        self.positions.append(pos)
        self.uvs.append(uv)
        self.colors.append(color)
        return len(self.positions)-1

    def face(self,a,b,c):
        self.faces.append((a,c,b))

    def quad(self,a,b,c,d):
        self.face(a,b,c)
        self.face(a,c,d)

    def grid(self, rows, cols, point, reverse=False):
        start=len(self.positions)
        for row in range(rows+1):
            for col in range(cols+1):
                self.vertex(*point(row/rows,col/cols))
        for row in range(rows):
            for col in range(cols):
                a=start+row*(cols+1)+col
                c=a+cols+2
                if reverse:
                    self.quad(a,a+1,c,c-1)
                else:
                    self.quad(a,c-1,c,a+1)

    def close_bed(self, start, rows, cols, thickness):
        count=(rows+1)*(cols+1)
        under=len(self.positions)
        for index in range(start,start+count):
            x,y,z=self.positions[index]
            self.vertex((x,y,z-thickness),self.uvs[index],self.colors[index])
        for row in range(rows):
            for col in range(cols):
                a=under+row*(cols+1)+col
                c=a+cols+2
                self.quad(a,a+1,c,c-1)
        bounds=([r*(cols+1) for r in range(rows+1)]
               +[rows*(cols+1)+c for c in range(1,cols+1)]
               +[r*(cols+1)+cols for r in range(rows-1,-1,-1)]
               +list(range(cols-1,0,-1)))
        for i,a in enumerate(bounds):
            b=bounds[(i+1)%len(bounds)]
            self.quad(start+a,under+a,under+b,start+b)


def profile(x, samples):
    for left,right in zip(samples,samples[1:]):
        if x <= right[0]:
            t=(x-left[0])/(right[0]-left[0])
            return [mix(a,b,t) for a,b in zip(left[1:],right[1:])]
    return samples[-1][1:]


def basin():
    water, gravel = Mesh(),Mesh()
    shoals=[(-52.,-17.,8.,5.),(-52.,27.,8.,5.),(-42.,33.,9.,5.),
            (-35.,-35.,11.,6.),(-15.,-27.,7.,5.),(1.,31.,7.,5.),(-54.,-6.,4.,5.)]
    def shores(x):
        t=(x-BANKS[0][0])/(BANKS[-1][0]-BANKS[0][0])
        y0,y1=profile(x,BANKS)
        bump=math.sin(t*39.1)*.61+math.sin(t*13.+.8)*.83
        return y0+bump,y1+.72*math.sin(t*29.5)
    def bed_height(x,y,k):
        depth=.63+2.77*(max(0.,math.sin(math.pi*k))**.61)
        depth+=.46*math.sin(x*.16+y*.14)+.22*math.sin(x*.48-y*.31)
        shoal=max(math.exp(-(((x-px)/rx)**2+((y-py)/ry)**2)) for px,py,rx,ry in shoals)
        return -max(.25,depth*(1.-shoal*.84))
    def cross(t,k,bed):
        x=mix(BANKS[0][0],BANKS[-1][0],t)
        y0,y1=shores(x)
        y=mix(y0,y1,k)
        ground=bed_height(x,y,k)
        z=ground if bed else 0.
        shallows=max(0.,min(1.,(2.8+ground)/2.6))
        return (x,y,z),(x*.15,y*.15),(shallows,1.,1.,1.) if not bed else WHITE
    for target,is_bed in [(water,False),(gravel,True)]:
        rows,cols=(76,61) if is_bed else (50,26)
        target.grid(rows,cols,lambda t,k:cross(t,k,is_bed))
        if is_bed:
            target.close_bed(0,rows,cols,.64)
    rng=random.Random(7801)
    for cx,cy,rx,ry in shoals:
        for j in range(32):
            x=cx+rx*rng.uniform(-.82,.82)
            y=cy+ry*rng.uniform(-.78,.78)
            lo,hi=shores(x)
            if not lo<y<hi:
                continue
            z=bed_height(x,y,(y-lo)/(hi-lo))-.045
            size=rng.uniform(.075,.42)*(1.65 if j<3 else 1.)
            az=rng.random()*TAU
            ring=[]
            for i in range(8):
                a=TAU*i/8+az+rng.uniform(-.10,.10)
                r=size*rng.uniform(.83,1.11)
                ring.append((math.cos(a)*r,math.sin(a)*r*.78))
            lower=[]; upper=[]
            for dx,dy in ring:
                lower.append(gravel.vertex((x+dx,y+dy,z-.16*size),(x+dx,y+dy)))
                upper.append(gravel.vertex((x+dx*.77,y+dy*.77,z+size*rng.uniform(.24,.41)),(x+dx,y+dy)))
            crown=gravel.vertex((x+.10*size,y-.08*size,z+size*.48),(x,y))
            for i in range(8):
                b=(i+1)%8
                gravel.quad(lower[i],lower[b],upper[b],upper[i])
                gravel.face(upper[i],upper[b],crown)
    return [Feature("ReflectionPool","M_SpringWater",water,(-22,0,0)),
            Feature("ReflectionPoolBed","M_SubmergedGravel",gravel,(-22,0,-2))]


def headwaters(side, points):
    surf, bed = Mesh(),Mesh()
    def cross_axis(index):
        if side!="Crown" or index in (0,len(points)-1) or any(
            points[j][2]!=points[index][2] for j in (index-1,index+1)):
            return (0.,1.)
        dx=points[index-1][0]-points[index+1][0]
        dy=points[index-1][1]-points[index+1][1]
        length=math.hypot(dx,dy)
        return (-dy/length,dx/length)
    for index,(a,b) in enumerate(zip(points,points[1:])):
        if a[2] != b[2]:
            continue
        length=math.hypot(a[0]-b[0],a[1]-b[1])
        def knot(t,k,is_bed):
            x,y,z,width=[mix(i,j,t) for i,j in zip(b,a)]
            boundary=(math.sin(2.8*t+1.7)*.3+math.sin(t*7.)*.18)*math.sin(t*math.pi)
            transverse=(k-.5)*(width+boundary)
            na=cross_axis(index)
            nb=cross_axis(index+1)
            x+=mix(nb[0],na[0],t)*transverse
            y+=mix(nb[1],na[1],t)*transverse
            if is_bed:
                z-=.53+1.35*math.sin(k*math.pi)+.16*math.sin(x*.87+y*.52)
            depth_color=.29+.55*(abs(k-.5)*2.)**1.4
            return (x,y,z),(x*.13,y*.13),(depth_color,1.,1.,1.) if not is_bed else WHITE
        rows=max(3,int(length/.95))
        for target,is_bed in [(surf,False),(bed,True)]:
            start=len(target.positions)
            target.grid(rows,10,lambda t,k:knot(t,k,is_bed))
            if is_bed:
                target.close_bed(start,rows,10,.52)
    return [Feature(side+"TierPools","M_SpringWater",surf,points[3][:3]),
            Feature(side+"PoolBeds","M_SubmergedGravel",bed,points[3][:3])]


def curtains(a,b,seed):
    rng=random.Random(seed)
    face=Mesh()
    x0,y0,z0,w0=a
    x1,y1,z1,w1=b
    h=z0-z1
    min_w=min(w0,w1)
    # Each winding plume starts from an upstream tongue, turns over the lip,
    # falls nearly vertically, and breaks into fine strands at the foot.
    def ribbon(center,span,depth,alpha,phase,thickness):
        def pt(t,k):
            if t<.13:
                q=t/.13
                x=x0+mix(1.12,0.,q)
                z=z0+.045-.10*q*q
                trail=0.
            else:
                trail=(t-.13)/.87
                travel=(1.-math.exp(-3.6*trail))/(1.-math.exp(-3.6))
                x=mix(x0,x1,travel)
                z=mix(z0-.055,z1-.07,trail*trail)
            sag=math.sin(math.pi*t)
            base=center+(k-.5)*span
            corr=.14*math.sin(base*4.9+phase+trail*3.)+.060*math.sin(base*14.5-phase)
            x+=corr*(.48+trail*.8)+depth+thickness*math.sin(k*math.pi)
            y=mix(y0,y1,trail)+base*(1.+.07*trail)
            y+=.19*sag*math.sin(phase+trail*5.7)+.1*trail*math.sin(base*3.17+trail*7.4)
            z+=.14*math.sin(base*2.65+phase)*sag
            edge=min(1.,min(k,1.-k)*7.)
            weight=alpha*(.12+.88*edge)*(.88+.12*math.sin(base*3.7+phase))
            return (x,y,z),(base+phase*.71,t*(h+2.1)),(1.,1.,1.,weight)
        face.grid(max(12,int(h*.92)),max(4,int(span*4)),pt,True)
    # Separate braided veils leave narrow rock windows across the broad lip.
    u=-min_w*.49
    while u<min_w*.47:
        span=min(rng.uniform(1.1,3.1) if min_w>10 else rng.uniform(.67,1.9),min_w*.5-u)
        if span<.16:
            break
        ribbon(u+span*.5,span,rng.uniform(-.36,.20),rng.uniform(.83,1.),rng.random()*TAU,.1)
        if span>1.14:
            ribbon(u+span*rng.uniform(.34,.66),span*rng.uniform(.33,.72),
                   rng.uniform(-.86,-.43),rng.uniform(.48,.74),rng.random()*TAU,.12)
        u+=span+rng.uniform(-.13,.24)
    for _ in range(max(6,int(min_w*.95))):
        lateral=rng.uniform(-min_w*.51,min_w*.51)
        ribbon(lateral,rng.uniform(.05,.22),rng.uniform(-1.0,-.38),
               rng.uniform(.32,.74),rng.random()*TAU,.025)
    # Oval cross-sections retain actual thickness around the fastest jets.
    for _ in range(max(3,int(min_w*.42))):
        base=rng.uniform(-min_w*.47,min_w*.47)
        radius=rng.uniform(.11,.28)
        front=rng.uniform(.35,.9)
        wave=rng.random()*TAU
        def jet(t,k):
            travel=(1.-math.exp(-3.4*t))/(1.-math.exp(-3.4))
            x=mix(x0+.12,x1-.12,travel)-front
            y=mix(y0,y1,t)+base+.13*t*math.sin(t*9.+wave)
            z=mix(z0+.085,z1-.05,t*t)
            angle=k*TAU
            r=radius*(1.-.36*t)*(.94+.06*math.sin(t*17.+wave))
            return ((x+r*.62*math.cos(angle),y+r*math.sin(angle),z),
                    (base+math.sin(angle)*r+wave*.87,t*(h+.5)),
                    (1.,1.,1.,.63+.22*math.sin(math.pi*t)))
        face.grid(max(16,int(h*.91)),7,jet,True)
    return face


def plunge_pool(a,b,seed):
    rng=random.Random(seed)
    x,y,z,w=b
    h=a[2]-z
    foam,mist=Mesh(),Mesh()
    for index in range(7):
        arc0=rng.uniform(-1.,.12)
        coverage=rng.uniform(3.4,5.65)
        rx=1.4+index*.33+min(h*.065,1.6)
        ry=w*(.26+.044*index)
        def ring(t,k):
            ang=arc0+t*coverage
            jitter=.15*math.sin(ang*5.+index*.93)+.11*math.sin(ang*11.-index)
            thick=(.16+.41*math.sin(t*math.pi))*(k-.5)
            px=x-.65+(rx+jitter+thick)*math.cos(ang)
            py=y+(ry+jitter+thick)*math.sin(ang)
            weight=math.sin(math.pi*k)**.68*math.sin(t*math.pi)**.65*(.9-index*.06)
            return (px,py,z+.035+.004*index),(t*rx,k),(1.,1.,1.,weight)
        foam.grid(64,4,ring)
    def turbulence(t,k):
        px=x+mix(-min(3.3,1.5+h*.08),.8,t)
        py=y+(k-.5)*w*(.94+.09*math.sin(t*4.))
        weight=(max(0,math.sin(t*math.pi)*math.sin(k*math.pi)))**.46
        return (px,py,z+.064),(t*w,k*w),(1.,1.,1.,weight)
    foam.grid(8,20,turbulence)
    # Compressed foamy tongues cross the rounded crest before turning down.
    for i in range(max(5,int(a[3]*.77))):
        offset=rng.uniform(-a[3]*.46,a[3]*.46)
        width=rng.uniform(.12,.55)
        length=rng.uniform(.42,1.34)
        def lip(t,k):
            px=a[0]+.22+(1.-t)*length
            py=a[1]+offset+(k-.5)*width
            weight=(math.sin(math.pi*k)*math.sin(math.pi*t))**.7
            return (px,py,a[2]+.06),(t,k),(1.,1.,1.,.67*weight)
        foam.grid(4,4,lip)
    # Thin, arched splash jets erupt from irregular points of the impact line.
    for _ in range(max(18,int(w*3.3))):
        sx=x+rng.uniform(-.76,.3)
        sy=y+rng.uniform(-w*.45,w*.45)
        reach=rng.uniform(.3,1.03)*min(2.85,.57+h*.085)
        height=rng.uniform(.20,1.)*min(1.84,.27+h*.052)
        angle=rng.uniform(2.1,4.15)
        radius=rng.uniform(.008,.037)
        def splash(t,k):
            px=sx+math.cos(angle)*reach*t
            py=sy+math.sin(angle)*reach*t
            pz=z+.041+height*4.*t*(1.-t)
            return (px,py+math.cos(k*TAU)*radius,pz+math.sin(k*TAU)*radius), (t,k),(1.,1.,1.,.83)
        foam.grid(7,3,splash)
    for i in range(max(10,int(w*1.28))):
        cy=y+rng.uniform(-.48,.48)*w
        cx=x+rng.uniform(-1.8,.3)
        sz=(.80+min(h*.135,3.3))*rng.uniform(.58,1.42)
        cz=z+rng.uniform(.28,.77)*sz
        angle=rng.uniform(0,TAU)
        wide=rng.uniform(.9,1.8)*sz
        def wisp(t,k):
            r=(k-.5)*wide*2.
            bulge=math.sin(k*math.pi)*math.sin(t*math.pi)*sz*.18
            return ((cx+r*math.cos(angle)+bulge*math.sin(angle),
                     cy+r*math.sin(angle)-bulge*math.cos(angle),cz+(t-.5)*2*sz),
                    (k,t),(1.,1.,1.,.62))
        mist.grid(3,4,wisp)
    return foam,mist


def lilies():
    rng=random.Random(2476)
    mesh=Mesh()
    yellow=(.75,.41,.035)
    def pad(x,y,size,heading,green):
        def leaf(r,k):
            ang=(.105+6.02*k)
            radius=(.021+.979*r)*size*(1.+.051*math.sin(ang*4.1+.25)+.034*math.sin(ang*7.+.4))
            dx=radius*math.cos(ang)*1.04
            dy=radius*math.sin(ang)*.89
            tissue=.004*math.cos(ang*14.+r)*r+.024*(r**4)*(.45+.55*math.sin(ang*3.2))
            return ((x+dx*math.cos(heading)-dy*math.sin(heading),
                     y+dx*math.sin(heading)+dy*math.cos(heading),.027+tissue),
                    (k,r),(*green,1.))
        mesh.grid(4,26,leaf)
    def blossom(x,y,size):
        z=.08
        for layer,count in [(0,8),(1,7),(2,5)]:
            for i in range(count):
                a=i*TAU/count+layer*.38+rng.uniform(-.1,.1)
                petal_size=size*(1.-layer*.18)
                col=(.79+rng.random()*.1,.28+layer*.08+rng.random()*.12,.34+layer*.1)
                def petal(t,k):
                    forward=petal_size*(.12+t*.91)
                    spread=(k-.5)*petal_size*.62*max(.015,math.sin(math.pi*t))**.66
                    lift=petal_size*(.06+.13*layer+(.26+layer*.18)*t*t+.14*abs(2*k-1)*math.sin(math.pi*t))
                    value=.70+.3*t
                    return ((x+math.cos(a)*forward-math.sin(a)*spread,
                             y+math.sin(a)*forward+math.cos(a)*spread,z+lift),
                            (k,t),tuple(v*value for v in col)+(1.,))
                mesh.grid(5,4,petal)
        for k in range(7):
            a=k*TAU/7
            u=mesh.vertex((x,y,z+size*.31),(0,0),(*yellow,1))
            v=mesh.vertex((x+size*.16*math.cos(a),y+size*.16*math.sin(a),z+size*.20),(.1,1),(*yellow,1))
            b=a+TAU/7
            q=mesh.vertex((x+size*.16*math.cos(b),y+size*.16*math.sin(b),z+size*.20),(.8,1),(*yellow,1))
            mesh.face(u,v,q)
    for px,py,rx,ry,count in LILY_PATCHES:
        occupied=[]
        for i in range(count):
            size=rng.uniform(.13,.33)
            for attempt in range(40):
                theta=rng.uniform(0,TAU)
                radius=rng.random()**.58
                x=px+rx*math.cos(theta)*radius
                y=py+ry*math.sin(theta)*radius
                if all(math.hypot(x-a,y-b)>.85*(size+c) for a,b,c in occupied):
                    break
            occupied.append((x,y,size))
            hue=rng.random()
            green=(mix(.13,.32,hue),mix(.21,.34,hue),mix(.044,.070,hue))
            pad(x,y,size,rng.uniform(0,TAU),green)
            if i in (1,7) or (i==11 and rng.random()<.4):
                blossom(x+.05,y-.025,rng.uniform(.12,.23))
    return Feature("LotusShelves","M_LiliesAndLotus",mesh,(-34,4,0))


def features(only=None):
    if only is None or only=="basin":
        yield from basin()
        yield lilies()
    for si,(side,points) in enumerate(CHANNELS.items()):
        if only is None or only==side:
            yield from headwaters(side,points)
        index=0
        for i,(a,b) in enumerate(zip(points,points[1:])):
            if a[2]==b[2]:
                continue
            index+=1
            name=f"{side}Falls{index:02}"
            if only is not None and only not in (side,name):
                continue
            salt=17+i*117+si*953
            yield Feature(name,"M_CascadeVeil",curtains(a,b,salt),a[:3])
            contact,cloud=plunge_pool(a,b,salt+1)
            yield Feature(name+"Whitewater","M_BrokenFoam",contact,b[:3])
            yield Feature(name+"Spray","M_SprayMist",cloud,b[:3])
