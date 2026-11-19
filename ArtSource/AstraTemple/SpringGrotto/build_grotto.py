"""A water-cut joint and spring alcove built on the surveyed West Canopy trail."""
from pathlib import Path
import bisect
import json
import math
import random
import sys

import bpy
import bmesh
from mathutils import Vector as V
from mathutils.noise import noise

DEST=Path(__file__).resolve().parent
sys.path.insert(0,str(DEST.parent/"Tools"))
import valley
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system="METRIC"
root=V((107,-10,valley.terrain(107,-10)))
rng=random.Random(19238)
Z=V((0,0,1))
TAU=math.tau
def smooth(x):return valley.sm(x)
def fract(a,b,c):return noise(V((a,b,c)))
def interp(a,b,t):return a+(b-a)*t
guide=[V((105.9,-8.5)),V((107,-10)),V((109,-14)),V((114,-17.59)),V((120,-22)),V((121.7,-27.15)),V((122.12,-28.34))]
samples=[]
for i in range(1,len(guide)-2):
    p0,p1,p2,p3=guide[i-1:i+3]
    for j in range(30):
        t=j/30
        samples.append(.5*(2*p1+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
samples.append(guide[-2])
arc=[0]
for a,b in zip(samples,samples[1:]):arc.append(arc[-1]+(b-a).length)
L=arc[-1]
def frame(distance):
    k=max(0,min(len(arc)-2,bisect.bisect_right(arc,distance)-1))
    a,b=samples[k:k+2]
    t=(distance-arc[k])/(arc[k+1]-arc[k]);p=a.lerp(b,t);d=(b-a).normalized()
    return p,d,V((-d.y,d.x))
def waist(s):
    return math.exp(-((s-.47)/.14)**4)
def widths(s):
    return 2.28+.32*math.sin(6.7*s)+2.44*waist(s),2.35+.33*math.cos(9*s)
def height(s):
    return 3.52+.46*math.cos(9.8*s-.7)+.58*waist(s)+.27*math.sin(21*s)
def point(s,horiz,z):
    c,d,n=frame(s*L);p=c+n*horiz
    return V((p.x,p.y,z))
def geology_uv(p,direction):
    a=max(range(3),key=lambda j:abs(direction[j]))
    return ((p.y if a==0 else p.x)/2.15,(p.y if a==2 else p.z)/2.15)
materials={}
def mat(name,tex,normal,rough,wet=1,tint=(1,1,1)):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    for file,role in ((tex,"color"),(normal,"normal"),(rough,"roughness")):
        node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(file),check_existing=True)
        node.image.colorspace_settings.name='sRGB' if role=='color' else 'Non-Color'
        if role!='normal':
            geo=m.node_tree.nodes.new('ShaderNodeNewGeometry')
            mapping=m.node_tree.nodes.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs['Scale'].default_value=1/2.15
            m.node_tree.links.new(geo.outputs['Position'],mapping.inputs[0]);m.node_tree.links.new(mapping.outputs['Vector'],node.inputs['Vector'])
            node.projection='BOX';node.projection_blend=.39
        source=node.outputs['Color']
        if role=='normal':
            n=m.node_tree.nodes.new('ShaderNodeNormalMap');m.node_tree.links.new(source,n.inputs['Color']);source=n.outputs['Normal']
        elif role=='roughness':
            n=m.node_tree.nodes.new('ShaderNodeMath');n.operation='MULTIPLY';n.inputs[1].default_value=wet
            m.node_tree.links.new(source,n.inputs[0]);source=n.outputs[0]
        else:
            n=m.node_tree.nodes.new('ShaderNodeMixRGB');n.blend_type='MULTIPLY';n.inputs[0].default_value=1;n.inputs[2].default_value=(*tint,1)
            m.node_tree.links.new(source,n.inputs[1]);source=n.outputs[0]
        m.node_tree.links.new(source,bs.inputs[{'normal':'Normal','roughness':'Roughness','color':'Base Color'}[role]])
    materials[name]=m
for name,src,damp,color in [
    ('M_GrottoJoint','JointedRock',.78,(.94,.91,.83)),
    ('M_GrottoWet','JointedRock',.46,(.71,.79,.72)),
    ('M_GrottoStrata','SedimentaryBand',.88,(.82,.81,.72))]:
    mat(name,*(DEST/'Textures'/f'T_{src}_{ch}.jpg' for ch in ('Color','NormalGL','Roughness')),damp,color)
ter=DEST.parent/'Terrain'
mat('M_GrottoMoss',*(next(ter.glob('T_mossy_rock_'+key+'.*')) for key in ('Color','Normal','Rough')), .83,(.58,.76,.51))
mat('M_GrottoBed',*(next(ter.glob('T_brown_mud_rocks_01_'+key+'.*')) for key in ('Color','Normal','Rough')), .71,(.72,.72,.62))
roles=list(materials)

class Geometry:
    def __init__(self):
        self.points=[];self.faces=[];self.roles=[];self.smooth=[]
    def vertex(self,p):
        self.points.append(V(p));return len(self.points)-1
    def face(self,indices,role,smooth_faces=True):
        self.faces.append(indices);self.roles.append(roles.index(role));self.smooth.append(smooth_faces)
    def solid(self,low,upper,role):
        n=len(low);base=[self.vertex(p) for p in low];top=[self.vertex(p) for p in upper]
        self.face(base[::-1],role,False);self.face(top,role,False)
        for j in range(n):
            k=(j+1)%n;self.face((base[j],base[k],top[k],top[j]),role,False)
    def finish(self):
        mesh=bpy.data.meshes.new("West Spring Grotto")
        # Blender mirrors Y; the FBX importer mirrors it back into Unreal.
        mesh.from_pydata([(p.x-root.x,root.y-p.y,p.z-root.z) for p in self.points],[],self.faces)
        for s in materials.values():mesh.materials.append(s)
        mesh.polygons.foreach_set("material_index",self.roles);mesh.polygons.foreach_set("use_smooth",self.smooth)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        uv=mesh.uv_layers.new(name="World-scaled mineral grain")
        for poly in mesh.polygons:
            n=poly.normal
            for li in poly.loop_indices:
                uv.data[li].uv=geology_uv(self.points[mesh.loops[li].vertex_index],n)
        obj=bpy.data.objects.new('SM_WestSpringGrotto',mesh);scene.collection.objects.link(obj);return obj

g=Geometry();anchors=[];N=73;M=36
# Wall-to-wall horseshoe. Broken strata lie above a broad joint, with a low rock
# bench on the uphill side. The backing is a continuous ridge with flared toes.
vertical=[-.29,.16,.37,.58,.70,.82,.89,.95,.98,.93,.925,.96,.92,.83,.72,.56,.37,.17,-.30]
horizontal=[-1,-1.035,-1.03,-.995,-.94,-.84,-.68,-.47,-.23,-.045,.14,.34,.51,.68,.84,.92,.97,1.02,1.0]
def pick(a,t):
    v=t*(len(a)-1);k=min(len(a)-2,int(v));return interp(a[k],a[k+1],v-k)
def ring(s,u,outer=False):
    boundary=math.exp(-(s/.090)**2)-math.exp(-((1-s)/.09)**2)
    drift=boundary*(.58*math.cos(u*9+.45)+.26*math.sin(16*u+.31)-.22*math.sin(math.pi*u))*(1.27 if outer else 1)
    d=s*L+drift
    c,tan,n=frame(d);st=d/L
    floor=valley.terrain(*c);left,right=widths(st);h=height(st)
    xx=pick(horizontal,u);zz=pick(vertical,u)
    joint=fract(st*13,u*4,4.7);chip=fract(st*37,u*21,1.5)
    if not outer:
        w=xx*(left if xx<0 else right)
        w+=abs(xx)**1.5*(.23*joint+.059*chip+.075*math.sin(zz*30+st*5.3))
        z=floor+h*zz+.24*joint+.085*chip+.12*math.sin(11*st+7*u)
        if u<.055 or u>.945:
            position=c+n*w;local=valley.terrain(*position);z=min(z,local-.48) if u in (0,1) else z
    else:
        w=xx*((left+3.9+1.48*math.sin(st*4.4)) if xx<0 else (right+2.65+.65*math.sin(st*5.3)))
        p=c+n*w;soil=valley.terrain(*p)
        bedding=.46*math.sin(st*31+u*6+2.5*fract(st*5,u*4,4.1))
        rockfold=.63*(abs(math.sin(st*13.3+u*4.8+.59*math.cos(6*u)))**.44-.4)
        top=floor+h+1.36+.73*fract(st*6,u*5,1.47)+.46*fract(st*17,u*12,13.1)+bedding+rockfold
        ridge=top+.36*math.sin(st*13+.41)-1.30*(abs(xx)**1.4)
        # Feather through the *actual* side slope. Sections of the natural
        # bank climb more than ten metres across the footprint near the spring.
        skirt=smooth((abs(xx)-.59)/.425)
        z=interp(ridge,soil-.51,skirt)
        if abs(xx)>.56:z+=.23*joint
    p=c+n*w
    return V((p.x,p.y,z))
def skylight(s,u):
    return (((s-.325)/.057)**2+((u-.40)/.129)**2<1 or
            ((s-.745)/.042)**2+((u-.65)/.096)**2<1)
vertices=[[[g.vertex(ring(i/N,j/M,outer)) for j in range(M+1)] for i in range(N+1)] for outer in (False,True)]
present={(i,j) for i in range(N) for j in range(M) if not skylight((i+.5)/N,(j+.5)/M)}
rimids={}
for i,j in sorted(present):
    s=(i+.5)/N;u=(j+.5)/M
    band=fract(s*6,u*7,4)+.20*math.sin(17*s+15*u)
    inner='M_GrottoJoint'
    outer='M_GrottoJoint'
    grid=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)]
    for o,role in enumerate((inner,outer)):
        q=[vertices[o][a][b] for a,b in grid]
        if (i+j)%2:q=q[1:]+q[:1]
        g.face((q[0],q[1],q[2]),role);g.face((q[0],q[2],q[3]),role)
    for k,near in enumerate(((i,j-1),(i+1,j),(i,j+1),(i-1,j))):
        if near in present:continue
        a,b=grid[k],grid[(k+1)%4]
        p0,p1=vertices[0][a[0]][a[1]],vertices[0][b[0]][b[1]]
        p2,p3=vertices[1][b[0]][b[1]],vertices[1][a[0]][a[1]]
        if near[0] in (-1,N):
            # Erode the portal ends into rounded noses and weathered hollows.
            sign=-1 if near[0]==-1 else 1
            ti=frame(s*L)[1];forward=V((ti.x,ti.y,0))*sign
            prev1,prev2=p0,p1
            for m in range(1,6):
                t=m/5;arc_t=math.sin(math.pi*t)
                if m==5:q1,q2=p3,p2
                else:
                    new=[]
                    for idx,start,stop in ((a,p0,p3),(b,p1,p2)):
                        stamp=(idx,m)
                        if stamp in rimids:
                            new.append(rimids[stamp]);continue
                        coords=g.points[start].lerp(g.points[stop],t);q=idx[1]/M
                        coords+=forward*arc_t*(.51+.31*math.cos(12*q+2*t)+.18*fract(q*11,t*3,5))
                        coords.z+=arc_t*.16*math.sin(q*16+t*5)
                        rimids[stamp]=g.vertex(coords)
                        new.append(rimids[stamp])
                    q1,q2=new
                g.face([prev1,prev2,q2,q1],'M_GrottoJoint')
                prev1,prev2=q1,q2
        else:g.face([p0,p1,p2,p3],'M_GrottoJoint')
