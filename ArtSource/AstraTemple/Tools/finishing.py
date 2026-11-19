import editor as e
import stonework
from pathlib import Path
import unreal as u

def details():
    names=e.all_named()
    base=e.BASE
    stone={}
    for role in ["Sandstone","Ochre","CarvedStone","ShadeStone","MossStone","Pinestone"]:
        name="M_Astra_"+role
        stone[name]=e.assets.load_asset(base+"/Architecture/Materials/"+name)
    arch=base+"/Architecture/Meshes"
    stonework.import_mesh(e.ROOT/"Architecture/SM_Astra_PortalMasonry.fbx",arch,nanite=True,binding=stone)
    names["Face of the Spring Keeper"].static_mesh_component.set_static_mesh(e.assets.load_asset(arch+"/SM_Astra_PortalMasonry"))
    def native(label,mesh_path,folder,point,angle=0,scale=(1,1,1),solid=True):
        mesh=e.assets.load_asset(mesh_path)
        if not mesh:raise RuntimeError(mesh_path)
        a=names.get(label) or e.place(u.StaticMeshActor,label,folder,point,angle,scale=scale)
        a.set_actor_location_and_rotation(e.vector(point),e.rotation(angle),False,True);a.set_actor_scale3d(u.Vector(*scale))
        a.static_mesh_component.set_static_mesh(mesh)
        if not solid:a.static_mesh_component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        return a
    native("The Spring Keeper",base+"/Reliefs/SM_SpringKeeperMask","Temple/Sanctuary",(68.61,0,45.72))
    fore=e.ROOT/"Terrain/SM_GateFigLimb.fbx";bark_names=("M_FigBark","M_RainLeaf","M_RainLeafShade","M_RainLeafLight")
    forest_mats={k:e.assets.load_asset(base+"/Nature/Materials/"+k) for k in bark_names}
    stonework.import_mesh(fore,base+"/Terrain/Meshes",binding=forest_mats,nanite=False,collision=True)
    native("The branch above the gate",base+"/Terrain/Meshes/SM_GateFigLimb","Hero Trees/Foregate",( -56.2,5.8,4.8)).static_mesh_component.set_collision_profile_name("BlockAll")
    for a in list(e.actors.get_all_level_actors()):
        if str(a.get_folder_path())=="Outer Gate/Approach" and "StairFlight" in a.get_actor_label():e.actors.destroy_actor(a)
    native("Foregate approach steps",arch+"/SM_Astra_ApproachSteps","Outer Gate/Approach",(-48.10,14.25,3.85),-52)
    native("Foregate upper landing",arch+"/SM_Astra_Paving","Outer Gate/Approach",(-45.65,11.35,4.65),-52,(.47,.72,1))
    for j,(x,y,z,angle,s) in enumerate([(77.1,-4.1,36.21,35,.69),(78.8,-3.8,36.36,47,.91),(84.5,3.92,36.42,-42,.79),(87.2,3.6,36.6,-27,.67),(74.1,3.4,35.,11,.54)]):
        native("Hanging nave vine "+str(j+1),base+"/Nature/Meshes/SM_LianaCurtain","Temple/Ritual Hall Growth",(x,y,z),angle,(s,s,s),False)
    for j,(x,y) in enumerate([(75.2,-6.46),(75.6,-5.45),(85.77,6.17),(90,-5.8)]):
        native("Nave fern "+str(j+1),base+"/Nature/Meshes/SM_Fern","Temple/Ritual Hall Growth",(x,y,27.95),j*41,(.8,.8,.8),False)
    return e.save()
