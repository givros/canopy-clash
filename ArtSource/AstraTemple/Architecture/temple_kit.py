"""Metric sculptural ashlar kit. X goes into a doorway, Y crosses it and Z is up."""
import bpy,bmesh,math,random,sys,json
from pathlib import Path
from mathutils import Vector
from mathutils import noise
from math import sin,cos,pi,exp,sqrt
root=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
rng=random.Random(58081)
noise.seed_set(58081)
pi2=pi*2
roles=['Sandstone','Ochre','CarvedStone','ShadeStone','MossStone','Pinestone']
tints=[(.76,.73,.67),(.82,.67,.51),(.91,.87,.78),(.52,.56,.55),(.46,.54,.32),(.86,.82,.69)]
materials=[]
def material(i):
    m=bpy.data.materials.new('M_Astra_'+roles[i]); m.diffuse_color=tuple(tints[i][k]*[.41,.31,.188][k] for k in range(3))+(1,)
    m.use_nodes=True; n=m.node_tree.nodes; link=m.node_tree.links.new; bs=n.get('Principled BSDF')
    tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(root/'T_Astra_TempleStone_BaseColor.png'),check_existing=True)
    mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;mix.inputs[2].default_value=(*tints[i],1);link(tex.outputs['Color'],mix.inputs[1]);link(mix.outputs[0],bs.inputs['Base Color'])
    nm=n.new('ShaderNodeTexImage');nm.image=bpy.data.images.load(str(root/'T_Astra_TempleStone_Normal.png'),check_existing=True);nm.image.colorspace_settings.name='Non-Color'
    norm=n.new('ShaderNodeNormalMap');norm.inputs['Strength'].default_value=.62;link(nm.outputs[0],norm.inputs['Color']);link(norm.outputs[0],bs.inputs['Normal'])
    rt=n.new('ShaderNodeTexImage');rt.image=bpy.data.images.load(str(root/'T_Astra_TempleStone_Roughness.png'),check_existing=True);rt.image.colorspace_settings.name='Non-Color';link(rt.outputs[0],bs.inputs['Roughness'])
    return m
materials=[material(i) for i in range(len(roles))]
def tone():return rng.choices([0,1,3,4,5],[58,14,10,4,14])[0]
assets={}
class Asset:
    def __init__(self,name):
        self.name='SM_Astra_'+name;self.v=[];self.f=[];self.m=[];self.s=[];self.groups={};self.component='Structure';self.shift=(0,0,0)
    def part(self,name):self.component=name
    def add(self,vs,fs,mi=0,smooth=False):
        base=len(self.v);dx,dy,dz=self.shift
        self.v.extend([(x+dx,y+dy,z+dz) for x,y,z in vs]);self.f.extend([tuple(base+k for k in f) for f in fs]);self.m.extend([mi]*len(fs));self.s.extend([smooth]*len(fs));self.groups.setdefault(self.component,[]).append((base,len(vs)))
    def finish(self):
        me=bpy.data.meshes.new(self.name);me.from_pydata(self.v,[],self.f);me.update()
        ob=bpy.data.objects.new(self.name,me);scene.collection.objects.link(ob)
        for mat in materials:me.materials.append(mat)
        for p,mi,sm in zip(me.polygons,self.m,self.s):p.material_index=mi;p.use_smooth=sm
        for name,ranges in self.groups.items():
            g=ob.vertex_groups.new(name=name)
            for start,n in ranges:g.add(range(start,start+n),1,'REPLACE')
        bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();me.update()
        uv=me.uv_layers.new(name='Quarry_2m40')
        for p in me.polygons:
            nx,ny,nz=[abs(a) for a in p.normal]
            for li in p.loop_indices:
                x,y,z=me.vertices[me.loops[li].vertex_index].co
                u,v=(x,y) if nz>=max(nx,ny) else ((y,z) if nx>=ny else (x,z))
                uv.data[li].uv=(u/2.4,v/2.4)
        if self.name in ('SM_Astra_StairFlight','SM_Astra_ApproachSteps'):
            group=ob.vertex_groups.get('Individually cut stair treads')
            if group:
                for face in me.polygons:
                    if face.normal.x<-.78 and abs(face.normal.z)<.43 and any(v.group==group.index for v in me.vertices[face.vertices[0]].groups):
                        face.material_index=3
        assets[self.name]=ob
        return ob
def rings(a,rows,m=0,sm=False):
    L=len(rows[0]);fs=[tuple(range(L-1,-1,-1)),tuple((len(rows)-1)*L+j for j in range(L))]
    for k in range(len(rows)-1):
        for j in range(L):fs.append((k*L+j,k*L+(j+1)%L,(k+1)*L+(j+1)%L,(k+1)*L+j))
    a.add(sum((list(r) for r in rows),[]),fs,m,sm)
def hewn(a,x,y,z,dx,dy,dz,m=None,wear=.075,tilt=0):
    if min(dx,dy,dz)<.008:return
    # Four irregular planar arrises, four clipped corners, three bevel rings.
    m=tone() if m is None else m
    base=min(wear,.13*min(dx,dy),dz*.22);ch=[min(dx,dy)*rng.uniform(.025,.13) for _ in range(4)]
    tx=rng.uniform(-.023,.023)*min(dx,1.5);ty=rng.uniform(-.023,.023)*min(dy,1.5)
    rows=[]
    for elev,inset,blend in [(0,base,0),(.8*base,0,.08),(dz-base*.9,0,.94),(dz,base,1)]:
        hx=dx/2-inset;hy=dy/2-inset
        pts=[(-hx+ch[0],-hy),(hx-ch[1],-hy),(hx,-hy+ch[1]),(hx,hy-ch[2]),(hx-ch[2],hy),(-hx+ch[3],hy),(-hx,hy-ch[3]),(-hx,-hy+ch[0])]
        rows.append([(x+xx+tx*blend,y+yy+ty*blend,z+elev+tilt*xx) for xx,yy in pts])
    rings(a,rows,m)
def masonry(a,x0,x1,y0,y1,z0,z1,course=.60,unit=1.33,axis='y',mat=None):
    n=max(1,round((z1-z0)/course));h=(z1-z0)/n
    for i in range(n):
        lo,hi=(y0,y1) if axis=='y' else (x0,x1)
        ln=hi-lo;k=max(1,round(ln/unit)+(i%2 and ln>2.5));ww=[rng.uniform(.72,1.25) for _ in range(k)];ws=sum(ww);pos=lo
        for w in ww:
            e=pos+ln*w/ws; z=z0+i*h+.008;drop=h-.014
            if axis=='y':hewn(a,(x0+x1)/2,(pos+e)/2,z,x1-x0,e-pos-.014,drop,mat)
            else:hewn(a,(pos+e)/2,(y0+y1)/2,z,e-pos-.014,y1-y0,drop,mat)
            pos=e
def caprow(a,x,y,z,dx,dy,dz,step=1.40,m=None,along='y'):
    q=dy if along=='y' else dx;k=max(1,round(q/step))
    for i in range(k):
        d=(i+.5)*q/k-q/2
        hewn(a,x+(d if along=='x' else 0),y+(d if along=='y' else 0),z,dx if along=='y' else q/k-.013,dy if along=='x' else q/k-.013,dz,m)
def ell(a,c,r,m=2,ns=24,nt=13):
    rows=[]
    for j in range(nt):
        lat=-pi*.5+pi*(j+.01)/(nt-.98)
        rows.append([(c[0]+r[0]*cos(lat)*cos(i*pi2/ns),c[1]+r[1]*cos(lat)*sin(i*pi2/ns),c[2]+r[2]*sin(lat)) for i in range(ns)])
    rings(a,rows,m,True)
