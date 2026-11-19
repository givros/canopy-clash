"""The low fig limb growing from the entry headland over the ruined gate."""
from pathlib import Path
from mathutils import Vector, noise
from mathutils.geometry import interpolate_bezier
import bpy, math, random, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import valley
root=Path(__file__).resolve().parents[1]/"Terrain"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
origin=Vector((-56.2,5.8,4.8));rng=random.Random(19220)
vertices=[];faces=[];mats=[];uvs=[]
def vertex(p):
    p=p.copy()
    # The secondary crown turns upward over the gate; keep a window onto the ridge.
    crown=valley.sm((p.x+53.5)/9)*valley.sm((p.z-10.5)/4)
    p.z+=2.65*crown
    q=p-origin;vertices.append((q.x,-q.y,q.z));return len(vertices)-1
def face(ids,uv,slot):
    faces.append(ids);uvs.append(uv);mats.append(slot)
def branch(values,r0,r1,strands=13):
    controls=[Vector(i) for i in values];path=[]
    for j,(a,b) in enumerate(zip(controls,controls[1:])):
        d0=(b-controls[max(0,j-1)])*.18;d1=(controls[min(len(controls)-1,j+2)]-a)*.18
        steps=max(3,int((b-a).length/.35)+1)
        segment=interpolate_bezier(a,a+d0,b-d1,b,steps)
        path.extend(segment[1:] if j else segment)
    lengths=[0.]
    for a,b in zip(path,path[1:]):lengths.append(lengths[-1]+(b-a).length)
    rings=[];side=Vector((0,1,0));phase=rng.random()*6.
    for j,p in enumerate(path):
        t=lengths[j]/lengths[-1]
        direction=(path[min(j+1,len(path)-1)]-path[max(0,j-1)]).normalized()
        side=(side-direction*side.dot(direction)).normalized();up=side.cross(direction).normalized()
        radius=(r0*(1-t)+r1*t)*(1+.07*math.sin(t*11+phase))
        row=[]
        for k in range(strands):
            a=2*math.pi*k/strands
            rr=radius*(1+.065*math.cos(5*a+t*3)+.045*noise.noise(p*.54+side*math.cos(a)))
            row.append(vertex(p+rr*(side*math.cos(a)*1.07+up*math.sin(a))))
        rings.append(row)
    for j,(r,s) in enumerate(zip(rings,rings[1:])):
        for k in range(strands):
            o=(k+1)%strands
            turns=max(1,round(2*math.pi*r0/1.65))
            face((r[k],s[k],s[o],r[o]),((turns*k/strands,lengths[j]/2.4),(turns*k/strands,lengths[j+1]/2.4),(turns*(k+1)/strands,lengths[j+1]/2.4),(turns*(k+1)/strands,lengths[j]/2.4)),0)
    face(tuple(rings[0]),[(0,0)]*strands,0);face(tuple(reversed(rings[-1])),[(0,0)]*strands,0)
    return path
def blade(p,d,length,w,slot):
    d=d.normalized();s=Vector((-d.y,d.x,0)).normalized();up=d.cross(s).normalized()
    rows=[];segs=9;roll=rng.uniform(-.43,.43);s=(s+up*roll).normalized()
    for k in range(segs+1):
        t=k/segs;profile=math.sin(t*math.pi)**.77*(.80+.35*(1-t))
        c=p+d*(length*t)+Vector((0,0,length*(.18*math.sin(t*3.14)-.53*t*t)))
        rows.append([vertex(c+s*(side*profile*w)+up*(abs(side)*profile*w*.19)) for side in (-1,0,1)])
    for i in range(segs):
        for j in (0,1):
            face((rows[i][j],rows[i+1][j],rows[i+1][j+1],rows[i][j+1]),((j/2,i/segs),(j/2,(i+1)/segs),((j+1)/2,(i+1)/segs),((j+1)/2,i/segs)),slot)
