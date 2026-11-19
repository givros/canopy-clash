"""Build the two detachable Nanite friezes. Front is -X, all mesh units centimetres."""
from array import array
from pathlib import Path
import math
import struct
import zlib

import unreal as ue


ROOT="/Game/AstraTemple/Reliefs"
STONE="/Game/AstraTemple/Architecture/Materials/T_Astra_TempleStone_"
NAMES=("JaguarProcession","RainbirdOffering")
CUTS={"JaguarProcession":(0,.315,.698,1),"RainbirdOffering":(0,.356,.714,1)}


def make_stone():
    ue.EditorAssetLibrary.make_directory(ROOT)
    key="M_CarvedRiverLimestone"
    path=ROOT+"/"+key
    lib=ue.MaterialEditingLibrary
    mat=ue.load_asset(path) if ue.EditorAssetLibrary.does_asset_exist(path) else None
    if mat is None:
        mat=ue.AssetToolsHelpers.get_asset_tools().create_asset(key,ROOT,ue.Material,ue.MaterialFactoryNew())
    mat.modify()
    lib.delete_all_material_expressions(mat)
    def expr(cls,x,y):
        return lib.create_material_expression(mat,cls,x,y)
    def wire(a,b,pin,output=""):
        if not lib.connect_material_expressions(a,output,b,pin):
            raise RuntimeError(pin)
    def prop(a,target):
        if not lib.connect_material_property(a,"",getattr(ue.MaterialProperty,"MP_"+target)):
            raise RuntimeError(target)
    coords=expr(ue.MaterialExpressionTextureCoordinate,-980,-100)
    color=expr(ue.MaterialExpressionVertexColor,-980,120)
    def sample(suffix,typ,row):
        node=expr(ue.MaterialExpressionTextureSample,-720,row)
        node.set_editor_property("texture",ue.load_asset(STONE+suffix))
        node.set_editor_property("sampler_type",getattr(ue.MaterialSamplerType,"SAMPLERTYPE_"+typ))
        wire(coords,node,"UVs")
        return node
    base=sample("BaseColor","COLOR",-200)
    normal=sample("Normal","NORMAL",100)
    rough=sample("Roughness","LINEAR_COLOR",380)
    def custom(text,code,source,components,row,target):
        node=expr(ue.MaterialExpressionCustom,-340,row)
        inputs=[]
        for pin,_,_ in source:
            item=ue.CustomInput()
            item.set_editor_property("input_name",pin)
            inputs.append(item)
        node.set_editor_properties({"description":text,"code":code,"inputs":inputs,
            "output_type":getattr(ue.CustomMaterialOutputType,"CMOT_FLOAT"+str(components))})
        for pin,origin,out in source:
            wire(origin,node,pin,out)
        prop(node,target)
    custom("Limestone patina in the carved recesses",
           """float h=saturate(Carving.r); float exposed=smoothstep(.05,.72,h);
           float3 sandstone=lerp(float3(.79,.77,.51),float3(1.09,.94,.69),exposed);
           float3 grain=lerp(dot(Rock,float3(.29,.56,.15)),Rock,.62);
           return grain*sandstone*(.74+.26*exposed)*(.94+.09*Carving.b);""",
           [("Rock",base,"RGB"),("Carving",color,"")],3,-100,"BASE_COLOR")
    custom("Fine stone grain over the sculpted normals",
           "return normalize(lerp(float3(0.,0.,1.),Rock,.34));",
           [("Rock",normal,"RGB")],3,170,"NORMAL")
    custom("Weathered diffuse stone","return saturate(.53+.41*Rock);",
           [("Rock",rough,"R")],1,410,"ROUGHNESS")
    errors=list(lib.recompile_material(mat))
    if errors:
        raise RuntimeError(errors)
    if not ue.EditorAssetLibrary.save_loaded_asset(mat,False):
        raise RuntimeError(path)
    return mat


def field_for(name):
    p=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir()))/"AstraAuthoring"/"ReliefHeights"/(name+".rawz")
    data=p.read_bytes()
    w,h=struct.unpack("<HH",data[:4])
    heights=array("H")
    heights.frombytes(zlib.decompress(data[4:]))
    return w,h,heights


