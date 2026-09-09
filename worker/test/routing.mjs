/* End-to-end tests for the Worker, without Cloudflare and without WWFF.
 *
 *   node worker/test/routing.mjs
 *
 * KV is replaced by a Map and the upstream by a stub, so this exercises the
 * three things that actually protect the key — CORS, the kill switch and the
 * rate limiting — and proves that nothing reaches "WWFF" that should not.
 *
 * The stub also records what it was sent, which is how the last test can assert
 * that the API key travels to WWFF and appears nowhere else.
 */
import worker from '../src/index.js';

let passed = 0, failed = 0;
function ok(condition, what) {
  if (condition) { passed++; console.log(`  ✓ ${what}`); }
  else { failed++; console.log(`  ✗ ${what}`); }
}

/* --- a KV namespace that is just a Map, with the TTL ignored --- */
function fakeKv(initial) {
  const store = new Map(Object.entries(initial || {}));
  return {
    store,
    async get(k) { return store.has(k) ? store.get(k) : null; },
    async put(k, v) { store.set(k, String(v)); },
    async delete(k) { store.delete(k); },
  };
}

function makeEnv(over) {
  return {
    WWFF_BASE: 'https://spots-dev.example',
    WWFF_API_KEY: 'TEST-KEY-NOT-REAL',
    ALLOWED_ORIGINS: 'https://diana-onff.github.io,http://localhost:8011',
    LIMIT_IP_SPOTS: '5', LIMIT_IP_WINDOW: '600',
    LIMIT_IP_AGENDA: '10', LIMIT_GLOBAL_MINUTE: '40',
    UPSTREAM_TIMEOUT_MS: '8000',
    DIANA_KV: fakeKv(),
    ...over,
  };
}

/* --- stand in for WWFF and remember every call --- */
const sent = [];
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, opts) => {
  sent.push({ url: String(url), opts });
  return new Response(JSON.stringify({ spot_id: 12345 }), {
    status: 201, headers: { 'Content-Type': 'application/json' },
  });
};

const ORIGIN = 'https://diana-onff.github.io';
const spot = {
  activator: 'ON3VZ/P', spotter: 'ON3VZ',
  frequency_khz: 14285, mode: 'SSB', reference: 'ONFF-0104',
};

function post(path, body, opts) {
  const o = opts || {};
  const headers = { 'Content-Type': 'application/json', 'CF-Connecting-IP': o.ip || '198.51.100.7' };
  if (o.origin !== null) headers.Origin = o.origin || ORIGIN;
  return new Request(`https://worker.example${path}`, {
    method: 'POST', headers, body: JSON.stringify(body),
  });
}

console.log('\n[1] CORS preflight');
{
  const good = await worker.fetch(new Request('https://worker.example/spot', {
    method: 'OPTIONS', headers: { Origin: ORIGIN },
  }), makeEnv());
  ok(good.status === 204, 'a known origin gets 204');
  ok(good.headers.get('Access-Control-Allow-Origin') === ORIGIN, 'and is echoed back');
  ok(good.headers.get('Vary') === 'Origin', 'Vary: Origin is set so caches cannot cross the wires');

  const bad = await worker.fetch(new Request('https://worker.example/spot', {
    method: 'OPTIONS', headers: { Origin: 'https://evil.example' },
  }), makeEnv());
  ok(bad.status === 403, 'an unknown origin gets 403');
  ok(!bad.headers.get('Access-Control-Allow-Origin'), 'and no CORS header at all');
}

console.log('\n[2] a preflight costs nothing');
{
  const env = makeEnv();
  await worker.fetch(new Request('https://worker.example/spot', {
    method: 'OPTIONS', headers: { Origin: ORIGIN },
  }), env);
  ok(env.DIANA_KV.store.size === 0, 'no KV writes — the 1000/day budget is untouched');
}

console.log('\n[3] a blocked origin never reaches WWFF');
{
  const before = sent.length;
  const r = await worker.fetch(post('/spot', spot, { origin: 'https://evil.example' }), makeEnv());
  ok(r.status === 403, 'refused with 403');
  ok(sent.length === before, 'nothing was forwarded');
}

console.log('\n[4] an invalid spot never reaches WWFF');
{
  const env = makeEnv();
  const before = sent.length;
  const r = await worker.fetch(post('/spot', { ...spot, frequency_khz: 14.285 }, {}), env);
  const body = await r.json();
  ok(r.status === 400, 'refused with 400');
  ok(Array.isArray(body.details) && body.details.length === 1, 'and says what was wrong');
  ok(sent.length === before, 'nothing was forwarded');
  ok(env.DIANA_KV.store.size === 0, 'and it did not spend a rate-limit slot');
}

