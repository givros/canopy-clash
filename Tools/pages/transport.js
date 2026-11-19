// GitHub Pages serves static files. Translate UE's reads into reads of the
// content-addressed files in this release, including fetches inside Epic's SW.
function installPagesTransport(files) {
  const network = self.fetch.bind(self);
  const scope = self.registration.scope;
  const table = new Map(Object.entries(files).map(([path, item]) => [new URL(path, scope).href, item]));

  function readRange(value, size) {
    if (!value) return [0, size];
    const match = /^bytes=(\d*)-(\d*)$/i.exec(value);
    if (!match || (!match[1] && !match[2])) return null;
    const start = match[1] ? Number(match[1]) : Math.max(0, size - Number(match[2]));
    const end = match[1] && match[2] ? Math.min(size, Number(match[2]) + 1) : size;
    return start < end ? [start, end] : null;
  }

  function findSegment(segments, offset) {
    let lo = 0, hi = segments.length;
    while (lo + 1 < hi) {
      const mid = Math.floor((lo + hi) / 2);
      if (segments[mid][0] <= offset) lo = mid;
      else hi = mid;
    }
    return lo;
  }

  // All intervals below are half-open. Merge physically adjacent segments
  // before issuing a request, even when a range straddles IoStore blocks.
  function* spans(file, start, end) {
    let previous = null;
    for (let i = findSegment(file.segments, start); start < end; i++) {
      const [logical, piece, offset] = file.segments[i];
      const next = Math.min(end, file.segments[i + 1]?.[0] ?? file.size);
      const first = offset + start - logical;
      if (previous && previous.piece === piece && previous.end === first) {
        previous.end += next - start;
      } else {
        if (previous) yield previous;
        previous = { piece, start: first, end: first + next - start };
      }
      start = next;
    }
    if (previous) yield previous;
  }

  async function* readSpan(file, span, signal) {
    const name = file.pieces[span.piece];
    const compressed = name.endsWith('.gzip.bin');
    const init = { signal };
    if (!compressed) init.headers = { Range: 'bytes=' + span.start + '-' + (span.end - 1) };
    const response = await network(new URL(name, scope), init);
    if ((response.status !== 200 && response.status !== 206) || !response.body) {
      throw new Error('Pages asset ' + name + ' returned HTTP ' + response.status);
    }
    let skip = span.start;
    let body = response.body;
    if (compressed) {
      body = body.pipeThrough(new DecompressionStream('gzip'));
    } else if (response.status === 206) {
      const actual = /^bytes (\d+)-(\d+)\/\d+$/.exec(response.headers.get('Content-Range') || '');
      if (!actual || Number(actual[1]) !== span.start || Number(actual[2]) !== span.end - 1) {
        throw new Error('Incorrect byte range for Pages asset ' + name);
      }
      skip = 0;
    }
    let remaining = span.end - span.start;
    const reader = body.getReader();
    try {
      while (remaining > 0) {
        const { value, done } = await reader.read();
        if (done) throw new Error('Truncated Pages asset ' + name);
        const from = Math.min(skip, value.byteLength);
        skip -= from;
        const count = Math.min(remaining, value.byteLength - from);
        if (count) {
          remaining -= count;
          yield value.subarray(from, from + count);
        }
      }
    } finally {
      await reader.cancel().catch(() => {});
    }
  }

  self.fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : input, scope);
    const path = url.origin + url.pathname.replace(/\/{2,}/g, '/');
    const file = table.get(path);
    if (!file) return network(input, init);
    const request = new Request(input, init);
    if (request.method !== 'GET' && request.method !== 'HEAD') return network(input, init);
    if (request.cache === 'only-if-cached') return new Response(null, { status: 504 });
    if (url.searchParams.has('v') && url.searchParams.get('v') !== file.sha1) {
      return new Response(null, { status: 410 });
    }
    const range = request.headers.get('Range');
    const interval = readRange(range, file.size);
    const headers = new Headers({ 'Accept-Ranges': 'bytes', 'Content-Type': file.type });
    if (!interval) {
      headers.set('Content-Range', 'bytes */' + file.size);
      return new Response(null, { status: 416, headers });
    }
    const [start, end] = interval;
    headers.set('Content-Length', String(end - start));
    if (range) headers.set('Content-Range', 'bytes ' + start + '-' + (end - 1) + '/' + file.size);
    const options = { status: range ? 206 : 200, headers };
    if (request.method === 'HEAD') return new Response(null, options);
    const abort = new AbortController();
    const signal = AbortSignal.any([request.signal, abort.signal]);
    const chunks = (async function* () {
      for (const span of spans(file, start, end)) yield* readSpan(file, span, signal);
    })();
    return new Response(new ReadableStream({
      async pull(controller) {
        try {
          const next = await chunks.next();
          if (next.done) controller.close();
          else controller.enqueue(next.value);
        } catch (error) {
          controller.error(error);
        }
      },
      cancel() {
        abort.abort();
        return chunks.return();
      },
    }), options);
  };
  return table;
}
