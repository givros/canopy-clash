"""Run a dedicated Team Deathmatch server and two real clients on Windows loopback."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time

PROJECT_ROOT=Path(__file__).resolve().parent.parent
PROJECT=PROJECT_ROOT/'gameAstraForest.uproject'
ENGINE=Path(os.environ['ProgramFiles'])/'Epic Games'/('UE_'+json.loads(PROJECT.read_text(encoding='utf-8-sig'))['EngineAssociation'])/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
MAP='/Game/AstraTemple/Maps/L_CanopyDeathmatch'

def isolate(folder, freeze_assets=False):
    """Freeze only the loaded DLL and settings so subsequent project links stay available."""
    root=folder/'Runtime';root.mkdir()
    shutil.copy2(PROJECT,root/PROJECT.name)
    shutil.copytree(PROJECT_ROOT/'Config',root/'Config')
    dest=root/'Binaries/Win64';dest.mkdir(parents=True)
    for name in ('UnrealEditor-gameAstraForest.dll','UnrealEditor.modules','UnrealEditor.uclasses','gameAstraForestEditor.target'):
        shutil.copy2(PROJECT_ROOT/'Binaries/Win64'/name,dest/name)
    if freeze_assets:
        shutil.copytree(PROJECT_ROOT/'Content',root/'Content')
    else:
        subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(root/'Content'),str(PROJECT_ROOT/'Content')],stdout=subprocess.DEVNULL,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return root/PROJECT.name

def records(path,token="TQA"):
    if not path.exists():return []
    return [line.split(token+'|',1)[1].split('|') for line in path.read_text(encoding='utf-8',errors='replace').splitlines() if token+'|' in line and ('LogTempleAudit:' in line or 'LogTempleDuel:' in line)]

def summarize_duel(folder,bindings):
    data={r:records(folder/(r+'.log'),'TQD') for r in ('server','shooter','target')}
    hits=[r for r in data['server'] if r[0]=='hit']
    server=next((r for r in data['server'] if r[0]=='respawn'),None)
    frag=next((r for r in data['shooter'] if r[0]=='frag'),None)
    client=next((r for r in data['target'] if r[0]=='respawn'),None)
    checks={
        'loopback_only':bindings==['127.0.0.1'],
        'both_remote_clients_completed':all(any(v[:2]==['done',k] for v in d) for k,d in data.items()),
        'real_carbine_damage':len(hits)>=2 and float(hits[0][3])==100 and float(hits[-1][4])==0,
        'body_and_head_damage':{24.,48.}.issubset({float(r[3])-float(r[4]) for r in hits}),
        'victim_received_replicated_damage':bool(client and float(client[2])==0 and float(client[3])==100 and int(client[4])==1),
        'server_respawned_safely':bool(server and float(server[2])==100 and int(server[3])==1 and int(server[4])==1),
        'attacker_received_credit':bool(frag and int(frag[2])==1 and int(frag[3])<30),
    }
    flick=next((r for r in data['shooter'] if r[0]=='turn_and_tap'),None)
    if flick:
        checks['same_frame_turn_and_tap_connects']=float(flick[2])==76 and int(flick[3])==29
    report=dict(passed=all(checks.values()),checks=checks,events=data,loopback_binding=bindings)
    (folder/'DuelAudit.json').write_text(json.dumps(report,indent=2));return report

def summarize(folder,bindings):
    all_roles={r:records(folder/(r+'.log')) for r in ('server','red','blue')}
    checks={};report={'loopback_binding':bindings,'roles':{}}
    final={}
    for role,rows in all_roles.items():
        phases=[dict(round=int(r[2]),phase=int(r[3]),clock=float(r[4]),red=int(r[5]),blue=int(r[6]),winner=int(r[7]),limit=int(r[8])) for r in rows if r[0]=='phase']
        results=[a for a in phases if a['phase']==3]
        final[role]=[(a['round'],a['red'],a['blue'],a['winner']) for a in results]
        controls=next((r for r in rows if r[0]=='controls'),None)
        snaps=[r for r in rows if r[0]=='snapshot']
        kills=[r for r in rows if r[0]=='kill']
        checks[role+'_completed']=any(r[:2]==['done',role] for r in rows)
        checks[role+'_two_rounds']=len(results)==2 and any(a['round']==2 and a['phase'] in (1,2) and a['red']==a['blue']==0 for a in phases)
        checks[role+'_full_rosters']=any(int(r[7])==int(r[8])==5 and int(r[10])==(2 if role=='server' else 1) for r in snaps)
        checks[role+'_correct_winners']=len(results)==2 and all(a['winner']==(255 if a['red']==a['blue'] else int(a['blue']>a['red'])) for a in results)
        role_report={'phase_changes':phases,'feed_events':len(kills),'last_snapshot':snaps[-1] if snaps else None}
        if role!='server':
            team=next((r for r in rows if r[0]=='team_rpc'),None)
            checks[role+'_team_rpc']=bool(team and team[2]!=team[3])
            valid=bool(controls)
            if controls:
                ammo,lowest,after,reserve,reserv_after,aim,reload,board=map(int,controls[2:10]);distance=float(controls[10])
                valid=ammo-lowest in range(2,9) and after==ammo and reserv_after==reserve-(ammo-lowest) and aim and reload and board and distance>5
                role_report['controls']=dict(initial_ammo=ammo,lowest_ammo=lowest,reloaded=after,reserve_before=reserve,reserve_after=reserv_after,ads=bool(aim),reload=bool(reload),scoreboard=bool(board),movement_cm=distance)
            checks[role+'_replicated_controls']=bool(valid)
        report['roles'][role]=role_report
    authority=all_roles['server'];events=[r for r in authority if r[0]=='kill']
    checks['matched_remote_results']=bool(final['server'] and final['server']==final['red']==final['blue'])
    checks['loopback_only']=bool(bindings) and all(addr=='127.0.0.1' for addr in bindings)
    checks['real_enemy_eliminations']=len(events)>0 and all(r[6]!=r[7] for r in events)
    friend=next((r for r in authority if r[0]=='friendly_probe'),None)
    checks['friendly_fire_blocked']=bool(friend and float(friend[1])==float(friend[2]) and float(friend[3])==0. and int(friend[4])==0)
    respawns=[r for r in authority if r[0]=='respawn'];checks['respawn_after_delay']=len(respawns)>0 and all(float(r[4])>=float(r[3])-.18 for r in respawns)
    motion=next((r for r in authority if r[0]=='movement'),None);checks['agents_moved']=bool(motion and int(motion[1])>=6 and float(motion[2])>15)
    phase_ends=[r for r in report['roles']['server']['phase_changes'] if r['phase']==3]
    modes=[]
    for p in phase_ends:
        if max(p['red'],p['blue'])>=p['limit']:modes.append('score')
        else:
            active=next((r for r in authority if r[0]=='snapshot' and int(r[2])==p['round'] and int(r[3])==2),None)
            modes.append('timer' if active and p['clock']>=float(active[12])-.25 else 'other')
    checks['both_round_end_conditions']=set(modes)=={'timer','score'}
    checks['client_requested_replay']=any(r[:2]==['replay_rpc','red'] for r in all_roles['red'])
    report.update(checks=checks,passed=all(checks.values()),result_modes=modes,respawns=len(respawns),friendly_probe=friend,movement=motion)
    (folder/'MatchAudit.json').write_text(json.dumps(report,indent=2))
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--port',type=int,default=17991)
    ap.add_argument('--timeout',type=int,default=900);ap.add_argument('--score-limit',type=int);ap.add_argument('--time-limit',type=int);ap.add_argument('--duel',action='store_true')
    ap.add_argument('--flick',action='store_true',help='Turn 85 degrees and tap in one client frame')
    ap.add_argument('--packet-lag',type=int,default=0,help='Delay each outgoing packet by this many milliseconds')
    a=ap.parse_args()
    if a.flick:a.duel=True
    folder=PROJECT_ROOT/'Saved/Deathmatch'/('DuelAudit' if a.duel else 'NetworkAudit')/datetime.now().strftime('%Y%m%d_%H%M%S');folder.mkdir(parents=True)
    runtime=isolate(folder,freeze_assets=True)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as check:check.bind(('127.0.0.1',a.port))
    standard=['-NullRHI','-RenderOffscreen','-Unattended','-NoSound','-NoSplash','-NoLiveCoding','-NoAutosave','-NoSourceControl','-NoEpicPortal','-NoCrashDialog','-NoMessaging','-MULTIHOME=127.0.0.1','-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocol.ModelContextProtocolSettings]:bAutoStartServer=False']
    procs={}
    def spawn(role,route,mode):
        flag='-TempleDuel=' if a.duel else '-TempleMatchAudit='
        options=[str(ENGINE),str(runtime),route,mode,*standard,flag+role,'-AbsLog='+str(folder/(role+'.log')),'-ExecCmds=t.MaxFPS 30']
        if a.flick:options.append('-TempleFlick')
        if a.packet_lag:options.append('-PktLag='+str(a.packet_lag))
        if role=='server':options.append('-port='+str(a.port))
        p=subprocess.Popen(options,cwd=PROJECT_ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        procs[role]=p;return p
    limit=time.monotonic()+a.timeout;bind=[]
    try:
        route=MAP
        if a.duel:route+='?TeamSize=1?ScoreLimit=12?TimeLimit=150'
        if a.score_limit:route+='?ScoreLimit='+str(a.score_limit)
        if a.time_limit:route+='?TimeLimit='+str(a.time_limit)
        srv=spawn('server',route,'-server');print('Dedicated process',srv.pid,folder,flush=True)
        while time.monotonic()<limit:
            if srv.poll() is not None:raise RuntimeError('Dedicated process exited before accepting clients.')
            log=folder/'server.log'
            if log.exists() and re.search(r'listening on port\s+'+str(a.port),log.read_text(errors='replace'),re.I):break
            time.sleep(1)
        cmd=f"(Get-NetUDPEndpoint -OwningProcess {srv.pid} -LocalPort {a.port} -ErrorAction SilentlyContinue).LocalAddress"
        q=subprocess.run(['powershell','-NoProfile','-Command',cmd],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
        bind=[s.strip() for s in q.stdout.splitlines() if s.strip()]
        if bind!=['127.0.0.1']:raise RuntimeError('Dedicated game socket did not bind exclusively to loopback: '+str(bind))
        for role in (('shooter','target') if a.duel else ('red','blue')):
            spawn(role,f'127.0.0.1:{a.port}?Name=Audit{role.title()}','-game')
        print('Server socket and client processes',bind,{key:p.pid for key,p in procs.items()},flush=True)
        while time.monotonic()<limit and any(p.poll() is None for p in procs.values()):
            for role,p in procs.items():
                if p.poll() is not None and not any(r[:2]==['done',role] for r in records(folder/(role+'.log'),'TQD' if a.duel else 'TQA')):
                    raise RuntimeError(role+' exited before finishing the match audit')
            time.sleep(2)
    finally:
        for p in procs.values():
            if p.poll() is None:p.terminate()
        for p in procs.values():p.wait(timeout=20)
        report=(summarize_duel if a.duel else summarize)(folder,bind)
        print(json.dumps(dict(passed=report['passed'],results=report.get('result_modes'),checks=report['checks'],folder=str(folder))),flush=True)
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
