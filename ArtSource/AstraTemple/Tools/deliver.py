"""Assemble the Unreal captures and measured native route/profile results."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/"Review"


def read(file):
    return json.loads(file.read_text(encoding="utf-8"))


def write(name,value):
    (ROOT/name).write_text(json.dumps(value,indent=2),encoding="utf-8")


def gallery():
    names=[("Reference","Temple of the Canopy"),("Bridge","Pilgrim causeway"),("Stairs","Monumental stairs"),
           ("PilgrimsApproach","Outer jungle"),("Sanctuary","Ritual hall"),("SpringCourt","Rear spring court"),
           ("WestCloister","Western cloister"),("Basin","Reflection pool"),("Aerial","The two springs")]
    font=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf",19)
    sheet=Image.new("RGB",(1500,1215),(19,27,23))
    draw=ImageDraw.Draw(sheet)
    for i,(name,caption) in enumerate(names):
        x,y=(i%3)*500,(i//3)*405
        with Image.open(REVIEW/("Final-"+name+".png")) as im:
            sheet.paste(ImageOps.fit(im.convert("RGB"),(500,375)),(x,y))
        draw.text((x+11,y+377),caption,font=font,fill=(239,229,206))
    sheet.save(REVIEW/"TempleViews.jpg",quality=93,subsampling=0)
    comparison=Image.new("RGB",(1800,710),(19,27,23))
    draw=ImageDraw.Draw(comparison)
    for i,(file,name) in enumerate([(ROOT/"References/JungleTemple.png","Supplied reference"),(REVIEW/"Final-Reference.png","Unreal Engine 5.9")]):
        with Image.open(file) as im:comparison.paste(ImageOps.fit(im.convert("RGB"),(900,675)),(i*900,0))
        draw.text((i*900+12,679),name,font=font,fill=(239,229,206))
    comparison.save(REVIEW/"ReferenceComparison.jpg",quality=94,subsampling=0)


def reports():
    inventory=read(ROOT/"asset_registry.json")
    source={k:len(v) for k,v in inventory["native_assets"].items()}
    walks={}
    pie={}
    for file in sorted(REVIEW.glob("Traversal_*.json")):
        route=read(file)
        walks[route["route"]]={k:route[k] for k in ("status","at_goal","total_goals","walked_m","max_continuous_air_seconds")}
        perf=read(REVIEW/("Performance_"+route["route"]+".json"))
        pie[route["route"]]={"viewport_px":route["startup"]["viewport_px"],"frame_time":perf["channels"]["FrameTime"],"gpu_time":perf["channels"]["GPUTime"],"sections":perf["sections"],"source":perf["source"]}
    games={}
    for resolution in ("1280x720","1920x1080"):
        report=REVIEW/("Standalone_"+resolution+".json")
        if report.exists():games[resolution]=read(report)
    write("render_profile.json",{"runtime":"Unreal Engine 5.9, Direct3D 12", "gpu":"NVIDIA GeForce RTX 3080",
          "lighting":"Fixed key, specified sky cubemap, fixed exposure, local bounced daylight",
          "water_reflections":"Screen-space reflections plus a local parallax-corrected basin capture; single-layer water",
          "vegetation":"Instanced mesh foliage with distance-limited wind, authored tree LODs and paired Nanite shadow geometry",
          "play_in_editor":pie,"standalone":games})
    grotto=read(REVIEW/"GrottoClearance.json")
    write("runtime_validation.json",{"map":inventory["world"],"runtime_default":"Config/DefaultEngine.ini","native_assets_by_class":source,
          "cameras":list(inventory["saved_cameras"]),"walks":walks,"grotto_clearance":{k:v for k,v in grotto.items() if k!="stations"},
          "native_shader_check":"Review/SavedWorldCheck.json","court_bearing_check":"Review/CourtBearing.json",
          "controls":read(REVIEW/"Traversal_main.json")["startup"],"standalone":list(games),"details":"Review/Traversal_*.json contains world positions, real character floor checks and native input results."})
    write("animation_manifest.json",{"fixed":["sun direction and intensity","sky radiance","exposure bounds"],
          "systems":[{"assets":["M_SpringWater"],"motion":"Crossing wave normals and underwater light caustics"},
                     {"assets":["M_CascadeVeil","M_BrokenFoam","M_SprayMist"],"motion":"Per-plume flowing strands, broken foam and slowly advected spray"},
                     {"assets":["Nature/Materials","FloraStudies"],"motion":"Weighted material wind on source leaf, frond and vine meshes; authored roots and structural bark are static","native_wind_clip":"Nature/Previews/UE_LeafWind.webp"}]})


if __name__=="__main__":
    gallery()
    reports()
