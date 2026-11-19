"""Editable, meter-scale jungle vegetation and lithic assets for the Astra Temple."""
import bpy
import json
import math
import random
import sys
from array import array
from pathlib import Path
from mathutils import Vector
from math import sin, cos, pi, exp

ROOT=Path(__file__).resolve().parents[1]
TEX=ROOT/"Textures"
SOURCE=ROOT/"Sources"
EXPORT=ROOT/"FBX"
OUT=ROOT/"Previews"
OUT.mkdir(exist_ok=True)
ARGS=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
V=Vector
Z=V((0,0,1))
TAU=2*pi
rng=random.Random(34728)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
materials={}
material_spec={}
assets={}
tree_lods={}

def surface(name, color, normal=None, roughness=.55, roughness_map=None, leaf=False,tint=None):
    mat=bpy.data.materials.new("M_"+name)
    mat.use_nodes=True
    shader=mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value=roughness
    channels={"base_color":color,"normal_gl":normal,"roughness_map":roughness_map}
    for channel,path in channels.items():
        if not path: continue
        image=bpy.data.images.load(str(path),check_existing=True)
        image.colorspace_settings.name='sRGB' if channel=='base_color' else 'Non-Color'
        node=mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image=image
        if channel=='normal_gl':
            normalnode=mat.node_tree.nodes.new("ShaderNodeNormalMap")
            normalnode.inputs["Strength"].default_value=.60 if leaf else .84
            mat.node_tree.links.new(node.outputs["Color"],normalnode.inputs["Color"])
            mat.node_tree.links.new(normalnode.outputs["Normal"],shader.inputs["Normal"])
        elif channel=='base_color' and tint:
            multiply=mat.node_tree.nodes.new('ShaderNodeMixRGB')
            multiply.blend_type='MULTIPLY'
            multiply.inputs[0].default_value=1
            multiply.inputs[2].default_value=(*tint,1)
            mat.node_tree.links.new(node.outputs['Color'],multiply.inputs[1])
            mat.node_tree.links.new(multiply.outputs['Color'],shader.inputs['Base Color'])
        else:
            target="Base Color" if channel=='base_color' else "Roughness"
            mat.node_tree.links.new(node.outputs["Color"],shader.inputs[target])
    # Deliberately real leaf outlines; opposite faces use the same surface.
    mat.use_backface_culling=False
    materials[name]=mat
    material_spec[mat.name]={k:str(p.relative_to(ROOT)).replace("\\","/") for k,p in channels.items() if p}
    material_spec[mat.name].update(roughness=roughness,two_sided=leaf)
    if tint:material_spec[mat.name]['linear_tint']=list(tint)

def make_surfaces():
    for name in ('RainLeaf','RainLeafLight','RainLeafShade','PalmBlade','MonsteraBlade','BractRed','BractGold','LilyLeaf','PetalRose','PetalCream','FernBlade','LivingStem'):
        surface(name,TEX/f'T_{name}_Color.jpg',TEX/'T_Botanical_NormalGL.png',.48 if 'Blade' in name else .54,leaf=True)
    surface('CanopySpray',TEX/'T_CanopySpray_ColorOpacity.png',roughness=.64,leaf=True)
    card=materials['CanopySpray']
    img=next(n for n in card.node_tree.nodes if n.type=='TEX_IMAGE')
    bsdf=card.node_tree.nodes.get('Principled BSDF')
    card.node_tree.links.new(img.outputs['Alpha'],bsdf.inputs['Alpha'])
    material_spec['M_CanopySpray']['alpha_cutout']=True
    for name,file in [('FigBark','japanese_hackberry_bark'),('PalmBark','palm_bark')]:
        surface(name,TEX/f'T_{file}_Color.jpg',TEX/f'T_{file}_NormalGL.jpg',.78,TEX/f'T_{file}_Roughness.jpg',
                tint=(.70,.56,.45) if name=='FigBark' else None)
    surface('MossNap',TEX/'T_MossNap_Color.jpg',roughness=.86)
    for name,src in [('SandstoneFace','rock_face_01'),('FracturedRock','namaqualand_cliff_01'),('MossRock','rock_moss_set_01')]:
        folder=SOURCE/src/"textures"
        rough=next(folder.glob('*rough*'),None)
        surface(name,next(folder.glob('*diff*')),next(folder.glob('*nor_gl*')),.86,rough)
        arm=next(folder.glob('*arm*'),None)
        if arm: material_spec['M_'+name]['arm']=str(arm.relative_to(ROOT)).replace("\\","/")

class Mesh:
    def __init__(self):
        self.vertices=[]
        self.faces=[]
        self.uv=array('f')
        self.mi=array('i')
        self.slots=[]
    def slot(self,mat):
        if mat not in self.slots:self.slots.append(mat)
        return self.slots.index(mat)
    def pt(self,p):
        self.vertices.append(tuple(p))
        return len(self.vertices)-1
    def face(self,inds,uv,mat):
        self.faces.append(inds)
        self.uv.extend(co for pair in uv for co in pair)
        self.mi.append(mat)
    def finish(self,name):
        data=bpy.data.meshes.new(name)
        data.from_pydata(self.vertices,[],self.faces,shade_flat=False)
        data.materials.clear()
        for role in self.slots:data.materials.append(materials[role])
        data.polygons.foreach_set("material_index",self.mi)
        uv=data.uv_layers.new(name="SurfaceUV")
        uv.uv.foreach_set("vector",self.uv)
        obj=bpy.data.objects.new(name,data)
        scene.collection.objects.link(obj)
        assets[name]=obj
        return obj

def radial(a):
    return V((cos(a),sin(a),0))

def spline(points, radii, steps=4):
    p=list(map(V,points))
    out=[]
    rr=[]
    for i in range(len(p)-1):
        p0,p1,p2,p3=p[max(0,i-1)],p[i],p[i+1],p[min(len(p)-1,i+2)]
        for j in range(steps):
            t=j/steps
            out.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
            rr.append(radii[i]*(1-t)+radii[i+1]*t)
    return out+[p[-1]], rr+[radii[-1]]