# A bedrock bench fills the side recess where the modern walking route crosses
# the ancient fissure. The bottom and outer edges penetrate underlying terrain.
rows=[]
for i in range(22):
    s=.32+i/21*.30;c,d,n=frame(s*L)
    side=1.10+3.60*math.sin(i/21*math.pi)**.7
    surf=[]
    for f in (0,.23,.48,.74,1):
        w=-interp(.54,side,f)
        p=c+n*w;ground=valley.terrain(*p)
        z=valley.terrain(*c)-.11+.14*f+.04*fract(s*11,f*4,2)
        if f==0:z=min(ground-.13,z)
        if i in (0,21):z=min(ground-.14,z)
        surf.append((g.vertex((p.x,p.y,z)),g.vertex((p.x,p.y,min(ground-.44,z-.44)))))
    rows.append(surf)
for i in range(len(rows)-1):
    for j in range(4):
        for layer in (0,1):
            q=[rows[ix][jx][layer] for ix,jx in [(i,j),(i+1,j),(i+1,j+1),(i,j+1)]]
            g.face(q,'M_GrottoWet')
        for a,b in ([(i, j),(i+1,j)],[(i,j+1),(i+1,j+1)]) if j in (0,3) else []:
            if (j==0 and a[1]!=0) or (j==3 and a[1]!=4):continue
            g.face([rows[a[0]][a[1]][0],rows[b[0]][b[1]][0],rows[b[0]][b[1]][1],rows[a[0]][a[1]][1]],'M_GrottoJoint')
