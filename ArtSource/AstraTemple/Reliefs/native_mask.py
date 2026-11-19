"""Import the closed Spring Keeper sculpture into its own native Nanite asset."""
from pathlib import Path
import math
import struct
from zipfile import ZipFile

import unreal as ue


ROOT="/Game/AstraTemple/Reliefs"
MASK=ROOT+"/SM_SpringKeeperMask"


def surface():
    path=ROOT+"/M_SpringKeeperPatina"
    al=ue.EditorAssetLibrary
    if al.does_asset_exist(path):
        return ue.load_asset(path)
    mat=al.duplicate_asset(ROOT+"/M_CarvedRiverLimestone",path)
    if not mat:
        raise RuntimeError(path)
    lib=ue.MaterialEditingLibrary
    prop=ue.MaterialProperty.MP_BASE_COLOR
    original=lib.get_material_property_input_node(mat,prop)
    if not original:
        raise RuntimeError("Missing limestone base colour")
    color=lib.create_material_expression(mat,ue.MaterialExpressionVertexColor,-700,670)
    position=lib.create_material_expression(mat,ue.MaterialExpressionWorldPosition,-700,880)
    patina=lib.create_material_expression(mat,ue.MaterialExpressionCustom,-240,270)
    pins=[]
    for key in ("Limestone","Lichen","P"):
        pin=ue.CustomInput()
        pin.set_editor_property("input_name",key)
        pins.append(pin)
    patina.set_editor_properties({"inputs":pins,"description":"Lichen in damp stone pockets",
        "output_type":ue.CustomMaterialOutputType.CMOT_FLOAT3,
        "code":"""float a=sin(P.z*.062+sin(P.y*.10))*cos(P.y*.061+sin(P.z*.11));
                 float b=sin(P.y*.29+P.z*.17)*cos(P.z*.24-P.x*.09);
                 float coat=saturate((Lichen-.15+.19*a+.12*b)*1.42);
                 float3 moss=lerp(float3(.43,.52,.26),float3(.72,.76,.36),a*.5+.5);
                 return lerp(Limestone,Limestone*moss,coat*.64);"""})
    for source,port,pin in [(original,"","Limestone"),(color,"G","Lichen"),(position,"","P")]:
        if not lib.connect_material_expressions(source,port,patina,pin):
            raise RuntimeError(pin)
    if not lib.connect_material_property(patina,"",prop):
        raise RuntimeError("Base colour")
    errors=list(lib.recompile_material(mat))
    if errors:raise RuntimeError(errors)
    if not al.save_loaded_asset(mat,False):raise RuntimeError(path)
    return mat


async def build():
    import asyncio
    saved=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir()))
    with ZipFile(saved/"AstraAuthoring"/"ReliefHeights"/"SpringKeeperNative.zip") as source:
        xyz=source.read("positions");normal=source.read("normals");faces=source.read("faces");tone=source.read("tone")
    vertices=[];uv=[];color=[]
    def patch(u,v,cx,cy,rx,ry):
        return math.exp(-(((u-cx)/rx)**2+((v-cy)/ry)**2))
    for i,(x,y,z) in enumerate(struct.iter_unpack("<3f",xyz)):
        vertices.append(ue.Vector(x,y,z))
        uv.append(ue.Vector2D((y+550.+.28*x)/219.,(435.-z+.1*x)/219.))
        u=.5+y/1000.;v=.5-z/870.
        moss=(.78*patch(u,v,.746,.708,.064,.15)+.61*patch(u,v,.28,.26,.12,.14)
              +.64*patch(u,v,.858,.83,.068,.094)+.34*patch(u,v,.478,.958,.18,.05))
        color.append(ue.LinearColor(tone[i]/255.,min(1.,moss),.49,1.))
    await asyncio.sleep(.02)
    normals=[ue.Vector(*p) for p in struct.iter_unpack("<3f",normal)]
    triangles=[ue.IntVector(*q) for q in struct.iter_unpack("<3i",faces)]
    buffers=ue.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_properties({"vertices":vertices,"triangles":triangles,"uv0":uv,
                                  "normals":normals,"vertex_colors":color})
    del vertices,normals,triangles,uv,color,xyz,normal
    mesh=ue.new_object(ue.DynamicMesh)
    mesh.append_buffers_to_mesh(buffers)
    expected=len(faces)//12
    assert mesh.get_triangle_count()==expected,(mesh.get_triangle_count(),expected)
    assert mesh.get_is_closed_mesh(),"The sculpture shell is open"
    await asyncio.sleep(.02)
    al=ue.EditorAssetLibrary
    if al.does_asset_exist(MASK):
        target=ue.load_asset(MASK)
        opt=ue.GeometryScriptCopyMeshToAssetOptions()
        opt.set_editor_properties({"enable_recompute_normals":False,"enable_recompute_tangents":True})
        _,outcome=ue.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(mesh,target,opt,ue.GeometryScriptMeshWriteLOD(),True)
    else:
        opt=ue.GeometryScriptCreateNewStaticMeshAssetOptions()
        nanite=ue.MeshNaniteSettings();nanite.set_editor_property("enabled",True)
        opt.set_editor_properties({"enable_collision":False,"enable_recompute_normals":False,"enable_recompute_tangents":True,
                                   "enable_nanite":True,"nanite_settings":nanite})
        target,outcome=ue.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh,MASK,opt)
    if not target or outcome!=ue.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError(MASK)
    mat=surface()
    target.set_material(0,mat)
    nanite=target.get_editor_property("nanite_settings")
    if not nanite.enabled:
        nanite.set_editor_property("enabled",True)
        ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem).set_nanite_settings(target,nanite,True)
    if not al.save_loaded_asset(target,False):raise RuntimeError(MASK)
    bounds=target.get_bounding_box()
    return {"asset":MASK,"triangles":mesh.get_triangle_count(),"closed":mesh.get_is_closed_mesh(),
            "min":str(bounds.min),"max":str(bounds.max),"nanite":target.get_editor_property("nanite_settings").enabled}