def tube(m,points,radii,mat='FigBark',sides=8,steps=3,flatten=1,grooves=.05,phase=0):
    if hasattr(m,'wood') and mat=='FigBark' and max(radii)>.052:
        m.wood.append((points,radii,sides,steps,flatten,grooves,phase))
    p,rs=spline(points,radii,steps)
    slot=m.slot(mat)
    last=None
    midU=TAU*max(rs)*.52 if mat in ('FigBark','PalmBark') else 1
    v=0
    for i,(pos,radius) in enumerate(zip(p,rs)):
        tangent=(p[min(i+1,len(p)-1)]-p[max(0,i-1)]).normalized()
        if i==0:
            axis=tangent.cross(Z if abs(tangent.z)<.92 else V((0,1,0))).normalized()
        else:
            axis=(axis-tangent*tangent.dot(axis)).normalized()
        y=tangent.cross(axis).normalized()
        ring=[]
        prev_v=v
        if i:v+=(pos-p[i-1]).length*.62
        for k in range(sides):
            a=TAU*k/sides
            bump=1+grooves*(.8*sin(5*a+.13*i+phase)+.5*sin(3*a-.08*i+phase*2))
            ring.append(m.pt(pos+(axis*cos(a)*flatten+y*sin(a))*radius*bump))
        if last:
            for k in range(sides):
                kk=(k+1)%sides
                u0=k/sides*midU
                u1=(k+1)/sides*midU
                m.face((last[k],last[kk],ring[kk],ring[k]),((u0,prev_v),(u1,prev_v),(u1,v),(u0,v)),slot)
        else:
            m.face(tuple(reversed(ring)),tuple((.5+.49*cos(-TAU*k/sides),.5+.49*sin(-TAU*k/sides)) for k in range(sides)),slot)
        last=ring
    m.face(tuple(last),tuple((.5+.49*cos(TAU*k/sides),.5+.49*sin(TAU*k/sides)) for k in range(sides)),slot)

def simple_leaf(m,base,heading,length,width,mat,rise=.1,fall=.29,fold=.18,rows=4,roll=0):
    # Ridged, swept, elliptical blade, modeled to a single tapered point.
    slot=m.slot(mat)
    p=V(base)
    d=radial(heading)
    side=radial(heading+pi/2)
    rollvec=side*cos(roll)+Z*sin(roll)
    t0=m.pt(p)
    previous=None
    for i in range(1,rows):
        t=i/rows
        envelope=sin(pi*t)**.84*(1.16-.30*t)
        mid=p+d*length*t+Z*length*(rise*sin(pi*t)-fall*t**2)
        w=width*envelope
        row=[m.pt(mid-rollvec*w-Z*(w*fold)),m.pt(mid),m.pt(mid+rollvec*w-Z*(w*fold))]
        if previous:
            for k in range(2):
                m.face((previous[k],row[k],row[k+1],previous[k+1]),((k*.5,(i-1)/rows),(k*.5,t),((k+1)*.5,t),((k+1)*.5,(i-1)/rows)),slot)
        else:
            for k in range(2):
                m.face((t0,row[k],row[k+1]),((.5,0),(k*.5,t),((k+1)*.5,t)),slot)
        previous=row
    tip=m.pt(p+d*length-Z*length*fall)
    for k in range(2):m.face((previous[k],tip,previous[k+1]),((k*.5,(rows-1)/rows),(.5,1),((k+1)*.5,(rows-1)/rows)),slot)

def twig_spray(m,base,a,scale,dip=0):
    d=radial(a)
    length=rng.uniform(.82,1.57)*scale
    ep=base+d*length+Z*rng.uniform(-.22,.23)*scale
    mid=base+d*length*.52+Z*.18*scale
    tube(m,[base,mid,ep],[.022*scale,.014*scale,.004*scale],sides=4,steps=2,grooves=0)
    tone=rng.choices(['RainLeaf','RainLeafLight','RainLeafShade'],[.47,.27,.26])[0]
    if hasattr(m,'sprays'):m.sprays.append((base.copy(),mid.copy(),ep.copy(),a,scale))
    for i in range(7):
        for sign in (-1,1):
            t=.09+i*.12+(sign+1)*.016
            point=(1-t)*base+t*ep+Z*sin(pi*t)*.17*scale
            lengthleaf=rng.uniform(.28,.51)*scale*(1.2-.48*t)
            angle=a+sign*rng.uniform(.69,1.41)
            simple_leaf(m,point,angle,lengthleaf,lengthleaf*rng.uniform(.16,.25),tone,
                        rng.uniform(.07,.24),rng.uniform(.12,.59)+dip,rows=3,roll=rng.uniform(-.6,.6))
    simple_leaf(m,ep,a,.32*scale,.073*scale,tone,.075,.33)

def primary_trunk(m,height,offset,root_dirs,scale):
    slot=m.slot('FigBark')
    levels=[(-.20,1.72,1),(.15,1.65,.95),(.8,1.53,.76),(2,1.34,.54),(3.6,1.21,.32),(5.2,1.1,.13),(7,.98,.055),(9,.91,.018),(10.7,.76,0),(12,.59,0),(13,.31,0)]
    rings=[]
    for layer,(z,r,weight) in enumerate(levels):
        t=z/13
        center=V((.3*sin(t*5.1),.26*sin(t*4.5),0))*scale+t*offset
        verts=[]
        for k in range(112):
            a=TAU*k/112
            root=0
            for ang,reach in root_dirs:
                dist=abs((a-ang+pi)%TAU-pi)
                root+=reach*exp(-(dist/(.115+.09*weight))**2)
            radius=(r*(1+.10*sin(a*7+t*4)+.06*cos(a*12-t*2)+.034*sin(a*19+t*3))+weight*root)*scale
            verts.append(m.pt(center+radial(a)*radius+Z*z*height/13))
        if rings:
            for k in range(112):
                kk=(k+1)%112
                m.face((rings[-1][k],rings[-1][kk],verts[kk],verts[k]),((k/112*5,levels[layer-1][0]*.58),((k+1)/112*5,levels[layer-1][0]*.58),((k+1)/112*5,z*.58),(k/112*5,z*.58)),slot)
        rings.append(verts)
    return offset+Z*height

