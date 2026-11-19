// This policy is loaded before Unreal's compatibility check and error card.
const canopyGraphics = {
  canvasRatio(canvas, ratio) {
    if (new URL(location.href).searchParams.get('gpuRecovery') !== '1') return ratio;
    const pixels = 1280 * 720;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!(width > 0 && height > 0)) return ratio;

    const fit = Math.min(ratio, Math.sqrt(pixels / (width * height)));
    const initialRatio = Math.min(Math.max(1, Math.floor(width * fit)) / width,
                                  Math.max(1, Math.floor(height * fit)) / height);
    // UE keeps the initial canvas/input scale for the life of the application.
    // Bound a later window enlargement in CSS as well, so the engine's own
    // resize event sees the capped surface and its pointer coordinates match.
    const fitWindow = () => {
      const w = canvas.parentElement.clientWidth;
      const h = canvas.parentElement.clientHeight;
      if (!(w > 0 && h > 0)) return;
      let maxWidth = w, maxHeight = h;
      if (Math.round(w * initialRatio) * Math.round(h * initialRatio) > pixels) {
        const scale = Math.sqrt(pixels / (w * h));
        maxWidth = Math.max(1, Math.floor(Math.floor(w * scale) / initialRatio));
        maxHeight = Math.max(1, Math.floor(Math.floor(h * scale) / initialRatio));
      }
      canvas.style.maxWidth = maxWidth + 'px';
      canvas.style.maxHeight = maxHeight + 'px';
    };
    Object.assign(canvas.style, { position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)' });
    fitWindow();
    window.addEventListener('resize', fitWindow, true);
    return initialRatio;
  },

  async forwardReason(choice, defaultTier, browser, probe) {
    if (choice) return choice === 'forward' ? 'forward renderer selected' : '';
    if (defaultTier === 'forward') return 'forward renderer by default';
    if (browser.name === 'Firefox') return 'forward renderer for Firefox';
    if (defaultTier !== 'auto') return '';

    // UE already caches the real adapter probe. Avoid requesting a second
    // device for its full-HD stress draw on shared or unidentified hardware.
    const { adapter } = await probe();
    if (!adapter || adapter.fallback || adapter.integrated !== false) {
      return 'forward renderer for a shared or unclassified GPU';
    }
    return '';
  },

  deviceLossText(button) {
    if (new URL(location.href).searchParams.get('gpuRecovery') === '1') {
      return 'The graphics device stopped again with safer graphics. Download the log for troubleshooting.';
    }
    button.dataset.gpuRetry = '1';
    button.textContent = 'Restart with safer graphics';
    return 'The graphics device stopped. Restart with safer graphics to use a smaller render surface. Settings for that session are temporary.';
  },

  reload(button) {
    if (!button.dataset.gpuRetry) {
      location.reload();
      return;
    }
    location.assign(this.recoveryUrl().href);
  },

  recoveryUrl() {
    const url = new URL(location.href);
    url.searchParams.set('gpuRecovery', '1');
    url.searchParams.set('tier', 'forward');
    url.searchParams.set('prewarm', '0');
    url.searchParams.set('saved', 'memory');
    // A diagnostic run can deliberately bypass the normal renderer choice.
    for (const key of ['bench', 'gpucheck', 'harness', 'compat', 'sp']) url.searchParams.delete(key);
    const args = url.searchParams.get('args') || '';
    const kept = args.replace(/(?:^|\s)"?-Web(?:ScreenPercentage=\d+|QualityPreset=\w+)"?(?=\s|$)/gi, ' ').trim();
    if (kept !== args) {
      if (kept) url.searchParams.set('args', kept);
      else url.searchParams.delete('args');
    }
    return url;
  },

  normalizeLink() {
    if (new URL(location.href).searchParams.get('gpuRecovery') !== '1') return;
    const link = this.recoveryUrl().href;
    if (link !== location.href) history.replaceState(history.state, '', link);
  },
};