def section(mesh,name,data,slab):
    count,rows,heights=data
    cuts=CUTS[name]
    begins,ends=cuts[slab:slab+2]
    columns=round((ends-begins)*(count-1))+1
    pos=[];uv=[];rgb=[];norm=[];tri=[]
    def point(x,y,z,normal,color):
        pos.append(ue.Vector(x,y,z))
        uv.append(ue.Vector2D((y+350.)/194.+.023*slab,(165.-z)/194.))
        rgb.append(ue.LinearColor(*color))
        norm.append(ue.Vector(*normal))
        return len(pos)-1
    def face(a,b,c):
        tri.append(ue.IntVector(a,b,c))
    def curve(t,index):
        if index==0 or index==3:return 0.
        return .76*math.sin(14*t+2.7*index)+.41*math.sin(31*t+index)+.12*math.sin(69*t)
    def sample_height(y,row):
        yy=max(0,min(count-1,(y+350.)*(count-1)/700.))
        i=int(yy); frac=yy-i
        return (heights[row*count+i]*(1.-frac)+heights[row*count+min(i+1,count-1)]*frac)*.001
    secondary=1. if name=="RainbirdOffering" else 0.
    for row in range(rows):
        t=row/(rows-1)
        z=330.*t-165.
        left=-350.+700.*begins+curve(t,slab)+(.76 if slab else 0.)
        right=-350.+700.*ends+curve(t,slab+1)-(.76 if slab<2 else 0.)
        for col in range(columns):
            s=col/(columns-1)
            y=left+(right-left)*s
            # Offset tablet edges along a continuous irregular joint; preserve the sculpt registration.
            relief=sample_height(y,row)
            dist=min(y-left,right-y,165.-abs(z))
            bevel=min(1.,max(0.,dist/1.65))
            worn=.18*math.sin(y*.097+z*.156+secondary)*math.cos(z*.031-y*.024)
            face_tilt=(t-.5)*(.42 if slab==1 else -.27)+(.16*slab-.16)
            x=-relief+worn+face_tilt+(1.-bevel)*(1.50+.13*relief)
            dy=(sample_height(y+1.05,row)-sample_height(y-1.05,row))/2.10
            bottom=max(0,row-1); top=min(rows-1,row+1)
            dz=(sample_height(y,top)-sample_height(y,bottom))/((top-bottom)*330./(rows-1))
            nx,ny,nz=-1.,-dy,-dz
            if bevel<1:
                nx*=.70
                if col==0:ny-=.52
                if col==columns-1:ny+=.52
                if row==0:nz-=.52
                if row==rows-1:nz+=.52
            magnitude=math.sqrt(nx*nx+ny*ny+nz*nz)
            point(x,y,z,(nx/magnitude,ny/magnitude,nz/magnitude),
                  (min(1.,relief/38.),bevel,.25+.29*slab,1.))
    for row in range(rows-1):
        for col in range(columns-1):
            a=row*columns+col
            b=a+1; c=b+columns; d=a+columns
            if (row+col)%2:
                face(a,b,d);face(b,c,d)
            else:
                face(a,b,c);face(a,c,d)
    perimeter=(list(range(columns))+[r*columns+columns-1 for r in range(1,rows)]
               +[(rows-1)*columns+c for c in range(columns-2,-1,-1)]
               +[r*columns for r in range(rows-2,0,-1)])
    back=[]
    for index in perimeter:
        vector=pos[index]
        back.append(point(22.,vector.y,vector.z,(1.,0.,0.),(.10,1.,.37,1.)))
    center=point(22.,-350.+350.*(begins+ends),0.,(1.,0.,0.),(.10,1.,.37,1.))
    for i,a in enumerate(perimeter):
        j=(i+1)%len(perimeter); b=perimeter[j]
        face(b,a,back[i]);face(b,back[i],back[j]);face(center,back[j],back[i])
    buffers=ue.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_properties({"vertices":pos,"triangles":tri,"normals":norm,"uv0":uv,"vertex_colors":rgb})
    mesh.append_buffers_to_mesh(buffers)
    return len(tri)


async def make(name,material=None):
    import asyncio
    path=ROOT+"/SM_"+name+"Frieze"
    fields=field_for(name)
    mesh=ue.new_object(ue.DynamicMesh)
    count=0
    for slab in range(3):
        count+=section(mesh,name,fields,slab)
        await asyncio.sleep(.02)
    assert mesh.get_triangle_count()==count,(mesh.get_triangle_count(),count)
    if ue.EditorAssetLibrary.does_asset_exist(path):
        target=ue.load_asset(path)
        options=ue.GeometryScriptCopyMeshToAssetOptions()
        options.set_editor_properties({"enable_recompute_normals":False,"enable_recompute_tangents":True})
        _,result=ue.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(mesh,target,options,ue.GeometryScriptMeshWriteLOD(),True)
    else:
        options=ue.GeometryScriptCreateNewStaticMeshAssetOptions()
        nanite=ue.MeshNaniteSettings()
        nanite.set_editor_property("enabled",True)
        options.set_editor_properties({"enable_collision":False,"enable_recompute_normals":False,
                                    "enable_recompute_tangents":True,"enable_nanite":True,"nanite_settings":nanite})
        target,result=ue.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh,path,options)
    if not target or result!=ue.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(path)
    target.set_material(0,material or ue.load_asset(ROOT+"/M_CarvedRiverLimestone"))
    nanite=target.get_editor_property("nanite_settings")
    if not nanite.enabled:
        nanite.set_editor_property("enabled",True)
        ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem).set_nanite_settings(target,nanite,True)
    if not ue.EditorAssetLibrary.save_loaded_asset(target,False):
        raise RuntimeError(path)
    bounds=target.get_bounding_box()
    return {"path":path,"triangles":count,"closed_shells":mesh.get_is_closed_mesh(),
            "bounds":(str(bounds.min),str(bounds.max)),"nanite":target.get_editor_property("nanite_settings").enabled}