def cable(a,path,r,m=2,sides=7,scales=None,sm=True):
    rows=[];last=None
    for i,pt in enumerate(path):
        d=Vector(path[min(len(path)-1,i+1)])-Vector(path[max(0,i-1)]);d.normalize()
        if last is None:up=Vector((1,0,0)) if abs(d.x)<.75 else Vector((0,1,0));v=d.cross(up).normalized()
        else:v=(last-d*last.dot(d)).normalized()
        w=d.cross(v);last=v;dia=r*(scales[i] if scales else 1)
        rows.append([tuple(Vector(pt)+dia*(cos(pi2*j/sides)*v+sin(pi2*j/sides)*w)) for j in range(sides)])
    rings(a,rows,m,sm)
def disc(a,x,y,z,ry,rz,depth,m=2):
    rows=[]
    for xx,fac in [(x+depth*.45,.90),(x+depth*.38,.98),(x-depth*.29,1),(x-depth*.5,.92)]:
        rows.append([(xx,y+ry*fac*cos(pi2*j/40),z+rz*fac*sin(pi2*j/40)) for j in range(40)])
    rings(a,rows,m)
def band(a,x,y,z,ry,rz,thick,m=2):
    path=[(x,y+ry*cos(pi2*j/42),z+rz*sin(pi2*j/42)) for j in range(43)];cable(a,path,thick,m,8)
def scroll(a,x,y,z,r,rotate=0,sg=1,m=2):
    path=[]
    for j in range(39):
        t=j/38;ang=(t*1.52*pi2+rotate)*sg
        path.append((x,y+r*(.13+.87*t)*cos(ang),z+r*(.13+.87*t)*sin(ang)))
    cable(a,path,r*.095,m,6)
def polyrel(a,x,y,z,pts,depth,m=2):
    a.add([(x+xx,y+yy,z+zz) for xx in [0,-depth] for yy,zz in pts],[tuple(range(len(pts))),tuple(range(len(pts),2*len(pts)))]+[(j,(j+1)%len(pts),(j+1)%len(pts)+len(pts),j+len(pts)) for j in range(len(pts))],m)
def glyph(a,x,y,z,s,kind=0):
    if kind%4 in (0,3):
        coords=[(-.38,-.38),(.36,-.38),(.36,.34),(-.34,.34),(-.34,-.16),(.12,-.16),(.12,.11),(-.10,.11)]
        if kind%4==3:coords=[(-u,v) for u,v in coords]
        cable(a,[(x,y+u*s,z+v*s) for u,v in coords],s*.065,2,sides=5,sm=False)
    elif kind%4==1:
        scroll(a,x,y,z,s*.39,m=2)
    else:
        polyrel(a,x,y,z,[(-.38*s,-.28*s),(-.18*s,-.28*s),(-.18*s,-.08*s),(.05*s,-.08*s),(.05*s,.13*s),(.24*s,.13*s),(.24*s,.34*s),(.39*s,.34*s),(.39*s,.44*s),(.08*s,.44*s),(.08*s,.24*s),(-.13*s,.24*s),(-.13*s,.04*s),(-.38*s,.04*s)],.07*s)
def glyphblock(a,x,y,z,s,kind=0):
    hewn(a,x+.065,y,z-s/2,.20,s*.96,s*.95,rng.choice((0,0,2,1)),wear=.055);glyph(a,x-.054,y,z,s*.94,kind)
def sculptface(a,xc,yc,zc,w=7.1,h=5.8):
    # Continuous weathered round head; brow ridge, lid slits, alae, parted lips,
    # cheek planes and chin are sculpted into the same closed stone surface.
    rows=[];nt=104;ns=190
    def g(q,s):return exp(-(q/s)**2)
    for j in range(nt):
        t=(j+.025)/(nt-.95);t=min(t,.9998)
        rad=(sin(pi*t)**.32)*(1-.23*(1-t)**2)
        rr=[]
        for i in range(ns):
            ang=pi2*i/ns;v=sin(ang)*rad;z=t;cosine=cos(ang)
            base=.41*rad*(abs(cosine)**.55)*(1 if cosine>=0 else -1)
            u=abs(v)
            cheek=.19*g(u-.57,.29)*g(z-.44,.16)+.10*g(u-.65,.21)*g(z-.59,.12)
            ey= .635+.026*(u-.37)/.23
            eye=(-.31*g(u-.38,.27)*g(z-ey,.068)+.22*g(u-.39,.228)*g(z-ey+.012,.035)
                 -.18*g(u-.39,.226)*g(z-ey-.006,.013)+.135*g(u-.39,.228)*g(z-ey+.050,.020))
            brow=.31*g(u-.38,.32)*g(z-(ey+.075+.035*g(u-.40,.22)),.042)
            nose=.30*g(v,.115)*g(z-.565,.154)+.48*g(v,.149)*g(z-.475,.065)+.27*g(u-.16,.108)*g(z-.453,.046)-.28*g(u-.121,.057)*g(z-.427,.024)
            chin=.23*g(v,.49)*g(z-.165,.105)
            lipline=.295+.030*g(v,.20)-.025*(u/.43)**2
            phil=.07*g(u-.063,.042)*g(z-.366,.042)
            lips=(.23*g(v,.38)*g(z-lipline-.023,.031)+.25*g(v,.40)*g(z-lipline+.041,.039)-.21*g(v,.415)*g(z-lipline+.005,.012))
            fold=-.098*g(u-(.23+.13*(.44-z)/.14),.035)*g(z-.35,.086)
            face=cheek+eye+brow+nose+lips+chin+phil+fold
            relief=face*max(0,cosine)**2
            p=(xc-w*(.43*base+.48*relief),yc+v*w*.5,zc+z*h)
            er=noise.noise_vector(Vector(p)*3.9)[0]*.018+noise.noise_vector(Vector(p)*.86)[0]*.029
            rr.append((p[0]+er,p[1],p[2]))
        rows.append(rr)
    rings(a,rows,2,True)
    def skin(v,t):
        j=max(0,min(nt-1,round(t*(nt-.95)-.025)));tt=min(.9998,(j+.025)/(nt-.95));rr=sin(pi*tt)**.32*(1-.23*(1-tt)**2)
        angle=math.asin(max(-.999,min(.999,v/rr)));i=round((angle%pi2)*ns/pi2)%ns
        return rows[j][i][0]
    for sg in [-1,1]:
        # The palpebral opening is an almond, carved with a solid overlapping
        # upper eyelid; a shallow dark medial cut stays legible at a distance.
        rr=[]; ns_eye=30; lens_scale=w/8.1
        for j in range(ns_eye+1):
            k=j/ns_eye;v=sg*(.164+.422*k);shape=max(.006,sin(pi*k)**.78);t=.634+.023*k
            xx=(xc-w*(.196-.021*k+.020*sin(pi*k)))-.14*lens_scale; yy=yc+w*v*.5; zz=zc+h*t
            rr.append([(xx+.16*lens_scale,yy,zz+shape*h*.054),(xx-.080*lens_scale,yy,zz+shape*h*.043),
                       (xx-.175*lens_scale,yy,zz+shape*h*.021),(xx-.185*lens_scale,yy,zz-shape*h*.010),
                       (xx-.085*lens_scale,yy,zz-shape*h*.040),(xx+.19*lens_scale,yy,zz-shape*h*.047)])
        rings(a,rr,2,True)
        for lower in (False,True):
            pts=[];sc=[]
            for j in range(ns_eye+1):
                k=j/ns_eye;v=sg*(.148+.451*k);shape=max(.006,sin(pi*k)**.78);t=.633+.023*k
                xx=(xc-w*(.196-.021*k+.020*sin(pi*k)))-(.17 if lower else .216)*lens_scale;yy=yc+w*v*.5
                zz=zc+h*(t+(-.038 if lower else .034)*shape)
                pts.append((xx,yy,zz));sc.append(.32+.68*shape)
            cable(a,pts,h*(.009 if lower else .014),2,8,sc)
        pts=[];sc=[]
        for j in range(ns_eye+1):
            k=j/ns_eye;v=sg*(.18+.39*k);t=.635+.023*k;shape=max(.006,sin(pi*k)**.8)
            pts.append(((xc-w*(.196-.021*k+.020*sin(pi*k)))-.32*lens_scale,yc+w*v*.5,zc+h*(t+.006*shape)));sc.append(.16+.84*shape)
        cable(a,pts,h*.0065,3,7,sc)
    # Carved ear helix and pendant plugs.
    for sg in [-1,1]:
        y=yc+sg*w*.497
        disc(a,xc-.10*w,y,zc+h*.60,w*.145,h*.20,w*.16,2)
        band(a,xc-.18*w,y,zc+h*.60,w*.112,h*.155,w*.019,2)
        scroll(a,xc-.183*w,y,zc+h*.60,w*.074,.25,sg,2)
        disc(a,xc-.15*w,y+sg*.045*w,zc+h*.307,w*.112,h*.138,w*.115,0)
        band(a,xc-.206*w,y+sg*.045*w,zc+h*.307,w*.080,h*.094,w*.018)
        disc(a,xc-.213*w,y+sg*.045*w,zc+h*.307,w*.038,h*.047,w*.024,3)
    # A wrapped crown flares over forehead, with stone beading and upright glyphs.
    def circ(level,pr,mat):
        rr=[]
        for dz,r in pr:
            rr.append([(xc+w*.225*r*cos(ang*pi2/68),yc+w*.53*r*sin(ang*pi2/68),zc+h*(level+dz)) for ang in range(68)])
        rings(a,rr,mat)
    circ(.79,[(0,.934),(.021,1),(.055,1.009),(.083,.985)],1)
    circ(.84,[(0,.975),(.018,1.038),(.055,1.04),(.067,1.013)],2)
    circ(.902,[(0,1.0),(.020,1.014),(.130,.97),(.152,.95)],0)
    for i in range(-8,9):
        ang=i*.15;y=yc+w*.524*sin(ang);xx=xc-w*.234*cos(ang)
        hewn(a,xx,y,zc+h*.918,w*.065,w*.08,h*(.122+.028*((i+12)%3)),2,wear=.045)
        glyph(a,xx-w*.034,y,zc+h*.976,w*.076,abs(i))
