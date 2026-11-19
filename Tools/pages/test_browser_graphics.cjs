const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, 'browser-graphics.js'), 'utf8');

function page(search = '') {
  const navigations = [];
  const listeners = {};
  const location = {
    href: 'https://example.com/game/' + search,
    assign: url => navigations.push(url),
    reload: () => navigations.push(location.href),
  };
  const history = { state: {}, replaceState: (_state, _title, href) => { location.href = href; } };
  const window = { addEventListener: (type, fn) => { listeners[type] = fn; } };
  const policy = vm.runInNewContext(script + '\ncanopyGraphics', { location, history, window, URL });
  return { policy, listeners, navigations, location };
}

test('let the player request a single lighter configuration after a device loss', () => {
  const old = page('?lang=fr&sp=150&gpucheck=1&args=-culture%3Dfr%20-WebScreenPercentage%3D150#play');
  const button = { dataset: {} };
  old.policy.deviceLossText(button);
  assert.equal(old.navigations.length, 0);
  old.policy.reload(button);
  const target = new URL(old.navigations[0]);
  assert.equal(target.searchParams.get('gpuRecovery'), '1');
  assert.equal(target.searchParams.get('tier'), 'forward');
  assert.equal(target.searchParams.get('prewarm'), '0');
  assert.equal(target.searchParams.get('saved'), 'memory');
  assert.equal(target.searchParams.has('sp'), false);
  assert.equal(target.searchParams.has('gpucheck'), false);
  assert.equal(target.searchParams.get('args'), '-culture=fr');
  assert.equal(target.hash, '#play');
  const retry = page(target.search);
  const retryButton = { dataset: {} };
  assert.match(retry.policy.deviceLossText(retryButton), /again/);
  assert.equal(retryButton.dataset.gpuRetry, undefined);
  assert.equal(retry.navigations.length, 0);
});

test('a direct recovery link takes effect before boot without another navigation', () => {
  const direct = page('?gpuRecovery=1&saved=opfs&args=-WebQualityPreset%3DEpic%20-culture%3Dfr#play');
  direct.policy.normalizeLink();
  const url = new URL(direct.location.href);
  assert.equal(url.searchParams.get('saved'), 'memory');
  assert.equal(url.searchParams.get('prewarm'), '0');
  assert.equal(url.searchParams.get('tier'), 'forward');
  assert.equal(url.searchParams.get('args'), '-culture=fr');
  direct.policy.normalizeLink();
  assert.equal(direct.location.href, url.href);
  assert.equal(direct.navigations.length, 0);
});

test('cap the recovery surface on resize while retaining the engine input scale', () => {
  const { policy, listeners } = page('?gpuRecovery=1');
  const parent = { clientWidth: 865, clientHeight: 577 };
  const canvas = { ...parent, parentElement: parent, style: {} };
  const native = policy.canvasRatio(canvas, 1);
  function checkSize() {
    const w = Math.round(parseInt(canvas.style.maxWidth, 10) * native);
    const h = Math.round(parseInt(canvas.style.maxHeight, 10) * native);
    assert.ok(w > 0 && h > 0 && w * h <= 1280 * 720);
    assert.ok(Math.abs(w / h - parent.clientWidth / parent.clientHeight) < 0.01);
  }
  checkSize();
  parent.clientWidth = 3840;
  parent.clientHeight = 2160;
  listeners.resize();
  checkSize();
  const normal = page();
  assert.equal(normal.policy.canvasRatio(canvas, 1.5), 1.5);
  assert.equal(normal.listeners.resize, undefined);
});

test('skip the stress draw for shared or unidentified GPUs and preserve explicit choices', async () => {
  const { policy } = page();
  const browser = { name: 'Edge' };
  for (const integrated of [true, null]) {
    const adapter = { integrated, fallback: false };
    assert.ok(await policy.forwardReason('', 'auto', browser, async () => ({ adapter })));
  }
  const discrete = async () => ({ adapter: { integrated: false, fallback: false } });
  assert.equal(await policy.forwardReason('', 'auto', browser, discrete), '');
  const unusedProbe = () => assert.fail('fixed renderer should not probe twice');
  assert.equal(await policy.forwardReason('deferred', 'auto', browser, unusedProbe), '');
  assert.ok(await policy.forwardReason('forward', 'auto', browser, unusedProbe));
  assert.ok(await policy.forwardReason('', 'auto', { name: 'Firefox' }, unusedProbe));
});
