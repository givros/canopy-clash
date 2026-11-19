"""Bind the loader to the worker carrying this build's physical shard map."""
from hashlib import sha256


WORKER_READY = """
async function canopyReleaseWorker(needsController) {
  const container = navigator.serviceWorker;
  const url = new URL(swUrl(), location.href).href;
  const registration = await container.register(url);
  // A registration can still have the previous release active while its
  // replacement installs. Only the expected worker understands these ranges.
  const until = performance.now() + 30000;
  let claimRequested = false;
  while (performance.now() < until) {
    const active = registration.active;
    if (active?.scriptURL === url && active.state === 'activated') {
      if (!needsController || container.controller?.scriptURL === url) return registration;
      if (!claimRequested) {
        active.postMessage({ type: 'claim' });
        claimRequested = true;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 75));
  }
  throw new Error("The game update could not take control of this tab. Reload to try again.");
}
"""


def pin_release_worker(site):
    worker = (site / "sw.js").read_bytes()
    name = f"sw-{sha256(worker).hexdigest()[:20]}.js"
    (site / name).write_bytes(worker)
    loader = site / "wasm-loader.js"
    script = loader.read_text(encoding="utf-8")
    start = script.index("function swUrl()")
    script = script[:start] + WORKER_READY + "\n" + script[start:]
    url = "return q ? 'sw.js?' + q : 'sw.js';"
    register = "const registration = await navigator.serviceWorker.register(swUrl());"
    if script.count(url) != 1 or script.count(register) != 2:
        raise ValueError("Unexpected worker registration in Unreal's Wasm loader")
    script = script.replace(url, f"return q ? '{name}?' + q : '{name}';")
    # A non-isolated first navigation only needs the active worker to serve
    # its reload. A playable page requires that worker as its own controller.
    script = script.replace(register, "await canopyReleaseWorker(false);", 1)
    first_wait = script.index("        // wait for the isolating worker itself")
    first_end = script.index("        sessionStorage.setItem('ue.isolation.reload'", first_wait)
    script = script[:first_wait] + script[first_end:]
    script = script.replace(register, "const registration = await canopyReleaseWorker(true);", 1)
    legacy_wait = script.index("        // (A reload of a page whose worker was already active")
    bind = script.index("        if (navigator.serviceWorker.controller) {", legacy_wait)
    script = script[:legacy_wait] + script[bind:]
    loader.write_text(script, encoding="utf-8", newline="\n")
