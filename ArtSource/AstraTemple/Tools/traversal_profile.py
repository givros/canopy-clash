"""Summarize native Unreal CSV Profiler channels for the matching gameplay run."""
import argparse
import csv
import gzip
import json
import math
import re
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[3]
REVIEW=Path(__file__).resolve().parents[1]/"Review"

def percentile(values,p):
    sorted_values=sorted(values);t=(len(sorted_values)-1)*p;a=math.floor(t);b=math.ceil(t)
    return round(sorted_values[a]+(sorted_values[b]-sorted_values[a])*(t-a),3)

def summarize(csv_path):
    opener=gzip.open if csv_path.name.endswith('.gz') else open
    with opener(csv_path,'rt',encoding='utf-8-sig',newline='') as file:
        reader=csv.reader(file)
        header=next(reader)
        # The profiler appends newly discovered channels. Its trailing header
        # enumerates them without changing the indices in the existing rows.
        for row in reader:
            if row and row[0]==header[0] and len(row)>len(header):header=row
        file.seek(0);reader=csv.reader(file);next(reader)
        passes={i:k for i,k in enumerate(header) if k.startswith('GPU/') and k!='GPU/FrameTime'}
        frame_index=header.index('FrameTime');pass_sums={};pass_counts={}
        def mean_top(key):
            if not pass_counts.get(key):return {}
            return {k:round(v/pass_counts[key],3) for k,v in sorted(pass_sums[key].items(),key=lambda p:p[1],reverse=True)[:6]}
        # Requested channels are in milliseconds. The unprefixed CSV channels
        # are created by the engine, separate from named rendering pass scopes.
        candidates={'frametime','gamethreadtime','renderthreadtime','rhithreadtime','gpu','gputime','gpu frametime','gpubusytime','gputime2','gpu/frametime','frame time','framecount'}
        fields={i:name for i,name in enumerate(header) if name.strip().casefold() in candidates}
        columns={name:[] for name in fields.values() if name.casefold()!='framecount'}
        skipped=0;by_section={};section=None
        for row in reader:
            if not row or row[0]==header[0] or row[0].startswith('['):skipped+=1;continue
            event=re.search(r'Trace\.Bookmark AstraWalk_([^;#]+)',row[0])
            if event:
                section=event.group(1).replace('_',' ');by_section.setdefault(section,{'FrameTime':[],'GPUTime':[]})
            try:frame_ms=float(row[frame_index])
            except (ValueError,IndexError):continue
            buckets=['frames_over_33ms' if frame_ms>1000/30 else 'frames_under_33ms']
            if section:buckets.append('section_'+section)
            for bucket in buckets:
                totals=pass_sums.setdefault(bucket,{})
                pass_counts[bucket]=pass_counts.get(bucket,0)+1
                for idx,name in passes.items():
                    if idx<len(row) and row[idx]:
                        try:value=float(row[idx])
                        except ValueError:continue
                        totals[name]=totals.get(name,0)+value
            for i,name in fields.items():
                if name not in columns:continue
                try:value=float(row[i])
                except (ValueError,IndexError):continue
                if value>0 and math.isfinite(value):
                    columns[name].append(value)
                    if section and name in by_section[section]:by_section[section][name].append(value)
        if not any(columns.values()):raise ValueError("Native CSV contains no recognized timing channels; headers: "+str(header[:80]))
        summary={}
        for name,values in columns.items():
            if not values:continue
            mean=sum(values)/len(values)
            summary[name]={"samples":len(values),"mean_ms":round(mean,3),"median_ms":percentile(values,.5),"p95_ms":percentile(values,.95),"p99_ms":percentile(values,.99),"max_ms":round(max(values),3)}
            if name.strip().casefold() in {'frametime','frame time'}:summary[name]['mean_fps']=round(1000/mean,2)
        sections={}
        for name,series in by_section.items():
            frame=series['FrameTime'];gpu=series['GPUTime']
            if frame:
                sections[name]={'top_gpu_pass_mean_ms':mean_top('section_'+name),'native_frames':len(frame),'mean_fps':round(1000*len(frame)/sum(frame),2),'frame_p95_ms':percentile(frame,.95),'gpu_p95_ms':percentile(gpu,.95) if gpu else None}
        slow={k:{'frame_count':pass_counts.get(k,0),'top_gpu_pass_mean_ms':mean_top(k)} for k in ['frames_over_33ms','frames_under_33ms']}
        return {"slow_frame_diagnostics":slow,"sections":sections,"source":str(csv_path.relative_to(PROJECT)),"scope":"Native engine counters during offscreen Play In Editor; editor overhead and concurrent GPU processes remain included. GPU timing is reported only for a populated native GPU channel.","channels":summary,"skipped_non_frame_rows":skipped}

def capture(route):
    report=REVIEW/('Traversal_'+route+'.json')
    data=json.loads(report.read_text(encoding='utf-8'));stem=data['native_csv_basename']
    if not stem:raise RuntimeError('Route did not enter the walking phase')
    files=[f for f in (PROJECT/'Saved/Profiling').rglob(stem+'*') if f.is_file() and f.suffix in ('.csv','.gz')]
    if not files:raise FileNotFoundError('Native CSV not yet written for '+stem)
    detail=summarize(max(files,key=lambda f:f.stat().st_mtime))
    boot=data['startup']
    detail['runtime']={k:boot[k] for k in ('engine_version','viewport_px','r_screen_percentage','t_max_fps','render_cvars') if k in boot}
    detail['runtime']['route_completed']=data['status']=='passed'
    detail['runtime']['walk_distance_m']=data['walked_m']
    destination=REVIEW/('Performance_'+route+'.json')
    destination.write_text(json.dumps(detail,indent=2),encoding='utf-8')
    return detail

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument('route');args=parser.parse_args()
    print(json.dumps(capture(args.route),indent=2))
