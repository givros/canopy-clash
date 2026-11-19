"""Read and verify the actual archived Unreal IoStore package and Windows executable."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--development-stage", type=Path, help="Compare the cooked containers from both staged configurations")
    options = arguments.parse_args()
    project = Path(__file__).resolve().parent.parent
    archive = project / "Builds/Windows"
    evidence = project / "Saved/Deathmatch/Packaging" / ("ArchiveContents_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    evidence.mkdir(parents=True)
    version = json.loads((project / "gameAstraForest.uproject").read_text(encoding="utf-8-sig"))["EngineAssociation"]
    tool = Path(os.environ["ProgramFiles"]) / "Epic Games" / ("UE_" + version) / "Engine/Binaries/Win64/UnrealPak.exe"
    data = archive / "gameAstraForest"
    index = data / "Content/Paks/gameAstraForest-Windows.utoc"
    inventory = evidence / "IoStore.csv"
    with (evidence / "UnrealPak.log").open("w", encoding="utf-8") as log:
        subprocess.run([str(tool), f"-ListContainer={index}", f"-Csv={inventory}", "-Unattended"],
                       stdout=log, stderr=subprocess.STDOUT, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        config_root = evidence / "PublishedConfig"
        subprocess.run([str(tool), str(index.with_suffix(".pak")), "-Extract", str(config_root),
                        "-Filter=*gameAstraForest/Config/DefaultGame.ini", "-Unattended"],
                       stdout=log, stderr=subprocess.STDOUT, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    shipped_config = (config_root / "gameAstraForest/Config/DefaultGame.ini").read_text(encoding="utf-8-sig")
    title = next((line.partition("=")[2].strip() for line in shipped_config.splitlines()
                  if line.strip().startswith("ProjectDisplayedTitle=")), "")
    with inventory.open(encoding="utf-8-sig", newline="") as source:
        entries = list(csv.DictReader(source, skipinitialspace=True))
    names = {item["Filename"].removeprefix("../../../gameAstraForest/Content/") for item in entries}
    maps = sorted(name for name in names if name.endswith(".umap") and not name.startswith("../"))
    required = {
        "Rules": ["BP_CanopyDeathmatch", "BP_CanopyRanger", "BP_CanopyBot"],
        "Animation": ["ABP_TempleArms", "ABP_TempleBody", "SKM_TempleArms", "M_TempleSleeveLining"],
        "Presentation": ["SKM_CanopyReceiver", "SM_CanopyMagazine"],
        "Feedback": ["NS_CarbineMuzzle", "NS_CarbineContact", "M_CarbineSpark", "M_CarbineTrace",
                     "SM_CarbineTrace", "S_CarbineCycle", "S_TagConfirm", "S_CanopyReport"],
        "Feedback/Footsteps": [f"S_Step{surface}{number:02d}" for surface in ("Stone", "Forest") for number in range(1, 4)],
    }
    assets = {f"TempleTDM/{folder}/{name}.uasset": f"TempleTDM/{folder}/{name}.uasset" in names
              for folder, contents in required.items() for name in contents}
    shaders = sorted(name for name in names if name.startswith("ShaderArchive-gameAstraForest-"))
    exe = data / "Binaries/Win64/gameAstraForest-Win64-Shipping.exe"
    hashes = {}
    for item in (archive / "gameAstraForest.exe", exe, index, index.with_suffix(".ucas"), index.with_suffix(".pak")):
        with item.open("rb") as stream:
            hashes[str(item.relative_to(archive))] = hashlib.file_digest(stream, "sha256").hexdigest()
    shared_containers = {}
    if options.development_stage:
        for item in sorted([*index.parent.glob("*.utoc"), *index.parent.glob("*.ucas")]):
            development = options.development_stage / item.relative_to(archive)
            with item.open("rb") as shipping_file, development.open("rb") as development_file:
                shared_containers[item.name] = (hashlib.file_digest(shipping_file, "sha256").digest()
                                                == hashlib.file_digest(development_file, "sha256").digest())
    source_map = project / "Content/AstraTemple/Maps/L_CanopyDeathmatch.umap"
    with source_map.open("rb") as source:
        source_hash = hashlib.file_digest(source, "sha256").hexdigest()
    binary = exe.read_bytes()
    development_flags = ["TempleMatchAudit=", "TemplePrivateAudit=", "TempleLifetime=", "TempleUIAudit=", "TempleCapture="]
    dev_markers = {flag: flag.encode("utf-16-le") in binary or flag.encode("ascii") in binary for flag in development_flags}
    files = [item for item in archive.rglob("*") if item.is_file()]
    result = {
        "passed": maps == ["AstraTemple/Maps/L_CanopyDeathmatch.umap"] and all(assets.values())
                  and all(any(shader in name for name in shaders) for shader in ("PCD3D_SM5", "PCD3D_SM6"))
                  and not any(dev_markers.values()) and title == 'INVTEXT("Canopy Clash")'
                  and all(shared_containers.values()),
        "archive": str(archive), "bootstrap": str(archive / "gameAstraForest.exe"), "native_executable": str(exe),
        "bytes": sum(item.stat().st_size for item in files), "file_count": len(files),
        "iostore_entries": len(entries), "project_maps": maps, "gameplay_assets": assets, "shaders": shaders,
        "archived_project_displayed_title": title,
        "source_level_sha256_at_inspection": source_hash, "identical_development_containers": shared_containers,
        "development_instrumentation_markers": dev_markers, "sha256": hashes,
    }
    report = evidence / "Contents.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(report)
    print(json.dumps({key: result[key] for key in ("passed", "bytes", "file_count", "iostore_entries", "project_maps")}))
    raise SystemExit(not result["passed"])


if __name__ == "__main__":
    main()
