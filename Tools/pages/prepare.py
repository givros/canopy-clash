"""Prepare an Unreal Wasm stage for a static host without custom headers."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from iostore import pack_container


CHUNK_BYTES = 8 * 1024 * 1024
SITE_BUDGET = 1_000_000_000
INVENTORY = "pages-release.json"


def replace_once(text, old, new, filename):
    if text.count(old) != 1:
        raise ValueError(f"Unexpected Unreal template in {filename}: {old}")
    return text.replace(old, new)


def pack_module(source, site):
    segments = []
    pieces = []
    logical = 0
    with source.open("rb") as stream:
        while (block := stream.read(CHUNK_BYTES)):
            packed = gzip.compress(block, compresslevel=9, mtime=0)
            name = "blobs/" + hashlib.sha256(packed).hexdigest() + ".gzip.bin"
            (site / name).write_bytes(packed)
            segments.append([logical, len(pieces), 0])
            pieces.append(name)
            logical += len(block)
    return {"size": logical, "segments": segments, "pieces": pieces}


def prepare(stage, site):
    manifest = json.loads((stage / "wasm-cache.json").read_text(encoding="utf-8"))
    entries = {entry["url"]: entry for entry in manifest}
    virtual = {}
    (site / "blobs").mkdir()
    for source in sorted(stage.rglob("*")):
        if not source.is_file():
            continue
        path = source.relative_to(stage).as_posix()
        if source.suffix == ".br" or path == "_headers":
            continue
        entry = entries.get(path)
        if source.suffix == ".wasm" or (source.suffix == ".ucas" and source.stat().st_size >= CHUNK_BYTES):
            if not entry:
                raise ValueError(f"Missing Unreal cache manifest entry for {path}")
            with source.open("rb") as file:
                if hashlib.file_digest(file, "sha1").hexdigest() != entry["sha1"]:
                    raise ValueError(f"Stale Unreal cache manifest for {path}")
            if source.suffix == ".ucas":
                item = pack_container(source, site)
            else:
                item = pack_module(source, site)
            if item["size"] != entry["size"]:
                raise ValueError(f"Incorrect logical size for {path}")
            item["sha1"] = entry["sha1"]
            item["type"] = "application/wasm" if source.suffix == ".wasm" else "application/octet-stream"
            virtual[path] = item
            entry["pagesVirtual"] = True
            if source.suffix == ".wasm":
                entry["pagesWireBytes"] = sum((site / name).stat().st_size for name in item["pieces"])
            elif item["size"] >= 256 * 1024 * 1024:
                entry["pagesStreamed"] = True
            continue
        if source.stat().st_size >= 100 * 1024 * 1024:
            raise ValueError(f"Unsplittable file exceeds GitHub's file limit: {path}")
        target = site / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if not any(path.endswith(".wasm") for path in virtual):
        raise ValueError("No WebAssembly module found")
    index = site / "index.html"
    switch = '<meta name="ue-sw-isolation" content="1">'
    page = index.read_text(encoding="utf-8")
    if switch not in page:
        page = replace_once(page, switch.replace('"1"', '"0"'), switch, index.name)
    index.write_text(page, encoding="utf-8", newline="\n")

    # Pages stores no Brotli sidecars. Count the initial files as transferred,
    # excluding the large container Unreal will read on demand during play.
    for entry in manifest:
        entry["br"] = 0
    (site / "wasm-cache.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    loader = site / "wasm-loader.js"
    script = loader.read_text(encoding="utf-8")
    script = replace_once(script, "Array.isArray(f.parts) && f.parts.length",
                          "f.pagesVirtual || (Array.isArray(f.parts) && f.parts.length)", loader.name)
    script = replace_once(script, "&& !late(f.url)", "&& !late(f.url) && !f.pagesStreamed", loader.name)
    script = replace_once(script, "const wire = f => f.br || f.size;",
                          "const wire = f => f.pagesWireBytes || f.size;", loader.name)
    loader.write_text(script, encoding="utf-8", newline="\n")

    # Have Epic's cache retain the logical module. Only the physical shards
    # exist in the host's HTTP cache, so its second copy of the logical URL
    # for a browser's compiled-module cache cannot be populated.
    sw = site / "sw.js"
    engine = sw.read_text(encoding="utf-8")
    guard = "if (!isWasm(url) || entry.parts) continue;"
    engine = replace_once(engine, guard, "if (!isWasm(url) || entry.parts || pagesFiles.has(url)) continue;", sw.name)
    # Each tab's UE manifest pins its build. Keep that identity on a range
    # cache miss too, so an open tab cannot mix two deployments' bytes.
    engine = engine.replace("toNetwork(url, range)", "toNetwork(key, range)")
    engine = engine.replace("toNetwork(url)", "toNetwork(key)")
    transport = Path(__file__).with_name("transport.js").read_text(encoding="utf-8")
    manifest_js = json.dumps(virtual, separators=(",", ":"))
    sw.write_text(transport + "\nconst pagesFiles = installPagesTransport(" + manifest_js + ");\n" + engine,
                  encoding="utf-8", newline="\n")
    # Used by incremental preparation to remove only this tool's stale output.
    files = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())
    (site / INVENTORY).write_text(json.dumps({"files": files}, separators=(",", ":")), encoding="utf-8")
    return set(files) | {INVENTORY}


def publish_local(temporary, destination, files):
    previous = set()
    if destination.exists() and any(destination.iterdir()):
        inventory = destination / INVENTORY
        if not inventory.is_file():
            raise ValueError(f"Use an empty output directory or an existing prepared site: {destination}")
        previous = set(json.loads(inventory.read_text(encoding="utf-8"))["files"]) | {INVENTORY}
    for name in previous | files:
        if not (destination / name).resolve().is_relative_to(destination) or Path(name).is_absolute():
            raise ValueError(f"Unsafe inventory path: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in sorted(files - {INVENTORY}):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary / name, target)
    for stale in previous - files:
        (destination / stale).unlink(missing_ok=True)
    os.replace(temporary / INVENTORY, destination / INVENTORY)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stage, output = args.stage.resolve(), args.output.resolve()
    if stage.is_relative_to(output) or output.is_relative_to(stage):
        parser.error("The input stage and output directory must be separate.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ue-pages-", dir=output.parent) as tmp:
        site = Path(tmp)
        files = prepare(stage, site)
        size = sum((site / name).stat().st_size for name in files)
        if size > SITE_BUDGET:
            raise ValueError(f"Site is {size:,} bytes, over the {SITE_BUDGET:,} byte budget")
        publish_local(site, output, files)
        print(f"{len(files)} files, {size:,} bytes: {output}")


if __name__ == "__main__":
    main()
