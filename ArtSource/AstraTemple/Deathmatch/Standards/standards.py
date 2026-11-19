"""Model a bronze-capped wooden standard and sewn hanging textile for each team, in metres."""
from pathlib import Path
import math
import random
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
parts=[]
materials={}
def material(name,color,rough=.7,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=rough
    shader.inputs['Metallic'].default_value=metal
    materials[name]=m
    return m

def setmat(ob,mat):
    ob.data.materials.append(materials[mat]);parts.append(ob)
    return ob

def mesh(name,vs,fs,mat,smooth=True):
    data=bpy.data.meshes.new(name);data.from_pydata(vs,[],fs);data.update()
    ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob)
    for face in data.polygons:face.use_smooth=smooth
    return setmat(ob,mat)

def rod(name,a,b,r,mat,n=12,r2=None):
    d=Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cone_add(vertices=n,radius1=r,radius2=r if r2 is None else r2,depth=d.length,location=(Vector(a)+Vector(b))*.5)
    ob=bpy.context.object;ob.name=name
    ob.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    for p in ob.data.polygons:p.use_smooth=len(p.vertices)==4
    return setmat(ob,mat)

def lathe(name,sections,mat,n):
    v=[];f=[]
    for rad,z in sections:
        for i in range(n):
            a=2*math.pi*i/n+math.pi/n
            v.append((rad*math.cos(a),rad*math.sin(a),z))
    for j in range(len(sections)-1):
        for i in range(n):
            i2=(i+1)%n;a=j*n;b=a+n;f.append((a+i,a+i2,b+i2,b+i))
    f.extend([tuple(reversed(range(n))),tuple(range((len(sections)-1)*n,len(sections)*n))])
    return mesh(name,v,f,mat,n>10)

def cord(name,points,radius,mat,tubes=6):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=2
    cu.bevel_depth=radius;cu.bevel_resolution=1;cu.resolution_u=1
    spline=cu.splines.new('POLY');spline.points.add(len(points)-1)
    for pt,p in zip(spline.points,points):pt.co=(*p,1)
    ob=bpy.data.objects.new(name,cu);scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    bpy.ops.object.convert(target='MESH')
    return setmat(ob,mat)

def clothpoint(t,s,side):
    # s moves downwards. Suspension flattens the upper edge; broad folds deepen under it.
    wave=(.35+.65*min(s*5,1))*(.085*math.sin(2*math.pi*t+4.1*s+side*.53)+.047*math.sin(4*math.pi*t-1.9*s+.58))
    x=-.16+wave-.052*s*s
    y=(t-.5)*1.38+.025*s*math.cos(t*5+s+side*.42)
    scallop=.078*math.sin(4*math.pi*t)**2*(1-.82*s)
    bottom=.095*math.cos(2*math.pi*t)**2+.029*math.sin(t*21+side)
    z=3.47-s*(2.09+bottom)-scallop
    return x,y,z

