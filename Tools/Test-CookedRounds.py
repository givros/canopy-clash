"""Run the cooked game's native menu cycle or eight-round lifetime check offscreen."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import runpy
import subprocess


ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "Saved/Deathmatch/Packaging"
LEVEL = "/Game/AstraTemple/Maps/L_CanopyDeathmatch"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("menu", "lifetime"))
    parser.add_argument("--build", type=Path, default=PACKAGING / "DevelopmentStage/Windows")
    args = parser.parse_args()
    executable = args.build.resolve() / "gameAstraForest/Binaries/Win64/gameAstraForest.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    folder = PACKAGING / (f"Cooked_{args.check}_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    folder.mkdir(parents=True)
    menu = args.check == "menu"
    game_options = ["?TeamSize=8?TimeLimit=24?ScoreLimit=50", f"-TempleUIAudit={folder/'UIAudit.json'}", "-NoSound"] if menu else [
        "?ScoreLimit=6?TimeLimit=18", f"-TempleLifetime={folder/'Lifetime.csv'}", "-DeterministicAudio"]
    width, height, fps, timeout = (1280, 720, 36, 135) if menu else (960, 540, 24, 300)
    command = [str(executable), LEVEL + game_options[0], *game_options[1:], f"-AbsLog={folder/'WindowsGame.log'}",
               "-RenderOffscreen", "-Windowed", "-ForceRes", f"-ResX={width}", f"-ResY={height}", "-NoSplash",
               "-NoCrashDialog", "-NoMessaging", "-Unattended", f"-SECONDS={timeout}",
               f"-ExecCmds=t.MaxFPS {fps},DisableAllScreenMessages"]
    print(folder, flush=True)
    result = subprocess.run(command, cwd=executable.parent, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout+55)
    if menu:
        native = json.loads((folder / "UIAudit.json").read_text(encoding="utf-8-sig"))
        passed_names = {item["name"] for item in native["checks"] if item["passed"]}
        required = {"match_clock_respects_start_and_expiry", "finished_match_owns_cursor_and_focus",
                    "completed_team_result_is_immutable", "pointer_restarts_match", "replay_clock_limited_to_countdown",
                    "replay_returns_focus_to_game", "quit_requests_native_process_exit"}
        passed = native["passed"] and required <= passed_names
        detail = {"checks": len(native["checks"]), "required_checks": sorted(required), "passed_checks": sorted(passed_names)}
    else:
        csv_path = folder / "Lifetime.csv"
        detail = runpy.run_path(str(ROOT / "Tools/Review-Lifetime.py"))["summarize"](csv_path)
        (folder / "Lifetime.json").write_text(json.dumps(detail, indent=2))
        passed = detail["passed"] and detail["checks"].get("one_muzzle_per_fighter_after_each_purge", False)
    summary = {"passed": bool(passed and result.returncode == 0), "native_exit": result.returncode, "source": str(executable),
               "evidence": str(folder), "result": detail}
    (folder / "Check.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({key: summary[key] for key in ("passed", "native_exit", "evidence")}))
    raise SystemExit(not summary["passed"])


if __name__ == "__main__":
    main()
