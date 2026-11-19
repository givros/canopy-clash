"""Exercise the private-match menu with two offscreen Unreal processes on one PC."""
import argparse
from datetime import datetime
import json
import ipaddress
import os
from pathlib import Path
import runpy
import socket
import subprocess
import time


ROOT = Path(__file__).resolve().parent.parent
HIDDEN = subprocess.CREATE_NO_WINDOW
FIELDS = ("reply", "mode", "endpoint", "roster", "humans", "menu", "private", "host", "join", "leave",
          "paused", "cursor", "feedback", "phase", "address_text")


class Peer:
    def __init__(self, folder, name, base, interface, port):
        self.folder = folder
        self.name = name
        self.command_file = folder / f"{name}.commands"
        self.state_file = folder / f"{name}.commands.state"
        self.sequence = 0
        self.process = subprocess.Popen([
            *base, "-RenderOffscreen", "-Windowed", "-ForceRes", "-ResX=960", "-ResY=540", "-NoSplash",
            "-NoLiveCoding", "-NoSound", "-NoAutosave", "-NoEpicPortal", "-NoCrashDialog", "-NoMessaging",
            "-Unattended", f"-MULTIHOME={interface}", f"-port={port}", f"-TempleName={name}",
            f"-TemplePrivateAudit={self.command_file}", f"-AbsLog={folder / (name + '.log')}",
            "-ExecCmds=t.MaxFPS 18,r.ScreenPercentage 50,DisableAllScreenMessages",
            "-ini:Engine:[/Script/gameAstraForest.TempleNetDriver]:InitialConnectTimeout=8.0",
            "-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocol.ModelContextProtocolSettings]:bAutoStartServer=False",
        ], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=HIDDEN)

    def state(self):
        try:
            values = self.state_file.read_text(encoding="utf-8-sig").split("|")
        except (FileNotFoundError, PermissionError):
            return {}
        return dict(zip(FIELDS, values)) if len(values) == len(FIELDS) else {}

    def wait(self, predicate, timeout=45):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.state()
            if state and predicate(state):
                return state
            if self.process.poll() is not None:
                raise RuntimeError(f"{self.name} exited with {self.process.returncode}, state {state}")
            time.sleep(.12)
        raise TimeoutError(f"{self.name} did not reach the required state: {self.state()}")

    def command(self, action, value=""):
        self.sequence += 1
        serial = str(self.sequence)
        draft = self.command_file.with_suffix(".tmp")
        draft.write_text(f"{serial}|{action}|{value}", encoding="utf-8")
        os.replace(draft, self.command_file)
        state = self.wait(lambda s: s["reply"].startswith(serial + ":"), timeout=12)
        if action == "escape":
            # Enhanced Input dispatches the viewport Escape binding on the next frame.
            return self.wait(lambda s: s["reply"].startswith(serial + ":") and s["menu"] == "1")
        if state["reply"] != serial + ":ok":
            raise RuntimeError(f"{self.name} could not {action} {value}: {state}")
        return state

    def private_page(self):
        state = self.wait(lambda s: s["roster"] == "10", timeout=105)
        if state["host"] == "1" or state["leave"] == "1":
            return state
        if state["menu"] == "0":
            self.command("escape")
        self.wait(lambda s: s["private"] == "1")
        self.command("click", "PrivateMatch")
        return self.wait(lambda s: s["host"] == "1" or s["leave"] == "1")

    def screenshot(self, title):
        self.command("capture", title)
        image = self.folder / f"{title}.png"
        deadline = time.monotonic() + 15
        while not image.exists() and time.monotonic() < deadline:
            time.sleep(.15)
        if not image.exists():
            raise RuntimeError(f"Missing native screenshot {image}")

    def stop(self):
        if self.process.poll() is not None:
            return
        try:
            self.command("stop")
            self.process.wait(timeout=55)
        except (OSError, RuntimeError, TimeoutError, subprocess.TimeoutExpired):
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=15)


