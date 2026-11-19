"""Sculpt continuous root sweeps on the as-built ledges, using Unreal metre datums."""
from pathlib import Path
import bpy, math, random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import valley
from mathutils import Vector
from mathutils.geometry import interpolate_bezier
from mathutils.noise import noise

root=Path(__file__).resolve().parents[1]/"Terrain"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system="METRIC"
bark=bpy.data.materials.new("M_FigBark")
def sculpt(name,origin,paths):
    verts=[];faces=[];uvs=[]
    obase=Vector(origin);rng=random.Random(914)
    def strand(path,variant):
        controls=[Vector(p[:3]) for p in path]
        track=[];radii=[]
        for i,(a,b) in enumerate(zip(controls,controls[1:])):
            t0=(b-controls[max(0,i-1)])*.16;t1=(controls[min(len(controls)-1,i+2)]-a)*.16
            steps=max(4,math.ceil((b-a).length/.32))
            bez=interpolate_bezier(a,a+t0,b-t1,b,steps+1)
            for j,p in enumerate(bez):
                if i and not j:continue
                t=j/steps;track.append(p)
                radii.append(path[i][3]*(1-t)+path[i+1][3]*t)
        rings=22;start=len(verts);di=0;lengths=[]
        side=None
        for k,(p,r) in enumerate(zip(track,radii)):
            tangent=(track[min(k+1,len(track)-1)]-track[max(0,k-1)]).normalized()
            if side is None:side=Vector((0,1,0)) if abs(tangent.y)<.94 else Vector((1,0,0))
            side=(side-tangent*side.dot(tangent)).normalized();up=tangent.cross(side).normalized()
            if k:di+=(p-track[k-1]).length
            lengths.append(di)
            for j in range(rings):
                a=2*math.pi*j/rings
                rmod=r*(1+.095*math.sin(5*a+di*.29+variant)+.07*math.sin(3*a-di*.13)+.042*noise(p*.45+Vector((math.cos(a),math.sin(a),0))))
                q=p+(side*math.cos(a)*1.18+up*math.sin(a)*(.91+.15*math.cos(di*.4)))*rmod-obase
                verts.append((q.x,-q.y,q.z))
        for k in range(len(track)-1):
            for j in range(rings):
                q=(j+1)%rings;i=start+k*rings
                faces.append((i+j,i+q,i+rings+q,i+rings+j))
                uvs.append([(j/rings,lengths[k]/2.8),((j+1)/rings,lengths[k]/2.8),((j+1)/rings,lengths[k+1]/2.8),(j/rings,lengths[k+1]/2.8)])
        faces.append(tuple(start+j for j in reversed(range(rings))));uvs.append([(0,0)]*rings)
        end=start+(len(track)-1)*rings
        faces.append(tuple(end+j for j in range(rings)));uvs.append([(0,0)]*rings)
    for n,base in enumerate(paths):
        strand(base,n)
        for side in [-1,1]:
            branch=[]
            for i,(x,y,z,r) in enumerate(base):
                t=i/(len(base)-1);w=math.sin(math.pi*t)
                branch.append((x+w*(.38*side+.39*math.cos(i*1.7+n)),y+side*w*(r*.78+.64*math.sin(i*.8)**2),z+.16+w*.21*math.sin(i+n),max(.025,r*(.31+.15*math.sin(i*.46+n)**2))))
            strand(branch,n+side*4)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.materials.append(bark);mesh.update()
    uv=mesh.uv_layers.new(name="Bark grain")
    for p,coords in zip(mesh.polygons,uvs):
        p.use_smooth=True
        for li,c in zip(p.loop_indices,coords):uv.data[li].uv=c
    # FBX reader uses the face winding after the Y reflection above.
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(root/(name+".fbx")),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False)
    return ob

upper=[
[(71.1,14.7,34,1.35),(70.5,16.05,30.7,1.35),(68.8,17.0,28.9,1.18),(63,18.3,28.65,.97),(59,18.5,28.5,.91),(57.1,19.6,27.8,.9),(56.05,20.6,24.7,.82),(54.45,21.9,20.6,.86),(51.3,23.1,20.45,.72),(46.1,24.8,20.45,.64),(40.9,26.5,20.5,.6),(39.15,27.2,19.8,.6),(37.8,27.8,15.7,.58),(36.1,29.3,12.5,.56),(29.4,31.2,12.26,.46),(21.3,33.35,12.32,.43),(19.5,34.7,11.7,.41),(18.95,35.1,7.15,.37),(17.3,36.8,4.0,.27),(14.7,37.4,1.1,.07)],
[(71.8,14.3,32.7,1.15),(68.8,13.7,29.1,1.0),(64.6,13.5,28.58,.75),(60.8,12.1,28.65,.66),(58.0,12.8,28.65,.62),(56.8,12.0,27.8,.54),(55.4,11.7,23.6,.52),(54.6,10.4,20.55,.48),(51.2,9.95,20.45,.38),(46.9,10.4,20.3,.19),(43.85,9.9,20.0,.04)],
[(72.,15.5,31.7,1.16),(73.6,17.3,28.95,.88),(75.4,18.55,28.6,.75),(76.3,19.45,28.0,.69),(75.65,20.1,23.9,.61),(75.2,21.2,20.55,.55),(74.1,23.6,20.4,.43),(75,26.9,20.3,.31),(76.8,27.8,17.6,.23),(77.6,28.4,13.8,.12),(78.6,29.3,12.0,.025)]]
def grounded(points):
    path=[]
    for x,y,offset,r in points:
        h=valley.terrain(x,y)
        if -46.2<x<-38.4 and .25<y<10.45:h=max(h,4.64)
        path.append((x,y,h+offset,r))
    return path
near=[grounded(p) for p in [
[(-56.2,5.8,4.75,.88),(-55.5,6.65,2.0,.78),(-54.0,8.1,.59,.61),(-51.1,9.35,.37,.53),(-48.6,9.06,.30,.42),(-46.25,10.1,.26,.35),(-44.55,10.3,.20,.30),(-43.0,10.12,.14,.21),(-41.7,10.55,.075,.12),(-40.3,11.05,-.02,.045),(-40.0,11.7,-.065,.019)],
[(-56.2,5.8,2.15,.71),(-55.45,7.55,.8,.57),(-55.85,9.65,.34,.47),(-57.15,11.75,.24,.35),(-58.5,13.1,.15,.24),(-60.1,13.8,.06,.14),(-61.25,14.82,-.03,.032)],
[(-56.2,5.8,2.25,.72),(-54.4,5.6,.76,.54),(-52.65,6.3,.31,.4),(-50.3,6.1,.19,.30),(-48.65,7.0,.1,.21),(-47.05,7.4,.055,.10),(-45.75,8.05,-.03,.035)]]]
sculpt("SM_SanctuaryRootCascade",(71.1,14.7,28),upper)
sculpt("SM_ForegateRootCrawl",(-56.2,5.8,4.8),near)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/"ArchitecturalRoots.blend"))
