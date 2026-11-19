const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const shell = fs.readFileSync(path.join(__dirname, '../../Build/Wasm/Template/texture-budget.js'), 'utf8');

async function start(options = {}) {
  const adapter = { integrated: false, limits: { maxBufferSize: 1024 ** 3 }, ...options.adapter };
  const window = {
    devicePixelRatio: options.dpr ?? 1,
    ueCompat: {
      deviceClass: () => options.deviceClass || 'desktop',
      browser: () => ({ name: options.browser || 'Edge', os: options.os || 'Windows' }),
      probe: async () => ({ adapter }),
    },
  };
  const [clientWidth, clientHeight] = options.size ?? [1920, 1080];
  const document = {
    currentScript: { onload() {} },
    getElementById: () => ({ clientWidth, clientHeight }),
    querySelector: () => null,
  };
  vm.runInNewContext(shell, {
    window, document, URLSearchParams,
    location: { search: options.search || '' },
    navigator: { deviceMemory: options.ram === undefined ? 8 : options.ram },
    localStorage: { getItem: () => options.renderer || null },
    sessionStorage: { getItem: () => null },
    fetch: async () => ({ ok: true, text: async () => '' }),
  });
  await document.currentScript.onload();
  return Array.from(window.ueExtraArgs || []);
}

test('scale only the 3D scene for the initial desktop viewport', async () => {
  for (const [width, height, scale] of [[1280, 720, 100], [1600, 900, 100], [1920, 1080, 83], [2560, 1440, 62], [3840, 2160, 41]]) {
    const args = await start({ size: [width, height], dpr: 2 });
    assert.ok(args.includes('-WebScreenPercentage=' + scale));
    assert.ok(args.includes('-CanopyWebAdaptive=' + scale));
    assert.ok(args.includes('-WebQualityPreset=Medium'));
  }
});

test('keep manual and recovery settings', async () => {
  for (const options of [
    { search: '?sp=90' }, { search: '?args=-WebScreenPercentage%3D80' },
    { search: '?tier=forward' }, { renderer: 'forward' }, { search: '?gpuRecovery=1' },
    { search: '?gpucheck=1' },
  ]) {
    const args = await start(options);
    assert.ok(!args.some(arg => arg.startsWith('-WebScreenPercentage=')), JSON.stringify(options));
    assert.ok(!args.some(arg => arg.startsWith('-CanopyWebAdaptive=')));
  }
  assert.deepEqual(await start({ search: '?args=-WebQualityPreset%3DEpic' }), ['-TempleWebTexturePool=512']);
  assert.deepEqual(await start({ search: '?gpuRecovery=1' }), ['-WebQualityPreset=Medium']);
});

test('adapt with shared GPUs and other desktop browsers without extending their memory pool', async () => {
  for (const options of [{ adapter: { integrated: true } }, { adapter: { integrated: null } },
    { adapter: { fallback: true } }, { browser: 'Firefox', adapter: { integrated: true } }]) {
    const args = await start(options);
    assert.ok(args.includes('-CanopyWebAdaptive=' + (options.adapter.fallback ? 50 : 83)));
    assert.ok(!args.includes('-CanopyWebHandheld'));
    assert.ok(!args.some(arg => arg.startsWith('-TempleWebTexturePool=')));
  }
});

test('use frame timings or GPU timestamps on handhelds without expanding the texture pool', async () => {
  const iphone = { os: 'iOS', browser: 'Chrome', deviceClass: 'ios', dpr: 3, size: [874, 402], ram: null };
  const timed = await start({ ...iphone, adapter: { features: ['texture-compression-astc', 'timestamp-query'] } });
  assert.deepEqual(timed, ['-WebQualityPreset=Medium', '-WebScreenPercentage=100', '-CanopyWebAdaptive=100',
    '-CanopyWebHandheld', '-CanopyWebGpuTiming']);
  const untimed = await start({ os: 'Android', browser: 'Chrome', deviceClass: 'android', size: [800, 360], ram: 4 });
  assert.deepEqual(untimed, ['-WebQualityPreset=Medium', '-WebScreenPercentage=85', '-CanopyWebAdaptive=85',
    '-CanopyWebHandheld']);
  assert.deepEqual(await start({ ...iphone, search: '?adaptive=0' }), ['-WebQualityPreset=Medium', '-WebScreenPercentage=100']);
  assert.deepEqual(await start({ ...iphone, search: '?sp=90' }), ['-WebQualityPreset=Medium']);
});