def rain_tree(hero=True):
    m=Mesh()
    m.wood=[];m.sprays=[]
    scale=1 if hero else .77
    root_dirs=[(.13,2.2),(.96,1.5),(1.81,3.2),(2.72,2.45),(3.49,2.2),(4.40,3.7),(5.48,1.8)]
    if not hero:
        root_dirs=[(a,r*.52) for a,r in root_dirs]
    offset=(V((1.0,-.82,0)) if hero else V((-.64,1.44,0)))*scale
    primary_trunk(m,13*scale,offset,root_dirs,scale)
    for j,(a,reach) in enumerate(root_dirs):
        s=scale
        heading=radial(a)
        perp=radial(a+pi/2)
        twist=-.48 if j%2 else .54
        ext=(reach+1.35)*s
        stretch=s*(rng.uniform(1.5,3.1)+(1.35 if j in (3,4) and hero else 0))
        curling=(-1 if j%2 else 1)*s
        base=radial(a+twist)*.66*s+Z*s*rng.uniform(5.9,8.4)
        shoulder=radial(a+twist*.45)*1.47*s+Z*2.8*s
        ankle=heading*ext+perp*.23*curling+Z*.22*s
        knuckle=heading*(ext+stretch*.40)-perp*.29*curling+Z*.066*s
        joint=heading*(ext+stretch*.72)-perp*.52*curling-Z*.11*s
        tip=heading*(ext+stretch*.94)+perp*.07*curling-Z*.42*s
        tube(m,[base,shoulder,heading*.66*ext+Z*.71*s,ankle,knuckle,joint,tip],
             [v*s for v in (.42,.55,.60,.35,.19,.10,.024)],sides=16,steps=5,flatten=.90,grooves=.085,phase=j)
        for sign in (-1,1):
            branch_base=ankle.lerp(knuckle,.35+(sign+1)*.17)
            branch_tip=branch_base+radial(a+.65*sign)*s*(1.05+reach*.49)
            branch_tip.z=-.35*s
            bend=branch_base.lerp(branch_tip,.45)+perp*.19*s*sign
            bend.z=.035*s
            tube(m,[branch_base,bend,branch_tip],[.16*s,.091*s,.012*s],sides=9,steps=4,phase=j)
    # Living, spiralling aerial columns alternate in front and behind the main bole.
    for i in range(12 if hero else 5):
        a=TAU*i/(12 if hero else 5)+.23
        azimuth=rng.uniform(-1.0,1.1)
        points=[offset+radial(a+azimuth*.7)*.28*scale+Z*(12.4+rng.uniform(-1.6,1.1))*scale,
                radial(a+azimuth*1.25)*1.43*scale+Z*9.35*scale,
                radial(a+azimuth*.39)*1.78*scale+Z*6.5*scale,
                radial(a-.19)*1.66*scale+Z*3.2*scale,
                radial(a-.33)*1.74*scale+Z*1.15*scale,
                radial(a-.27)*1.33*scale+Z*.12*scale]
        tube(m,points,[scale*v for v in (.29,.38,.28,.34,.33,.12)],steps=5,sides=14,phase=i*.8)
    # Branch stratification: low lateral boughs, scaffold forks, twigs, terminal leaf sprays.
    count=11 if hero else 9
    for j in range(count):
        a=j*2.39996+rng.uniform(-.25,.25)
        layer=j/(count-1)
        origin=offset*(.54+.46*layer)+Z*(7.9+layer*4.5)*scale
        span=scale*((9.1-2.7*layer) if hero else (8.0-3.1*layer))*rng.uniform(.84,1.20)
        h=scale*(8+2.8*layer)*rng.uniform(.83,1.13)
        trunk=origin+radial(a+.16)*span*.36+Z*h*.51
        end=origin+radial(a)*span*.78+Z*h*.85
        tube(m,[origin,trunk,end],[scale*(.72-.20*layer),.45*scale,.20*scale],sides=14,steps=6,phase=j)
        for k in range(5):
            a2=a+(k-2)*.65+rng.uniform(-.28,.28)
            start=trunk.lerp(end,.08+.218*k)
            elbow=start+radial(a2)*rng.uniform(1.65,2.9)*scale+Z*rng.uniform(.70,2.2)*scale
            branchend=elbow+radial(a2+.16)*rng.uniform(1.0,1.85)*scale+Z*rng.uniform(.35,1.4)*scale
            tube(m,[start,elbow,branchend],[.28*scale,.17*scale,.055*scale],sides=9,steps=4)
            for l in range(4):
                a3=a2+(l-1.5)*.91+rng.uniform(-.45,.45)
                t=.17+.235*l
                begin=elbow.lerp(branchend,t)
                subend=begin+radial(a3)*rng.uniform(1.05,2.55)*scale+Z*rng.uniform(-.29,1.1)*scale
                tube(m,[begin,begin.lerp(subend,.48)+Z*.16*scale,subend],[.105*scale,.063*scale,.023*scale],sides=6,steps=2)
                for b in range(5):
                    a4=a3+(b-2)*.96+rng.uniform(-.24,.24)
                    sprayroot=begin.lerp(subend,.26+.17*b)
                    reach=scale*rng.uniform(.53,1.09)
                    fork=sprayroot+radial(a4)*reach+Z*rng.uniform(.19,.70)*scale
                    tube(m,[sprayroot,fork],[.032*scale,.014*scale],sides=4,steps=1,grooves=0)
                    twig_spray(m,fork,a4+.62,scale*rng.uniform(.96,1.49))
                    twig_spray(m,fork,a4-.66,scale*rng.uniform(.95,1.45))
    name="SM_StranglerFig" if hero else "SM_JungleCanopy"
    built=m.finish(name)
    tree_lods[name]=[]
    for lod in (1,2,3):
        reduced=Mesh()
        primary_trunk(reduced,13*scale,offset,root_dirs,scale)
        for pts,rs,sides,steps,flat,grooves,phase in m.wood:
            if max(rs)<scale*(.062,.16,.34)[lod-1]:continue
            tube(reduced,pts,rs,'FigBark',max(4,min(sides,9-lod)),max(1,min(steps,4-lod)),flat,grooves,phase)
        slot=reduced.slot('CanopySpray')
        for i,(start,mid,ep,a,sz) in enumerate(m.sprays):
            if lod==3 and i%3==2:continue
            d=radial(a);side=radial(a+pi/2)
            target=ep+d*(.39*sz)-Z*(.07*sz)
            wide=sz*(.56 if lod<3 else .63)
            rows=[]
            span=(0,.50,1) if lod==1 else (0,1)
            for t in span:
                h=.095*sin(i*.7)
                p=start.lerp(target,t)+Z*(.13*sin(pi*t)*sz)
                extent=wide*(1.09-.27*t)
                rows.append([reduced.pt(p-side*extent+Z*(h-.04)*sz),reduced.pt(p+side*extent+Z*(-h-.04)*sz)])
            for k in range(len(rows)-1):
                reduced.face((rows[k][0],rows[k+1][0],rows[k+1][1],rows[k][1]),((0,span[k]),(0,span[k+1]),(1,span[k+1]),(1,span[k])),slot)
        variant=reduced.finish(name+'_LOD'+str(lod))
        tree_lods[name].append(variant)
        del assets[variant.name]
        variant.hide_render=True
    return built

