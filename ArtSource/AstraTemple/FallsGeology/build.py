"""Export the surveyed spray cliff and fitted Crown shrine undercroft in metric FBX."""
from pathlib import Path
import json,math
import bpy,bmesh,numpy as np
from mathutils import Vector
DEST=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
def mesh(name,points,faces,roles,matindex,colors=None):
    m=bpy.data.meshes.new(name);m.from_pydata([(x,-y,z) for x,y,z in points],[],faces);m.update()
    for role in roles:m.materials.append(bpy.data.materials.get(role) or bpy.data.materials.new(role))
    m.polygons.foreach_set('material_index',matindex)
    bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
    if colors is not None:
        color=m.color_attributes.new(name="RootedLedges",type='FLOAT_COLOR',domain='POINT')
        color.data.foreach_set('color',np.asarray(colors,dtype='f4').ravel());m.color_attributes.active_color=color
    m.polygons.foreach_set('use_smooth',[colors is not None]*len(m.polygons))
    uv=m.uv_layers.new(name="Cracked face")
    for f in m.polygons:
        axis=max(range(3),key=lambda i:abs(f.normal[i]))
        for loop in f.loop_indices:
            x,y,z=points[m.loops[loop].vertex_index]
            uv.data[loop].uv=((y if axis==0 else x)/3.45,(y if axis==2 else z)/3.45)
    obj=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.fbx(filepath=str(DEST/(name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',colors_type='LINEAR',mesh_smooth_type='FACE',bake_anim=False)
    return obj
s=np.load(DEST/'survey.npz');rock=mesh("SM_SpringSprayCliff",s['verts'],s['faces'],['M_SprayLedges'],np.zeros(len(s['faces']),dtype='i4'),s['colors'])
# Foundation at local 7.75,-4.72 on the shrine. Watertight, staggered rough-cut heel blocks.
points=[];faces=[];slots=[]
def block(x0,x1,y0,y1,z0,z1,i):
    corners=[(x0+.07,y0),(x1-.10,y0),(x1,y0+.09),(x1,y1-.10),(x1-.07,y1),(x0+.08,y1),(x0,y1-.06),(x0,y0+.08)]
    n=len(corners);start=len(points);h=.042
    for ring,(z,inset) in enumerate(((z0,.05),(z0+h,0),(z1-h,0),(z1,.052))):
        for j,(x,y) in enumerate(corners):
            dx=(x-.5*(x0+x1));dy=(y-.5*(y0+y1));w=.018*math.sin(i+2.2*j)
            points.append((x-math.copysign(inset,dx)+w,y-math.copysign(inset,dy),z+(.017*math.cos(3*j+i) if ring!=3 else 0)))
    faces.extend([list(range(start+n-1,start-1,-1)),list(range(start+3*n,start+4*n))]);slots.extend([i%2]*2)
    for k in range(3):
        for j in range(n):
            a=start+k*n+j;b=start+k*n+(j+1)%n
            faces.append([a,b,b+n,a+n]);slots.append(i%2)
for index,(x0,x1,y0,y1,z0,z1) in enumerate([(-1.98,.3,-.98,1.19,-3.48,-1.79),(.28,1.34,-.98,1.19,-3.48,-1.79),(-1.91,-.48,-.92,1.15,-1.81,-.83),(-.49,1.31,-.92,1.15,-1.81,-.83),(-1.86,.54,-.86,1.12,-.85,-.08),(.52,1.27,-.86,1.12,-.85,-.08)]):
    block(x0,x1,y0,y1,z0,z1,index)
foundation=mesh("SM_CrownCornerFoundation",points,faces,['M_Astra_ShadeStone','M_Astra_MossStone'],slots)
foundation.hide_render=True;foundation.hide_set(True)
# Preserve physical texture and vertex-weathering authoring in the editable source.
mat=rock.data.materials[0];mat.use_nodes=True
nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.get("Principled BSDF")
def tex(path,srgb=True):
    n=nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(path),check_existing=True)
    n.image.filepath=bpy.path.relpath(str(path),start=str(DEST));n.image.colorspace_settings.name='sRGB' if srgb else 'Non-Color'
    return n.outputs['Color']
def blend(a,b,t,op='MIX'):
    n=nodes.new('ShaderNodeMixRGB');n.blend_type=op
    for dest,src in ((0,t),(1,a),(2,b)):
        if isinstance(src,(int,float,tuple)):n.inputs[dest].default_value=src
        else:links.new(src,n.inputs[dest])
    return n.outputs['Color']
rocktex=DEST.parent/'SpringGrotto'/'Textures';soil=DEST.parent/'Terrain'
joint=tex(rocktex/'T_JointedRock_Color.jpg');moss=tex(next(soil.glob('T_mossy_rock_Color.*')))
attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='RootedLedges'
channels=nodes.new('ShaderNodeSeparateColor');links.new(attr.outputs['Color'],channels.inputs[0])
color=blend(joint,moss,channels.outputs[0]);damped=blend(color,(.65,.72,.67,1.),1.,'MULTIPLY')
links.new(blend(color,damped,channels.outputs[1]),bs.inputs['Base Color'])
norm=nodes.new('ShaderNodeNormalMap');links.new(tex(rocktex/'T_JointedRock_NormalGL.jpg',False),norm.inputs['Color']);links.new(norm.outputs['Normal'],bs.inputs['Normal'])
links.new(tex(rocktex/'T_JointedRock_Roughness.jpg',False),bs.inputs['Roughness'])
foundation.location=(70,0,0)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(DEST/'SpringSprayGeology.blend'),compress=True)

