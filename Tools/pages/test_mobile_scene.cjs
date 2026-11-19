const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'mobile-scene-check.js'), 'utf8');
const alternate = vm.runInNewContext(source + '\ncanopyAlternateGraphics', { URL, window: {} });

test('the explicit mobile retry picks a distinct profile and keeps unrelated link options', () => {
  for (const deferred of [false, true]) {
    const next = alternate('https://host.test/game/?textures=astc&gpuRecovery=1&sp=99&args=-WebGPUSM5%20-MyTest', deferred);
    assert.equal(next.searchParams.get('textures'), 'astc');
    assert.equal(next.searchParams.get('tier'), deferred ? 'deferred' : 'forward');
    assert.equal(next.searchParams.get('sp'), deferred ? '80' : '65');
    assert.equal(next.searchParams.get('args'), deferred ? '-MyTest' : '-MyTest -WebQualityPreset=Low');
    assert.equal(next.searchParams.get('gpuRecovery'), null);
    assert.equal(next.searchParams.get('mobileGraphicsRetry'), '1');
  }
});
