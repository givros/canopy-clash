const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const test = require('node:test');
const vm = require('node:vm');

const helper = execFileSync('python', ['-c', 'from worker_update import WORKER_READY; print(WORKER_READY)'],
  { cwd: __dirname, encoding: 'utf8' });
const scope = 'https://example.com/game/';
const expected = scope + 'sw-build.js?isolate=1';

test('wait for both the current shard map and control of the revisiting page', async () => {
  const old = { scriptURL: scope + 'sw.js?isolate=1', state: 'activated' };
  const registration = { active: old };
  const container = { controller: old, register: async url => { assert.equal(url, expected); return registration; } };
  let claims = 0, polls = 0;
  const current = {
    scriptURL: expected, state: 'activated',
    postMessage(message) { assert.equal(message.type, 'claim'); claims++; },
  };
  const wait = vm.runInNewContext(helper + '\ncanopyReleaseWorker', {
    navigator: { serviceWorker: container }, location: { href: scope }, URL,
    performance: { now: () => polls * 75 }, swUrl: () => 'sw-build.js?isolate=1',
    setTimeout(resolve) {
      polls++;
      if (polls === 1) registration.active = current;
      if (polls === 2) container.controller = current;
      resolve();
    },
  });
  assert.equal(await wait(true), registration);
  assert.equal(container.controller, current);
  assert.equal(claims, 1);
  assert.equal(polls, 2);
  container.controller = null;
  assert.equal(await wait(false), registration);
  assert.equal(polls, 2);
});
