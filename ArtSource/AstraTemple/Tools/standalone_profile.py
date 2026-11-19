"""Profile a first-person standalone UE run without opening a visible window."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
PROJECT=next(ROOT.glob("*.uproject"))
MAP="/Game/AstraTemple/Maps/L_TempleOfTheCanopy"
ENGINE=Path(os.environ.get("ProgramFiles","C:/Program Files"))/"Epic Games"/("UE_"+json.loads(PROJECT.read_text(encoding="utf-8-sig"))["EngineAssociation"])/"Engine/Binaries/Win64/UnrealEditor.exe"
REPORT=ROOT/"ArtSource/AstraTemple/Review"
SAVED=ROOT/"Saved/AstraAuthoring/Standalone"
FRAMES=1205
# Screenshots and the positional jump fall outside the timed intervals.
WINDOWS={"dense_player_start":(265,565),"bridge_gameplay_view":(865,1165)}
def settings():
    src=(ROOT/"Config/DefaultEngine.ini").read_text(encoding='utf-8-sig')
    default=re.search(r"(?m)^GameDefaultMap=(.+)$",src)
    if not default or default[1].strip().split('.')[0]!=MAP:
        raise RuntimeError("Configured GameDefaultMap differs from the intended standalone map.")
    if not ENGINE.is_file() or not (ROOT/'Content/AstraTemple/Maps/L_TempleOfTheCanopy.umap').is_file():
        raise FileNotFoundError("Installed Unreal Editor or native map file is missing.")
CANDIDATE_CVARS={"r.Shadow.Virtual.ResolutionLodBiasDirectional":"-0.5","r.Shadow.Virtual.NonNanite.IncludeInCoarsePages":"0","r.TSR.History.ScreenPercentage":"125"}
def launch_command(width,height,folder,tag,candidate=None):
    marks=[(155,"r.Shadow.Virtual.ResolutionLodBiasDirectional"),(156,"r.Shadow.Virtual.NonNanite.IncludeInCoarsePages"),(157,"r.TSR.History.ScreenPercentage"),
           (165,"r.ScreenPercentage"),(166,"sg.ResolutionQuality"),(167,"r.DynamicRes.OperationMode"),
           (219,f'Shot filename={tag}_Start.png -nosuffix'),(264,'Trace.Bookmark AstraStandalone_DenseStart'),
           (565,'Trace.Bookmark AstraStandalone_DenseEnd'),(584,'EnableCheats'),
           (585,'BugItGo -4280 1820 537 6 15 0'),(819,f'Shot filename={tag}_Bridge.png -nosuffix'),
           (864,'Trace.Bookmark AstraStandalone_BridgeStart'),(1165,'Trace.Bookmark AstraStandalone_BridgeEnd')]
    base=[ENGINE,PROJECT,'-game','-RenderOffscreen','-Windowed','-ForceRes',f'-ResX={width}',f'-ResY={height}',
          '-Unattended','-NoSound','-NoSplash','-NoLiveCoding','-NoSourceControl','-NoCrashDialog',
          '-NoEpicPortal','-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocol.ModelContextProtocolSettings]:bAutoStartServer=False',
          '-csvGpuStats','-csvCompression=0',f'-csvCaptureFrames={FRAMES}','-ExitAfterCsvProfiling']
    overrides=dict(CANDIDATE_CVARS) if candidate in ('balanced','tsr85','shadows') else {}
    if candidate=="shadows":overrides.pop("r.TSR.History.ScreenPercentage")
    if candidate=="tsr85":overrides["r.ScreenPercentage"]="85"
    commands=' -ExecCmds="'+','.join(k+' '+v for k,v in overrides.items())+'"' if overrides else ''
    # UE parses values after the equals sign directly from GetCommandLineW.
    return (subprocess.list2cmdline([str(i) for i in base])+f' -AbsLog="{folder/"Standalone.log"}"'
            +commands+' -csvExecCmds="'+','.join(str(f)+':'+cmd for f,cmd in marks)+'"')
def percentile(vals,frac):
    data=sorted(vals);k=(len(data)-1)*frac;i=math.floor(k)
    return round(data[i]+(data[min(i+1,len(data)-1)]-data[i])*(k-i),3)
def describe(vals):
    return dict(mean_ms=round(statistics.mean(vals),3),median_ms=percentile(vals,.5),p95_ms=percentile(vals,.95),p99_ms=percentile(vals,.99))
def read_csv(path):
    csv.field_size_limit(16*1024*1024)
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.reader(stream))
    header=rows[0]
    if rows[-2][0]==header[0] and len(rows[-2])>=len(header):header=rows[-2]
    meta={a.strip('[]').lower():b for a,b in zip(rows[-1][::2],rows[-1][1::2])} if rows[-1][0].startswith('[') else {}
    frames=[]
    idx=header.index('FrameTime')
    for row in rows[1:]:
        try:ft=float(row[idx])
        except (ValueError,IndexError):continue
        if ft>=0:frames.append(row)
    lookup={k:i for i,k in enumerate(header)};events={};gpu=[(i,k[4:]) for i,k in enumerate(header) if k.startswith('GPU/') and k!="GPU/FrameTime"]
    for n,row in enumerate(frames):
        for label in ("DenseStart","DenseEnd","BridgeStart","BridgeEnd"):
            if 'Trace.Bookmark AstraStandalone_'+label in row[0]:events.setdefault(label,n)
    sections={}
    for name,(start,end) in WINDOWS.items():
        a,b=('DenseStart','DenseEnd') if name=='dense_player_start' else ('BridgeStart','BridgeEnd')
        first=events.get(a,start)+1;last=events.get(b,end)
        rows=frames[first:last];times={}
        if len(rows)<180:raise ValueError("Insufficient standalone gameplay samples for "+name)
        for col in ('FrameTime','GPUTime','GameThreadTime','RenderThreadTime','RHIThreadTime'):
            if col not in lookup:continue
            i=lookup[col];vals=[float(r[i]) for r in rows if len(r)>i and r[i] and float(r[i])>0.]
            if vals:times[col]=describe(vals)
        if 'GPUTime' not in times:raise ValueError("Native GPU frame timings are missing.")
        passes={}
        for i,label in gpu:
            values=[float(r[i]) for r in rows if len(r)>i and r[i]]
            if values:passes[label]=round(statistics.mean(values),3)
        ms=times['FrameTime']['mean_ms']
        sections[name]=dict(frames=len(rows),start_frame=first,end_frame_exclusive=last,mean_fps=round(1000/ms,2),timings=times,
                            top_gpu_pass_mean_ms=dict(sorted(passes.items(),key=lambda item:-item[1])[:6]))
    meta={k:v for k,v in meta.items() if k in ('platform','config','buildversion','engineversion','os','cpu','gpu','cpubrand','gpubrand','deviceprofile','physicalcores','logicalcores','systemmemory','rhi','rhiadapter','driver') or any(s in k for s in ('adapter','driver','cores','systemresolution'))}
    return len(frames),events,sections,meta
def screenshot(tag,view,folder,width,height):
    version=json.loads(PROJECT.read_text(encoding='utf-8-sig'))['EngineAssociation']
    stores=[ROOT/'Saved',Path(os.environ['LOCALAPPDATA'])/'UnrealEngine'/version/'Saved']
    choices=[p for store in stores for p in (store/'Screenshots').glob('**/'+tag+'_'+view+'.png')]
    if not choices:return None
    src=max(choices,key=lambda f:f.stat().st_mtime);dest=folder/(view+'.png')
    with src.open('rb') as f:dims=struct.unpack('>II',f.read(24)[16:24])
    if dims!=(width,height):raise RuntimeError(f'Actual output {dims} differs from request {(width,height)}')
    shutil.copy2(src,dest);return str(dest.relative_to(ROOT))
def inspect(folder,tag,width,height,elapsed,started_utc=None):
    log=(folder/'Standalone.log').read_text(encoding='utf-8-sig',errors='replace')
    world=re.search(r"Bringing World ([^ ]*L_TempleOfTheCanopy[^ ]*) up for play",log)
    mode=re.search(r"Game class is '([^']+)'",log)
    marker=re.search(r"Capture Ended\. Writing CSV to file\s*:\s*([^\r\n]+)",log)
    if not marker or not world or not mode or mode[1]!='BP_FirstPersonGameMode_C':raise RuntimeError("Native map, first-person game mode or CSV completion marker is missing.")
    raw=Path(marker[1].strip().strip('"'))
    if not raw.is_absolute():raw=(ENGINE.parent/raw).resolve()
    if not raw.is_file():
        version=json.loads(PROJECT.read_text(encoding='utf-8-sig'))['EngineAssociation']
        raw=Path(os.environ['LOCALAPPDATA'])/'UnrealEngine'/version/'Saved/Profiling/CSV'/raw.name
    if not raw.is_file():raw=ROOT/'Saved/Profiling/CSV'/raw.name
    file=folder/('Frames.csv.gz' if raw.suffix=='.gz' else 'Frames.csv');shutil.copy2(raw,file)
    n,events,sections,meta=read_csv(file)
    moved=bool(re.search(r"LogCheatManager:.*BugItGo to:",log))
    if not moved:raise RuntimeError("Second player-camera position was not acknowledged by the game.")
    load=re.findall(r"Took ([\d.]+) seconds to LoadMap\([^)]*L_TempleOfTheCanopy",log)
    match=re.search(r"\[(\d{4}\.\d\d\.\d\d-\d\d\.\d\d\.\d\d:\d{3})\].*?Bringing World [^ ]*L_TempleOfTheCanopy[^ ]* up for play",log)
    ready_seconds=None
    if match and started_utc:
        at=datetime.strptime(match[1],'%Y.%m.%d-%H.%M.%S:%f').replace(tzinfo=timezone.utc)
        ready_seconds=round((at-started_utc).total_seconds(),3)
    diag=[s.split(']')[-1].strip() for s in log.splitlines() if re.search(r'(Adapter Name:|Using Highest Feature Level|D3D12.*Chosen|GPU DeviceId:|GPU Driver Version:|Name:.*(?:NVIDIA|AMD Radeon|Intel.*Graphics))',s,re.I)]
    screens={k:screenshot(tag,k,folder,width,height) for k in ('Start','Bridge')}
    health=[s.strip()[-350:] for s in log.splitlines() if re.search(r'out of video memory|GPU Crashed|video memory has been exhausted|Fatal error:|VSM.*overflow|texture streaming pool over budget',s,re.I) and 'metadata' not in s.lower()]
    monitored=tuple(CANDIDATE_CVARS)+("r.ScreenPercentage","sg.ResolutionQuality","r.DynamicRes.OperationMode")
    screen_settings=[s.strip()[-200:] for s in log.splitlines() if any(k+" =" in s for k in monitored)]
    return dict(map=world[1],game_mode=mode[1],boot_to_world_ready_seconds=ready_seconds,resolution=[width,height],launch="UnrealEditor -game -RenderOffscreen",process_seconds=round(elapsed,2),
                map_load_seconds=float(load[-1]) if load else None,raw_csv=str(file.relative_to(ROOT)),log=str((folder/'Standalone.log').relative_to(ROOT)),
                capture_frames=n,excluded_startup_and_warmup_frames=265,bookmarks=events,sections=sections,hardware=meta,rhi=diag[:10],
                screen_settings=screen_settings,screenshots=screens,rendering_warnings=health[:15])
def host_snapshot():
    names=[]
    listing=subprocess.run(['tasklist','/FO','CSV','/NH','/FI','IMAGENAME eq UnrealEditor.exe'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=8)
    for row in csv.reader(listing.stdout.decode(errors='replace').splitlines()):
        if len(row)>1 and row[0].lower()=='unrealeditor.exe':names.append(int(row[1]))
    result={'preexisting_unreal_editor_pids':names}
    smi=shutil.which('nvidia-smi')
    if smi:
        fields=['name','driver_version','memory.total','memory.used','utilization.gpu']
        query=subprocess.run([smi,'--query-gpu='+','.join(fields),'--format=csv,noheader,nounits'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=8)
        if query.returncode==0:result['gpu_before_launch']=[dict(zip(fields,(s.strip() for s in row))) for row in csv.reader(query.stdout.decode(errors='replace').splitlines())]
    return result
def run(width,height,preview=False,candidate=None):
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S');tag=f'AstraStandalone_{width}x{height}_{stamp}'
    folder=SAVED/tag;args=launch_command(width,height,folder,tag,candidate)
    if preview:print(args);return
    folder.mkdir(parents=True);before=host_snapshot();start=time.monotonic();started_utc=datetime.now(timezone.utc)
    phase={'started_utc':started_utc.isoformat(),'host_before_launch':before,'candidate':candidate}
    (folder/'Run.json').write_text(json.dumps(phase,indent=2))
    smi=shutil.which('nvidia-smi');monitor=None
    with (folder/'GpuTelemetry.csv').open('w') as telemetry:
        if smi:
            monitor=subprocess.Popen([smi,'--query-gpu=timestamp,pstate,clocks.current.graphics,clocks.current.memory,temperature.gpu,power.draw,utilization.gpu,memory.used',
                '--format=csv,nounits','--loop=2'],stdout=telemetry,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            proc=subprocess.Popen(args,executable=str(ENGINE),cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            try:code=proc.wait(timeout=420)
            except subprocess.TimeoutExpired:
                proc.terminate();proc.wait(timeout=20);raise TimeoutError(f'Own standalone process {proc.pid} did not finish in time. See {folder}')
        finally:
            if monitor and monitor.poll() is None:monitor.terminate();monitor.wait(timeout=8)
    elapsed=time.monotonic()-start
    phase['process_seconds']=elapsed;phase['exit_code']=code
    (folder/'Run.json').write_text(json.dumps(phase,indent=2))
    if code:raise RuntimeError(f'Standalone Unreal process exited {code}: {folder}')
    result=inspect(folder,tag,width,height,elapsed,started_utc)
    if smi:result['gpu_telemetry']=str((folder/'GpuTelemetry.csv').relative_to(ROOT))
    result['host_before_launch']=before
    result["candidate"]=candidate
    prefix="Standalone_Candidate_"+candidate+"_" if candidate else "Standalone_"
    REPORT.mkdir(exist_ok=True);dest=REPORT/f'{prefix}{width}x{height}.json';dest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(dest),'fps':{k:v['mean_fps'] for k,v in result['sections'].items()},'screenshots':result['screenshots']}),flush=True)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--resolution',action='append',choices=('1280x720','1920x1080'));p.add_argument('--dry-run',action='store_true')
    p.add_argument('--candidate',choices=('control','shadows','balanced','tsr85'));args=p.parse_args();settings()
    for res in (args.resolution or ('1280x720','1920x1080')):
        run(*map(int,res.split('x')),preview=args.dry_run,candidate=args.candidate)
if __name__=='__main__':main()






