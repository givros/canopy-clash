"""Verify the archived Shipping game's default match using a local cooked Development client."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import socket
import subprocess
import time


PROJECT = Path(__file__).resolve().parent.parent
PACKAGING = PROJECT / "Saved/Deathmatch/Packaging"
HIDDEN = subprocess.CREATE_NO_WINDOW


def start_game(executable, options):
    directory = executable.parent / "gameAstraForest/Binaries/Win64"
    native = directory / "gameAstraForest-Win64-Shipping.exe"
    if not native.is_file():
        native = directory / "gameAstraForest.exe"
    return subprocess.Popen(
        [str(native), *options], cwd=executable.parent, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=HIDDEN | subprocess.BELOW_NORMAL_PRIORITY_CLASS,
    )


def listening_process(port):
    query = (
        f"$socket=Get-NetUDPEndpoint -LocalPort {port} -ErrorAction SilentlyContinue; "
        "foreach($item in $socket){$process=Get-Process -Id $item.OwningProcess;"
        "[pscustomobject]@{address=$item.LocalAddress;pid=$process.Id;path=$process.Path}|ConvertTo-Json -Compress}"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", query], capture_output=True, text=True,
        creationflags=HIDDEN, timeout=12,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def stop_game(process):
    if process and process.poll() is None:
        # A direct native process handle scopes shutdown to this test, even if OS discovery is busy.
        process.terminate()
        process.wait(timeout=20)


def read_rows(path):
    if not path.exists():
        return []
    return [
        line.split("TQA|", 1)[1].split("|")
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if "LogTempleAudit:" in line and "TQA|" in line
    ]


def metrics(rows):
    rounds = [r for r in rows if r[0] == "phase"]
    end = next((r for r in rounds if r[2:4] == ["1", "3"]), None)
    roster = next((r for r in rows if r[0] == "snapshot" and r[7:11] == ["5", "5", "2", "1"]), None)
    return {
        "two_humans_in_five_per_side": bool(roster),
        "legitimate_eliminations": len([r for r in rows if r[0] == "kill" and r[2] == "1" and r[6] != r[7]]),
        "first_round_score": [int(end[5]), int(end[6])] if end else None,
        "first_round_winner": int(end[7]) if end else None,
        "default_score_limit": int(end[8]) if end else None,
        "requested_replay": any(r[0] == "replay_rpc" for r in rows),
        "reset_to_zero": any(r[2] == "2" and r[3] in ["1", "2"] and r[5:7] == ["0", "0"] for r in rounds),
        "second_round_frag": any(r[0] == "kill" and r[2] == "2" for r in rows),
        "team_change": any(r[0] == "team_rpc" and r[2] != r[3] for r in rows),
    }


def verify_shipping_guest(development, shipping, standard, port, out):
    log = out / "ObserverOfShippingPeers.log"
    host = first_guest = second_guest = observer = None
    observed = False
    expected = {"Mosskeeper", "Ranger", "Ranger 2", "Marshlight"}
    try:
        host = start_game(shipping, [*standard, "-TempleHost", "-TempleName=Mosskeeper"])
        deadline = time.monotonic() + 60
        endpoint = []
        while not endpoint and time.monotonic() < deadline and host.poll() is None:
            endpoint = listening_process(port)
            if not endpoint:
                time.sleep(.5)
        if len(endpoint) != 1 or endpoint[0]["address"] != "127.0.0.1":
            return False
        if not Path(endpoint[0]["path"]).resolve().is_relative_to(shipping.parent):
            return False
        first_guest = start_game(shipping, [*standard, "-TempleJoin"])
        second_guest = start_game(shipping, [*standard, "-TempleJoin"])
        observer = start_game(development, [
            *standard, "-TempleJoin", "-TempleName=Marshlight", "-TempleInspectNames", "-TempleMatchAudit=blue", f"-AbsLog={log}",
        ])
        while time.monotonic() < deadline and all(p.poll() is None for p in (first_guest, second_guest, observer)):
            rows = read_rows(log)
            names = {r[3] for r in rows if r[0] == "human_name"}
            observed = expected.issubset(names) and any(r[0] == "snapshot" and r[7:11] == ["5", "5", "4", "1"] for r in rows)
            if observed:
                break
            time.sleep(1)
    finally:
        stop_game(observer)
        stop_game(second_guest)
        stop_game(first_guest)
        stop_game(host)
    (out / "PeerNames.json").write_text(json.dumps({"passed": observed, "required": sorted(expected),
        "observed": sorted({r[3] for r in read_rows(log) if r[0] == "human_name"})}, indent=2))
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shipping", type=Path, default=PROJECT / "Builds/Windows")
    parser.add_argument("--development", type=Path, default=PACKAGING / "DevelopmentStage/Windows")
    parser.add_argument("--port", type=int, default=17993)
    parser.add_argument("--timeout", type=int, default=840)
    args = parser.parse_args()
    shipping = args.shipping.resolve() / "gameAstraForest.exe"
    client_exe = args.development.resolve() / "gameAstraForest.exe"
    for executable in (shipping, client_exe):
        if not executable.is_file():
            raise FileNotFoundError(executable)

    out = PACKAGING / ("ShippingMatch_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    out.mkdir(parents=True)
    log = out / "RemoteClient.log"
    standard = ["-RenderOffscreen", "-Windowed", "-Unattended", "-NoSound", "-NoSplash",
                "-NoCrashDialog", "-NoMessaging", "-NullRHI", f"-port={args.port}"]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as check:
        check.bind(("127.0.0.1", args.port))

    host = client = None
    endpoint = []
    error = None
    started = time.monotonic()
    try:
        host = start_game(shipping, [*standard, "-TempleHost"])
        while time.monotonic() - started < 110:
            if host.poll() is not None:
                raise RuntimeError(f"Shipping bootstrap exited with {host.returncode}.")
            endpoint = listening_process(args.port)
            if endpoint:
                break
            time.sleep(1)
        if len(endpoint) != 1 or endpoint[0]["address"] != "127.0.0.1":
            raise RuntimeError(f"Expected one loopback game socket, got {endpoint}.")
        if not Path(endpoint[0]["path"]).resolve().is_relative_to(shipping.parent):
            raise RuntimeError("Socket owner is outside the Shipping archive.")
        print("Shipping socket verified", endpoint, flush=True)
        client = start_game(client_exe, [*standard, "-TempleJoin", "-TempleMatchAudit=red", f"-AbsLog={log}"])
        while time.monotonic() - started < args.timeout:
            if metrics(read_rows(log))["second_round_frag"]:
                break
            if host.poll() is not None or client.poll() is not None:
                raise RuntimeError("A game instance exited before completing the replay.")
            time.sleep(2)
    except (OSError, ValueError, RuntimeError) as problem:
        error = str(problem)
    finally:
        stop_game(client)
        stop_game(host)

    result = metrics(read_rows(log))
    result["shipping_guest_joined"] = not error and verify_shipping_guest(client_exe, shipping, standard, args.port, out)
    score = result["first_round_score"]
    correct_winner = bool(score and 50 in score and result["first_round_winner"] == int(score[1] > score[0]))
    checks = [not error, bool(endpoint), result["two_humans_in_five_per_side"], correct_winner,
              result["default_score_limit"] == 50, result["legitimate_eliminations"] > 0,
              result["team_change"], result["requested_replay"], result["reset_to_zero"], result["second_round_frag"],
              result["shipping_guest_joined"]]
    report = dict(passed=all(checks), error=error, shipping_executable=str(shipping), observer_executable=str(client_exe),
                  endpoint=endpoint, default_map="L_CanopyDeathmatch", seconds=round(time.monotonic() - started, 1),
                  observations=result, network_errors=[])
    if log.exists():
        report["network_errors"] = [line[-220:] for line in log.read_text(errors="replace").splitlines()
                                    if re.search(r"NetFailure|LogNet: Error:|TravelFailure|Fatal error:", line)][:12]
    report["passed"] = report["passed"] and not report["network_errors"]
    (out / "ShippingMatch.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