def pier(a,x,y,z,height=6,w=1.85,ornate=True):
    a.part('Footings');hewn(a,x,y,z,w*1.39,w*1.39,height*.08,0);hewn(a,x,y,z+height*.08,w*1.18,w*1.18,height*.10,1)
    a.part('Fluted shaft and rings')
    def shaft(zbase,top,r1,r2,flute=True):
        rs=[]
        for k in range(6):
            tt=k/5;R=(r1*(1-tt)+r2*tt)*(1+.023*sin(tt*pi))
            rs.append([(x+R*(1-(.048 if flute else 0)*(1+cos(12*ang*pi2/72)))*cos(ang*pi2/72),y+R*(1-(.048 if flute else 0)*(1+cos(12*ang*pi2/72)))*sin(ang*pi2/72),zbase+(top-zbase)*tt) for ang in range(72)])
        rings(a,rs,0,True)
    for k in range(4):shaft(z+height*(.18+.154*k),z+height*(.18+.154*(k+1))-.014,w*(.50-.008*k),w*(.50-.008*(k+1)))
    for zz,hh,ss,mm in [(.18,.04,1.02,1),(.23,.024,.98,2),(.77,.04,.99,1),(.810,.045,1.08,2),(.855,.044,1.22,0),(.90,.100,1.38,0)]:
        hewn(a,x,y,z+height*zz,w*ss,w*ss,height*hh,mm,.045)
    if ornate:
        for k in range(3):glyphblock(a,x-w*.47,y,z+height*(.38+.14*k),w*.60,k)
def paving(a,x0,x1,y0,y1,z,course=1,unit=1.75):
    n=max(1,round((x1-x0)/course));d=(x1-x0)/n
    for j in range(n):
        x=x0+(j+.5)*d;limit=y1-y0;k=max(1,round(limit/unit)+(j%2 and limit>3));ww=[rng.uniform(.70,1.32) for _ in range(k)];w=sum(ww);y=y0
        for l in ww:
            size=limit*l/w;hewn(a,x,y+size/2,z-.26,d-.016,size-.017,.26+rng.uniform(-.012,.008),None,.042);y+=size
def discroof(a,x,y,z,dx,dy,hs):
    for i,(width,step) in enumerate(hs):
        caprow(a,x,y,z,dx*width,dy*width,step,m=(1 if i%3==1 else 0));z+=step
def portal():
    a=Asset('Portal');a.part('Deep reveals')
    for sg in [-1,1]:
        masonry(a,.25,5.05,min(sg*3.46,sg*9.8),max(sg*3.46,sg*9.8),0,9.0,.78,1.70)
        # The side wall overlaps the chamber shell behind the portico.
        for d in [0,1.25,2.55,3.85]:
            hewn(a,d+.37,sg*3.55,0,.73,.68,.43,1);hewn(a,d+.37,sg*3.55,.43,.68,.54,8.24,0,.09)
            hewn(a,d+.37,sg*3.55,8.64,.86,.8,.39,1)
    a.part('Sculptural door surround')
    for sg in [-1,1]:
        pier(a,-.12,sg*4.03,0,9.15,1.10)
        for yy in (5.22,8.73):
            y=sg*yy;hewn(a,-.08,y,0,.93,1.23,.63,0)
            for k in range(7):glyphblock(a,-.50,y,.95+(k+.32)*1.12,1.16,k+int(yy))
            hewn(a,-.13,y,8.41,1.0,1.48,.70,2)
        masonry(a,-.10,1.90,min(sg*5.8,sg*8.1),max(sg*5.8,sg*8.1),0,9.0,.65,1.25)
    a.part('Carved lintel and cornice')
    masonry(a,.02,5.1,-9.8,9.8,9.,11.27,.73,2.03)
    for i in range(-8,9):glyphblock(a,-.12,i*1.15,10.04,1.08,i)
    for z,dx,dy,h,m in [(9.00,5.53,20.07,.31,1),(10.74,5.66,20.08,.25,1),(11.04,5.92,20.48,.33,2)]:
        caprow(a,2.30,0,z,dx,dy,h,1.65,m)
    a.part('Upper stepped masonry')
    masonry(a,.10,5.05,-8.75,8.75,11.35,13.10,.72,1.50)
    masonry(a,.40,5.02,-7.25,7.25,13.10,15.43,.78,1.54)
    masonry(a,.82,4.99,-5.83,5.83,15.43,18.10,.70,1.43)
    masonry(a,1.10,4.87,-4.52,4.52,18.10,19.96,.63,1.11)
    for j in range(-3,4):
        c=abs(j);h=[1.48,1.19,.92,.53][c]
        hewn(a,2.88,j*1.15,19.94,2.0,1.14,h,0)
        glyphblock(a,1.84,j*1.15,19.95+h*.45,h*.72,j)
    a.part('Deity headdress and facial sculpture');sculptface(a,.14,0,12.46,8.1,6.21)
    for sg in [-1,1]:
        for j in range(2):glyphblock(a,-.05,sg*(5.23+j*1.13),12.12,1.09,j+1)
    # Darkening derives from the deep opening and stone shell, not a back plate.
    a.finish()
def arch_wedge(a,x,y,z,ri,ro,zi,zo,th0,th1,wide,m):
    rows=[]
    for t in (th0,(th0+th1)/2,th1):
        rows.append([(x+rr*cos(t),y+side*wide/2,z+rz*sin(t)) for rr,rz,side in [(ri,zi,-1),(ro,zo,-1),(ro,zo,1),(ri,zi,1)]])
    rings(a,rows,m)
