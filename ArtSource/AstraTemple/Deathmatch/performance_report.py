"""Read native Unreal CSV captures from 5v5 play and reject empty or idle samples."""
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
PROJECT = SOURCE.parents[2]


def quantile(values,p):
    s=sorted(values)
    position=(len(s)-1)*p
    i=math.floor(position)
    return round(s[i]+(s[min(i+1,len(s)-1)]-s[i])*(position-i),3)


def read(run):
    folder=PROJECT/"Saved"/"Deathmatch"/run
    file=folder/"FrameTimes.csv"
    with file.open(encoding="utf-8-sig",newline="") as stream:
        rows=list(csv.reader(stream))
    header=rows[-2] if rows[-2][0]==rows[0][0] else rows[0]
    fields={k:i for i,k in enumerate(header)}
    meta={a.lower().strip("[]"):b for a,b in zip(rows[-1][::2],rows[-1][1::2])}
    frames=[]
    for row in rows[1:]:
        try:
            if float(row[fields["FrameTime"]])>0:
                frames.append(row)
        except (IndexError,ValueError):
            continue
    def column(key):
        return [float(row[fields[key]]) for row in frames]
    count=len(frames)
    roster=column("TempleMatch/Roster")
    score=column("TempleMatch/Score")
    speed=column("TempleMatch/Speed")
    if count<2000 or min(roster)!=10 or max(roster)!=10 or max(score)<=min(score) or max(speed)<4:
        raise ValueError("Capture did not contain a moving player and a live 5v5 match: "+run)
    times=column("FrameTime")
    timings={}
    for label in ("FrameTime","GPUTime","GameThreadTime","RenderThreadTime","RHIThreadTime"):
        values=column(label)
        timings[label]=dict(mean=round(statistics.mean(values),3),median=quantile(values,.5),
                            p95=quantile(values,.95),p99=quantile(values,.99),maximum=round(max(values),3))
    lines=(folder/"Review.log").read_text(encoding="utf-8",errors="replace").splitlines()
    params=next((l for l in lines if "LogInit: Command Line:" in l),"")
    def fingerprint(path):
        with path.open("rb") as source:
            return hashlib.file_digest(source,"sha256").hexdigest()
    return dict(run=run,raw=str(file.relative_to(PROJECT)).replace("\\","/"),
                map_sha256=fingerprint(folder/"Runtime/Content/AstraTemple/Maps/L_CanopyDeathmatch.umap"),
                editor_module_sha256=fingerprint(folder/"Runtime/Binaries/Win64/UnrealEditor-gameAstraForest.dll"),
                rendering="Unreal Standalone Development, native D3D12, offscreen viewport",
                resolution=[int(meta["systemresolution.resx"]),int(meta["systemresolution.resy"])],
                graphics_card=meta["gpu"],driver=meta["gpudriver"],cpu=meta["cpu"],
                engine=meta["engineversion"],audio="disabled" if "-NoSound" in params else "native non-realtime mixer",
                timed_frames=count,timed_seconds=round(sum(times)/1000,2),roster=10,
                points_during_capture=int(max(score)-min(score)),
                frames_moving_percent=round(100*sum(v>.1 for v in speed)/count,1),
                frames_under_16_67ms_percent=round(100*sum(v<=1000/60 for v in times)/count,2),
                average_fps=round(1000/statistics.mean(times),1),timings_ms=timings)


if __name__=="__main__":
    reports=[read(a) for a in sys.argv[1:]]
    if not reports:raise SystemExit("Supply capture directory names")
    for field in ("map_sha256","editor_module_sha256"):
        if len({report[field] for report in reports}) != 1:
            raise SystemExit("Resolution comparisons require the same arena and native module.")
    report={"method":"CSV profiling starts after 16 seconds of active play. During capture the actual player walks, acquires opponents and fires. The native UI and nine bots run continuously. These are local PC measurements, not hardware requirements.","captures":reports}
    (SOURCE/"Review"/"MatchPerformance.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    for run in reports:
        print(run["run"],run["average_fps"],run["timings_ms"]["FrameTime"]["p95"])