def wall_roots():
    m=Mesh()
    veins=[
      ([(2.2,-1.02,.14),(.49,-.53,.29),(-.07,-.15,.23),(-.36,.42,-.62),(-.60,.13,-1.41),(-.38,-.55,-2.35),(-.27,-.35,-3.40),(-.42,.29,-4.46),(-1.25,.71,-4.78),(-3.0,.98,-4.90)],[.36,.40,.43,.34,.31,.29,.29,.25,.16,.016]),
      ([(1.54,-.77,.16),(.22,-.66,.18),(-.18,-.76,-.13),(-.34,-.55,-1.0),(-.32,.22,-1.81),(-.42,.67,-2.49),(-.32,.70,-3.32),(-.36,1.38,-4.35),(-1.2,1.83,-4.81),(-2.35,2.88,-4.88)],[.20,.32,.28,.27,.21,.25,.19,.16,.13,.015]),
      ([(1.25,-.67,.24),(.64,-.86,.22),(-.19,-1.29,-.07),(-.26,-1.44,-.85),(-.36,-.75,-1.84),(-.54,-.51,-2.35),(-.43,-1.25,-3.16),(-.29,-1.55,-4.49),(-.79,-1.94,-4.83),(-1.74,-2.58,-4.88)],[.19,.21,.19,.16,.13,.14,.19,.16,.104,.013]),
      ([(1.07,-.60,.26),(.23,-.03,.24),(-.22,.48,-.02),(-.45,.85,-.81),(-.30,1.6,-1.36),(-.27,1.85,-2.40),(-.23,2.1,-3.29),(-.16,2.04,-4.10)],[.14,.16,.15,.11,.12,.09,.07,.012])]
    for j,(pts,radii) in enumerate(veins):
        tube(m,pts,radii,sides=16,steps=5,phase=j)
        for k in range(3,len(pts)-1):
            if k%2==0 and j>1:continue
            p=V(pts[k]);following=V(pts[k+1])
            side=1 if (j+k)%2==1 else -1
            split=p.lerp(following,.28)
            tip=V((-.22,p.y+side*(.48+.16*(k%3)),max(-4.88,p.z-rng.uniform(1.0,2.15))))
            if tip.z< -4.65:tip.x=-.65-rng.random()*.81
            middle=split.lerp(tip,.42)+V((-.05,side*.17,-.06))
            tube(m,[split,middle,tip],[radii[k]*.58,radii[k]*.36,.011],sides=7,steps=4)
    return m.finish('SM_WallRoots')

def palm():
    m=Mesh()
    shaft=[V((0,0,-.10)),V((.02,.02,.32)),V((.17,-.12,2)),V((.42,-.23,4.6)),V((1.05,-.42,7.35)),V((1.39,-.58,8.08))]
    tube(m,shaft,[.30,.22,.17,.157,.143,.13],'PalmBark',18,6,grooves=.028)
    head=shaft[-1]
    tube(m,[shaft[-2],head,head+Z*.36],[.153,.177,.089],'LivingStem',15,4)
    for j in range(16):
        a=j*2.4+rng.uniform(-.13,.13)
        d=radial(a)
        lateral=radial(a+pi/2)
        high=j/15
        root=head+Z*(high*.42-.22)
        span=3.55-.88*high
        sag=1.92-2.48*high
        def rachis(t):
            return root+d*(span*t)+lateral*(sin(pi*t)*.13*sin(j))+Z*(1.34*sin(pi*t)-sag*t**1.6)
        tube(m,[rachis(t) for t in (0,.23,.50,.77,1)],[.071,.052,.032,.017,.002],'LivingStem',7,3)
        for k in range(29):
            for sign in (-1,1):
                t=.07+.0306*k+(.008 if sign>0 else 0)
                blade=(.35+.58*sin(pi*t)**.64)*(1-.36*t)*rng.uniform(.89,1.1)
                angle=a+sign*(1.27-.59*t+rng.uniform(-.08,.08))
                simple_leaf(m,rachis(t),angle,blade,.044*(.36+.86*sin(pi*t)**.5),'PalmBlade',rise=.07+.17*high,fall=.36+.24*(1-high),roll=sign*.24,rows=4)
    return m.finish('SM_ArecaPalm')

