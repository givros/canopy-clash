const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'network-quality.js'), 'utf8');

test('sustained slow transfers lower detail and fast transfers restore it', () => {
  const makeMeter = vm.runInNewContext(source + '\ncanopyDeliveryMeter');
  const changes = [];
  const meter = makeMeter(value => changes.push(value));
  let now = 1;
  function window(bytes, duration, cached = false) {
    for (let i = 0; i < 3; i++) {
      const startTime = now;
      now += duration;
      meter({ startTime, responseStart: startTime + 30, responseEnd: now,
        transferSize: cached ? 0 : bytes + 300, encodedBodySize: bytes });
    }
  }
  window(65536, 700, true);
  window(65536, 700);
  assert.deepEqual(changes, []);
  window(65536, 700);
  assert.deepEqual(changes, [true]);
  window(512000, 100);
  window(512000, 100);
  assert.deepEqual(changes, [true, false]);
});
