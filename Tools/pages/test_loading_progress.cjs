const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'loading-progress.js'), 'utf8');
function loadingScreen() {
  const elements = new Map();
  const timers = new Map();
  const events = new Map();
  const steps = new Map();
  let sequence = 0;
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {
      style: {}, setAttribute(name, value) { this[name] = value; },
      querySelector: () => ({ addEventListener() {} }),
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    URL, $, T: text => text, failed: false, lifted: false,
    document: { hidden: false, addEventListener() {} },
    window: { addEventListener(name, handler) { events.set(name, handler); } },
    ueSteps: { set(id, state, detail) { steps.set(id, detail); } },
    setTimeout(callback) { timers.set(++sequence, callback); return sequence; },
    clearTimeout(id) { timers.delete(id); },
  });
  const { count, ui } = vm.runInContext(source + '\n;({ count: canopyStartupBytes, ui: canopyLoading })', context);
  return { $, count, ui, timers, events, steps };
}

test('cache, concurrent reports, repeat ranges and retries count each startup byte once per build', () => {
  const { count } = loadingScreen();
  const base = 'https://example.test/canopy-clash/';
  const files = [{ url: 'app.wasm', size: 1000, sha1: 'one' }, { url: 'base.pak', size: 500, sha1: 'two' }];
  const bytes = count(files, base);
  const wasm = (n, sha1 = 'one') => bytes.report({ url: base + 'app.wasm', loaded: n, sha1 });
  assert.equal(bytes.total, 1500);
  assert.equal(wasm(500, 'old-build'), null);
  assert.equal(wasm(300).loaded, 300);
  assert.equal(wasm(300), null);
  assert.equal(wasm(100), null);
  assert.equal(bytes.report({ url: base + 'streamed.ucas', loaded: 999999, sha1: 'three' }), null);
  assert.equal(bytes.report({ url: base + 'base.pak', loaded: 500, sha1: 'two', cached: true }).loaded, 800);
  assert.equal(wasm(400).delta, 100);
  assert.equal(wasm(Infinity), null);
  assert.equal(wasm(1200).loaded, 1500);
  assert.equal(wasm(1000), null);
});

test('only reports move the indicator; an idle load can retry or resume naturally', () => {
  const { $, ui, timers, events, steps } = loadingScreen();
  ui.bytes(25, 100);
  assert.match($('progress-text').textContent, /Loading game data.*25%/);
  ui.stage('runtime');
  assert.match($('progress-text').textContent, /16%.*1\/6 stages/);
  const before = $('progress-text').textContent;
  for (const callback of [...timers.values()]) callback();
  assert.equal($('progress-text').textContent, before);
  assert.equal($('loading-retry').hidden, false);
  ui.bytes(100, 100);
  assert.equal($('progress-text').textContent, before);
  assert.equal($('loading-retry').hidden, true);
  ui.stage('map_loaded');
  assert.match($('progress-text').textContent, /50%.*3\/6 stages/);
  events.get('ue-progress')({ detail: { fraction: .7 } });
  events.get('ue-warmup')({ detail: { pso: 3, textures: 1 } });
  assert.match(steps.get('site'), /3 shaders remaining.*1 texture remaining.*Package queue 70%/);
  ui.stage('engine_init');
  assert.match($('progress-text').textContent, /50%/);
  ui.stage('first_frame');
  ui.stage('canvas');
  assert.match($('progress-text').textContent, /83%.*5\/6 stages/);
  ui.stage('playable');
  ui.stop();
  assert.match($('progress-text').textContent, /Ready.*100%/);
  assert.equal(timers.size, 0);
});
