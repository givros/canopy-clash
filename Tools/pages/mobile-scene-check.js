// Sample the exact back buffer Unreal is copying into the active game canvas.
// A fresh swapchain image or a 2D capture between presents can read black on
// WebKit even when the player can see the world.
async function canopySceneSample(canvas) {
  let context, device;
  try {
    context = canvas.getContext('webgpu');
    device = context?.getConfiguration?.()?.device;
  } catch { return null; }
  const proto = globalThis.GPUCommandEncoder?.prototype;
  if (!device || !proto) return null;
  const original = proto.copyTextureToTexture;
  // Stay away from the score, crosshair, weapon, touch controls and HUD rails.
  const points = [[.24,.25],[.42,.23],[.65,.25],[.76,.39],[.32,.40],[.58,.37],[.23,.55],[.43,.58],[.64,.53]];
  async function sample(texture) {
    let buffer;
    try {
      if (!(texture.usage & GPUTextureUsage.COPY_SRC) || !/^(bgra|rgba)8unorm(-srgb)?$/.test(texture.format) ||
          texture.width < 32 || texture.height < 32) return null;
      device.pushErrorScope('validation');
      let valid;
      try {
        // Four pixels in a single row per location: no row stride/padding.
        buffer = device.createBuffer({ size: points.length * 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
        const encoder = device.createCommandEncoder();
        points.forEach(([x,y], index) => encoder.copyTextureToBuffer(
          { texture, origin: [Math.floor(texture.width * x), Math.floor(texture.height * y), 0] },
          { buffer, offset: index * 16 }, [4,1,1]));
        device.queue.submit([encoder.finish()]);
      } finally { valid = device.popErrorScope(); }
      if (await valid) return null;
      await buffer.mapAsync(GPUMapMode.READ);
      const bytes = new Uint8Array(buffer.getMappedRange());
      let max = 0;
      for (let i=0; i<bytes.length; i+=4) max = Math.max(max, bytes[i], bytes[i+1], bytes[i+2]);
      return max;
    } catch { return null; } finally { buffer?.destroy(); }
  }
  return new Promise(resolve => {
    function restore() {
      if (proto.copyTextureToTexture === inspect) proto.copyTextureToTexture = original;
    }
    function inspect(source, target, extent) {
      const result = original.call(this, source, target, extent);
      try {
        // UE's PresentOffscreen creates a dedicated encoder for this copy;
        // the scene draw commands have already been submitted to the queue.
        if (source.texture.label === 'BackBuffer' && target.texture === context.getCurrentTexture()) {
          restore();
          sample(source.texture).then(finish, () => finish(null));
        }
      } catch { finish(null); }
      return result;
    }
    function finish(value) { clearTimeout(timer); restore(); resolve(value); }
    const timer = setTimeout(() => finish(null), 2000);
    try { proto.copyTextureToTexture = inspect; } catch { finish(null); }
  });
}

function canopyAlternateGraphics(address, deferred) {
  const url = new URL(address);
  url.searchParams.set('mobileGraphicsRetry', '1');
  url.searchParams.set('tier', deferred ? 'deferred' : 'forward');
  url.searchParams.set('sp', deferred ? '80' : '65');
  url.searchParams.set('prewarm', '0');
  url.searchParams.set('saved', 'memory');
  url.searchParams.delete('gpuRecovery');
  const args = (url.searchParams.get('args') || '').split(/\s+/).filter(arg => arg &&
    !/^-Web(?:GPU(?:NoMobileDeferred|MobileDeferred|SM5|NoSM5)|ScreenPercentage=|QualityPreset=)/i.test(arg));
  if (!deferred) args.push('-WebQualityPreset=Low');
  if (args.length) url.searchParams.set('args', args.join(' '));
  else url.searchParams.delete('args');
  return url;
}

(() => {
  const compat = window.ueCompat;
  if (compat?.deviceClass() !== 'ios') return;
  const canvas = $('canvas');
  const panel = document.createElement('aside');
  panel.id = 'canopy-graphics-recovery';
  panel.hidden = true;
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = T('Try alternate graphics');
  const log = document.createElement('button');
  log.type = 'button';
  log.textContent = T('Download the log');
  log.addEventListener('click', () => $('log').click());
  panel.append(status, button, log);
  document.body.appendChild(panel);
  const key = 'ue.' + pageMeta('ue-project', 'game') + '.mobileGraphicsRetry';
  let retried = new URLSearchParams(location.search).has('mobileGraphicsRetry');
  try { retried ||= sessionStorage.getItem(key) === '1'; } catch { /* private tab */ }
  let persistentBlack = false;
  let inspecting = false;
  let switching = false;
  let pauseRequested = false;
  const controls = $('canopy-controls');
  const pause = $('canopy-pause');
  const retryLoading = $('loading-retry');
  const menuOpen = () => controls?.hidden && cover.hidden && window.Module?.ueWebPage?.wanted === false;
  function update() {
    const loadingStalled = !retryLoading.hidden && ready;
    const active = !document.hidden && !failed && !recovering &&
      (loadingStalled || (cover.hidden && (persistentBlack || pauseRequested || menuOpen())));
    panel.hidden = !active;
    if (!active) return;
    const tier = compat.runningTier(window.Module?.arguments || []);
    const why = persistentBlack ? T('The world is still dark.') : loadingStalled ? T('Waiting for a rendered frame.') : '';
    status.textContent = retried ? [why, T('Alternate graphics already tried') + ' (' + tier + ').'].filter(Boolean).join(' ') : why;
    button.hidden = retried;
    log.hidden = !retried;
  }
  // The web pause button is still usable when the engine draws no menu or
  // stops processing the Escape key. Reveal recovery on that gesture too.
  pause?.addEventListener('click', () => { pauseRequested = true; update(); });
  document.addEventListener('pointerdown', event => {
    if (pauseRequested && !panel.contains(event.target) && !pause?.contains(event.target)) {
      pauseRequested = false;
      update();
    }
  }, { capture: true });
  button.addEventListener('click', async () => {
    if (retried || switching) return;
    switching = true;
    button.disabled = true;
    let deferred = false;
    try {
      const stage = await fetch('wasm-tiers.json', { signal: AbortSignal.timeout(3000) }).then(r => r.ok ? r.json() : null);
      const set = compat.hasTextureSets() ? await compat.textureSet() : null;
      const limits = canvas.getContext('webgpu')?.getConfiguration?.()?.device?.limits;
      const fallback = sessionStorage.getItem('ue.' + pageMeta('ue-project', 'game') + '.gpuFallback');
      deferred = !!(compat.stageHas(stage).deferred && !set?.mobileOnly &&
        compat.runningTier(window.Module?.arguments || []) === 'forward' && !fallback &&
        limits?.maxColorAttachments >= 4 && limits?.maxColorAttachmentBytesPerSample >= 32);
    } catch { /* A reduced forward pass is available without extra capabilities. */ }
    const next = canopyAlternateGraphics(location.href, deferred);
    try { sessionStorage.setItem(key, '1'); } catch { /* URL preserves the guard. */ }
    console.log('CANOPY_SCENE_CHECK retry', next.searchParams.get('tier'));
    location.assign(next.href);
  });
  async function checkScene() {
    if (inspecting || !cover.hidden || failed || document.hidden || menuOpen()) return;
    inspecting = true;
    // A respawn/fade is temporary. Four separated, nearly black world samples
    // only reveal an optional button; they never pause or restart a match.
    for (const delay of [5500, 2700, 2700, 2700]) {
      await new Promise(resolve => setTimeout(resolve, delay));
      if (failed || document.hidden || menuOpen() || !cover.hidden) { inspecting = false; return; }
      const value = await canopySceneSample(canvas);
      if (value === null || value > 4) return;
    }
    persistentBlack = true;
    console.log('CANOPY_SCENE_CHECK four dark world samples', compat.runningTier(window.Module?.arguments || []));
    update();
  }
  const observer = new MutationObserver(() => { update(); checkScene(); });
  for (const element of [cover, controls, retryLoading]) {
    if (element) observer.observe(element, { attributes: true, attributeFilter: ['hidden'] });
  }
  document.addEventListener('visibilitychange', () => { update(); checkScene(); });
})();
