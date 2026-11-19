(() => {
  const compat = window.ueCompat;
  const params = new URLSearchParams(location.search);
  const explicitBudget = /\br\.Streaming\.PoolSize\b|-TempleWebTexturePool=/i;
  const desktopRenderer = /(?:^|\s)-WebGPUSM5(?:\s|$)/i;
  if (!compat) return;

  async function configure() {
    const [gpu, commandLine] = await Promise.all([
      compat.probe(),
      fetch('UECommandLine.txt', { cache: 'no-cache' }).then(response => response.ok ? response.text() : '').catch(() => ''),
    ]);
    const adapter = gpu.adapter;
    if (gpu.message || !adapter) return;
    const deviceClass = compat.deviceClass();
    const handheld = deviceClass === 'ios' || deviceClass === 'android' ||
      ['Android', 'iOS'].includes(compat.browser().os);
    const metaArgs = ['ue-args', 'ue-args-' + deviceClass, 'ue-args-' + compat.browser().name.toLowerCase()]
      .map(name => document.querySelector('meta[name=' + name + ']')?.content || '');
    const existingArgs = [params.get('args'), commandLine, ...metaArgs, ...(window.ueExtraArgs || [])].join(' ');
    const calibrating = params.has('bench') || params.get('gpucheck') === '1' ||
      document.querySelector('meta[name=ue-gpucheck]')?.content === '1';
    const useDefaultQuality = !calibrating && !/\bWebQualityPreset=/i.test(existingArgs);
    if (useDefaultQuality) {
      // The engine applies this preset only when the player has no saved graphics settings.
      (window.ueExtraArgs ||= []).push('-WebQualityPreset=Medium');
    }
    const ramGiB = navigator.deviceMemory;
    if (params.get('gpuRecovery') === '1' || params.get('tier') === 'desktop' || desktopRenderer.test(existingArgs)) return;

    // Preserve the native HUD. The desktop scene's ceiling is about 900p worth
    // of pixels, using the same CSS-to-device ratio as Unreal.
    const manualResolution = params.has('sp') || /\b(?:WebScreenPercentage|r\.ScreenPercentage|sg\.ResolutionQuality)\b/i.test(existingArgs);
    const project = document.querySelector('meta[name=ue-project]')?.content || 'game';
    let selectedRenderer = params.get('tier');
    try {
      selectedRenderer ||= localStorage.getItem('ue.' + project + '.renderer');
      selectedRenderer ||= JSON.parse(sessionStorage.getItem('ue.' + project + '.gpuFallback') || 'null');
    } catch { /* Storage is optional. */ }
    if (useDefaultQuality && !manualResolution && !selectedRenderer) {
      const canvas = document.getElementById('canvas');
      const maxDpr = Number(document.querySelector('meta[name=ue-max-dpr]')?.content) || 1;
      const dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
      const pixels = Math.round(canvas.clientWidth * dpr) * Math.round(canvas.clientHeight * dpr);
      if (pixels > 0) {
        // The handheld drawing surface is already bounded to 720p. Keep its
        // crisp HUD and aim controls while the 3D scene responds to frame cost.
        const desktopPixelBudget = adapter.fallback ? 960 * 540 : 1600 * 900;
        let percentage = Math.max(25, Math.min(100, Math.floor(100 * Math.sqrt(desktopPixelBudget / pixels))));
        if (handheld) {
          percentage = ramGiB > 0 && ramGiB <= 4 ? 85 : 100;
          if (adapter.fallback) percentage = 75;
        }
        window.ueExtraArgs.push('-WebScreenPercentage=' + percentage);
        if (params.get('adaptive') !== '0') {
          window.ueExtraArgs.push('-CanopyWebAdaptive=' + percentage);
          if (handheld) window.ueExtraArgs.push('-CanopyWebHandheld');
          if (adapter.features?.includes('timestamp-query')) window.ueExtraArgs.push('-CanopyWebGpuTiming');
        }
      }
    }

    // Phones use UE's memory-aware, mobile-capped texture streaming pool.
    if (handheld || !(ramGiB >= 8) || adapter.integrated !== false ||
        adapter.fallback || explicitBudget.test(existingArgs)) return;
    const bufferMiB = adapter.limits.maxBufferSize / 1048576;
    if (!(bufferMiB >= 1024)) return;

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