def bridge():
    a=Asset('BridgeSpan')
    a.part('Foundation and springing piers')
    for sg in [-1,1]:
        xc=sg*4.56;masonry(a,xc-.42,xc+.42,-2.56,2.56,-5.20,-3.15,.52,1.25)
        caprow(a,xc,0,-3.35,.86,5.35,.28,1.15,1)
    a.part('Load bearing vault')
    for j in range(17):
        t0=j*pi/17+.0047;t1=(j+1)*pi/17-.0047
        # Bond three voussoir bands through barrel thickness.
        for k in range(3):
            iy=-1.64+k*1.64;arch_wedge(a,0,iy,-3.15,4.13,4.80,2.56,3.09,t0,t1,1.63,tone())
        for sg in [-1,1]:arch_wedge(a,0,sg*2.49,-3.15,4.075,4.82,2.52,3.12,t0,t1,.39,2 if j%5==0 else tone())
    a.part('Spandrel ashlar')
    for j in range(24):
        xx=-5+(j+.5)*(10/24);edge=max(0,min(1,abs(xx)/4.82));h=-3.15+3.1*sqrt(max(0,1-edge*edge))
        if abs(xx)>4.82:h=-3.15
        for sg in [-1,1]:
            # Lower arris follows arch extrados to avoid floating spandrels.
            xl=xx-10/48;xr=xx+10/48
            def low(xt):return -3.15+3.09*sqrt(max(0,1-(xt/4.82)**2))
            b1=min(-.19,low(xl)-.043);b2=min(-.19,low(xr)-.043)
            y1=sg*2.18;y2=sg*2.56
            a.add([(xl,y1,b1),(xr,y1,b2),(xr,y2,b2),(xl,y2,b1),(xl,y1,-.18),(xr,y1,-.18),(xr,y2,-.18),(xl,y2,-.18)],[(0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],tone())
    a.part('Transverse end walls')
    for sg in (-1,1):
        xx=sg*4.89
        masonry(a,xx-.105,xx+.105,-2.51,2.51,-3.135,-.177,.59,1.12)
    a.part('Worn paving');paving(a,-5,5,-2.69,2.69,0,1.07,1.45)
    for sg in [-1,1]:
        a.part('Carved parapet and cutwaters');caprow(a,0,sg*2.51,.008,10,.44,.22,1.33,0,'x')
        for j in range(2):
            x=-2.5+j*5
            hewn(a,x,sg*2.48,.22,.73,.70,.25,1)
            hewn(a,x,sg*2.48,.46,.54,.54,.49,0)
            hewn(a,x,sg*2.48,.94,.79,.72,.18,2)
            glyph(a,x-.28,sg*2.48,.70,.43,j)
        for j in range(4):
            x=-3.75+j*2.5
            hewn(a,x,sg*2.48,.22,.24,.32,.36,0)
        caprow(a,0,sg*2.47,.56,10,.33,.19,2.5,2,'x')
    a.finish()
def stairs():
    a=Asset('StairFlight');N=40;run=13.2;rise=8;W=10.3
    a.part('Individually cut stair treads')
    for j in range(N):
        zz=(j+1)*rise/N;x0=j*run/N;x1=(j+1)*run/N
        caprow(a,(x0+x1)/2,0,zz-.23,x1-x0+.019,W,.228,1.86)
    a.part('Solid stair backing and end courses')
    # Continuous structural backing bears the full stair, including tread midspans.
    outline=[(0,-.25),(13.2,-.25)]
    for j in reversed(range(N)):
        zz=(j+1)*rise/N-.205
        outline.extend([((j+1)*run/N,zz),(j*run/N,zz)])
    nv=len(outline);vs=[(xx,side*5.17,zz) for side in (-1,1) for xx,zz in outline]
    fs=[tuple(range(nv)),tuple(range(nv,2*nv))]+[(i,(i+1)%nv,(i+1)%nv+nv,i+nv) for i in range(nv)]
    a.add(vs,fs,3)
    masonry(a,12.96,13.216,-5.18,5.18,-.24,7.783,.66,1.48)
    a.part('Stepped lateral retaining walls')
    for sg in [-1,1]:
        for b in range(10):
            x0=b*run/10;x1=(b+1)*run/10;zb=(b*4+3)*rise/N;high=(b+1)*rise/10+.73
            y=sg*5.58;masonry(a,x0,x1,y-.49,y+.49,-.25,high-.24,.67,1.07,'x')
            for k in range(2):
                xc=x0+(k+.5)*(x1-x0)/2;z=xc/run*rise+.35
                hewn(a,xc,y,z,(x1-x0)/2+.016,1.16,.40,2,.08,tilt=rise/run)
            if b in (0,3,6,9):
                hewn(a,(x0+x1)/2,y,high-.26,1.23,1.25,.51,1)
                hewn(a,(x0+x1)/2,y,high+.25,1.11,1.10,.20,2)
    a.finish()
def output_asset(ob):
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(root/(ob.name+'.fbx')),use_selection=True,use_mesh_modifiers=False,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False,path_mode='RELATIVE',use_tspace=False,mesh_smooth_type='FACE',add_leaf_bones=False)
def render(ob,target,eye,size,filename):
    for ix in assets.values():ix.hide_render=ix!=ob
    cs=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',cs);scene.collection.objects.link(cam);cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cs.type='ORTHO';cs.ortho_scale=size;scene.camera=cam
    if filename=='RitualHall':cs.type='PERSP';cs.lens=19
    lamps=[]
    for loc,energy,area,col in [((-18,-12,28),22000,9,(1,.855,.66)),((-10,14,15),12000,12,(.77,.85,1)),((13,4,22),16000,10,(1,.94,.80))]:
        d=bpy.data.lights.new('Quarry study light','AREA');d.energy=energy;d.shape='DISK';d.size=area;d.color=col;l=bpy.data.objects.new(d.name,d);scene.collection.objects.link(l);l.location=loc;l.rotation_euler=(Vector(target)-l.location).to_track_quat('-Z','Y').to_euler();lamps.append(l)
    scene.world=bpy.data.worlds.get('Stone study') or bpy.data.worlds.new('Stone study');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.20,.23,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.render.resolution_x=710;scene.render.resolution_y=650;scene.render.resolution_percentage=100;scene.render.film_transparent=False;scene.render.image_settings.file_format='PNG'
    out=Path(bpy.app.tempdir).parent/'astra_arch_studies';out.mkdir(exist_ok=True)
    import tempfile
    out=Path(tempfile.gettempdir())/'astra_arch_studies';out.mkdir(exist_ok=True);scene.render.filepath=str(out/(filename+'.png'));bpy.ops.render.render(write_still=True)
    for o in lamps+[cam]:bpy.data.objects.remove(o,do_unlink=True)
    for i in assets.values():i.hide_render=False
def first_wave():
    for fn in [portal,bridge,stairs]:
        fn();ob=next(reversed(assets.values()));output_asset(ob)
    render(assets['SM_Astra_Portal'],(0,0,10),(-38,-13,17),26,'Portal')
    render(assets['SM_Astra_BridgeSpan'],(0,0,-1.7),(-8,-19,7),12.2,'BridgeSpan')
