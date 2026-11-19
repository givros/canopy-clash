"""Capture the normal first-person view from the cooked Development game."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageStat


PROJECT = Path(__file__).resolve().parent.parent
PACKAGING = PROJECT / "Saved/Deathmatch/Packaging"
NATIVE_MARKERS = {
    "canopy_deathmatch": r"Bringing World [^\r\n]*L_CanopyDeathmatch[^\r\n]* up for play",
    "native_game_mode": r"Game class is 'BP_CanopyDeathmatch_C'",
    "native_screenshot_complete": r"TQA\|packaged_capture\|complete",
}
RUNTIME_ERROR = re.compile(
    r"Fatal error:|GPU Crashed|Log(?:Streaming|ShaderLibrary|Linker|Windows): Error:"
    r"|LogUObjectGlobals: Warning: Failed to find object[^\r\n]*/Game/"
    r"|Material with missing usage flag was applied to skeletal mesh /Game/"
)


def analyze_boot(log_path, screenshot):
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    teams = re.findall(r"TemplePlayerState_[^\s.]+\.Team = (\d+)", log)
    health = [float(value) for value in re.findall(r"BP_CanopyRanger_C_[^\s.]+\.Health = (\d+(?:\.\d+)?)", log)]
    phase = re.search(r"TempleGameState_[^\s.]+\.Phase = (\d+)", log)
    scores = re.findall(r"TempleGameState_[^\s.]+\.(RedScore|BlueScore) = (\d+)", log)
    game_window_titles = re.findall(r"LogSlate: Request Window '([^']+)' being destroyed", log)
    baked_paths = [{"team": int(team), "route": int(route), "filter": route_filter, "complete": full == "1",
                    "enemy_samples": int(inside), "length_m": float(length)}
                   for team, route, route_filter, full, inside, length in
                   re.findall(r"TQA\|baked_route\|(\d)\|(\d)\|(\w+)\|(\d)\|(\d+)\|([\d.]+)", log)]
    dimensions = None
    deviation = 0
    if screenshot.is_file():
        with Image.open(screenshot) as image:
            dimensions = list(image.size)
            deviation = ImageStat.Stat(image.convert("L")).stddev[0]
    return {
        "native_observations": {key: bool(re.search(regex, log)) for key, regex in NATIVE_MARKERS.items()},
        "players_by_team": [teams.count("0"), teams.count("1")],
        "health_samples": health,
        "phase": int(phase.group(1)) if phase else None,
        "native_window_titles": game_window_titles,
        "baked_paths": baked_paths,
        "score": {team: int(score) for team, score in scores},
        "actual_pixels": dimensions,
        "luminance_standard_deviation": round(deviation, 2),
        "asset_or_render_errors": [line[-300:] for line in log.splitlines() if RUNTIME_ERROR.search(line)][:22],
        "engine_tool_registration_warnings": sum(
            "no baked manifest" in line and "LogToolsetRegistry: Warning:" in line for line in log.splitlines()
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=PACKAGING / "DevelopmentStage/Windows")
    executable = parser.parse_args().build.resolve() / "gameAstraForest.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    evidence = PACKAGING / ("PackagedBoot_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    evidence.mkdir(parents=True)
    log_path = evidence / "WindowsGame.log"
    screenshot = evidence / "FirstPersonHUD.png"
    options = [
        str(executable), "-RenderOffscreen", "-Windowed", "-ResX=1280", "-ResY=720", "-ForceRes",
        "-NoSound", "-NoSplash", "-NoLiveCoding", "-Unattended", "-NoCrashDialog", "-NoEpicPortal",
        "-NoMessaging", "-MULTIHOME=127.0.0.1", "-SECONDS=28", f"-AbsLog={log_path}",
        "-ExecCmds=t.MaxFPS 30,DisableAllScreenMessages", f"-TempleCapture={screenshot.as_posix()}",
    ]
    process = subprocess.run(
        options, cwd=executable.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=260, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    report = analyze_boot(log_path, screenshot)
    paths = report["baked_paths"]
    report["passed"] = all([
        process.returncode == 0, all(report["native_observations"].values()), report["players_by_team"] == [5, 5],
        len(report["health_samples"]) >= 8, report["phase"] == 2, len(report["score"]) == 2,
        report["actual_pixels"] == [1280, 720], report["luminance_standard_deviation"] > 10,
        any(title == "Canopy Clash" or title.startswith("Canopy Clash (") for title in report["native_window_titles"]),
        {(p["team"], p["route"]) for p in paths} == {(team, route) for team in range(2) for route in range(3)},
        all(p["complete"] and p["enemy_samples"] == 0 and p["length_m"] > 0 and
            p["filter"] == ("TempleRedRouteFilter", "TempleBlueRouteFilter")[p["team"]] for p in paths),
        not report["asset_or_render_errors"],
    ])
    report.update(exit_code=process.returncode, launch_executable=str(executable), screenshot=str(screenshot), log=str(log_path))
    output = json.dumps(report, indent=2)
    (evidence / "Result.json").write_text(output, encoding="utf-8")
    print(output)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
