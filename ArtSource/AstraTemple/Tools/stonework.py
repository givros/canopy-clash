from editor import *

def make_finishes():
    path=BASE+"/Architecture/Materials"
    files=ROOT/"Architecture"
    texture=[import_texture(files/("T_Astra_TempleStone_"+s+".png"),path,s=="Roughness",s=="Normal") for s in ("BaseColor","Normal","Roughness")]
    texture[1].set_editor_property("flip_green_channel",True)
    assets.save_loaded_asset(texture[1])
    patina=import_texture(ROOT/"Terrain/T_MasonryWeathering.png",path,True)
    photograph=import_texture(ROOT/"Terrain/T_mossy_rock_Color.jpg",BASE+"/Terrain/Textures")
    # Multipliers in linear light. Separate shadow stone and moss from sun-worn carvings.
    colors={"Sandstone":(.91,.76,.61),"Ochre":(.83,.57,.37),"CarvedStone":(1.,.82,.62),"ShadeStone":(.51,.53,.48),"MossStone":(.39,.49,.27),"Pinestone":(.79,.67,.52)}
    result={}
    for k,c in colors.items():
        name="M_Astra_"+k
        if k=="PineStone":continue
        g=Graph(material(name,path))
        pos=g.node("WorldPosition")
        nrm=g.node("VertexNormalWS")
        xy=g.mask(pos,True,True)
        scale=g.const(570.)
        top_uv=g.pair("Divide",xy,scale)
        side_x=g.mask(pos,True,False);side_y=g.mask(pos,False,True);z=g.mask(pos,False,False,True)
        along=g.pair("Add",side_y,g.pair("Multiply",side_x,g.const(.79)))
        append=g.node("AppendVector");g.connect(append,along,"A");g.connect(append,z,"B")
        side_uv=g.pair("Divide",append,scale)
        facing=g.node("Saturate");g.connect(facing,g.mask(nrm,False,False,True),"Input")
        stains=g.blend(g.texture(patina,side_uv,linear=True),g.texture(patina,top_uv,linear=True),facing)
        growth=g.pair("Multiply",g.mask(stains),g.pair("Add",g.const(.27),g.pair("Multiply",facing,g.const(.52))))
        if k=="MossStone":growth=g.pair("Add",growth,g.const(.17))
        tint=g.node("Constant3Vector",constant=u.LinearColor(*c,1))
        col=g.pair("Multiply",g.texture(texture[0]),tint)
        moss=g.pair("Multiply",g.texture(photograph),g.node("Constant3Vector",constant=u.LinearColor(.55,.70,.34,1)))
        dirt=g.pair("Multiply",g.mask(stains,False,True),g.const(.24))
        col=g.blend(col,g.pair("Multiply",col,g.const(.42)),dirt)
        col=g.blend(col,moss,growth)
        g.result(col,"BASE_COLOR")
        flat=g.node("Constant3Vector",constant=u.LinearColor(0,0,1,1))
        g.result(g.blend(flat,g.texture(texture[1],normal=True),g.const(.55)),"NORMAL")
        g.result(g.texture(texture[2],linear=True),"ROUGHNESS","R")
        result[name]=g.finish()
    return result

def import_mesh(file,folder,replace=False,nanite=False,binding=None,collision=True):
    path=folder+"/"+file.stem
    if replace or not assets.does_asset_exist(path):
        u.SystemLibrary.execute_console_command(require_world(),"Interchange.FeatureFlags.Import.FBX 0")
        task=u.AssetImportTask()
        ui=u.FbxImportUI()
        ui.set_editor_properties({"import_mesh":True,"import_materials":False,"import_textures":False,"import_as_skeletal":False,"import_animations":False,"automated_import_should_detect_type":False,"mesh_type_to_import":u.FBXImportType.FBXIT_STATIC_MESH})
        static=ui.static_mesh_import_data
        static.set_editor_properties({"combine_meshes":True,"auto_generate_collision":False,"generate_lightmap_u_vs":False,"build_nanite":nanite,"convert_scene":True,"convert_scene_unit":True,"force_front_x_axis":False})
        task.set_editor_properties({"filename":str(file),"destination_path":folder,"destination_name":file.stem,"automated":True,"replace_existing":replace,"replace_existing_settings":True,"save":True,"options":ui})
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh=assets.load_asset(path)
    if not mesh:raise RuntimeError("Could not import "+str(file))
    slots=[]
    materials=list(mesh.get_editor_property("static_materials"))
    for i,sm in enumerate(materials):
        name=str(sm.get_editor_property("imported_material_slot_name")) or str(sm.get_editor_property("material_slot_name"))
        slots.append(name)
        if binding and name in binding:sm.set_editor_property("material_interface",binding[name])
    if binding:mesh.set_editor_property("static_materials",materials)
    if collision:
        mesh.get_editor_property("body_setup").set_editor_property("collision_trace_flag",u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    assets.save_loaded_asset(mesh,False)
    box=mesh.get_bounding_box()
    return (file.stem,str(box.min),str(box.max),slots)

def architecture(names=None,replace=False):
    finishes=make_finishes()
    files=sorted((ROOT/"Architecture").glob("SM_*.fbx"))
    return [import_mesh(f,BASE+"/Architecture/Meshes",replace,True,finishes) for f in files if not names or f.stem in names]

def piece(name,label,point,yaw=0,scale=(1,1,1),folder="MainTemple",pitch=0,roll=0):
    mesh=assets.load_asset(BASE+"/Architecture/Meshes/SM_Astra_"+name)
    if not mesh:raise RuntimeError("Missing architecture "+name)
    actor=place(u.StaticMeshActor,label,folder,point,yaw,pitch,scale)
    actor.set_actor_rotation(rotation(yaw,pitch,roll),False)
    actor.static_mesh_component.set_static_mesh(mesh)
    return actor

def preview():
    require_world()
    for a in actors.get_all_level_actors():
        if str(a.get_folder_path()).startswith("Composition Study"):actors.destroy_actor(a)
    for i,(foot,z) in enumerate(v.STAIRS):piece("StairFlight","Study flight "+str(i),(foot,0,z),folder="Composition Study")
    piece("Portal","Study portal",(68,0,28),folder="Composition Study")
    ax,ay=v.BRIDGE_START
    yaw=math.degrees(math.atan2(v.BRIDGE_END[1]-ay,v.BRIDGE_END[0]-ax))
    dx,dy=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    for i in range(4):piece("BridgeSpan","Study arch "+str(i),(ax+dx*(5+10*i),ay+dy*(5+10*i),4),yaw,folder="Composition Study")
    return save()