if __name__=='__main__' and '--specimen' in sys.argv:first_wave()
def serpent_head(a,xc=0,yc=0,zc=0,scale=1):
    # Upper and lower profiles follow separate curves from protruding muzzle
    # through the gape to the broadened hinge. Thick tooth roots meet each jaw.
    def conv(x,y,z):return (xc+x*scale,yc+y*scale,zc+z*scale)
    def profile(desc,m):
        rows=[]
        for x,yd,bot,top in desc:
            cz=(bot+top)*.5;rz=(top-bot)*.5
            rows.append([conv(x,yd*math.copysign(abs(cos(t*pi2/32))**.73,cos(t*pi2/32)),cz+rz*math.copysign(abs(sin(t*pi2/32))**.77,sin(t*pi2/32))) for t in range(32)])
        rings(a,rows,m,True)
    profile([(-2.18,.55,1.26,1.76),(-2.09,.84,1.15,1.96),(-1.55,1.01,1.15,2.13),(-.76,1.13,1.23,2.32),(-.10,1.25,1.17,2.68),(.72,1.27,.80,2.61),(1.16,1.10,.65,2.33),(1.39,.77,.59,1.90)],2)
    profile([(-1.97,.62,.15,.42),(-1.84,.80,.09,.51),(-1.04,.91,.07,.50),(-.34,1.05,.10,.50),(.37,1.10,.18,.65),(.89,1.12,.29,1.55),(1.26,.82,.42,1.68)],0)
    for sg in [-1,1]:
        # flared venom teeth hang into the real void.
        for j,(x,bottom,tip,sz) in enumerate([(-1.82,1.34,.62,.18),(-1.06,1.32,.91,.12),(-.45,1.36,1.0,.095),(-1.54,.40,.81,.12),(-.80,.42,.80,.115)]):
            rows=[]
            for u,rad in [(0,1),(.25,.83),(.77,.40),(1,.065)]:
                yy=sg*(.60 if x<-1.70 else (.71 if x<-1 else .79))
                rows.append([conv(x+.13*u*u+sz*rad*cos(pi2*k/12),yy+sz*rad*.73*sin(pi2*k/12),bottom+(tip-bottom)*u) for k in range(12)])
            rings(a,rows,5,True)
        # Broad eyes are relief shields on the sloping skull flanks.
        e=( -.46,sg*1.06,2.05)
        def sidepath(x,z,r,pr,loop=36):
            return [conv(x+r*cos(k*pi2/loop),sg*(pr+.045*cos(k*pi2/loop)),z+r*sin(k*pi2/loop)) for k in range(loop+1)]
        cable(a,sidepath(e[0],e[2],.40,1.066),scale*.125,0,8)
        cable(a,sidepath(e[0],e[2],.246,1.14),scale*.080,2,8)
        ell(a,conv(e[0],sg*1.14,e[2]),(.20*scale,.10*scale,.21*scale),3,22,12)
        cable(a,sidepath(.725,1.47,.47,1.15),scale*.10,2,8)
        path=[]
        for j in range(31):
            t=j/30;ang=t*pi2*1.3
            path.append(conv(.71+(.06+.36*t)*cos(ang),sg*1.17,1.44+(.06+.36*t)*sin(ang)))
        cable(a,path,scale*.066,2,7)
        for j in range(4):
            xx=-1.83+j*.25;yy=.84+(j*.058);zz=1.62+j*.079
            path=[conv(xx+.12,sg*(yy+.061),zz+.21),conv(xx-.072,sg*(yy+.067),zz+.12),conv(xx-.13,sg*(yy+.060),zz-.03),conv(xx+.014,sg*(yy+.078),zz-.135)]
            cable(a,path,scale*.066,1,7)
        for j in range(3):
            xx=-1.50+j*.44;yy=.80+.08*j
            cable(a,[conv(xx-.14,sg*yy,.29),conv(xx,sg*(yy+.024),.265),conv(xx+.13,sg*(yy+.029),.315)],scale*.046,2,7)
        nost=conv(-1.95,sg*.69,1.80);ell(a,nost,(.15*scale,.10*scale,.096*scale),3,18,8)
        for j in range(5):
            k=j/4
            path=[conv(-1.84+k*.9,sg*(.67+k*.24),2.005+k*.064),conv(-1.78+k*.9,sg*(.79+k*.24),1.84+k*.12),conv(-1.64+k*.9,sg*(.84+k*.21),1.80+k*.10)]
            cable(a,path,.045*scale,1,7)
    # Sagittal ridge with scalloped scale plates joining the skull.
    for j in range(5):
        x=-.75+j*.41
        p=conv(x,0,2.24+.12*sin(j*.63))
        ell(a,p,(scale*.30,scale*.46,scale*(.21+.10*sin(j*.63))),0,22,10)
def serpent():
    a=Asset('Serpent');a.part('Battered stele shaft')
    hewn(a,0,0,-.18,3.20,3.05,.48,0);hewn(a,0,0,.30,2.75,2.80,.44,1)
    for j in range(4):
        hewn(a,0,0,.74+j*.91,2.19,2.26,.90,0)
        glyphblock(a,-1.11,0,1.19+j*.91,.91,j+1)
        for sg in [-1,1]:
            polyrel(a,-1.121,sg*.76,1.19+j*.91,[(-.109,-.38),(.104,-.31),(.15,.26),(.015,.39),(-.172,.22)],.12,1)
    hewn(a,0,0,4.38,2.47,2.53,.36,1);hewn(a,0,0,4.74,2.75,2.78,.22,2)
    a.part('Serpent mask and fanged jaws');serpent_head(a,.12,0,4.81,1.20)
    a.finish()
def procession(a,x,y,z,size,flip=False,kind=0):
    # A low-relief profile figure with headdress, flexed limbs and wrist bands.
    s=size;sg=-1 if flip else 1
    def point(u,v):return (x-.072*s,y+sg*s*u,z+s*v)
    hewn(a,x+.065,y,z-.51*s,.22,s*.98,s*.99,3,.025)
    def contour(fr,m=2):polyrel(a,x-.009,y,z,[(sg*u*s,v*s) for u,v in fr],.068*s,m)
    contour([(-.16,.046),(-.06,.19),(.04,.18),(.14,.024),(.08,-.11),(.245,-.15),(.25,-.23),(-.17,-.24),(-.19,-.11)])
    for rib in [[(-.093,.05),(.08,-.06)],[(-.13,.00),(.035,-.108)]]:
        cable(a,[point(u,v) for u,v in rib],s*.012,1,6)
    # bent arms, divergent supporting legs, heels and splayed hands.
    limbs=[[(-.10,.085),(-.25,-.03),(-.34,.007),(-.37,.10)],[(.08,.115),(.22,-.005),(.34,.086),(.36,.15)],[(-.105,-.19),(-.18,-.31),(-.28,-.425),(-.36,-.423)],[(.085,-.185),(.20,-.26),(.17,-.407),(.27,-.425)]]
    for ix,limb in enumerate(limbs):
        cable(a,[point(u,v) for u,v in limb],s*(.034 if ix<2 else .042),2,7,[1,.91,.72,.50])
    for up in [-1,1]:
        for j in range(3):
            yy=.36*up
            cable(a,[point(yy,.115),point(yy+up*(.024+.011*j),.17+.014*j)],s*.010,2,6)
    contour([(-.107,.15),(-.104,.29),(-.035,.355),(.050,.332),(.081,.299),(.093,.270),(.144,.237),(.085,.232),(.08,.178),(.040,.159),(.016,.12)])
    # Beaded collar, cheek/eye, lip, nose bridge, ear plug and waist fringe.
    for uv in [[(-.088,.277),(-.025,.296),(.047,.289),(.084,.272)],[(.01,.253),(.043,.261),(.076,.256)],[(.060,.205),(.085,.204)], [(-.083,.172),(-.07,.133),(-.006,.113),(.048,.129)], [(-.13,-.125),(.142,-.127)]]:
        cable(a,[point(u,v) for u,v in uv],s*.011,1,7)
    for j in range(6):
        ell(a,point(-.06+j*.021,.12-.015*sin(pi*j/5)),(s*.024,s*.012,s*.017),1,10,6)
    # Anatomical knee contours carry the garment, while shoes bear the weight.
    contour([(-.15,-.21),(-.056,-.206),(-.110,-.304),(-.211,-.361),(-.246,-.407),(-.296,-.421),(-.24,-.314),(-.186,-.263)])
    contour([(.072,-.21),(.138,-.215),(.221,-.264),(.208,-.343),(.186,-.409),(.146,-.413),(.159,-.281),(.095,-.262)])
    for j in range(3):
        for v in (-.289,-.392):
            yy=(-.182 if v>-.36 else -.275)+.010*j
            cable(a,[point(yy,v+.013*j),point(yy+.046,v+.011*j)],s*.011,1,6)
    for off in (0,1):
        q=-.30 if off==0 else .18
        contour([(q-.040,-.408),(q+.028,-.405),(q+.076,-.428),(q+.096,-.451),(q-.063,-.450)],1)
    for j in range(4):
        angle=(.87+j*.12)*pi
        by=-.028+.036*j; bz=.329
        tipy=-.30+.085*j;tipz=.462+.022*sin(angle)
        contour([(by-.017,bz),(by+.019,bz),(tipy+.025,tipz-.034),(tipy,tipz),(tipy-.020,tipz-.046)],2)
    # Central belt buckle and small pendant medallions.
    disc(a,x-.093*s,y,z-.119*s,.037*s,.032*s,.027*s,1)
    for j in range(3):
        side=(-.178,.102,-.232)[j]
        scroll(a,x-.05*s,y+sg*side*s,z+(-.075+.064*j)*s,.022*s,m=1)
    for j in range(5):
        st=(-.078+.035*j,.320)
        tip=(-.29+j*.088,.448+.038*sin(j*pi/4))
        cable(a,[point(*st),point((st[0]+tip[0])/2,(st[1]+tip[1])/2+.015),point(*tip)],s*.023,2,6,[1,.73,.12])
    disc(a,x-.087*s,y-sg*.079*s,z+.214*s,.042*s,.054*s,.045*s,1)
    for k in range(5):
        xx=-.153+.075*k
        contour([(xx,-.19),(xx+.03,-.19),(xx+.058,-.274),(xx+.012,-.251)],1)