def monstera_blade(m,base,a,length,width,sign):
    d=radial(a)
    lateral=radial(a+pi/2)
    slot=m.slot('MonsteraBlade')
    base=V(base)
    # Deep marginal cuts vary independently on each flank. True interior fenestrations
    # are made as rings in the sheet, accounting for the blade's cupped surface.
    def margin(t,side):
        if t<=.001 or t>=.999:return .01
        raw=sin(pi*t)**.57*(1.25-.48*t)
        cuts=[.29,.49,.67,.81]
        for k,c in enumerate(cuts):
            center=c+.013*side+.009*sin(k+sign*3.1)
            if t>=center:width_t=.027
            else:width_t=.047
            raw*=1-(.60+.08*sin(k+sign))*exp(-((t-center)/width_t)**2)
        return raw
    roll=.21*sin(a*2.8)
    droop=.24+.31*(.5+.5*sin(a+.9))
    def sample(t,s):
        edge=margin(t,-1 if s<0 else 1)*width
        cup=abs(s)**1.55
        return (base+d*length*(t-.41*sin(pi*t)*(abs(s)**1.4)*max(1-2.1*t,0)+.18*sin(pi*t)*abs(s)*max(0,t-.18))
                +lateral*(s*edge+.045*length*sin(pi*t)*sign)
                +Z*(s*edge*roll+length*(.20*sin(pi*t)-droop*t*t-.045*cup+.023*cup*sin(17*t+sign))))
    stations=sorted(set([0,.08,.17,.232,.334,.415,.48,.565,.64,.70,.76,.85,.915,1]+[round(x/50,4) for x in range(1,50)]))
    sv=[-1,-.72,-.43,-.19,0,.19,.43,.72,1]
    grid=[[m.pt(sample(t,s)) for s in sv] for t in stations]
    holes=[(.145,.20,1),(.395,.442,1),(.19,.244,-1)]
    # Flatten small internal slots into ellipses spanning consecutive sample rows.
    for i in range(len(stations)-1):
        t0,t1=stations[i:i+2]
        for j in range(len(sv)-1):
            s0,s1=sv[j:j+2]
            if any(lo<=t0 and t1<=hi and (s0,s1)==((.43,.72) if side==1 else (-.72,-.43)) for lo,hi,side in holes):
                continue
            m.face((grid[i][j],grid[i+1][j],grid[i+1][j+1],grid[i][j+1]),
                   (((s0+1)/2,t0),((s0+1)/2,t1),((s1+1)/2,t1),((s1+1)/2,t0)),slot)
    rib=[sample(t,0)+Z*.003 for t in (0,.17,.33,.5,.66,.83,.98)]
    tube(m,rib,[length*v for v in (.013,.011,.009,.007,.005,.003,.0008)],'LivingStem',5,2)

def monstera():
    m=Mesh()
    tube(m,[(-.08,.02,-.055),(.03,-.02,.10),(.08,.01,.24),(.14,.045,.48)],[.042,.037,.038,.018],'LivingStem',9,4)
    for j in range(10):
        a=j*2.399+rng.uniform(-.19,.19)
        layer=j/9
        start=V((.07,.015,.07+.29*layer))
        d=radial(a)
        span=.61-.38*layer
        tip=start+d*span+Z*(.48+.41*layer)
        tube(m,[start,start+d*span*.37+Z*.29,tip],[.021,.016,.010],'LivingStem',7,4)
        monstera_blade(m,tip,a,rng.uniform(.49,.73),rng.uniform(.21,.27),(-1)**j)
    return m.finish('SM_Monstera')

def fern():
    m=Mesh()
    tube(m,[(0,0,-.045),(.004,0,.01),(0,0,.070)],[.041,.074,.038],'LivingStem',9,3)
    for j in range(15):
        a=j*2.4+rng.uniform(-.18,.18)
        d=radial(a)
        level=j/14
        length=1.02-.5*level
        def spine(t):
            return d*(t*length)+Z*(.038+(.41+.19*level)*sin(pi*t*.87)+(.04+.38*level)*t*t)
        tube(m,[spine(t) for t in (0,.25,.5,.75,1)],[.013,.0105,.007,.004,.0008],'LivingStem',5,3)
        for k in range(15):
            for sign in (-1,1):
                t=.11+.056*k+(.014 if sign==1 else 0)
                p=spine(t)
                li=(.115+.16*sin(pi*t))*(1-.62*t)*length
                a2=a+sign*(1.18-.44*t)
                d2=radial(a2)
                end=p+d2*li+Z*li*.13
                tube(m,[p,end],[.0032,.0006],'LivingStem',4,1)
                for q in range(6):
                    for side in (-1,1):
                        h=.08+.147*q
                        tiplen=li*(.34-.15*h)
                        simple_leaf(m,p.lerp(end,h),a2+side*.79,tiplen,tiplen*.21,'FernBlade',.15,.18,rows=2)
                simple_leaf(m,end,a2,.04,.010,'FernBlade',.04,.1,rows=2)
    return m.finish('SM_Fern')

def bract(m,p,a,length):
    d=radial(a)
    side=radial(a+pi/2)
    red=m.slot('BractRed')
    gold=m.slot('BractGold')
    levels=[(0,.17,.018,.015),(.21,.28,.119,.043),(.52,.40,.140,.057),(.74,.56,.086,.046),(1,.85,.003,.003)]
    rings=[]
    for t,h,w,depth in levels:
        c=p+d*(length*t)+Z*((h-.17)*length)
        ring=[]
        for k in range(10):
            ang=k*TAU/10
            ring.append(m.pt(c+side*(sin(ang)*w*length*2.5)+Z*(cos(ang)*depth*length*2.5)))
        if rings:
            prev=rings[-1]
            for k in range(10):
                kk=(k+1)%10
                m.face((prev[k],ring[k],ring[kk],prev[kk]),((k/10,t-.20),(k/10,t),((k+1)/10,t),((k+1)/10,t-.20)),red if t<1 else gold)
        rings.append(ring)

def heliconia():
    m=Mesh()
    for j in range(9):
        a=j*2.4+.24
        d=radial(a)
        s=d*rng.uniform(.015,.105)
        height=rng.uniform(.26,.55)
        end=s+d*.145+Z*height
        tube(m,[s-Z*.025,s.lerp(end,.52),end],[.014,.011,.006],'LivingStem',6,2)
        simple_leaf(m,end,a,rng.uniform(.30,.51),rng.uniform(.061,.10),'PalmBlade',.59,.075,rows=9,roll=rng.uniform(-.45,.45))
    for j in range(3):
        a=.34+j*2.2
        d=radial(a)
        h=[1.03,.81,.61][j]
        root=d*.038
        front=root+d*.15+Z*h
        tube(m,[root-Z*.012,root+Z*.31,front-d*.022-Z*.22,front],[.018,.016,.010,.005],'LivingStem',7,3)
        for k in range(5):
            t=.55+.096*k
            p=root.lerp(front,t)
            length=(.22-.023*k)*h
            bract(m,p,a+pi*(k%2),length)
    return m.finish('SM_Heliconia')

