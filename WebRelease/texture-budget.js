(() => {
  const compat = window.ueCompat;
  const params = new URLSearchParams(location.search);
  const explicitBudget = /\br\.Streaming\.PoolSize\b|-TempleWebTexturePool=/i;
  const desktopRenderer = /(?:^|\s)-WebGPUSM5(?:\s|$)/i;
  if (!compat || compat.deviceClass() !== 'desktop' ||
      ['Android', 'iOS'].includes(compat.browser().os)) return;

  async function configure() {
    const [gpu, commandLine] = await Promise.all([
      compat.probe(),
      fetch('UECommandLine.txt', { cache: 'no-cache' }).then(response => response.ok ? response.text() : '').catch(() => ''),
    ]);
    const adapter = gpu.adapter;
    if (gpu.message || !adapter) return;
    const metaArgs = ['ue-args', 'ue-args-desktop', 'ue-args-' + compat.browser().name.toLowerCase()]
      .map(name => document.querySelector('meta[name=' + name + ']')?.content || '');
    const existingArgs = [params.get('args'), commandLine, ...metaArgs, ...(window.ueExtraArgs || [])].join(' ');
    const calibrating = params.has('bench') || params.get('gpucheck') === '1' ||
      document.querySelector('meta[name=ue-gpucheck]')?.content === '1';
    const useDefaultQuality = !calibrating && !/\bWebQualityPreset=/i.test(existingArgs);
    if (useDefaultQuality) {
      // The engine applies this preset only when the player has no saved graphics settings.
      (window.ueExtraArgs ||= []).push('-WebQualityPreset=Medium');
    }
    // The recovery session keeps the engine's conservative streaming pool.
    const ramGiB = navigator.deviceMemory;
    if (params.get('gpuRecovery') === '1' || params.get('tier') === 'desktop' || !(ramGiB >= 8) ||
        adapter.integrated !== false || adapter.fallback ||
        desktopRenderer.test(existingArgs)) return;

    const bufferMiB = adapter.limits.maxBufferSize / 1048576;
    if (!(bufferMiB >= 1024)) return;

    // Preserve the native HUD. Render the scene at up to about 900p worth of pixels
    // on a known discrete desktop GPU, using the same CSS-to-device ratio as Unreal.
    const manualResolution = params.has('sp') || /\b(?:WebScreenPercentage|r\.ScreenPercentage|sg\.ResolutionQuality)\b/i.test(existingArgs);
    const project = document.querySelector('meta[name=ue-project]')?.content || 'game';
    let selectedRenderer = params.get('tier');
    try {
      selectedRenderer ||= localStorage.getItem('ue.' + project + '.renderer');
      selectedRenderer ||= JSON.parse(sessionStorage.getItem('ue.' + project + '.gpuFallback') || 'null');
    } catch { /* Storage is optional. */ }
    if (useDefaultQuality && !manualResolution && !selectedRenderer &&
        ['Chrome', 'Edge'].includes(compat.browser().name)) {
      const canvas = document.getElementById('canvas');
      const maxDpr = Number(document.querySelector('meta[name=ue-max-dpr]')?.content) || 1;
      const dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
      const pixels = Math.round(canvas.clientWidth * dpr) * Math.round(canvas.clientHeight * dpr);
      if (pixels > 0) {
        const percentage = Math.max(25, Math.min(100, Math.floor(100 * Math.sqrt((1600 * 900) / pixels))));
        window.ueExtraArgs.push('-WebScreenPercentage=' + percentage);
      }
    }

    if (explicitBudget.test(existingArgs)) return;

    // WebGPU hides VRAM. Use host RAM and the adapter's buffer limit as
    // independent bounds; the game also checks the actual Wasm heap ceiling.
    const budgetMiB = Math.floor(Math.min(640, ramGiB * 64, bufferMiB / 2) / 16) * 16;
    (window.ueExtraArgs ||= []).push('-TempleWebTexturePool=' + budgetMiB);
  }

  // Unreal builds the command line after the shell's load callback. Keep
  // that callback pending while the shared adapter probe is still resolving.
  const script = document.currentScript;
  const loaded = script.onload;
  const ready = configure().catch(error => console.info('Using Unreal rendering defaults:', error.message));
  script.onload = event => ready.then(() => loaded?.call(script, event));
})();
