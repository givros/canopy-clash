(() => {
  const compat = window.ueCompat;
  const params = new URLSearchParams(location.search);
  const explicitBudget = /\br\.Streaming\.PoolSize\b|-TempleWebTexturePool=/i;
  const desktopRenderer = /(?:^|\s)-WebGPUSM5(?:\s|$)/i;
  const queryArgs = params.get('args') || '';
  const ramGiB = navigator.deviceMemory;
  if (!compat || compat.deviceClass() !== 'desktop' || !(ramGiB >= 8) ||
      ['Android', 'iOS'].includes(compat.browser().os) || params.get('tier') === 'desktop' ||
      explicitBudget.test(queryArgs) || desktopRenderer.test(queryArgs)) return;

  async function configure() {
    const [gpu, commandLine] = await Promise.all([
      compat.probe(),
      fetch('UECommandLine.txt', { cache: 'no-cache' }).then(response => response.ok ? response.text() : ''),
    ]);
    const adapter = gpu.adapter;
    const existingArgs = commandLine + ' ' + (window.ueExtraArgs || []).join(' ');
    if (gpu.message || adapter?.integrated !== false || adapter.fallback ||
        explicitBudget.test(existingArgs) || desktopRenderer.test(existingArgs)) return;

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
  const ready = configure().catch(error => console.info('Using Unreal texture budget:', error.message));
  script.onload = event => ready.then(() => loaded?.call(script, event));
})();
