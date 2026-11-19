"""Export the editable portal body with a separate socket for the freestanding mask."""
from pathlib import Path
import sys,bpy
arch=Path(__file__).resolve().parents[1]/"Architecture"
sys.path.insert(0,str(arch))
import temple_kit as kit
kit.rng.seed(58081)
# The removable face and ear ornaments are the only replaced part of the kit.
create_face=kit.sculptface
try:
    kit.sculptface=lambda *args,**kwargs:None
    kit.portal()
finally:
    kit.sculptface=create_face
mesh=kit.assets['SM_Astra_Portal'];mesh.name='SM_Astra_PortalMasonry';mesh.data.name=mesh.name
kit.output_asset(mesh)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(arch/"PortalMasonry.blend"))
