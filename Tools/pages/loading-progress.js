// Count decoded startup data. The service worker reports a cumulative offset for
// a whole file, also on cache hits. Range traffic for the streamed world has
// no fixed startup total and is intentionally outside this counter.
function canopyStartupBytes(files, base) {
  const entries = new Map(files.map(file => [new URL(file.url, base).href, { file, seen: 0 }]));
  const total = files.reduce((sum, file) => sum + file.size, 0);
  let loaded = 0;
  return {
    total,
    report(data) {
      const entry = entries.get(data.url);
      if (!entry || data.sha1 !== entry.file.sha1 || !Number.isFinite(data.loaded)) return null;
      const next = Math.min(entry.file.size, data.loaded);
      if (next <= entry.seen) return null;
      const delta = next - entry.seen;
      entry.seen = next;
      loaded += delta;
      return { loaded, total, delta, file: entry.file };
    },
  };
}

// These are completed milestones, not a timer or an estimate of remaining work.
// The last two signals can arrive in either order on the browser's main thread.
const canopyLoading = (() => {
  const stages = ['runtime', 'engine_init', 'map_loaded', 'first_frame', 'canvas', 'playable'];
  const done = new Set();
  let levelStarted = false;
  let packages = null;
  let shaderCount = 0;
  let textureCount = 0;
  let retryTimer;
  let ended = false;
  const retry = $('loading-retry');
  function activity() {
    if (ended || failed || lifted) return;
    retry.hidden = true;
    clearTimeout(retryTimer);
    retryTimer = setTimeout(() => {
      if (!ended && !failed && !lifted && !document.hidden) retry.hidden = false;
    }, 75000);
  }
  retry.querySelector('button').addEventListener('click', () => location.reload());
  document.addEventListener('visibilitychange', () => { if (!document.hidden) activity(); });
  function stop() {
    ended = true;
    clearTimeout(retryTimer);
    retry.hidden = true;
  }
  function bar(text, percent) {
    const label = $('progress-text');
    if (label.textContent !== text) label.textContent = text;
    const value = $('progressbar');
    value.setAttribute('aria-valuenow', String(percent));
    value.setAttribute('aria-valuetext', text);
    $('bar').style.width = percent + '%';
  }
  function showLevel() {
    if (!levelStarted) return;
    const percent = Math.floor(100 * done.size / stages.length);
    const count = done.size + '/' + stages.length + ' ' + T('stages');
    const next = !done.has('engine_init') ? 'Initializing the engine'
      : !done.has('map_loaded') ? 'Loading the map'
      : !done.has('first_frame') ? 'Preparing the first frame'
      : !done.has('canvas') ? 'Waiting for the first rendered frame'
      : !done.has('playable') ? 'Preparing gameplay' : 'Ready';
    const detail = percent + '% · ' + count;
    const remaining = [];
    if (shaderCount) remaining.push(shaderCount + ' ' + T(shaderCount === 1 ? 'shader remaining' : 'shaders remaining'));
    if (textureCount) remaining.push(textureCount + ' ' + T(textureCount === 1 ? 'texture remaining' : 'textures remaining'));
    if (packages !== null) remaining.push(T('Package queue') + ' ' + Math.floor(100 * packages) + '%');
    ueSteps.set('site', done.size === stages.length ? 'done' : 'active',
      done.size === stages.length ? detail : [detail, ...remaining].join(' · '));
    bar(T(next) + ' · ' + detail, percent);
  }
  function stage(key) {
    if (ended || failed || lifted || done.has(key)) return;
    // A map or world-frame notification also proves the earlier synchronous
    // engine stages finished when its stdout markers arrive late or batched.
    const index = stages.indexOf(key);
    if (index < 0) return;
    if (index <= 3) {
      for (let i = 0; i <= index; i++) done.add(stages[i]);
      levelStarted = true;
    } else {
      done.add(key);
    }
    activity();
    showLevel();
  }
  window.addEventListener('ue-progress', ({ detail }) => {
    const fraction = detail?.fraction;
    if (ended || failed || !Number.isFinite(fraction) || fraction < 0 || fraction > 1 || packages === fraction) return;
    packages = fraction;
    activity();
    showLevel();
  });
  window.addEventListener('ue-warmup', ({ detail }) => {
    if (ended || failed || !detail) return;
    const shaders = Math.max(0, Math.floor(Number(detail.pso) || 0));
    const textures = Math.max(0, Math.floor(Number(detail.textures) || 0));
    if (shaders === shaderCount && textures === textureCount) return;
    shaderCount = shaders;
    textureCount = textures;
    activity();
    showLevel();
  });
  function bytes(loaded, total) {
    if (ended || failed || lifted || !total) return;
    activity();
    const percent = Math.floor(100 * loaded / total);
    const mib = bytes => (bytes / 1048576).toFixed(1);
    const detail = percent + '% · ' + mib(loaded) + ' / ' + mib(total) + ' MiB';
    ueSteps.set('download', loaded === total ? 'done' : 'active', detail);
    if (!levelStarted) bar(T('Loading game data') + ' · ' + detail, percent);
  }
  activity();
  return { stage, bytes, stop };
})();