def lily():
    m=Mesh()
    for j,(x,y,rad,ang) in enumerate([(-.12,.08,.203,.4),(.17,-.07,.160,-2.2),(-.04,-.19,.088,-.7),(.13,.14,.096,1.9)]):
        p=V((x,y,.014+.003*j))
        slot=m.slot('LilyLeaf')
        middle=m.pt(p-Z*.008)
        previous=None
        for k in range(45):
            a=ang+.13+(TAU-.27)*k/44
            d=radial(a)
            w=rad*(.97+.036*sin(3*a+.55)+.018*sin(10*a))
            if k<=1 or k>=43:w*=.83 if k in (0,44) else .94
            ring=[]
            for f in (.41,.81,1):
                point=p+d*w*f+Z*(.005*f*f*(1+sin(a*7+j))-.004*(1-f))
                ring.append(m.pt(point))
            if previous:
                prev_a=ang+.13+(TAU-.27)*(k-1)/44
                def uv(a,f):return (.5+.48*cos(a)*f,.5+.48*sin(a)*f)
                m.face((middle,previous[0],ring[0]),((.5,.5),uv(prev_a,.41),uv(a,.41)),slot)
                for idx,(f1,f2) in enumerate([(.41,.81),(.81,1)]):
                    m.face((previous[idx],previous[idx+1],ring[idx+1],ring[idx]),(uv(prev_a,f1),uv(prev_a,f2),uv(a,f2),uv(a,f1)),slot)
            previous=ring
    center=V((.029,.01,.086))
    tube(m,[(.026,.012,-.12),(.03,.013,.04),center],[.010,.009,.012],'LivingStem',7,3)
    for ring,(count,l,w,h,mat) in enumerate([(13,.087,.018,.014,'PetalRose'),(10,.070,.016,.040,'PetalRose'),(8,.047,.011,.056,'PetalCream'),(11,.021,.005,.034,'BractGold')]):
        for k in range(count):
            a=TAU*k/count+ring*.37
            base=center+radial(a)*.006+Z*ring*.002
            simple_leaf(m,base,a,l,w,mat,rise=.11,fall=-h/l,fold=-.40,rows=6)
    return m.finish('SM_WaterLily')

def liana():
    m=Mesh()
    for j in range(9):
        a=j*.67
        y=(j-4)*.28
        length=rng.uniform(1.5,4.9)
        start=V((rng.uniform(-.15,.10),y,0))
        def line(t):
            return start+V((-.12-.18*sin(t*6+a)*t,-.14*sin(t*4.8+a)+.18*sin(t*8+a)*t,-length*t))
        tube(m,[line(t) for t in (0,.17,.33,.50,.67,.83,1)],[.028,.023,.019,.018,.013,.008,.002],sides=6,steps=4)
        for k in range(int(length*7.2)):
            t=(k+.3)/(length*7.3)
            if k%8==0 and j%2: continue
            p=line(t)
            angle=(-pi*.47 if k%2 else pi*.47)-pi*.51+sin(k+j)*.48
            size=rng.uniform(.16,.29)*(1-.52*t)
            simple_leaf(m,p,angle,size,size*.33,'RainLeaf' if j%3 else 'RainLeafLight',rise=.07,fall=.80,fold=.32,rows=5,roll=rng.uniform(-.78,.71))
        for k in range(3 if j in (1,3,4,7) else 1):
            t=rng.uniform(.06,.50)
            p=line(t)
            side=rng.choice((-1,1))
            off=V((rng.uniform(-.16,.18),side*rng.uniform(.21,.53),-.12))
            fork=p+off+V((0,side*.15,-.50-rng.random()*.5))
            tube(m,[p,p+off,fork],[.012,.008,.002],'FigBark',5,4)
            for n in range(8):
                h=n/8
                anchor=(p+off).lerp(fork,h)
                angle=(-.32 if n%2 else -2.83)+j*.28
                size=.17*(1-.49*h)*rng.uniform(.82,1.29)
                simple_leaf(m,anchor,angle,size,size*.31,'RainLeaf' if n%3 else 'RainLeafLight',rise=.05,fall=.42+.35*h,rows=4,roll=side*.42)
    return m.finish('SM_LianaCurtain')

def moss():
    m=Mesh()
    # Flat interlocking cushions with fringe shoots, exposed substrate and irregular borders.
    centers=[(-.34,-.06,.24,.19),(-.16,.0,.30,.22),(.06,.07,.24,.19),(.28,.12,.26,.16),
             (.37,-.03,.16,.14),(-.06,-.17,.17,.12),(.07,-.24,.13,.085),(-.41,.17,.11,.09),(.54,.17,.087,.06)]
    slot=m.slot('MossNap')
    for j,(x,y,sx,sy) in enumerate(centers):
        p=V((x,y,0)); rings=[]
        for i in range(6):
            f=.008+i*.198
            row=[]
            for k in range(24):
                a=TAU*k/24
                edge=1+.12*sin(3*a+j)+.095*cos(5*a-j*.7)+.045*sin(11*a+2*j)
                off=V((sx*cos(a)*edge,sy*sin(a)*edge,0))
                h=.059*(1-f**2)*(.84+.13*sin(a*4+f*2+j))-.008*f
                point=p+off*f+Z*h
                row.append(m.pt(point))
            if rings:
                for k in range(24):
                    kk=(k+1)%24
                    corners=(rings[-1][k],row[k],row[kk],rings[-1][kk])
                    m.face(corners,[((m.vertices[id][0]+1)*2.2,(m.vertices[id][1]+1)*2.2) for id in corners],slot)
            rings.append(row)
        for t in range(100):
            f=rng.random()**.5
            a=rng.uniform(0,TAU)
            edge=1+.12*sin(3*a+j)+.095*cos(5*a-j*.7)+.045*sin(11*a+2*j)
            h=.059*(1-f*f)*(.84+.13*sin(a*4+f*2+j))-.008*f
            sprout=p+V((sx*f*cos(a)*edge,sy*f*sin(a)*edge,h-.004))
            for k in range(3):
                simple_leaf(m,sprout,a+k*2.1,rng.uniform(.01,.019),.0033,'FernBlade' if t%5 else 'RainLeafLight',.42,-.73,rows=2)
    return m.finish('SM_MossCushion')