def terrace():
    a=Asset('TerraceBay');a.part('Retaining masonry');masonry(a,.19,1.66,-4,4,-.14,7.63,.72,1.48)
    # Side bands look continuous when adjacent bays butt.
    for z,w,h,mi in [(0,2,.43,1),(.43,1.84,.25,0),(2.0,1.80,.30,1),(5.95,1.90,.30,1),(6.27,1.93,.21,2),(7.53,1.93,.26,1),(7.79,2.02,.21,2)]:
        caprow(a,.83,0,z,w,8,h,1.50,mi)
    a.part('Procession bas relief')
    for j in range(3):procession(a,.11,(j-1)*2.28,4.16,2.23,j%2==0,j)
    for j in range(-3,4):glyphblock(a,.17,j*1.10,1.12,.83,j)
    for sg in [-1,1]:
        hewn(a,.16,sg*3.67,2.29,.47,.40,3.64,0)
        for j in range(3):glyph(a,-.097,sg*3.67,2.87+j*1.13,.37,j)
    for j in range(3):
        pos=(j-1)*2.71+.14
        hewn(a,.79,pos,7.992,1.29,.84,.40,0,.075)
        hewn(a,.78,pos,8.385,1.41,.98,.18,1)
    a.finish()
def tile():
    a=Asset('Paving');a.part('Irregular bonded pavement');paving(a,-4,4,-4,4,0,.95,1.65);a.finish()
def colonnade():
    a=Asset('Colonnade');a.part('Foundations');pier(a,0,0,-.06,6.48,1.65,True);a.finish()
def parapet():
    a=Asset('Balustrade');a.part('Terrace perimeter')
    caprow(a,0,0,0,.76,8,.24,1.35,1)
    for j in range(9):
        y=-3.72+j*.93
        hewn(a,0,y,.23,.63,.47,.13,0)
        hewn(a,0,y,.36,.47,.345,.45,0)
        hewn(a,0,y,.80,.53,.41,.13,2)
    caprow(a,0,0,.91,.67,8,.22,1.67,2)
    for y in [-3.51,0,3.51]:
        hewn(a,0,y,.23,.81,.80,.97,0);hewn(a,0,y,1.20,.93,.89,.21,1);glyph(a,-.43,y,.77,.61,0)
    a.finish()
def hall():
    a=Asset('RitualHall');a.part('Incised paving');paving(a,0,18,-8.15,8.15,0,1.22,1.84)
    a.part('Full height processional walls')
    for sg in [-1,1]:
        y=sg*7.74;masonry(a,0,18,y-.39,y+.39,-.08,7.25,.79,1.66,'x')
        for off,h,ww,mi in [(0,.36,1.03,1),(.37,.24,.93,2),(3.50,.22,.94,1),(6.94,.33,1.15,1)]:
            caprow(a,9,y,off,18,ww,h,1.7,mi,'x')
    a.part('Ritual wall reliefs')
    for sg in [-1,1]:
        for k in range(4):
            mark=len(a.v);local_x=3.05+3.73*k
            procession(a,0,0,3.97,2.16,k%2==0)
            for vi in range(mark,len(a.v)):
                px,py,pz=a.v[vi]
                a.v[vi]=(local_x-sg*py,sg*(7.35+px),pz)
    # Two portals with a seven-metre clear passage at both ends.
    for x in [.4,17.6]:
        for sg in [-1,1]:
            masonry(a,x-.40,x+.40,min(sg*3.68,sg*7.6),max(sg*3.68,sg*7.6),0,6.38,.65,1.5)
            hewn(a,x,sg*3.87,.02,1.1,.54,6.08,0)
        masonry(a,x-.55,x+.55,-7.8,7.8,6.20,7.4,.60,1.65)
        for j in range(-5,6):glyphblock(a,x-.61,j*1.22,6.81,1.07,j)
    a.part('Skylit stone corbels')
    for sg in [-1,1]:
        for j in range(5):
            yy=sg*(6.72-.495*j);wide=2.37+.33*j
            caprow(a,9,yy,7.22+.33*j,18,wide,.35,1.54,2 if j%3==1 else 0,'x')
    for x in [1.16,16.84]:
        for row,(depth,h) in enumerate([(2.36,.46),(3.01,.46),(3.64,.42)]):
            caprow(a,x,0,7.30+row*.44,depth,12.25-.23*row,h,2.12,0)
    for x in [5.1,12.87]:
        for sg in [-1,1]:
            yy=sg*4.77;pier(a,x,yy,0,7.35,1.69,False)
            for j in range(2):glyphblock(a,x-.84,yy,1.90+j*.90,.85,j)
            a.part('Hall masks');sculptface(a,x-.68,yy,3.55,1.62,1.55)
            hewn(a,x,yy,7.29,2.32,2.26,.34,1)
    a.finish()
def shrine():
    a=Asset('Shrine');a.part('Paved lower plinth');paving(a,-1.70,8.2,-5.22,5.22,0)
    for sg in [-1,1]:
        yy=sg*4.66;masonry(a,-.08,8.05,yy-.38,yy+.38,0,5.18,.53,1.11,'x')
        masonry(a,0,1.08,min(sg*2.1,sg*4.63),max(sg*2.1,sg*4.63),0,4.25,.57,1.17)
        pier(a,-.22,sg*2.3,0,4.29,.78)
        for j in range(4):glyphblock(a,-.09,sg*3.65,.54+j*1.01,.92,j)
    masonry(a,7.40,8.05,-4.78,4.78,0,5.23,.61,1.28)
    for x in (3.25,6.25):
        for sg in [-1,1]:pier(a,x,sg*3.37,0,5.15,.91,False)
    masonry(a,-.09,1.12,-4.78,4.78,4.25,5.20,.55,1.22)
    for j in range(-3,4):glyphblock(a,-.15,j*1.17,4.74,.80,j)
    a.part('Corbel-vaulted shrine roof')
    for row in range(5):
        y=4.04-.49*row
        for sg in [-1,1]:caprow(a,4.01,sg*y,5.14+row*.43,8.45-.38*row,2.02+.12*row,.46,1.40,1 if row==0 else 0,'x')
    caprow(a,4.01,0,7.29,6.89,6.53,.48,1.42,0)
    for row in range(3):
        caprow(a,4.40,0,7.77+row*.49,5.43-row*.9,4.88-row*.84,.49,1.17,0)
    for j in range(-1,2):hewn(a,4.45,j*1.07,9.24,1.74,1.01,.90-.25*abs(j),0)
    a.part('Offering stand');hewn(a,6.36,0,0,1.42,2.37,.27,1);hewn(a,6.36,0,.27,1.04,1.73,.62,0);hewn(a,6.36,0,.88,1.5,2.28,.21,2)
    a.finish()
