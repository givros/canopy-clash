"""Prepare an Unreal Wasm stage for a static host without custom headers."""
import argparse
import filecmp
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from iostore import pack_container
from loading_progress import patch_loading_progress
from worker_update import pin_release_worker


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
    shared_blocks, shared_pieces = {}, []
    (site / "blobs").mkdir()
    # Pack the desktop containers first to preserve existing content-addressed
    # URLs when the handheld texture set is added.
    for source in sorted(stage.rglob("*"), key=lambda p: ("ASTC" in p.parts, p)):
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
                item = pack_container(source, site, shared_blocks, shared_pieces)
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
    touch = Path(__file__).with_name("mobile-controls.js").read_text(encoding="utf-8")
    touch_css = Path(__file__).with_name("mobile-controls.css").read_text(encoding="utf-8")
    page = replace_once(page, '</head>', '<style>\n' + touch_css + '\n</style>\n</head>', index.name)
    player_tag = '<script src="wasm-play.js">'
    page = replace_once(page, player_tag, '<script>\n' + touch + '\n</script>\n' + player_tag, index.name)
    # Unreal's JS sampler runs on the DOM side and feeds its existing atomic
    # gamepad buffer. Only handhelds install the virtual controller.
    # UAT names the Development module after the game and appends its
    # configuration to the Shipping module. Follow the staged Wasm entry.
    game_modules = [Path(name) for name in virtual if name.endswith(".wasm") and "Binaries" in Path(name).parts]
    module, = game_modules
    glue = site / module.with_suffix(".js")
    original = "List=navigator.getGamepads?navigator.getGamepads():[]"
    compiled = replace_once(glue.read_text(encoding="utf-8"), original,
                            "List=window.canopyTouch?window.canopyTouch.gamepads():(" + original[5:] + ")", glue.name)
    glue.write_text(compiled, encoding="utf-8", newline="\n")
    glue_entry = entries[glue.relative_to(site).as_posix()]
    glue_entry.update(size=glue.stat().st_size, sha1=hashlib.sha1(glue.read_bytes()).hexdigest())
    if switch not in page:
        page = replace_once(page, switch.replace('"1"', '"0"'), switch, index.name)
    advice = '<meta name="ue-browser-advice" content="">'
    if advice in page:
        page = replace_once(page, advice, advice.replace('content=""', 'content="none"'), index.name)
    graphics = Path(__file__).with_name("browser-graphics.js").read_text(encoding="utf-8")
    network_quality = Path(__file__).with_name("network-quality.js").read_text(encoding="utf-8")
    head_script = "<script>\n// The display's refresh rate"
    page = replace_once(page, head_script,
                        "<script>\n" + graphics + "\ncanopyGraphics.normalizeLink();\n" + network_quality +
                        "\ninstallCanopyNetworkPage();\n// The display's refresh rate", index.name)
    compat = site / "wasm-compat.js"
    script = compat.read_text(encoding="utf-8")
    script = replace_once(script, "candidates.find((s) => s.features.every((f) => adapter.features.has(f))) || null",
                          "canopyGraphics.textureSet(candidates, adapter.features, handheld)", compat.name)
    pick = "const asked = chosenTier();"
    script = replace_once(script, pick, pick + """
      const fastForward = !resolution && !gpuFallback() && !handheld()
        ? await canopyGraphics.forwardReason(asked, defaultTier, browser(), probe) : '';""", compat.name)
    script = replace_once(script, "if (!resolution && (!(sm5 || deferred)",
                          "if (!resolution && (fastForward || !(sm5 || deferred)", compat.name)
    script = replace_once(script, "const tier = pickTier(null, 0, stage);",
                          "const tier = fastForward ? { tier: 'forward', preset: null, why: fastForward } : pickTier(null, 0, stage);",
                          compat.name)
    no_gpu = "WebGPU has no GPU to use here: the GPU or its driver may be blocked by the browser (see ${page})."
    script = replace_once(script, no_gpu,
                          "The browser did not provide a WebGPU adapter. ${browser().os === 'Windows' ? "
                          "'Check that hardware acceleration is enabled, restart the browser, and reload the game. ' : ''}"
                          "See ${page} for GPU diagnostics.", compat.name)
    compat.write_text(script, encoding="utf-8", newline="\n")

    player = site / "wasm-play.js"
    script = player.read_text(encoding="utf-8")
    script = replace_once(script, "const text = T(errorCards[kind] || errorCards.abort);",
                          "const text = kind === 'device-lost' ? canopyGraphics.deviceLossText($('reload')) : T(errorCards[kind] || errorCards.abort);",
                          player.name)
    script = replace_once(script, "$('reload').addEventListener('click', () => location.reload());",
                          "$('reload').addEventListener('click', () => canopyGraphics.reload($('reload')));", player.name)
    player.write_text(script, encoding="utf-8", newline="\n")

    # Pages stores no Brotli sidecars. Count the initial files as transferred,
    # excluding the large container Unreal will read on demand during play.
    for entry in manifest:
        entry["br"] = 0
    (site / "wasm-cache.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    loader = site / "wasm-loader.js"
    script = loader.read_text(encoding="utf-8")
    dpr = "Math.min(window.devicePixelRatio || 1, Number(pageMeta('ue-max-dpr')) || 1)"
    script = replace_once(script, dpr, f"canopyGraphics.canvasRatio(canvas, {dpr})", loader.name)
    script = replace_once(script, "Array.isArray(f.parts) && f.parts.length",
                          "f.pagesVirtual || (Array.isArray(f.parts) && f.parts.length)", loader.name)
    script = replace_once(script, "&& !late(f.url)", "&& !late(f.url) && !f.pagesStreamed", loader.name)
    script = replace_once(script, "const wire = f => f.br || f.size;",
                          "const wire = f => f.pagesWireBytes || f.size;", loader.name)
    loader.write_text(script, encoding="utf-8", newline="\n")
    page = patch_loading_progress(site, page)

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
    sw.write_text(network_quality + "\nconst canopyNetworkSample = installCanopyNetworkWorker();\n" + transport +
                  "\nconst pagesFiles = installPagesTransport(" + manifest_js + ", canopyNetworkSample);\n" + engine,
                  encoding="utf-8", newline="\n")
    pin_release_worker(site)
    # Returning players can have the previous scripts in their HTTP cache.
    for name in ("wasm-compat.js", "wasm-play.js", "wasm-loader.js", "texture-budget.js"):
        attribute = "content" if name == "texture-budget.js" else "src"
        stamp = hashlib.sha256((site / name).read_bytes()).hexdigest()[:16]
        page = replace_once(page, f'{attribute}="{name}"', f'{attribute}="{name}?build={stamp}"', index.name)
    index.write_text(page, encoding="utf-8", newline="\n")
    # Used by incremental preparation to remove only this tool's stale output.
    files = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())
    (site / INVENTORY).write_text(json.dumps({"files": files}, separators=(",", ":")), encoding="utf-8")
    return set(files) | {INVENTORY}


