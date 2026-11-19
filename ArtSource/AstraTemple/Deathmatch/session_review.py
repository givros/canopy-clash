"""Check native late join, capacity, bot replacement and friendly-fire scoring on loopback."""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("network_audit", ROOT / "Tools/Run-MatchAudit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def review():
    directory = ROOT / "Saved/Deathmatch" / ("Session_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    directory.mkdir(parents=True)
    project = audit.isolate(directory, freeze_assets=True)
    port = 18046
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", port))
    roles = {}
    outcomes = {}

    def log(role):
        path = directory / (role + ".log")
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def spawn(role, route, server=False, observer=None):
        options = [str(audit.ENGINE), str(project), route, "-server" if server else "-game",
                   "-NullRHI", "-RenderOffscreen", "-Unattended", "-NoSound", "-NoSplash",
                   "-NoLiveCoding", "-NoEpicPortal", "-NoCrashDialog", "-NoMessaging",
                   "-multihome=127.0.0.1", "-ExecCmds=t.MaxFPS 30", "-port=" + str(port),
                   "-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocol.ModelContextProtocolSettings]:bAutoStartServer=False",
                   "-AbsLog=" + str(directory / (role + ".log"))]
        if server or observer:
            options.append("-TempleMatchAudit="+("server" if server else observer))
        if not server:
            options.append("-TempleName="+("LateRanger" if role=="guest" else role))
        proc = subprocess.Popen(options, cwd=directory, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        roles[role] = proc
        print("Launched", role, proc.pid, flush=True)

    def until(label, criterion):
        deadline = time.monotonic() + 80
        while time.monotonic() < deadline:
            result = criterion()
            if result:
                outcomes[label] = result
                print(label, result, flush=True)
                return
            time.sleep(.4)
        raise RuntimeError("Timed out at " + label)

    def stop(role):
        proc = roles[role]
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=20)

    def snapshot(humans, after=0):
        rows = audit.records(directory / "server.log")
        for row in reversed(rows):
            if row[0] != "snapshot" or int(row[3]) != 2:
                continue
            stamp, red, blue, red_size, blue_size, count, links = float(row[4]), *map(int, row[5:11])
            if stamp > after and red_size == blue_size == 1 and count == links == humans:
                return {"seconds": stamp, "players": [red_size, blue_size], "humans": count,
                        "connections": links, "score": [red, blue]}

    def connect(role):
        spawn(role, f"127.0.0.1:{port}?Name={role}")

    def team_damage():
        for row in audit.records(directory / "friendly.log"):
            if row[0] != "friendly_enabled":
                continue
            before, damage, health = map(float, row[1:4])
            changes = list(map(int, row[4:]))
            if before > 0 and damage == before and health == 0 and changes == [0, 0, 0, 1]:
                return {"before": before, "damage": damage, "after": health,
                        "red_points": changes[0], "blue_points": changes[1],
                        "attacker_kills": changes[2], "victim_deaths": changes[3]}

    try:
        spawn("server", audit.MAP + "?TeamSize=1?ScoreLimit=500?TimeLimit=400", True)
        until("match_running_before_players", lambda: snapshot(0))
        connect("First")
        until("late_player_replaces_one_bot", lambda: snapshot(1))
        connect("Second")
        until("two_players_replace_both_bots", lambda: snapshot(2))
        connect("Overflow")
        until("full_session_rejects_third_player", lambda: "Server full." in log("Overflow"))
        stop("Overflow")
        when_full = outcomes["two_players_replace_both_bots"]["seconds"]
        stop("Second")
        until("departure_replaced_by_bot", lambda: snapshot(1, when_full))
        connect("Replacement")
        restored = outcomes["departure_replaced_by_bot"]["seconds"]
        until("replacement_joins_existing_match", lambda: snapshot(2, restored))
        for role in ("Replacement", "First", "server"):
            stop(role)
        spawn("friendly", audit.MAP + "?TeamSize=2?FriendlyFire=1?ScoreLimit=500", True)
        until("enabled_friendly_elimination", team_damage)
        stop("friendly")
        spawn("finished", audit.MAP + "?TeamSize=2?ScoreLimit=2?TimeLimit=120", True)

        def standings(role, round_number):
            return sorted(row[3:] for row in audit.records(directory/(role+".log"))
                          if row[0]=="final_row" and int(row[2])==round_number)

        until("botted_match_has_final_table", lambda: standings("finished",1) if len(standings("finished",1))==4 else None)
        spawn("guest", f"127.0.0.1:{port}?Name=LateRanger", observer="red")
        def viewer_id(round_number):
            return next((r[3] for r in audit.records(directory/"guest.log")
                         if r[0]=="final_viewer" and int(r[2])==round_number),None)
        def late_table():
            old=outcomes["botted_match_has_final_table"]
            seen=standings("guest",1)
            guest=viewer_id(1)
            if guest and int(guest)>=0 and seen==old and all(row[0]!=guest for row in seen):
                return {"identical_to_original":True,"players":len(seen),"late_viewer_id":guest}
        until("postmatch_guest_receives_original_table", late_table)
        def replay_table():
            seen=standings("guest",2)
            guest=viewer_id(2)
            if guest and len(seen)==4 and seen==standings("finished",2) and any(row[0]==guest for row in seen):
                return {"scores":seen,"guest_id_in_replayed_match":guest}
        until("replay_publishes_new_participants_and_scores", replay_table)
    finally:
        for role in roles:
            stop(role)
        report = {"passed": len(outcomes) == 10, "results": outcomes}
        (directory / "Session.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(directory, flush=True)


if __name__ == "__main__":
    review()