def pioneer_sapling():
    """A young palmate-leaved Cecropia for regenerating forest gaps."""
    m=Mesh()
    trunktop=V((.12,-.05,2.47))
    branchbase=V((.07,.05,1.39))
    tube(m,[(-.013,.02,-.048),(.012,.01,.41),branchbase,(.06,.004,1.95),trunktop],[.043,.039,.034,.029,.015],'FigBark',11,5)
    terminals=[trunktop]
    for a,length,rise,z in ((.6,.54,.61,1.77),(2.96,.63,.53,1.51),(4.68,.39,.53,1.98)):
        d=radial(a);base=V((.075,.015,z))
        end=base+d*length+Z*rise
        tube(m,[base,base+d*.22+Z*.16,end],[.025,.021,.013],'FigBark',8,3)
        terminals.append(end)
    for g,end in enumerate(terminals):
        for i in range(5):
            a=i*2.4+g*1.66
            d=radial(a)
            height=(i/4-.45)*.28
            anchor=end-Z*(.17-i*.04)
            petiole=anchor+d*(.26+.1*(1-i/4))+Z*(.12+height)
            tube(m,[anchor,anchor.lerp(petiole,.57)+Z*.036,petiole],[.0085,.0066,.0043],'LivingStem',6,3)
            material=m.slot('RainLeafLight' if (i+g)%4==0 else 'RainLeaf')
            center=m.pt(petiole)
            inner=[];outer=[]
            for k in range(84):
                theta=TAU*k/84
                angle=theta+a
                ray=radial(angle)
                petal=(.5+.5*cos(theta*7))**.82
                length=(.119+.218*petal)*(1+.235*cos(theta))*(1-.085*i)
                h=length*(.10+.13*cos(theta+g))
                bent=d*.044*(1-cos(theta))
                inner.append(m.pt(petiole+ray*length*.44-Z*.008))
                outer.append(m.pt(petiole+ray*length+bent-Z*h))
            def uv(idx):
                p=V(m.vertices[idx])-petiole
                return (.5+p.dot(radial(a+pi/2))*.96,.49+p.dot(d)*.99)
            for k in range(84):
                kk=(k+1)%84
                m.face((center,inner[k],inner[kk]),((.5,.49),uv(inner[k]),uv(inner[kk])),material)
                inds=(inner[k],outer[k],outer[kk],inner[kk])
                m.face(inds,[uv(idx) for idx in inds],material)
            for k in range(7):
                tip=V(m.vertices[outer[k*12]])
                tube(m,[petiole+Z*.002,petiole.lerp(tip,.49)+Z*.009,tip],[.0029,.0017,.0004],'LivingStem',4,2)
    return m.finish('SM_CecropiaSapling')

def scans():
    for source,name,role in [('rock_face_01','SM_SandstoneCliff','SandstoneFace'),
                             ('namaqualand_cliff_01','SM_FracturedCliff','FracturedRock'),
                             ('rock_moss_set_01','SM_MossBoulder','MossRock')]:
        bpy.ops.import_scene.gltf(filepath=str(SOURCE/source/(source+'.gltf')))
        objs=sorted([o for o in bpy.context.selected_objects if o.type=='MESH'],key=lambda item:item.name)
        for i,obj in enumerate(objs):
            # Origins belong at the natural soil line. Scans retain buried geometry.
            obj.location=(0,0,0)
            bpy.context.view_layer.update()
            bounds=[obj.matrix_world@V(p) for p in obj.bound_box]
            low,high=[V([f(p[ax] for p in bounds) for ax in range(3)]) for f in (min,max)]
            shift=V(((low.x+high.x)/2,(low.y+high.y)/2,low.z+(high.z-low.z)*(.36 if 'Boulder' in name else .045)))
            mat=obj.matrix_world
            for v in obj.data.vertices:v.co=mat@v.co-shift
            obj.rotation_euler=(0,0,0)
            obj.scale=(1,1,1)
            obj.name=name if i==0 else name+f'{i+1:02d}'
            obj.data.name=obj.name
            obj.data.materials.clear()
            obj.data.materials.append(materials[role])
            assets[obj.name]=obj

