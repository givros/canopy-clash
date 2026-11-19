"""Isolated construction check on an exact excerpt from the valley heightfield."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector as V
dest=Path(bpy.data.filepath).parent
sys.path.insert(0,str(dest.parent/'Tools'))
import valley as v
manifest=json.loads((dest/'grotto.json').read_text());base=V(manifest['origin'])
def local(p):
    p=V(p)-base
    return V((p.x,-p.y,p.z))
sc=bpy.context.scene
zscale=1
points=[];faces=[]
for i in range(97):
    x=95+i*.43
    for j in range(104):
        y=-40+.43*j
        points.append(local((x,y,v.terrain(x,y))))
        if i and j:
            z=i*104+j;faces.append((z,z-1,z-105,z-104))
terrain=bpy.data.meshes.new('Surveyed trail');terrain.from_pydata(points,[],faces)
ob=bpy.data.objects.new('Survey ground',terrain);sc.collection.objects.link(ob)
terrain.materials.append(bpy.data.materials['M_GrottoBed'])
sunlight=bpy.data.lights.new('Ravine daylight','SUN');sunlight.energy=3.4;sunlight.angle=.16
sun=bpy.data.objects.new('Ravine daylight',sunlight);sc.collection.objects.link(sun)
sun.rotation_euler=V((.35,.48,-.8)).to_track_quat('-Z','Y').to_euler()
sc.world=bpy.data.worlds.new('Sky');sc.world.use_nodes=True
bg=sc.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.40,.53,.66,1);bg.inputs['Strength'].default_value=.72
cd=bpy.data.cameras.new('Inspection camera');cam=bpy.data.objects.new('Inspection camera',cd);sc.collection.objects.link(cam);sc.camera=cam
sc.render.engine='CYCLES';sc.cycles.samples=12;sc.cycles.use_denoising=True
sc.render.resolution_x=900;sc.render.resolution_y=630;sc.render.resolution_percentage=100
for label,x,y,tx,ty,lower,pitch,lens in [
    ('Portal',103.25,-6.80,109.8,-14.6,1.76,1.7,24),
    ('Alcove',110.4,-14.3,115.6,-21.0,1.71,2.75,18),
    ('SpringExit',118.1,-21.7,121.6,-27.3,1.58,2.15,17),
    ('RockSpur',98,4,113.5,-17.5,18.,2.4,32)]:
    camera_z=v.terrain(x,y)+lower
    if label=='RockSpur':camera_z=52.
    cam.location=local((x,y,camera_z));focus=local((tx,ty,v.terrain(tx,ty)+pitch))
    cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cd.lens=lens;cd.clip_start=.03
    sc.render.filepath=str(dest/(label+'.png'))
    bpy.ops.render.render(write_still=True)