def twigs(path,pt0=.18):
    for j in range(2,len(path)-1,2):
        progress=j/(len(path)-1)
        if progress<pt0:continue
        a=path[j];t=(path[j+1]-path[j-1]).normalized()
        s=Vector((-t.y,t.x,0)).normalized()*(-1 if (j//2)%2 else 1)
        end=a+t*.23+s*rng.uniform(.5,1.16)+Vector((0,0,rng.uniform(-.5,.28)))
        twig=branch([a,a.lerp(end,.58)+Vector((0,0,.09)),end],.042*(1-.55*progress),.012,7)
        for i in range(1,len(twig)):
            d=(twig[i]-twig[i-1]).normalized()
            for sign in [-1,1]:
                d1=(d*.52+Vector((-d.y,d.x,0))*sign*.82+Vector((0,0,rng.uniform(-.37,.39)))).normalized()
                blade(twig[i],d1,rng.uniform(.34,.72),rng.uniform(.088,.157),rng.choice([1,1,1,2,3]))
    return path
p=branch([(-56.25,5.8,7.1),(-55.52,6.18,10.25),(-53.23,6.50,12.35),(-50.2,7.77,14.8),(-47.25,9.85,16.04),(-44.6,11.68,16.75),(-41.72,14.0,16.07)],1.04,.11,21)
for j in [8,13,17,20,23,26,len(p)-2]:
    if j>=len(p):continue
    a=p[j];side=-1 if j%2 else 1;extension=rng.uniform(2.0,4.7)
    b=a+Vector((1.0,side*extension*.59,1.00));c=a+Vector((2.9,side*extension,.23+rng.uniform(-1.3,1.0)))
    twigs(branch([a,b,c],rng.uniform(.15,.31),.031,12))
    for ii in [-1,1]:
        d=b+Vector((rng.uniform(.5,2),ii*rng.uniform(1.2,2.6),rng.uniform(-1.1,.7)))
        twigs(branch([b,b.lerp(d,.47)+Vector((0,0,.29)),d],.087,.019,9),0)
twigs(p,.72)
# A strangling fig grows secondary columns wherever its aerial roots reach soil.
# These fluted columns join the existing fork, leaving the stepped approach clear.
foot=Vector((-53.4,12.12,valley.terrain(-53.4,12.12)-.18))
knee=Vector((-53.02,11.87,6.65))
crook=Vector((-50.35,11.17,10.86))
fork=Vector((-47.25,9.85,16.04))
top=Vector((-44.85,11.48,16.66))
branch([foot,knee,crook,(-49.22,11.21,13.18),fork,top],.85,.13,35)
for i in range(11):
    ang=i*2*math.pi/11
    n=Vector((math.cos(ang),math.sin(ang),0))
    tip=foot+n*rng.uniform(2.2,3.7)
    tip.z=valley.terrain(tip.x,tip.y)-.10
    toe=foot.lerp(tip,.69);toe.z=valley.terrain(toe.x,toe.y)+.08
    b=foot+n*rng.uniform(.95,1.28);b.z=valley.terrain(b.x,b.y)+.18
    line=[tip,toe,b,knee+n*.72,crook+Vector((n.y,-n.x,0))*.58,fork+n*.21,top]
    branch(line,.115,.075,14)
    branch([crook+Vector((n.y,-n.x,0))*.27,knee+n*.63,b,toe,tip],.28,.033,17)
    if i%2==0:
        turn=Vector((-n.y,n.x,0))
        branch([b,knee+n*.71,knee.lerp(crook,.48)+turn*.64,crook-n*.51,
                crook.lerp(fork,.48)-turn*.39,fork+n*.26,top],.18,.055,16)
        base=knee.lerp(crook,rng.uniform(.12,.93))+n*.62
        s=base+n*.47+Vector((.1,.1,.35))
        twigs(branch([base,s,s+turn*.89+Vector((0,0,-.24))],.053,.014,9),0)
for t,n in [(.32,-1),(.44,1),(.64,1),(.83,-1)]:
    anchor=crook.lerp(fork,t)
    tip=anchor+Vector((1.40,n*2.15,1.15))
    twigs(branch([anchor,anchor.lerp(tip,.58)+Vector((0,0,.26)),tip],.12,.022,13),.05)
mesh=bpy.data.meshes.new("SM_GateFigLimb");mesh.from_pydata(vertices,[],faces);mesh.update()
for name in ["M_FigBark","M_RainLeaf","M_RainLeafShade","M_RainLeafLight"]:mesh.materials.append(bpy.data.materials.new(name))
uv=mesh.uv_layers.new(name="Bark and blade")
for poly,points,slot in zip(mesh.polygons,uvs,mats):
    poly.material_index=slot;poly.use_smooth=True
    for i,pt in zip(poly.loop_indices,points):uv.data[i].uv=pt
import bmesh
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj)
obj.select_set(True);bpy.context.view_layer.objects.active=obj
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/"GateFigLimb.blend"))
bpy.ops.export_scene.fbx(filepath=str(root/(mesh.name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False)