for i in (0,len(rows)-1):
    for j in range(4):g.face([rows[i][j][0],rows[i][j+1][0],rows[i][j+1][1],rows[i][j][1]],'M_GrottoJoint')

# A thin mineral bed rests directly on the trail's surveyed center. It extends
# to the interior walls with solid support where erosion drops away at the sides.
floorrows=[]
for i in range(56):
    s=i/55;c,t,n=frame(s*L);floor=valley.terrain(*c)
    edgefade=min(smooth(s/.07),smooth((1-s)/.09))
    row=[]
    for j in range(13):
        side=-1+2*j/12
        w=side*((widths(s)[0] if side<0 else widths(s)[1])+.31);p=c+n*w
        soil=valley.terrain(*p)
        tread=floor+.025+.034*abs(side)+.04*fract(s*9,side*4,16)*abs(side)
        top=interp(soil-.13,max(tread,soil+.014),edgefade)
        # Close to the natural center grade, always allow natural ridges to blend through.
        top=min(top,interp(tread,soil+.03,.72) if soil>tread+.1 else tread)
        bottom=min(soil-.25,top-.26)
        row.append((g.vertex((p.x,p.y,top)),g.vertex((p.x,p.y,bottom))))
    floorrows.append(row)
for i in range(55):
    for j in range(12):
        for l in (0,1):
            q=[floorrows[ix][jx][l] for ix,jx in ((i,j),(i+1,j),(i+1,j+1),(i,j+1))]
            g.face(q,'M_GrottoBed' if l==0 else 'M_GrottoJoint')
        for k,outer_edge in enumerate((j==0,i==54,j==11,i==0)):
            if outer_edge:
                ids=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)];a,b=ids[k],ids[(k+1)%4]
                g.face([floorrows[a[0]][a[1]][0],floorrows[b[0]][b[1]][0],floorrows[b[0]][b[1]][1],floorrows[a[0]][a[1]][1]],'M_GrottoJoint')

