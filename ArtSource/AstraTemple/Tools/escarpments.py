"""Carve bedded, fractured exposures out of the waterfall shelves' actual cross sections."""
from pathlib import Path
import math, sys, array
import bpy
from mathutils import Vector, noise
sys.path.insert(0,str(Path(__file__).resolve().parent))
import valley as v
root=Path(__file__).resolve().parents[1]/"Terrain"
west_only='--west-only' in sys.argv
if west_only:
    bpy.ops.wm.open_mainfile(filepath=str(root/"SpringEscarpments.blend"))
    old=bpy.data.objects["SM_WestSpringEscarpment"];old_mesh=old.data
    bpy.data.objects.remove(old,do_unlink=True)
    bpy.data.meshes.remove(old_mesh)
else:bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
height=array.array('f');height.frombytes((root/'ValleyHeights.f32').read_bytes())
def ground(x,y):
    a=(x-v.CENTRE[0])/.8+252;b=(y-v.CENTRE[1])/.8+252
    i=int(a);j=int(b);s=a-i;t=b-j;k=j*505+i
    return ((1-s)*((1-t)*height[k]+t*height[k+505])+s*((1-t)*height[k+1]+t*height[k+506]))*.01
stone=bpy.data.materials.get("M_RiverGorge") or bpy.data.materials.new("M_RiverGorge")
def exposure(name,bounds):
    x0,x1,y0,y1=bounds;step=.45
    nx=1+round((x1-x0)/step);ny=1+round((y1-y0)/step)
    verts=[];faces=[];coords=[];ids={}
    def vertex(i,j):
        key=(i,j)
        if key in ids:return ids[key]
        x=x0+i*step;y=y0+j*step
        x+=.10*math.sin(i*2.1+j*1.18);y+=.08*math.cos(j*1.8+i*.98)
        z=ground(x,y);gx=(ground(x+.4,y)-ground(x-.4,y))/.8;gy=(ground(x,y+.4)-ground(x,y-.4))/.8
        grad=math.hypot(gx,gy);normal=Vector((-gx,-gy,1)).normalized()
        s=noise.noise(Vector((x*.14,y*.19,z*.11)));frac=noise.noise(Vector((x*.66,y*.55,z*.25)))
        bedding=z*.57+.19*math.sin(x*.37)+.31*math.sin(y*.24)+.30*s
        shelf=((bedding%1)-.5)*.47
        joints=max(0,1-abs(math.sin(x*.54+y*.30+1.13*s+z*.045))*7.)
        edge,lev,w=v.river_sample(x,y)
        amount=v.sm((grad-.39)/.57)*v.sm((edge+.12)/1.8)
        relief=(-.23+amount*(.64+.34*s+.29*frac+shelf-.30*joints))
        p=Vector((x,y,z))+normal*relief
        ids[key]=len(verts);verts.append((p.x,-p.y,p.z));coords.append(p);return ids[key]
    for j in range(ny-1):
        for i in range(nx-1):
            x=x0+(i+.5)*step;y=y0+(j+.5)*step
            if 8<x<99 and abs(y)<36.3:continue
            edge,lev,w=v.river_sample(x,y)
            if edge<-.3 or edge>23.5 or v.trail_sample(x,y)[0]<2.5:continue
            grad=math.hypot(ground(x+.5,y)-ground(x-.5,y),ground(x,y+.5)-ground(x,y-.5))
            if grad<.41:continue
            a,b,c,d=vertex(i,j),vertex(i+1,j),vertex(i+1,j+1),vertex(i,j+1)
            if (i+j)%2:faces.extend([(a,c,b),(a,d,c)])
            else:faces.extend([(a,d,b),(b,d,c)])
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();mesh.materials.append(stone)
    uv=mesh.uv_layers.new(name="Sedimentary face")
    for face in mesh.polygons:
        face.use_smooth=True
        axis=max(range(3),key=lambda k:abs(face.normal[k]))
        for li in face.loop_indices:
            p=coords[mesh.loops[li].vertex_index]
            uv.data[li].uv=((p.y if axis==0 else p.x)/2.8,(p.y if axis==2 else p.z)/2.8)
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(root/(name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False)
for name,b in [('SM_WestSpringEscarpment',(13,155,-80,-19)),('SM_EastSpringEscarpment',(12,106,33,76))]:
    if not west_only or name=='SM_WestSpringEscarpment':exposure(name,b)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/'SpringEscarpments.blend'))
