"""Fit existing planting to a regraded trail without redistributing the surrounding forest."""
import array
import json
from pathlib import Path
import valley


def fit(previous_height_path):
    source=Path(__file__).resolve().parents[1]/"Terrain"
    layout_file=source/"Vegetation.json"
    layout=json.loads(layout_file.read_text())
    def grid(file):
        values=array.array("f")
        values.frombytes(Path(file).read_bytes())
        return values
    old=grid(previous_height_path)
    new=grid(source/"ValleyHeights.f32")
    def height(values,x,y):
        col=(x-valley.CENTRE[0])/.8+252
        row=(y-valley.CENTRE[1])/.8+252
        i,j=int(col),int(row)
        s,t=col-i,row-j
        n=505*j+i
        return .01*((1-t)*((1-s)*values[n]+s*values[n+1])+t*((1-s)*values[n+505]+s*values[n+506]))
    report={}
    for species,records in layout.items():
        fitted=[]
        adjusted=removed=0
        for rec in records:
            x,y=rec[:2]
            if 72<x<164 and -119<y<-50:
                offset=height(new,x,y)-height(old,x,y)
                if abs(offset)>.035:
                    dist,_=valley.trail_sample(x,y)
                    solid=species in ("StranglerFig","JungleCanopy","ArecaPalm","SandstoneCliff","FracturedCliff") or species.startswith("MossBoulder")
                    if dist<(3.2 if solid else 1.45):
                        removed+=1
                        continue
                    rec[2]=round(rec[2]+offset,4)
                    adjusted+=1
            fitted.append(rec)
        if adjusted or removed:
            layout[species]=fitted
            report[species]={"adjusted":adjusted,"removed_from_tread":removed}
    layout_file.write_text(json.dumps(layout,separators=(",",":")))
    return report