def flake(center,axis,side,width,depth,thickness,role):
    pts=[];top=[];n=rng.randint(8,12);phase=rng.uniform(-.4,.4)
    for j in range(n):
        a=TAU*j/n+phase;ca=math.cos(a);sa=math.sin(a)
        outline=rng.uniform(.85,1.12)
        q=center+axis*(width*ca*outline)+side*(depth*sa*outline)
        lo=q-Z*thickness*(.45+.11*ca+.12*sa)
        edge=1-.09*abs(sa)
        hi=center+(q-center)*edge+Z*thickness*(.39+.18*ca+.13*sa+.11*rng.random())
        pts.append(lo);top.append(hi)
    g.solid(pts,top,role)
for side in (-1,1):
    for band in range(4):
        for k in range(rng.randint(14,23)):
            s=rng.uniform(.015,.987);c,t,n=frame(s*L);u=(.060+.070*band+.012*math.sin(16*s+band))
            u=u if side<0 else 1-u
            p=ring(s,u);p-=V((n.x,n.y,0))*side*.055
            flake(p,V((t.x,t.y,.049*math.sin(s*11))),V((n.x,n.y,0)),rng.uniform(.38,1.51),rng.uniform(.13,.43),rng.uniform(.13,.38),
                  'M_GrottoWet' if band<2 else ('M_GrottoStrata' if rng.random()<.65 else 'M_GrottoJoint'))
