// Measure HTTP delivery of game assets in the service worker. Several parallel
// downloads share the same time window. Ranges already in the game's cache
// never reach this meter. Ignore tiny reads.
function canopyDeliveryMeter(change) {
  let constrained = false, slow = 0, fast = 0;
  let start = Infinity, end = 0, bytes = 0, requests = 0, delayed = 0;
  function reset() { start = Infinity; end = bytes = requests = delayed = 0; }
  return entry => {
    if (!(entry.transferSize > 0 && entry.encodedBodySize >= 16384 &&
          entry.responseStart > 0 && entry.responseEnd >= entry.responseStart)) return;
    if (requests && entry.startTime - end > 2500) reset();
    start = Math.min(start, entry.startTime);
    end = Math.max(end, entry.responseEnd);
    bytes += entry.encodedBodySize;
    requests++;
    if (entry.responseStart - entry.startTime >= 450) delayed++;
    const ms = end - start;
    if (requests < 3 || bytes < 128 * 1024 || ms <= 0 || (ms < 1500 && bytes < 1024 * 1024)) return;
    const mbps = bytes * 8 / (ms * 1000);
    slow = mbps < 2.5 || (mbps < 6 && delayed * 2 >= requests) ? slow + 1 : 0;
    fast = mbps >= 7 ? fast + 1 : 0;
    reset();
    const next = slow >= 2 || (constrained && fast < 2);
    if (next !== constrained) { constrained = next; change(next); }
  };
}

function installCanopyNetworkWorker() {
  let measured = null;
  const report = canopyDeliveryMeter(value => {
    measured = value;
    self.clients.matchAll().then(clients => {
      for (const client of clients) client.postMessage({ type: 'canopy-network', constrained: value });
    }).catch(() => {});
  });
  self.addEventListener('message', event => {
    if (event.data?.type === 'canopy-network-query' && measured !== null)
      event.source?.postMessage({ type: 'canopy-network', constrained: measured });
  });
  return report;
}

function installCanopyNetworkPage() {
  const link = navigator.connection;
  let measured = null;
  let gameReady = false;
  function apply() {
    if (!gameReady) return;
    const low = link?.saveData || (measured ?? ['slow-2g', '2g', '3g'].includes(link?.effectiveType));
    window.Module?._CanopySetNetworkPressure?.(low ? 1 : 0);
  }
  navigator.serviceWorker?.addEventListener('message', event => {
    if (event.data?.type !== 'canopy-network') return;
    measured = !!event.data.constrained;
    apply();
  });
  // The native module is installed after the page and the cache worker.
  window.addEventListener('ue-first-frame', () => {
    gameReady = true;
    navigator.serviceWorker?.controller?.postMessage({ type: 'canopy-network-query' });
    apply();
  }, { once: true });
  link?.addEventListener?.('change', () => { measured = null; apply(); });
}
