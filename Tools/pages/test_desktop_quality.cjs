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
      deviceClass: () => 'desktop',
      browser: () => ({ name: options.browser || 'Edge', os: 'Windows' }),
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
    navigator: { deviceMemory: 8 },
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
    assert.ok(args.includes('-WebQualityPreset=Medium'));
  }
});

test('leave the resolution to manual, recovery and lower-powered profiles', async () => {
  for (const options of [
    { search: '?sp=90' }, { search: '?args=-WebScreenPercentage%3D80' },
    { search: '?tier=forward' }, { renderer: 'forward' }, { search: '?gpuRecovery=1' },
    { search: '?gpucheck=1' }, { adapter: { integrated: true } }, { adapter: { integrated: null } },
    { adapter: { fallback: true } }, { browser: 'Firefox' },
  ]) {
    const args = await start(options);
    assert.ok(!args.some(arg => arg.startsWith('-WebScreenPercentage=')), JSON.stringify(options));
  }
  assert.deepEqual(await start({ search: '?args=-WebQualityPreset%3DEpic' }), ['-TempleWebTexturePool=512']);
  assert.deepEqual(await start({ search: '?gpuRecovery=1' }), ['-WebQualityPreset=Medium']);
});
