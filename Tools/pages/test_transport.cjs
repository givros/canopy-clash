const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { runInNewContext } = require('node:vm');
const { gzipSync } = require('node:zlib');

const scope = 'https://example.test/canopy-clash/';
const original = Buffer.from('ABCDEFGHABCD');
const source = readFileSync(join(__dirname, 'transport.js'), 'utf8');

for (const supportsRanges of [true, false]) {
  test('byte-exact reads when the host ' + (supportsRanges ? 'honors Range' : 'returns 200'), async () => {
    const blobs = new Map([
      ['a.bin', Buffer.from('ABCD')],
      ['b.gzip.bin', gzipSync(Buffer.from('EFGH'))],
    ]);
    const self = {
      registration: { scope },
      async fetch(input, options) {
        const url = new URL(input);
        assert.ok(url.href.startsWith(scope));
        const data = blobs.get(url.pathname.split('/').pop());
        if (!data) return new Response(null, { status: 404 });
        if (supportsRanges && options.headers?.Range) {
          const [, a, z] = /bytes=(\d+)-(\d+)/.exec(options.headers.Range);
          return new Response(data.subarray(+a, +z + 1), {
            status: 206, headers: { 'Content-Range': 'bytes ' + a + '-' + z + '/' + data.length },
          });
        }
        return new Response(data);
      },
    };
    const install = runInNewContext(source + '\ninstallPagesTransport', {
      self, URL, Request, Response, Headers, ReadableStream, DecompressionStream, AbortSignal, AbortController,
    });
    install({ 'main.ucas': { size: 12, sha1: 'build', type: 'application/octet-stream',
      pieces: [...blobs.keys()], segments: [[0, 0, 0], [4, 1, 0], [8, 0, 0]] } });
    const url = scope + 'main.ucas';
    for (const [range, from, end] of [
      [null, 0, 12], ['bytes=2-9', 2, 10], ['bytes=4-5', 4, 6], ['bytes=-3', 9, 12], ['bytes=7-', 7, 12],
    ]) {
      const result = await self.fetch(url, range ? { headers: { Range: range } } : {});
      assert.equal(result.status, range ? 206 : 200);
      assert.equal(result.headers.get('Content-Length'), String(end - from));
      if (range) assert.equal(result.headers.get('Content-Range'), 'bytes ' + from + '-' + (end - 1) + '/12');
      assert.deepEqual(Buffer.from(await result.arrayBuffer()), original.subarray(from, end));
    }
    const head = await self.fetch(url, { method: 'HEAD' });
    assert.equal(head.body, null);
    assert.equal(head.headers.get('Content-Length'), '12');
    assert.equal((await self.fetch(url, { headers: { Range: 'bytes=20-' } })).status, 416);
    assert.equal((await self.fetch(url + '?v=old')).status, 410);
  });
}
