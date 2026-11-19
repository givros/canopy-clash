"""Fit the skyline chamber to the original roof without modifying that building."""
from pathlib import Path
import sys
import unreal as u
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'Tools'))
import editor as e
from stonework import import_mesh

def mount():
    e.require_world()
    named=e.all_named();shrine=named['Shrine Above the Mist']
    name='SM_Astra_UpperWatchtower'
    mats={}
    for role in ['Sandstone','Ochre','CarvedStone','ShadeStone','MossStone','Pinestone']:
        mat='M_Astra_'+role
        mats[mat]=e.assets.load_asset('/Game/AstraTemple/Architecture/Materials/'+mat)
    package='/Game/AstraTemple/Watchtower'
    imported=import_mesh(ROOT/(name+'.fbx'),package,False,True,mats,collision=True)
    mesh=e.assets.load_asset(package+'/'+name)
    if not mesh.get_editor_property('nanite_settings').enabled or not all(mesh.get_material(i) for i in range(len(mesh.static_materials))):raise RuntimeError(imported)
    label='Upper Watchtower of the Mist'
    pos=u.MathLibrary.transform_location(shrine.get_actor_transform(),u.Vector(425,0,742))
    actor=named.get(label) or e.actors.spawn_actor_from_object(mesh,pos,shrine.get_actor_rotation())
    actor.set_actor_location_and_rotation(pos,shrine.get_actor_rotation(),False,True)
    scale=shrine.get_actor_scale3d()
    actor.set_actor_scale3d(u.Vector(scale.x,scale.y,scale.z*.77))
    actor.set_actor_label(label)
    actor.set_folder_path('Secondary Ruins/Shrines')
    return [e.save(),str(pos),imported]