def final_export():
    jobs=[portal,bridge,stairs,serpent,terrace,tile,colonnade,parapet,hall,shrine,ruined_gate,cloister,battered_terrace,spillway,approach_steps]
    for j,fn in enumerate(jobs):
        fn();ob=next(reversed(assets.values()))
        if '--stairs' in sys.argv:
            write=j in (2,14)
        elif '--retaining' in sys.argv:
            write=j in (12,13)
        else:write=True
        if write:output_asset(ob)
        else:
            # Preserve previously delivered quarry-chip geometry while adding
            # a family. FBX and Blender share the original vertex order.
            bpy.ops.import_scene.fbx(filepath=str(root/(ob.name+'.fbx')),use_image_search=False,use_anim=False)
            imported=bpy.context.selected_objects[0]
            assert len(imported.data.vertices)==len(ob.data.vertices)
            coords=[coord for v in imported.data.vertices for coord in (imported.matrix_world@v.co)]
            ob.data.vertices.foreach_set('co',coords);ob.data.update()
            imported_mesh=imported.data;bpy.data.objects.remove(imported,do_unlink=True)
            bpy.data.meshes.remove(imported_mesh)
    # Independent source assemblies, selectable component vertex groups,
    # packed PBR images and true metric scene geometry.
    for j,ob in enumerate(assets.values()):
        ob.location=(int(j%4)*32.,int(j//4)*32.,0.)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(root/'AstraTemple_Architecture.blend'))
    metrics={}
    for o in assets.values():
        vs=[tuple(v.co) for v in o.data.vertices];metrics[o.name]={'minimum':[round(min(v[i] for v in vs),3) for i in range(3)],'maximum':[round(max(v[i] for v in vs),3) for i in range(3)],'vertices':len(vs),'polygons':len(o.data.polygons),'components':list(o.vertex_groups.keys())}
    (root/'ArchitectureMetrics.json').write_text(json.dumps(metrics,indent=2))
    for ob in assets.values():ob.location=(0,0,0)
    for name,target,eye,size in [('RuinedGate',(0,0,6.3),(-22,8,9.1),17.3),('CollapsedCloister',(1,0,3.4),(-16,-12,8.5),13.5),('Portal',(0,0,10.5),(-35,-8,15),24.5),('BridgeSpan',(0,0,-1.7),(-8,-19,7),12.2),('Serpent',(0,0,3.98),(-13,-18,8.65),9.6),('TerraceBay',(0,0,4.15),(-18,-8,8),11.3),('Shrine',(3,0,4.50),(-15,-14,9.5),15.8),('StairFlight',(6.60,0,3.9),(-12,-19,13.9),19.9),('RitualHall',(13,0,3.64),(1.50,-.25,1.75),12.9)]:
        if ('--retaining' not in sys.argv and '--stairs' not in sys.argv) or ('--stairs' in sys.argv and name=='StairFlight'):render(assets['SM_Astra_'+name],target,eye,size,name)
    if '--stairs' not in sys.argv:render(assets['SM_Astra_BatteredBay'],(0,0,4.05),(-18,-9,8.5),11.5,'BatteredBay')
    if '--stairs' not in sys.argv:render(assets['SM_Astra_SpillwayBay'],(0,0,4.05),(-18,-9,8.5),11.5,'SpillwayBay')

def wedge_y(a,xc,yc,zc,r1,r2,h1,h2,t0,t1,depth,m=0):
    rows=[]
    for u,ins in [(0,.040),(.062,0),(.50,0),(.94,0),(1,.043)]:
        t=t0+(t1-t0)*u
        rows.append([(xc+ss*(depth/2-ins),yc+rr*cos(t),zc+hh*sin(t)) for ss,rr,hh in [(-1,r1+ins,h1+ins),(-1,r2-ins,h2-ins),(1,r2-ins,h2-ins),(1,r1+ins,h1+ins)]])
    rings(a,rows,m)
def ruined_gate():
    a=Asset('RuinedGate');a.part('Walking stones and stylobates')
    for sg in (-1,1):
        y=sg*4.35
        hewn(a,.40,y,-.28,3.65,3.27,.54,0,.14)
        hewn(a,.40,y,.26,3.25,2.94,.34,1,.11)
        hewn(a,.40,y,.60,3.04,2.62,.42,0,.10)
    a.part('Inscribed mask pier')
    y=-4.35
    for j in range(5):hewn(a,.30,y,1.02+j*.97,2.65,2.27,.966,0,.107)
    for j in range(3):glyphblock(a,-1.082,y,1.57+j*.98,.97,j*3)
    for sg in [-1,1]:
        track=y+sg*.89
        for j in range(4):hewn(a,-1.02,track,1.11+j*1.1,.32,.29,1.08,0,.038)
    sculptface(a,-.84,y,3.70,2.43,2.28)
    # Robust abacus bed; side faces finish independently around the pier.
    for z,dx,dy,h,mi in [(5.88,2.65,2.40,.24,1),(6.12,2.87,2.58,.23,2),(6.35,3.04,2.71,.45,0),(6.80,3.25,2.96,.34,1),(7.14,3.48,3.02,.49,0)]:
        hewn(a,.30,y,z,dx,dy,h,mi)
    for j in range(-1,2):glyphblock(a,-1.27,y+j*.70,6.56,.61,j+2)
    pier(a,.33,4.35,1.02,6.60,2.25,False)
    # True independent dressed arch rings spring from the abaci.
    a.part('Radiating bonded vault courses');N=19
    for j in range(N):
        t0=j*pi/N+.0037;t1=(j+1)*pi/N-.0037
        for k,(xc,depth) in enumerate([(-.77,1.38),(.59,1.24),(1.62,.81)]):
            r_added=(.18 if k==0 else .05)
            wedge_y(a,xc,0,7.40,2.98,4.29+r_added,3.23,4.44+r_added,t0,t1,depth,2 if j in (8,9,10) and k==0 else tone())
    a.part('Broken spandrels and crown')
    for sg in [-1,1]:
        for j in range(6):
            yy=sg*(3.30+.42*j);lim=abs(yy)
            bottom=7.4+4.51*sqrt(max(0,1-(lim/4.44)**2))
            top=11.90+(.36 if sg<0 else -.04)+(.18 if j<2 else 0)
            if sg>0:top-=j*.37
            if top>bottom+.28:masonry(a,-1.31,1.98,yy-.213,yy+.213,bottom-.027,top,.62,.87)
    # Horizontal crown stones illuminate the silhouette in broken clusters.
    heights=[1.35,1.65,1.55,.94,.50,.68,.56,.22,.30,0,0]
    for j,h in enumerate(heights):
        y=-4.60+j*.78;lower=7.40+4.61*sqrt(max(0,1-(y/4.45)**2))
        if y<-2.62:lower=12.26
        if h>.15:hewn(a,.23,y,lower-.08,2.78,.80,h,tone(),.10)
    # A posterior wall fragment retains its spring but has lost the vault.
    a.part('Rear wall fracture and fallen voussoirs')
    for sg in [-1,1]:
        y=sg*4.32
        for j,h in enumerate([5.26,3.12,1.07] if sg<0 else [4.32,1.65,.49]):
            x=2.40+j*.80
            masonry(a,x-.42,x+.42,y-.92,y+.92,-.16,h,.79,1.05)
    for k,(x,y,sz) in enumerate([(2.64,-5.76,1.05),(3.14,-6.38,.63),(4.56,-5.45,.91),(-.86,6.12,.75),(.21,6.58,.39),(3.19,5.62,.61)]):
        hewn(a,x,y,-.091,sz*1.35,sz*.91,sz*.75,tone(),.13,tilt=rng.uniform(-.11,.11))
    a.finish()
def cloister():
    a=Asset('CollapsedCloister');a.part('Surviving footing')
    for yy in [-3.0,2.93]:
        for z,dx,dy,h in [(-.26,2.96,3.01,.46),(.20,2.56,2.64,.31),(.51,2.16,2.23,.37)]:
            hewn(a,0,yy,z,dx,dy,h,0)
    # A surviving springer sits on one capital; its opposite pier collapsed into drums.
    pier(a,0,-3.,.88,4.98,1.77,False)
    a.part('Broken half vault')
    for j in range(5):
        t0=pi-(j+1)*pi/18+.006;t1=pi-j*pi/18-.006
        wedge_y(a,.04,-.03,5.65,2.51,3.37,2.75,3.53,t0,t1,1.89,tone())
    for j in range(3):
        yy=-3.35-j*.68;hewn(a,0,yy,5.47,1.90,.69,.88-j*.16,0)
    a.part('Splintered northern column')
    for j,(zc,rad,high) in enumerate([(.84,.85,.86),(1.70,.78,.79),(2.48,.775,.68)]):
        rows=[]
        for kk in range(3):
            row=[]
            for ii in range(48):
                th=ii*pi2/48
                zz=(zc+[0,.1,high][kk])+(max(0,.34*cos(th+.43)+.11*sin(3*th)+.158*cos(5*th)) if j==2 and kk==2 else 0)
                r=rad*(1-.050*(1+cos(12*th)))*(1-kk*.013)
                row.append((r*cos(th),2.93+r*sin(th),zz))
            rows.append(row)
        rings(a,rows,0,True)
    a.part('Fallen fluted drums and cap')
    for j,(x,y,r,length,angle) in enumerate([(1.67,2.45,.70,1.85,-.40),(3.19,1.69,.66,1.34,-.63),(4.60,1.04,.62,1.21,-.22)]):
        rows=[]
        for q in [0,.065,.94,1]:
            row=[]
            for ii in range(48):
                th=ii*pi2/48;rad=r*(1-.060*(1+cos(12*th)))*(1-.04*(q in (0,1)))
                along=(q-.5)*length
                row.append((x+along*cos(angle)-rad*cos(th)*sin(angle),y+along*sin(angle)+rad*cos(th)*cos(angle),r*.94+rad*sin(th)))
            rows.append(row)
        rings(a,rows,tone(),True)
    for j in range(18):
        xx=rng.uniform(1.22,5.1);yy=rng.uniform(-1.20,1.64);sz=rng.uniform(.22,.88)
        hewn(a,xx,yy,-.04,sz*1.34,sz*.83,sz*.68,tone(),sz*.19,tilt=rng.uniform(-.15,.15))
    a.finish()

def retaining(name,water):
    a=Asset(name);a.part('Battered retaining courses')
    for i in range(12):
        z=i*.524+.007;inset=.038*i
        mat=3 if water and i<2 else None
        if not water and 3<=i<=9:
            # A true blind niche: masonry returns at each jamb and a complete
            # recessed back. The lintel and sill bridge across the wall.
            aperture=1.65-.18*max(0,i-7)
            for side in [-1,1]:
                masonry(a,.05+inset,1.8,min(side*aperture,side*4),max(side*aperture,side*4),z,z+.52,.52,1.55,mat=mat)
            masonry(a,.57+inset,1.8,-aperture,aperture,z,z+.52,.52,1.26,mat=3 if i in (3,6) else None)
        else:masonry(a,.05+inset,1.80,-4.,4.,z,z+.52,.52,(1.86 if i%3 else 1.44),mat=mat)
    if not water:
        caprow(a,.82,0,1.50,1.15,3.69,.19,1.33,1)
        caprow(a,.98,0,5.20,1.33,3.65,.32,1.44,1)
        for sg in [-1,1]:
            for j in range(4):
                hewn(a,.35+.042*j,sg*1.75,1.69+j*.81,.47,.38,.80,0,.055)
    a.part('Splayed masonry buttresses')
    for sg in [-1,1]:
        y=sg*2.97
        for i in range(9):
            h=.700;off=.061*i
            xx=-.27+off
            hewn(a,xx+.36,y,i*h+.009,.75,1.25-.033*i,h-.011,tone(),.070)
        hewn(a,.39,y,6.31,1.07,1.31,.31,0)
    a.part('Recessed fret and cornice')
    ranges=[(-4,-1.32),(1.32,4)] if water else [(-4,4)]
    for lo,hi in ranges:
        masonry(a,.39,1.85,lo,hi,6.28,7.70,.63,1.42)
        caprow(a,.98,(lo+hi)/2,6.28,1.73,hi-lo,.28,1.51,1)
        if not water:
            caprow(a,.95,-1.12,7.68,1.95,5.76,.32,1.35,0)
            hewn(a,1.0,2.22,7.68,1.62,.91,.242,0,.125,tilt=-.023)
            hewn(a,1.05,3.32,7.68,1.79,1.29,.29,0,.136,tilt=.016)
        else:caprow(a,.95,(lo+hi)/2,7.68,1.95,hi-lo,.32,1.30,0)
        if hi-lo>4:
            for i in [-2,0,2]:
                # Just three narrow carved tablets, unlike a procession bay.
                glyphblock(a,.394,i,7.12,.76,1+i)
        else:glyphblock(a,.394,(hi+lo)/2,7.10,.73,2 if lo<0 else 3)
    if water:
        a.part('Lowered open scupper chute')
        for j in range(4):
            xx=-.70+j*.70
            hewn(a,xx,0,6.17,.73,2.83,.29,3,.06,tilt=.030)
        for sg in [-1,1]:
            for j in range(3):
                xx=-.62+j*.89
                hewn(a,xx,sg*1.27,6.38,.91,.40,.43,0,.063)
    else:
        for y in [-3.0,.85]:
            hewn(a,1.00,y,7.992,1.34,.85,.38,0)
            hewn(a,1.01,y,8.37,1.51,1.01,.18,1)
    a.finish()
def battered_terrace():retaining('BatteredBay',False)
def spillway():retaining('SpillwayBay',True)
def approach_steps():
    a=Asset('ApproachSteps');a.part('Individually cut stair treads')
    for row in range(5):
        level=(row+1)*.16
        cuts=[1.09,1.26,1.17,1.18,1.10] if row%2==0 else [.74,1.43,1.47,1.35,.81]
        y=-2.9
        for width in cuts:
            hewn(a,.21+row*.42,y+width*.5,level-.194,.433,width-.013,.194,tone(),.038)
            y+=width
    a.part('Structural masonry core')
    for row in range(5):
        h=row*.16
        if h>.003:hewn(a,row*.42+.21,0,-.06,.423,5.77,h+.03,3,.025)
    a.part('Outer stair cheeks')
    for sg in [-1,1]:
        for row in range(5):
            hewn(a,row*.42+.21,sg*2.83,-.074,.426,.215,.20+.16*row,0,.028)
    a.finish()
if __name__=='__main__' and '--build' in sys.argv:
    final_export()
    if '--stairs' in sys.argv:render(assets['SM_Astra_ApproachSteps'],(1.0,0,.36),(-4,-7,3.1),7.2,'ApproachSteps')

