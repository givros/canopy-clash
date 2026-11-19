"""Connect the Unreal page's startup indicators to measured boot events."""
from pathlib import Path


def _once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Unexpected Unreal loading template near: " + old[:90])
    return text.replace(old, new, 1)


def _section(text, start, end, new):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("Unexpected Unreal loading section: " + start)
    left = text.index(start)
    right = text.index(end, left)
    return text[:left] + new + text[right:]


def patch_loading_progress(site, page):
    player = site / "wasm-play.js"
    loader = site / "wasm-loader.js"
    worker = site / "sw.js"
    script = player.read_text(encoding="utf-8")
    script = _once(script, "let shown = 0;\n", "")
    script = _section(script, "// The start-up download (wasm-loader.js: stage",
                      "// A stop that is this browser", "")
    script = _once(script, "['download', 'Downloading the game']", "['download', 'Loading game data']")
    helpers = Path(__file__).with_name("loading-progress.js").read_text(encoding="utf-8")
    scene_check = Path(__file__).with_name("mobile-scene-check.js").read_text(encoding="utf-8")
    script = _section(script, "// The last stretch: the engine is up", "// The pipeline hold (",
                      helpers + "\n" + scene_check + "\n")
    script = _once(script, "  if (siteTimer) clearInterval(siteTimer);\n  lifted = true;",
                   "  canopyLoading.stop();\n  lifted = true;")
    script = _once(script, "  failed = true;\n  coverTo('failed');",
                   "  failed = true;\n  canopyLoading.stop();\n  coverTo('failed');")
    script = _once(script, "      if (!harness) $('progress-text').textContent = T('Ready: preparing shaders...');\n", "")
    # UE_RUN READY can arrive before the pipeline hold releases or before a
    # swapchain image is copied. The cover and its final 100% need both.
    script = _section(script, "  ready = true;\n  coverTo('ready');", "  pipelineHold.begin(readyProceed);",
                      "  ready = true;\n")
    wait = """  canopyLoading.stage('playable');
  if (!canvasFrame) { waitingForCanvas = true; return; }
  waitingForCanvas = false;
  canopyLoading.stop();
  coverTo('ready');
  if (cover.setAttribute) cover.setAttribute('aria-busy', 'false');
  document.body.dataset.ready = '1';
"""
    script = _once(script, "  if (harness) { lifted = true; showToast(); return; }",
                   wait + "  if (harness) { lifted = true; showToast(); return; }")
    script = _once(script, "  $('progress-text').textContent = T(startOnClick ? 'Ready: click to play' : 'Ready');",
                   """  const action = window.canopyTouch ? 'Tap to play' : 'Ready: click to play';
  $('progress-text').textContent = T(startOnClick ? action : 'Ready') + ' · 100%';""")
    script = _section(script, "// (The cover lifted onto an empty canvas", "  if (ueShell.active", """// This WebGPU build provides an explicit first canvas copy. A timer cannot certify a frame.
let canvasFrame = false, waitingForCanvas = false;
window.addEventListener('ue-first-frame', () => canopyLoading.stage('first_frame'));
window.addEventListener('ue-first-canvas-frame', () => {
  canvasFrame = true;
  canopyLoading.stage('canvas');
  console.log('LOADTIME first_canvas_frame ' + Math.round(performance.now()));
  if (waitingForCanvas) readyProceed();
});
function liftCover() {
  if (lifted || failed || !canvasFrame) return;
""")
    script = _once(script, "ueShell.handoff().then(() => liftCover(true))", "ueShell.handoff().then(() => liftCover())")
    player.write_text(script, encoding="utf-8", newline="\n")

    script = loader.read_text(encoding="utf-8")
    script = _section(script, "  const byUrl = new Map(needed", "  // The start-up download as counted here", """  const startupData = canopyStartupBytes(needed, swScope || location.href);
  if (cached && startupData.total) canopyLoading.bytes(0, startupData.total);
""")
    script = _section(script, "      const f = byUrl.get(data.url);", "  // Frames capped at the display's rate", """      const count = startupData.report(data);
      if (!count) return;
      if (boot) {
        // Preserve the engine's compressed-size estimate for its pipeline-hold
        // heuristic. The indicator above counts actual decoded bytes.
        const delta = count.delta * wire(count.file) / count.file.size;
        boot.bytes = Math.min(total, boot.bytes + delta);
        if (!data.cached) boot.netBytes += delta;
        boot.at = performance.now();
      }
      canopyLoading.bytes(count.loaded, count.total);
    });
  }
""")
    script = _once(script, "      rememberLine(t);", r"""      const milestone = /\bUE_RUN BOOT (engine_init|map_loaded|first_frame)\b/.exec(t);
      if (milestone) canopyLoading.stage(milestone[1]);
      rememberLine(t);""")
    script = _section(script, "      ueSteps.set('engine', 'done', ueSteps.took('engine'));", "    },\n  };\n  window.addEventListener('error'",
                      """      ueSteps.set('engine', 'done');
      coverTo('level');
      canopyLoading.stage('runtime');
""")
    script = _once(script, "    progress('Starting the engine...', 0.76);\n", "")
    loader.write_text(script, encoding="utf-8", newline="\n")

    script = worker.read_text(encoding="utf-8")
    script = _once(script, "function report(url, loaded, cached) { post({ type: 'progress', url, loaded, cached }); }",
                   "function report(url, loaded, cached, sha1) { post({ type: 'progress', url, loaded, cached, sha1 }); }")
    # Only data belonging to this tab's release can advance its progress. The
    # engine shares a worker (and cached file fills) between simultaneous tabs.
    for old, count in [("report(url, headSize + got, false)", 1), ("report(url, entry.size, true)", 2),
                       ("report(url, loaded, false)", 2)]:
        if script.count(old) != count:
            raise ValueError("Unexpected Unreal data progress reports: " + old)
        script = script.replace(old, old[:-1] + ", entry.sha1)")
    # A warm visit can be served from the running worker's complete in-memory
    # copy with no Cache Storage lookup and no network transfer.
    script = _once(script, "  if (loaded) return Promise.resolve(loaded.memory",
                   "  if (loaded) report(url, entry.size, true, entry.sha1);\n"
                   "  if (loaded) return Promise.resolve(loaded.memory")
    worker.write_text(script, encoding="utf-8", newline="\n")

    # Offer a retry after an idle stretch; retain the real load for slow clients.
    page = _once(page, "data-i18n>Starting...</div></div>",
                 'data-i18n>Starting...</div><div id="loading-retry" hidden><span data-i18n>Still waiting for the game.</span> '
                 '<button type="button" data-i18n>Retry loading</button></div></div>')
    mobile_css = Path(__file__).with_name("mobile-scene-check.css").read_text(encoding="utf-8")
    return _once(page, "#progress-text{", mobile_css +
                 "\n#loading-retry{text-align:center;margin-top:8px} #loading-retry button{margin-left:6px}\n#progress-text{")