console.log('\n[5] a valid spot is forwarded, once');
{
  const env = makeEnv();
  const before = sent.length;
  const r = await worker.fetch(post('/spot', spot, {}), env);
  ok(r.status === 201, 'the upstream status is passed through');
  ok(sent.length === before + 1, 'exactly one call went out');
  ok(sent[sent.length - 1].url === 'https://spots-dev.example/api/spots/add', 'to the right endpoint');
  ok(env.DIANA_KV.store.size === 2, 'two counters written: per IP and global');
}

console.log('\n[6] the per-IP limit holds, and one IP cannot block another');
{
  const env = makeEnv({ LIMIT_IP_SPOTS: '2' });
  await worker.fetch(post('/spot', spot, { ip: '198.51.100.1' }), env);
  await worker.fetch(post('/spot', spot, { ip: '198.51.100.1' }), env);
  const third = await worker.fetch(post('/spot', spot, { ip: '198.51.100.1' }), env);
  ok(third.status === 429, 'the third from that IP is refused');
  ok(third.headers.get('Retry-After') === '600', 'with a Retry-After the app can use');

  const other = await worker.fetch(post('/spot', spot, { ip: '203.0.113.9' }), env);
  ok(other.status === 201, 'a different IP is unaffected');
}

console.log('\n[7] the global ceiling holds even across different IPs');
{
  const env = makeEnv({ LIMIT_GLOBAL_MINUTE: '3' });
  for (let i = 0; i < 3; i++) {
    await worker.fetch(post('/spot', spot, { ip: `203.0.113.${i}` }), env);
  }
  const before = sent.length;
  const r = await worker.fetch(post('/spot', spot, { ip: '203.0.113.99' }), env);
  const body = await r.json();
  ok(r.status === 429, 'the fourth is refused, from a fresh IP');
  ok(/as a whole/.test(body.error), 'and the message says it is Diana, not you');
  ok(sent.length === before, 'nothing reached WWFF');
}

console.log('\n[8] the kill switch');
{
  const env = makeEnv({ DIANA_KV: fakeKv({ switch: 'off' }) });
  const before = sent.length;
  const r = await worker.fetch(post('/spot', spot, {}), env);
  const body = await r.json();
  ok(r.status === 503, 'everything is refused with 503');
  ok(body.enabled === false, 'and the app can see why');
  ok(sent.length === before, 'nothing reached WWFF');

  const status = await worker.fetch(new Request('https://worker.example/status', {
    headers: { Origin: ORIGIN },
  }), env);
  ok((await status.json()).enabled === false, '/status reports it too, without a key');
}

console.log('\n[9] a missing key is caught before anything is sent');
{
  const env = makeEnv({ WWFF_API_KEY: undefined });
  const before = sent.length;
  const r = await worker.fetch(post('/spot', spot, {}), env);
  ok(r.status === 500, 'refused with 500');
  ok(sent.length === before, 'nothing reached WWFF');
}

console.log('\n[10] the key goes to WWFF and nowhere else');
{
  const env = makeEnv();
  sent.length = 0;
  const r = await worker.fetch(post('/spot', { ...spot, remarks: 'test' }, {}), env);
  const call = sent[0];
  ok(call.opts.headers['X-API-Key'] === 'TEST-KEY-NOT-REAL', 'it is in the upstream header');
  ok(!JSON.stringify(call.opts.body).includes('TEST-KEY'), 'it is not in the forwarded body');

  const text = await r.text();
  ok(!text.includes('TEST-KEY'), 'it is not in the response to the browser');
  ok(![...r.headers.keys()].some(k => /key|auth/i.test(k)), 'no key-ish header comes back either');

  const stored = [...env.DIANA_KV.store.entries()].map(([k, v]) => k + v).join('');
  ok(!stored.includes('TEST-KEY'), 'it is not in KV');
  ok(!stored.includes('198.51.100'), 'and neither is the raw IP address');
}

console.log('\n[11] unknown routes and methods');
{
  ok((await worker.fetch(post('/anders', spot, {}), makeEnv())).status === 404, 'unknown path gives 404');
  ok((await worker.fetch(new Request('https://worker.example/spot', {
    method: 'GET', headers: { Origin: ORIGIN },
  }), makeEnv())).status === 405, 'GET on /spot gives 405');
}

console.log('\n[12] a broken upstream becomes an honest error');
{
  globalThis.fetch = async () => { throw Object.assign(new Error('aborted'), { name: 'AbortError' }); };
  const r = await worker.fetch(post('/spot', spot, {}), makeEnv());
  const body = await r.json();
  ok(r.status === 504, 'a timeout gives 504');
  ok(/in time/.test(body.error), 'with a message a user can understand');
  ok(!/AbortError|stack/i.test(JSON.stringify(body)), 'and no internals leak out');
}

globalThis.fetch = realFetch;
console.log(`\n${failed === 0 ? 'ALL OK' : 'FAILED'} — ${passed} passed, ${failed} failed\n`);
process.exit(failed === 0 ? 0 : 1);