def retry_busy(operation, *args, **kwargs):
    for attempt in range(7):
        try:
            return operation(*args, **kwargs)
        except PermissionError:
            if attempt == 6:
                raise
            time.sleep(.1 * 2 ** attempt)


def publish_local(temporary, destination, files):
    previous = set()
    pending = destination.parent / ("." + destination.name + "-pending-release.json")
    if destination.exists() and any(destination.iterdir()):
        inventory = destination / INVENTORY
        if not inventory.is_file() and not pending.is_file():
            raise ValueError(f"Use an empty output directory or an existing prepared site: {destination}")
        if inventory.is_file():
            previous = set(json.loads(inventory.read_text(encoding="utf-8"))["files"]) | {INVENTORY}
    if pending.is_file():
        previous.update(json.loads(pending.read_text(encoding="utf-8")))
    for name in previous | files:
        if not (destination / name).resolve().is_relative_to(destination) or Path(name).is_absolute():
            raise ValueError(f"Unsafe inventory path: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    # Record which files the packager owns even if a previous local copy was
    # interrupted between installing new chunks and retiring its old ones.
    record = temporary / ".pending-release.json"
    record.write_text(json.dumps(sorted(previous | files)), encoding="utf-8")
    retry_busy(os.replace, record, pending)
    for name in sorted(files - {INVENTORY}, key=lambda path: (path == "index.html", path)):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        staged = temporary / name
        if target.is_file() and filecmp.cmp(staged, target, shallow=False):
            continue
        # On Windows the active preview or virus scanner can briefly hold a
        # reader without delete sharing. The existing file stays valid.
        retry_busy(os.replace, staged, target)
    for stale in previous - files:
        retry_busy((destination / stale).unlink, missing_ok=True)
    retry_busy(os.replace, temporary / INVENTORY, destination / INVENTORY)
    retry_busy(pending.unlink, missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stage, output = args.stage.resolve(), args.output.resolve()
    if stage.is_relative_to(output) or output.is_relative_to(stage):
        parser.error("The input stage and output directory must be separate.")
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = output.parent
    if (scratch / "gameAstraForest.uproject").is_file():
        scratch = scratch / "Saved/PagesRelease"
        scratch.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix=".ue-pages-", dir=scratch)
    try:
        site = Path(temporary.name)
        files = prepare(stage, site)
        size = sum((site / name).stat().st_size for name in files)
        if size > SITE_BUDGET:
            raise ValueError(f"Site is {size:,} bytes, over the {SITE_BUDGET:,} byte budget")
        publish_local(site, output, files)
        print(f"{len(files)} files, {size:,} bytes: {output}")
    finally:
        retry_busy(temporary.cleanup)


if __name__ == "__main__":
    main()
