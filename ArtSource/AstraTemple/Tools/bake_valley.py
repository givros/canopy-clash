import json
import math
import struct
from pathlib import Path
from PIL import Image, ImageDraw
from valley import *

root=Path(__file__).resolve().parents[1]
height=[]
weights=Image.new('RGB',(RESOLUTION,RESOLUTION))
pixels=weights.load()
for j in range(RESOLUTION):
    y=CENTRE[1]+(j-(RESOLUTION-1)/2)*SPACING
    for i in range(RESOLUTION):
        x=CENTRE[0]+(i-(RESOLUTION-1)/2)*SPACING
        z=terrain(x,y)
        height.append(z*100)
        distance,_=trail_sample(x,y)
        river,_,_=river_sample(x,y)
        bank=within_bank(x,y)
        patch=.5*math.sin(.096*x+.32*math.sin(y*.21))+.32*math.sin(.34*y-.17*x)
        rock=clamp((z-24)/35+patch*.34+(.5 if abs(river)<2.6 else 0))
        mud=clamp(max(1-sm((distance-.8)/2.4),sm((bank+3)/6),.75*sm((2-river)/4))+.19*patch)
        green=clamp(.66+.35*patch-.83*mud)
        pixels[i,j]=(round(rock*255),round(mud*255),round(green*255))
(root/'Terrain/ValleyHeights.f32').write_bytes(struct.pack('<%df'%len(height),*height))
weights.save(root/'Terrain/T_ValleyZones.png')
def plane(x,y):
    return ((x-CENTRE[0])/SPACING+252,(y-CENTRE[1])/SPACING+252)
plan=Image.new("RGB",(505,505))
p=plan.load()
for j in range(505):
    for i in range(505):
        h=height[j*505+i]*.01
        p[i,j]=(int(49+max(0,h)*.86),int(78+max(0,h)*.68),int(61+max(0,h)*.41)) if h>0 else (48,115,116)
draw=ImageDraw.Draw(plan)
for path in TRAILS.values():draw.line([plane(*point[:2]) for point in path],fill='#e2b985',width=2)
for path in RIVERS:draw.line([plane(*point[:2]) for point in path],fill='#9bcfd4',width=4)
for f,r,h,b,t in TIERS:draw.rectangle((*plane(f,-h),*plane(r,h)),outline='#ddbc87')
draw.line([plane(*BRIDGE_START),plane(*BRIDGE_END)], fill='#f1d392',width=3)
draw.line([plane(16,0),plane(94,0)],fill='#fff1c7',width=3)
plan.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(root/'semantic_layout.png')
(root/'scene_spec.json').write_text(json.dumps({
    "title":"Temple of the Canopy", "runtime":"Unreal Engine 5.9", "units":"metres; +X into temple, +Y right, +Z up",
    "reference":"References/JungleTemple.png","observed":{"entrance":[.705,.245],"deity":[.697,.118],"stair_foot":[.55,.56],"bridge":"diagonal foreground right; three visible spans","palette":"sun-warmed ochre stone, deep cool shade, olive and deep green forest, teal water, pale blue atmospheric distance","light":"fixed high front-side daylight; back ridge hazier than carved facade"},
    "inferred":"Rear ritual nave, spring court, side shrines, ruined west cloister, two upper catchments and outer return trails. World dimensions and lens are reconstructed.",
    "camera":CAMERAS,"stairs":STAIRS,"retaining_tiers":TIERS,"watercourses":RIVERS,"main_basin":BANKS,"primary_bridge":[BRIDGE_START,BRIDGE_END],"trails":TRAILS,
    "interior_study":{"file":"References/InteriorStudy.png","method":"Built-in image generation using the original reference","brief":"A corbelled open-ended ritual nave with paired carved piers, daylight from a breached roof and a rear jungle court."}
},indent=2))
graph={"walking_trails":TRAILS,"main_route":["Pilgrims approach","Gate of Roots","Causeway","East quay","Plaza","Three stair flights","Ritual hall","Rain court"],
       "connections":[["Pilgrims approach","East jungle gallery"],["Pilgrims approach","Broken cloister"],["East jungle gallery","Plaza"],
                      ["Rain court","Spring trail"],["Rain court","West canopy trail"],["West canopy trail","High shrine ridge"],
                      ["High shrine ridge","Crown watch spur"]],
       "covered_sections":{"West canopy trail":"West spring grotto and side alcove","Broken cloister":"Root passage"},
       "destinations":{"Spring trail":"Eastern spring","High shrine ridge":"Shrine of the Split Leaf","Crown watch spur":"Shrine Above the Mist"}}
(root/'region_graph.json').write_text(json.dumps(graph,indent=2))