def aim(obj,target):
    obj.rotation_euler=(V(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def measure(obj):
    pts=[V(pt) for pt in obj.bound_box]
    low=[min(pt[i] for pt in pts) for i in range(3)]
    high=[max(pt[i] for pt in pts) for i in range(3)]
    return low,high

def render_inspection():
    scene.render.engine='CYCLES'
    scene.cycles.samples=5
    scene.cycles.use_denoising=True
    scene.render.resolution_x=640
    scene.render.resolution_y=640
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.world=bpy.data.worlds.new('Neutral lighting')
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.29,.34,.38,1)
    bg.inputs['Strength'].default_value=.75
    scene.view_settings.view_transform='AgX'
    camdata=bpy.data.cameras.new("InspectionCamera")
    cam=bpy.data.objects.new("InspectionCamera",camdata)
    scene.collection.objects.link(cam)
    camdata.type='ORTHO'
    scene.camera=cam
    lamp=bpy.data.lights.new('Canopy sunlight','SUN')
    lamp.energy=3.6
    lamp.angle=.08
    sun=bpy.data.objects.new('Canopy sunlight',lamp)
    scene.collection.objects.link(sun)
    sun.rotation_euler=V((.44,-.55,-.78)).to_track_quat('-Z','Y').to_euler()
    for obj in assets.values():
        obj.hide_render=True
    for name,obj in assets.items():
        chosen=next((arg.split("=",1)[1].split(",") for arg in ARGS if arg.startswith("review=")),None)
        if chosen and name not in chosen:continue
        if name.startswith('SM_MossBoulder') and name!='SM_MossBoulder':continue
        obj.hide_render=False
        lo,hi=map(V,measure(obj))
        center=(lo+hi)/2
        size=hi-lo
        direction=V((-2.3,-3.8,1.45)).normalized()
        if 'WallRoots' in name:direction=V((-3,-1.5,1.3)).normalized()
        if 'Cliff' in name:direction=V((-.8,-3,1.30)).normalized()
        cam.location=center+direction*max(size)*3
        aim(cam,center)
        camdata.ortho_scale=max(size)*1.25
        scene.render.filepath=str(OUT/(name+'.png'))
        bpy.ops.render.render(write_still=True)
        if name=='SM_StranglerFig':
            camera_target=V((-.6,0,3.8))
            cam.location=camera_target+V((-14,-13,3.6))
            aim(cam,camera_target)
            camdata.ortho_scale=14
            scene.render.filepath=str(OUT/'FigButtresses.png')
            bpy.ops.render.render(write_still=True)
        obj.hide_render=True
    for obj in assets.values():
        obj.hide_render=False
    for obj in (cam,sun):
        bpy.data.objects.remove(obj,do_unlink=True)

def trunk_collision(obj):
    """Simple convex segments follow solid wood while leaving buttress voids and canopy open."""
    if obj.name not in ("SM_StranglerFig","SM_JungleCanopy","SM_ArecaPalm"):
        return []
    branches=[]
    if obj.name=="SM_ArecaPalm":
        axis=[((0,0,0),.21),((.17,-.12,2),.16),((.42,-.23,4.6),.15),((1.05,-.42,7.35),.14),((1.39,-.58,8.08),.12)]
        branches.extend((a,b,r1,r2) for (a,r1),(b,r2) in zip(axis,axis[1:]))
    else:
        factor=1 if obj.name=="SM_StranglerFig" else .77
        center=V((1,-.82,0)) if factor==1 else V((-.64,1.44,0))
        points=[(center*t+Z*z,r) for t,z,r in [(0,-.1,1.19),(.28,3.6,1.13),(.55,7,.90),(.85,10.7,.77),(1,12.8,.53)]]
        branches.extend((a*factor,b*factor,r1*factor,r2*factor) for (a,r1),(b,r2) in zip(points,points[1:]))
        for a,l in ((.13,2.2),(.96,1.5),(1.81,3.2),(2.72,2.45),(3.49,2.2),(4.4,3.7),(5.48,1.8)):
            end=l*(1 if factor==1 else .52)+1.1
            points=[(radial(a)*1.3+Z*2.5,.40),(radial(a)*(end*.70)+Z*.8,.39),(radial(a)*end+Z*.24,.27)]
            branches.extend((p*factor,q*factor,r1*factor,r2*factor) for (p,r1),(q,r2) in zip(points,points[1:]))
    cols=[]
    for i,(p,q,r1,r2) in enumerate(branches):
        p,q=V(p),V(q)
        tangent=(q-p).normalized()
        side=tangent.cross(Z if abs(tangent.z)<.94 else V((0,1,0))).normalized()
        second=tangent.cross(side).normalized()
        rings=[[point+(side*cos(TAU*k/8)+second*sin(TAU*k/8))*r for k in range(8)] for point,r in ((p,r1),(q,r2))]
        faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(j,(j+1)%8,8+(j+1)%8,8+j) for j in range(8)]
        cname=f"UCX_{obj.name}_{i:02d}"
        data=bpy.data.meshes.new(cname)
        data.from_pydata(rings[0]+rings[1],[],faces)
        cobj=bpy.data.objects.new(cname,data)
        scene.collection.objects.link(cobj)
        cobj.select_set(True)
        cols.append(cobj)
    return cols

def export_assets():
    registry={}
    bpy.ops.object.select_all(action='DESELECT')
    for name,obj in assets.items():
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        colliders=trunk_collision(obj)
        bpy.ops.export_scene.fbx(filepath=str(EXPORT/(name+'.fbx')),use_selection=True,object_types={'MESH'},
            axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
            mesh_smooth_type='FACE',path_mode='RELATIVE',use_mesh_modifiers=True,add_leaf_bones=False,
            colors_type='SRGB',use_custom_props=False,bake_anim=False)
        obj.select_set(False)
        for cobj in colliders:
            bpy.data.objects.remove(cobj,do_unlink=True)
        lo,hi=measure(obj)
        registry[name]={"fbx":'FBX/'+name+'.fbx',"bounds_m":[lo,hi],"triangles":sum(len(poly.vertices)-2 for poly in obj.data.polygons),
                        "material_slots":[slot.name for slot in obj.data.materials]}
    for name,variants in tree_lods.items():
        directory=EXPORT/"LODs";directory.mkdir(exist_ok=True)
        registry[name]["lods"]=[]
        for mesh in variants:
            mesh.select_set(True)
            bpy.context.view_layer.objects.active=mesh
            file=directory/(mesh.name+'.fbx')
            bpy.ops.export_scene.fbx(filepath=str(file),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',
                apply_scale_options='FBX_SCALE_UNITS',mesh_smooth_type='FACE',path_mode='RELATIVE',bake_anim=False)
            mesh.select_set(False)
            registry[name]["lods"].append({"fbx":"FBX/LODs/"+file.name,"triangles":sum(len(face.vertices)-2 for face in mesh.data.polygons)})
            mesh.hide_viewport=True
    (ROOT/"nature_assets.json").write_text(json.dumps({"units":"meters","assets":registry,"materials":material_spec,
        "provenance":{"original":"Fig, buttress and aerial roots, tropical canopy, palm, undergrowth, lily, lianas, botanical albedos and normals are original.",
        "poly_haven":{"license":"https://polyhaven.com/license","assets":[f'https://polyhaven.com/a/{a}' for a in ('rock_face_01','namaqualand_cliff_01','rock_moss_set_01','palm_bark','japanese_hackberry_bark')]}}},indent=2))
    # Store the editable mesh collection in an organized nursery layout.
    x=0
    for obj in assets.values():
        lo,hi=measure(obj)
        width=hi[0]-lo[0]
        obj.location.x=x-lo[0]
        x+=width+1.2
    for image in bpy.data.images:
        if image.filepath and image.source=="FILE":
            full=bpy.path.abspath(image.filepath)
            image.filepath=bpy.path.relpath(full,start=str(ROOT))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Astra_Nature.blend'),compress=True,relative_remap=False)

make_surfaces()
rain_tree(True)
wall_roots()
monstera()
scans()
if 'representative' not in ARGS:
    rain_tree(False)
    palm()
    fern()
    heliconia()
    lily()
    liana()
    moss()
    pioneer_sapling()
bpy.context.view_layer.update()
if 'noreview' not in ARGS:render_inspection()
if 'representative' not in ARGS:export_assets()