# Broad overlapping crown plates on the exterior break the silhouette into a
# bedded rock spur. Windows remain clear to admit daylight.
for i in range(125):
    s=rng.uniform(.015,.984);u=rng.uniform(.15,.85)
    if any(skylight(s+ds,u+du) for ds in (-.048,0,.048) for du in (-.065,0,.065)):continue
    c,d,n=frame(s*L);p=ring(s,u,True)
    ds=(ring(min(.999,s+.006),u,True)-ring(max(.001,s-.006),u,True)).normalized()
    du=(ring(s,min(.99,u+.014),True)-ring(s,max(.01,u-.014),True)).normalized()
    face=ds.cross(du).normalized()
    if abs(face.z)<.77 or rng.random()<.60:continue
    flake(p-Z*.15,ds,du,rng.uniform(.53,1.28),rng.uniform(.25,.69),rng.uniform(.30,.50),
          'M_GrottoJoint' if rng.random()<.79 else 'M_GrottoWet')
for s,u in ((.08,.26),(.13,.72),(.22,.64),(.35,.61),(.47,.27),(.56,.58),(.66,.24),(.81,.36),(.88,.65),(.94,.30)):
    anchors.append(("MossCushion",list(ring(s,u,True)+Z*.04),rng.uniform(.75,1.75),rng.uniform(-170,170)))
for s,u in ((.024,.27),(.35,.34),(.34,.45),(.72,.62),(.99,.80)):
    p=ring(s,u);anchors.append(("LianaCurtain",list(p+Z*.1),rng.uniform(.21,.40),rng.uniform(-140,140)))
obj=g.finish()
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(DEST/(obj.name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',mesh_smooth_type='FACE',bake_anim=False)
for img in bpy.data.images:
    if img.filepath:img.filepath=bpy.path.relpath(bpy.path.abspath(img.filepath),start=str(DEST))
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(DEST/'WestSpringGrotto.blend'),compress=True,relative_remap=False)
bpy.context.view_layer.update()
from mathutils.bvhtree import BVHTree
bvh=BVHTree.FromPolygons(g.points,g.faces,all_triangles=False)
lowest=999.;sidewalls=999.
for i in range(95):
    c,t,n=frame(L*(.025+.95*i/94))
    for w in (-1.1,-.55,0,.55,1.1):
        loc=c+n*w;z=valley.terrain(*loc);start=V((loc.x,loc.y,z+.15))
        hit,_,_,distance=bvh.ray_cast(start,Z,15)
        if hit and distance>.4:lowest=min(lowest,distance+.15)
    head=V((c.x,c.y,valley.terrain(*c)+1.22))
    for q in (-1,1):
        hit,_,_,distance=bvh.ray_cast(head,V((n.x*q,n.y*q,0)),15)
        if hit:sidewalls=min(sidewalls,distance)
manifest={'origin':list(root),'centerline':[list(frame(s*L)[0]) for s in [k/44 for k in range(45)]],'length_m':L,
          'width_test_m':2.2,'minimum_roof_above_test_strip_m':lowest,'minimum_wall_from_center_m':sidewalls,
          'triangles':sum(len(f)-2 for f in g.faces),'botany':anchors,
          'surfaces':{'license':'https://polyhaven.com/license','assets':['https://polyhaven.com/a/rock_face_04','https://polyhaven.com/a/cliff_side','https://polyhaven.com/a/mossy_rock']}}
(DEST/'grotto.json').write_text(json.dumps(manifest,indent=2))
print("Grotto clearance",lowest,sidewalls)
