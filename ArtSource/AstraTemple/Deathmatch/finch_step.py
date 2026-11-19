"""Seat a single intermediate stone course along the southern plaza paving edge."""
from pathlib import Path
import unreal as u
import editor as e
import arena

LABELS=("South Quay Threshold West","South Quay Threshold Centre","South Quay Threshold East")
def build(stage=None):
    import quay
    world=arena.current()
    names=e.all_named()
    reference=names["Basin Plaza Paving 209"].static_mesh_component
    # The hidden part of each slab keys underneath the existing pavement. Using its
    # original laying scale keeps exposed quarry stones and joints at the same size.
    start,end=-27.55,-6.0
    length=(end-start)/3
    for i,label in enumerate(LABELS):
        at=(14.96,start+(i+.5)*length,3.805)
        actor=names.get(label) or e.place(u.StaticMeshActor,label,"Deathmatch/South Quay Threshold",at)
        actor.set_actor_location_and_rotation(e.vector(at),e.rotation(180 if i==1 else 0),False,True)
        actor.set_actor_scale3d(u.Vector(.54375,length/8.0,1))
        component=actor.static_mesh_component
        component.set_static_mesh(reference.static_mesh)
        for slot in range(reference.get_num_materials()):component.set_material(slot,reference.get_material(slot))
        component.set_collision_profile_name("BlockAll")
    u.SystemLibrary.execute_console_command(world,"RebuildNavigation")
    if stage:return quay.save_copy(stage)
    if not u.EditorLoadingAndSavingUtils.save_current_level():raise RuntimeError("Cannot save the quay threshold")
    return list(LABELS)