def listen_addresses(port):
    query = f"Get-NetUDPEndpoint -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object LocalAddress"
    result = subprocess.run(["powershell", "-NoProfile", "-Command", query], capture_output=True, text=True,
                            creationflags=HIDDEN, timeout=15)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_recovery(host, guest, endpoint, port, connected, check):
    guest.private_page()
    guest.command("type", endpoint)
    guest.command("click", "JoinMatch")
    check("guest_rejoins_after_intentional_leave", guest.wait(connected, 80))
    host.private_page()
    host.command("click", "LeaveMatch")
    check("host_returns_to_solo_and_removes_listener", host.wait(lambda s: s["mode"] == "0" and s["humans"] == "1"))
    check("socket_released", not listen_addresses(port))
    check("guest_recovers_and_sees_connection_notice", guest.wait(
        lambda s: s["mode"] == "0" and s["menu"] == "1" and s["host"] == "1"
        and s["feedback"] == "Connection lost. Rejoin when the host returns.", 100))
    check("previous_host_address_retained_after_disconnect", guest.wait(lambda s: s["address_text"] == endpoint))
    guest.screenshot("HostDisconnected")
    time.sleep(2)
    after_loss = guest.state()
    check("loss_notice_stays_visible_during_pause", after_loss.get("paused") == "1"
          and after_loss.get("address_text") == endpoint and after_loss.get("feedback", "").startswith("Connection lost."))

    guest.command("click", "JoinMatch")
    check("closed_port_attempt_shows_connecting", guest.wait(lambda s: "connecting" in s["feedback"].lower()))
    check("closed_port_failure_reenables_form", guest.wait(
        lambda s: s["mode"] == "0" and s["join"] == "1"
        and s["feedback"] == "Host unavailable. Check the address and port.", 150))
    check("unavailable_host_address_retained_for_retry", guest.wait(lambda s: s["address_text"] == endpoint))
    guest.screenshot("HostUnavailable")
    time.sleep(2)
    after_failure = guest.state()
    check("unavailable_notice_stays_visible_during_pause", after_failure.get("paused") == "1"
          and after_failure.get("address_text") == endpoint and after_failure.get("feedback", "").startswith("Host unavailable."))
    host.private_page()
    host.command("click", "HostMatch")
    check("host_reopens_identical_local_endpoint", host.wait(lambda s: s["mode"] == "2" and s["endpoint"] == endpoint))
    guest.command("click", "JoinMatch")
    check("guest_reconnects_from_failure_screen", guest.wait(connected, 80))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, help="Cooked Development build directory, otherwise use an editor snapshot")
    parser.add_argument("--port", type=int, default=18007)
    parser.add_argument("--local-interface", default="127.0.0.1", help="A private IPv4 address assigned to this PC")
    args = parser.parse_args()
    ip = ipaddress.IPv4Address(args.local_interface)
    private_ranges = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    if str(ip) != "127.0.0.1" and not any(ip in ipaddress.IPv4Network(r) for r in private_ranges):
        parser.error("Choose loopback or a private IPv4 address assigned to this PC.")
    endpoint = f"{ip}:{args.port}"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind((str(ip), args.port))
    folder = ROOT / "Saved/Deathmatch/PrivateMenu" / datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True)
    if args.build:
        base = [str(args.build.resolve() / "gameAstraForest/Binaries/Win64/gameAstraForest.exe")]
    else:
        native = runpy.run_path(str(ROOT / "Tools/Run-MatchAudit.py"))
        project = native["isolate"](folder)
        base = [str(native["ENGINE"]), str(project), native["MAP"], "-game"]

    report = {"passed": False, "endpoint": endpoint, "checks": {}, "source": base[0]}
    peers = []

    def check(name, state):
        if not state:
            raise RuntimeError(name)
        report["checks"][name] = state
        print(name, flush=True)

    try:
        host = Peer(folder, "Fern", base, str(ip), args.port)
        peers.append(host)
        host.private_page()
        check("private_page_starts_from_paused_solo", host.wait(lambda s: s["mode"] == "0" and s["paused"] == "1" and s["join"] == "1"))
        # Both processes finish loading before a listener opens on a physical adapter.
        guest = Peer(folder, "Moss", base, str(ip), args.port)
        peers.append(guest)
        guest.private_page()
        host.command("click", "HostMatch")
        check("host_button_creates_unpaused_listen_game", host.wait(lambda s: s["mode"] == "2" and s["paused"] == "0" and s["endpoint"] == endpoint))
        check("os_socket_binds_only_to_selected_local_interface", listen_addresses(args.port) == [str(ip)])
        host.screenshot("HostOpen")
        guest.command("type", endpoint)
        guest.screenshot("GuestAddress")
        guest.command("click", "JoinMatch")
        connected = lambda s: s["mode"] == "3" and s["endpoint"] == endpoint and s["humans"] == "2" and s["roster"] == "10"
        check("typed_address_and_click_join_remote_world", guest.wait(connected, 80))
        check("host_sees_guest_replacing_bot", host.wait(lambda s: s["humans"] == "2" and s["roster"] == "10"))

        guest.private_page()
        guest.command("click", "LeaveMatch")
        check("guest_returns_to_solo_through_button", guest.wait(lambda s: s["mode"] == "0" and s["humans"] == "1" and s["roster"] == "10"))
        check("host_backfills_departed_guest", host.wait(lambda s: s["humans"] == "1" and s["roster"] == "10"))
        if ip.is_loopback:
            check_recovery(host, guest, endpoint, args.port, connected, check)
        else:
            host.private_page()
            host.command("click", "LeaveMatch")
            check("host_returns_to_solo_and_removes_listener", host.wait(lambda s: s["mode"] == "0" and s["humans"] == "1"))
            check("socket_released", not listen_addresses(args.port))
        report["passed"] = True
    except (OSError, RuntimeError, TimeoutError) as error:
        report["error"] = str(error)
    finally:
        for peer in reversed(peers):
            peer.stop()
        report["remaining_game_bindings"] = listen_addresses(args.port)
        report["process_exit_codes"] = {peer.name: peer.process.poll() for peer in peers}
        report["passed"] = report["passed"] and not report["remaining_game_bindings"] and all(
            status == 0 for status in report["process_exit_codes"].values())
        (folder / "PrivateMenu.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(folder / "PrivateMenu.json")
    raise SystemExit(not report["passed"])


if __name__ == "__main__":
    main()
