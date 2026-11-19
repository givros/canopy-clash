"""Build a one-metre tapered luminous streak for the temporal shot feedback."""
from math import cos, pi, sin
from pathlib import Path
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
vertices, faces = [], []
for distance, radius in [(0, .0001), (.13, .0038), (.68, .0021), (1, .0001)]:
    for sector in range(6):
        angle = 2 * pi * sector / 6
        vertices.append((distance, radius * cos(angle), radius * sin(angle)))
for ring in range(3):
    for sector in range(6):
        a = ring * 6 + sector
        b = ring * 6 + (sector + 1) % 6
        faces.append((a, b, b + 6, a + 6))
mesh = bpy.data.meshes.new("LuminousStreak")
mesh.from_pydata(vertices, [], faces)
mesh.update()
part = bpy.data.objects.new("SM_CarbineTrace", mesh)
bpy.context.collection.objects.link(part)
part.select_set(True)
bpy.context.view_layer.objects.active = part
bpy.ops.export_scene.fbx(filepath=str(Path(__file__).with_name("SM_CarbineTrace.fbx")),
                         use_selection=True, axis_forward="-Y", axis_up="Z", use_mesh_modifiers=False)
