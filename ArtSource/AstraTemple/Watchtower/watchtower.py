"""Upper ridge watch pavilion. Model dimensions are metres; the bed joint is the local origin."""
from pathlib import Path
import sys
import bpy

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'Architecture'))
import temple_kit as kit

kit.rng.seed(41136)
a=kit.Asset('UpperWatchtower')

def stone(x,y,z,dx,dy,dz,tone=None,wear=.064):
    kit.hewn(a,x,y,z,dx,dy,dz,tone,wear=wear)

def wall(axis,fixed,lo,hi,z,width,height,unit,role=None):
    n=max(1,round((hi-lo)/unit))
    proportions=[kit.rng.uniform(.74,1.25) for _ in range(n)]
    p=lo
    for fraction in proportions:
        end=p+(hi-lo)*fraction/sum(proportions)
        if axis=='X':stone((p+end)*.5,fixed,z,end-p-.012,width,height,role)
        else:stone(fixed,(p+end)*.5,z,width,end-p-.012,height,role)
        p=end

def ring(z,sx,sy,height,width,unit,mat=None):
    for sign in [-1,1]:
        wall('X',sign*(sy-width)*.5,-sx*.5,sx*.5,z,width,height,unit,mat)
        wall('Y',sign*(sx-width)*.5,-sy*.5+width,sy*.5-width,z,width,height,unit,mat)

a.part('Splayed terraces fitted around the old corbel vault')
for course in [(-.015,6.37,5.97,.38,.59,1.17),(.353,6.08,5.74,.51,.68,1.25),(.86,5.81,5.42,.54,.69,1.17),(1.395,5.54,5.13,.47,.73,1.21),(1.86,5.36,4.94,.38,.72,1.23)]:
    ring(*course)
# Avoid exposing old roof tips at the bottom of the aperture. Keeping the lower
# rings hollow lets the old central ridge continue into the closed podium.
for i in range(4):
    wall('X',-1.80+i*1.2,-2.665,2.665,2.225,1.205,.47,1.72,3 if i==1 else None)
ring(2.59,5.53,5.04,.20,.55,1.48,0)

a.part('Battered external fins framing four corners')
for xx in [-1,1]:
    for yy in [-1,1]:
        for z,sx,sy,dx,dy,h in [(0,2.40,2.22,1.12,1.00,.59),(.57,2.36,2.14,1.02,.94,.63),(1.18,2.29,2.06,.95,.87,.69),(1.83,2.20,1.98,.87,.82,.65)]:
            stone(xx*sx,yy*sy,z,dx,dy,h,None,.06)

a.part('Open east and south watch chamber')
# The two solid windward leaves give the paired outward bays a genuine shaded
# depth. The narrow western vent keeps the deep chamber from reading as a slab.
for j in range(4):
    z=2.77+j*.48
    for xx in [-1,1]:
        for yy in [-1,1]:
            stone(xx*(1.72-.012*j),yy*(1.52-.012*j),z,1.17-.025*j,1.10-.021*j,.482,None,.062)
    wall('X',-1.63,-1.19,1.19,z,.65,.48,1.15,3 if j in [1,2] else 0)
    for low,high in ([(-1.03,-.17),(.26,1.03)] if j in [1,2] else [(-1.03,1.03)]):
        wall('Y',-1.85,low,high,z,.52,.48,1.25,3)
# Single proud front-facing jamb and lintel stones preserve dark window edges.
for xx in [-1,1]:
    stone(xx*1.105,1.90,2.80,.22,.20,1.88,0,.023)
for yy in [-1,1]:
    stone(2.18,yy*.975,2.81,.19,.23,1.87,1,.025)
stone(0,1.58,4.67,4.60,.95,.39,0,.067)
stone(1.81,-.04,4.67,.94,3.39,.39,0,.061)
stone(-1.81,-.04,4.67,.94,3.39,.39,3,.058)
stone(0,-1.63,4.67,4.60,.79,.39,3,.055)

a.part('Shaded coffered ceiling and upper dentil course')
for j in range(5):wall('Y',-1.80+j*.90,-2.03,2.03,5.025,.903,.225,4.10,3)
ring(5.04,4.83,4.30,.25,.48,1.31)
for xx in [-1,1]:
    for j in range(6):stone(xx*2.20,-1.69+j*.68,5.27,.23,.42,.20,None,.034)
for yy in [-1,1]:
    for j in range(6):stone(-1.98+j*.78,yy*1.93,5.27,.43,.22,.20,None,.032)
ring(5.46,4.58,4.05,.23,.60,1.32,0)

a.part('Stepped roof comb and weathered shoulders')
for i in range(3):wall('X',-.98+.98*i,-1.96,1.96,5.68,.99,.33,1.36)
for xx in [-1,1]:
    stone(xx*1.47,-.23,6.,.81,1.93,.31,0)
    stone(xx*1.43,-.35,6.30,.67,1.40,.21 if xx<0 else .34,1)
for j in range(2):wall('X',-.69+j*1.00,-1.09,1.09,6.,1.,.48,1.16,0)
stone(-.03,-.20,6.47,1.82,1.75,.34,0,.09)
stone(.10,-.30,6.79,1.46,1.40,.30,0,.09)

ob=a.finish() or kit.assets['SM_Astra_UpperWatchtower']
bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active=ob
bpy.ops.export_scene.fbx(filepath=str(ROOT/(ob.name+'.fbx')),use_selection=True,use_mesh_modifiers=False,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False,path_mode='RELATIVE',mesh_smooth_type='FACE',add_leaf_bones=False)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Watchtower.blend'))
if '--review' in sys.argv:
    kit.render(ob,(0,0,3.6),(7.5,17.5,-.4),9.5,'UpperWatchtower')