def make_cloth(team,side):
    name='M_Standard'+team
    m=material(name,(.46,.13,.1) if not side else (.06,.25,.42))
    sh=m.node_tree.nodes.get('Principled BSDF')
    for suffix,socket in [('C','Base Color'),('N','Normal')]:
        node=m.node_tree.nodes.new('ShaderNodeTexImage')
        image=bpy.data.images.load(str(ROOT/('T_Standard'+team+'_'+suffix+'.png')),check_existing=True)
        node.image=image
        if suffix=='N':
            image.colorspace_settings.name='Non-Color'
            normal=m.node_tree.nodes.new('ShaderNodeNormalMap');m.node_tree.links.new(node.outputs['Color'],normal.inputs['Color'])
            m.node_tree.links.new(normal.outputs['Normal'],sh.inputs[socket])
        else:m.node_tree.links.new(node.outputs['Color'],sh.inputs[socket])
    vs=[];fs=[];coords=[]
    nx,nz=48,58
    for j in range(nz+1):
        for i in range(nx+1):
            t,s=i/nx,j/nz
            vs.append(clothpoint(t,s,side));coords.append((t,1-s))
    for j in range(nz):
        for i in range(nx):
            a=j*(nx+1)+i
            fs.append((a,a+1,a+nx+2,a+nx+1))
    ob=mesh('Woven field – '+team,vs,fs,name)
    uv=ob.data.uv_layers.new(name='UVMap')
    for poly in ob.data.polygons:
        for idx in poly.loop_indices:uv.data[idx].uv=coords[ob.data.loops[idx].vertex_index]
    for t in (0.,1.):
        cord('Rolled selvedge',[clothpoint(t,i/50,side) for i in range(51)],.009,'M_StandardBraid')
    cord('Lower folded binding',[clothpoint(i/60,1.,side) for i in range(61)],.012,'M_StandardBraid')
    rng=random.Random(152+side)
    for i in range(38):
        t=.013+.974*i/37;a=Vector(clothpoint(t,1,side))
        l=rng.uniform(.042,.103)+(.043 if i in (0,37) else 0)
        cord('Hand knotted fringe',[a,a+Vector((-.007,.002,-l*.32)),a+Vector((-.015,rng.uniform(-.012,.012),-l))],rng.uniform(.0045,.0076),'M_StandardBraid')
    # Five leather bands carry the cloth on the beam. Their hanging ends meet the cloth seam.
    for i in range(5):
        t=i*.25; ax,ay,az=clothpoint(t,0,side)
        pts=[(ax,ay,az-.015),(-.19,ay,3.58),(-.17,ay,3.638),(-.117,ay,3.643),(-.092,ay,3.60),(-.11,ay,3.54),(ax+.009,ay,az)]
        cord('Loop binding',pts,.019,'M_StandardBraid')

def standard(team,side):
    global parts
    parts=[]
    lathe('Hewn tapered foot',[(.292,-.14),(.304,.17),(.278,.25),(.232,.265),(.216,.305),(.188,.324)],'M_Astra_ShadeStone',8)
    lathe('Aged bronze socket',[(.13,.278),(.155,.309),(.15,.366),(.116,.403),(.092,.50)],'M_StandardBronze',12)
    lathe('Carved wood mast',[(.084,.38),(.087,.546),(.071,2.54),(.066,3.48),(.079,3.53),(.061,3.82)],'M_StandardWood',16)
    for z,r,h in [(.49,.093,.064),(.60,.090,.027),(2.96,.079,.043),(3.46,.095,.084),(3.67,.084,.058)]:
        lathe('Peened pole collar',[(r-.007,z),(r,z+.007),(r,z+h-.008),(r-.008,z+h)],'M_StandardBronze',16)
    rod('Suspension beam',(-.144,-.879,3.59),(-.144,.879,3.59),.045,'M_StandardWood',14)
    for s in (-1,1):
        rod('Bronze crossbar tip',(-.144,s*.817,3.59),(-.144,s*.887,3.59),.059,'M_StandardBronze',12)
        rod('Turned beam end',(-.144,s*.887,3.59),(-.144,s*.942,3.59),.055,'M_StandardBronze',12,.018)
    rod('Beam socket',(-.16,0,3.59),(.04,0,3.59),.077,'M_StandardBronze',12)
    for j in range(7):
        a=[]
        for k in range(27):
            phi=k/26*math.tau;a.append((.096*math.sin(phi)-.049,.087*math.cos(phi),3.46+j*.019+.011*math.cos(phi)))
        cord('Woven beam lashing',a,.0085,'M_StandardBraid')
    lathe('Stepped crown',[(.067,3.73),(.113,3.77),(.118,3.80),(.084,3.82),(.082,3.85),(.121,3.88),(.084,3.90),(.066,3.94),(.018,4.044)],'M_StandardBronze',8)
    make_cloth(team,side)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in parts:ob.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join();ob=bpy.context.object
    ob.name='SM_Standard'+team
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.export_scene.fbx(filepath=str(ROOT/(ob.name+'.fbx')),use_selection=True,object_types={'MESH'},
        axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False,path_mode='RELATIVE',mesh_smooth_type='FACE',add_leaf_bones=False)
    return ob

material('M_Astra_ShadeStone',(.205,.19,.142),.88)
material('M_StandardWood',(.175,.094,.042),.70)
material('M_StandardBronze',(.27,.16,.063),.46,.68)
material('M_StandardBraid',(.37,.269,.142),.83)
red=standard('Red',0)
blue=standard('Blue',1)
red.location.y=-1.25;blue.location.y=1.25
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'WovenStandards.blend'))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'WovenStandards.blend'))
