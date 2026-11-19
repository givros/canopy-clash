"""Summarize the cooked -TempleLifetime=<path.csv> replay and garbage-collection soak."""
import argparse
import csv
import json
from pathlib import Path
import re
import statistics


def render_resource_samples(log):
    if not log.is_file():
        return []
    samples = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        replay = re.search(r"TempleLifetime_RHI after replay (\d+)", line)
        if replay:
            samples.append({"round": int(replay.group(1)), "resource_categories_mib": {}})
            continue
        if not samples:
            continue
        resource = re.search(r"([\d.]+)MB\s+-\s+(.+?)\s+-\s+STAT_\w+\s+-\s+STATGROUP_RHI", line)
        if resource:
            samples[-1]["resource_categories_mib"][resource.group(2)] = float(resource.group(1))
    return samples


def summarize(path):
    with path.open(encoding="utf-8-sig", newline="") as data:
        samples = [
            {key: value if key == "stage" else float(value) for key, value in row.items()}
            for row in csv.DictReader(data)
        ]
    rounds = [row for row in samples if row["stage"] == "match_end"]
    resets = [row for row in samples if row["stage"] == "replay_pre_gc"]
    post_gc = [row for row in samples if row["stage"] == "replay_post_gc"]
    if not post_gc:
        raise ValueError("No completed garbage-collection samples found.")

    retained = [
        "fighters", "bots", "humans", "player_states", "huds", "user_widgets", "widgets",
        "niagara", "active_niagara", "audio_components", "skinned_components", "static_components",
        "fighter_dynamic_materials", "global_objects", "working_set_mib", "private_commit_mib",
    ]
    if "active_mixer_sounds" in post_gc[0]:
        retained.append("active_mixer_sounds")
    if "ue_heap_mib" in post_gc[0]:
        retained.extend(["ue_heap_mib", "ue_heap_reserved_mib"])
    if "muzzles" in post_gc[0]:
        retained.extend(["muzzles", "muzzle_owners", "active_muzzles", "unowned_muzzles",
                         "retired_muzzles_still_allocated"])
    ranges = {}
    for metric in retained:
        values = [row[metric] for row in post_gc]
        warm = values[2:]
        ranges[metric] = {
            "all_eight": values, "min": min(values), "max": max(values),
            "rounds_3_to_8_net_change": round(warm[-1] - warm[0], 2) if warm else None,
            "rounds_3_to_8_slope_per_round": round(statistics.linear_regression(range(len(warm)), warm).slope, 3)
            if len(warm) >= 2 else None,
        }
    checks = {
        "eight_matches_and_full_purges": len(samples) == 24 and len(rounds) == len(resets) == len(post_gc) == 8,
        "natural_combat": all(row["phase"] == 3 and row["red"] + row["blue"] > 0 for row in rounds),
        "scores_and_countdowns_reset": all(row["red"] == row["blue"] == 0 and row["phase"] == 1 for row in resets),
        "previous_fighters_freed_after_each_purge": all(row["retired_pawns_still_allocated"] == 0 for row in post_gc),
        "fixed_5v5_roster": all(row["fighters"] == row["player_states"] == 10 and row["bots"] == 9 and row["humans"] == 1 for row in post_gc),
        "one_hud_tree_per_round": all(row["huds"] == row["user_widgets"] == 1 for row in post_gc)
                                  and len({row["widgets"] for row in post_gc}) == 1,
        "menus_and_scoreboards_exercised": all(row["opened_menu"] == row["opened_roster"] == 1 for row in rounds),
        "combat_effects_exercised": all(row["peak_active_niagara"] > 0 for row in rounds),
    }
    if "final_standings" in post_gc[0]:
        checks["result_snapshots_cleared"] = all(row["final_standings"] == 10 for row in rounds) and all(
            row["final_standings"] == 0 for row in post_gc
        )
    if "muzzles" in post_gc[0]:
        checks["one_muzzle_per_fighter_after_each_purge"] = all(
            row["muzzles"] == row["muzzle_owners"] == row["fighters"] and row["unowned_muzzles"] == 0
            for row in post_gc)
        checks["no_retired_muzzle_or_active_flash_after_each_purge"] = all(
            row["retired_muzzles_still_allocated"] == row["active_muzzles"] == 0 for row in post_gc)
        checks["muzzle_fired_without_duplicate_components"] = any(row["peak_active_muzzles"] > 0 for row in rounds) and all(
            row["peak_duplicate_muzzles"] == 0 for row in rounds)
        checks["displayed_clock_bound_in_all_rounds"] = all(0 < row["highest_active_clock"] <= row["round_duration"] for row in rounds)
    return {
        "passed": all(checks.values()), "checks": checks, "csv": str(path.resolve()),
        "final_scores": [[int(row["red"]), int(row["blue"])] for row in rounds],
        "peak_active_niagara_per_round": [int(row["peak_active_niagara"]) for row in rounds],
        "peak_active_muzzles_per_round": [int(row["peak_active_muzzles"]) for row in rounds if "peak_active_muzzles" in row],
        "other_niagara_after_gc": [int(row["niagara"] - row["muzzles"]) for row in post_gc if "muzzles" in row],
        "retired_pawns_after_gc": [int(row["retired_pawns_still_allocated"]) for row in post_gc],
        "post_gc": ranges,
        "post_gc_render_resources": render_resource_samples(path.with_name("WindowsGame.log")),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    report = summarize(args.csv)
    args.csv.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": report["checks"], "final_scores": report["final_scores"]}, indent=2))
    raise SystemExit(not report["passed"])
