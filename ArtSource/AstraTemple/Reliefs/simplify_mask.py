"""Simplify planar areas of the sculpture with Blender's geometry-aware decimator."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import bpy
import numpy as np


cache=Path(__file__).resolve().parents[3]/"Saved"/"AstraAuthoring"/"ReliefHeights"
with ZipFile(cache/"SpringKeeperVolume.zip") as source:
    xyz=np.frombuffer(source.read("positions"),dtype="<f4").reshape(-1,3)
    # Blender uses the opposite winding to UE for the same numerical coordinates.
    tris=np.frombuffer(source.read("faces"),dtype="<i4").reshape(-1,3)[:,::-1].copy()
mesh=bpy.data.meshes.new("Spring Keeper stone")
mesh.vertices.add(len(xyz));mesh.vertices.foreach_set("co",xyz.ravel())
mesh.loops.add(tris.size);mesh.loops.foreach_set("vertex_index",tris.ravel())
mesh.polygons.add(len(tris))
mesh.polygons.foreach_set("loop_start",np.arange(0,tris.size,3,dtype=np.int32))
mesh.update()
obj=bpy.data.objects.new("Spring Keeper",mesh)
bpy.context.collection.objects.link(obj)
opt=obj.modifiers.new("Remove coplanar and low-curvature triangles","DECIMATE")
opt.ratio=.34
dg=bpy.context.evaluated_depsgraph_get()
ev=obj.evaluated_get(dg)
out=ev.to_mesh()
out.calc_loop_triangles()
pos=np.empty((len(out.vertices),3),dtype="<f4");out.vertices.foreach_get("co",pos.ravel())
norm=np.empty_like(pos);out.vertices.foreach_get("normal",norm.ravel())
faces=np.empty((len(out.loop_triangles),3),dtype="<i4");out.loop_triangles.foreach_get("vertices",faces.ravel())
faces=np.ascontiguousarray(faces[:,::-1])
tone=.14+.57*np.clip(-pos[:,0]/185.,0,1)+.24*np.maximum(0.,norm[:,2])
with ZipFile(cache/"SpringKeeperNative.zip","w",ZIP_DEFLATED,compresslevel=4) as final:
    for key,values in {"positions":pos,"normals":norm,"faces":faces,"tone":np.rint(255*np.clip(tone,0,1)).astype("u1")}.items():
        final.writestr(key,values.tobytes())
print("SCULPT",len(pos),"vertices",len(faces),"triangles",pos.min(axis=0),pos.max(axis=0))
ev.to_mesh_clear()
