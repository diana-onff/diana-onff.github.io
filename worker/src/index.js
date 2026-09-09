/* ==================================================================== *
 * Diana — Spotline proxy
 *
 * WWFF hands out one API key per application and says, in as many words:
 * keep it server-side. Diana is a static page on GitHub Pages, so there is
 * no server to keep it on — anything the page can read, every visitor can
 * read. This Worker is that missing server, and it is the only thing in the
 * whole project that ever sees the key.
 *
 * The value of a proxy is not that it forwards. It is what it REFUSES:
 *
 *   - unknown fields are dropped, never passed on
 *   - callsign, frequency, mode and reference are checked here, so nonsense
 *     costs nothing from the shared WWFF budget
 *   - one IP cannot spend the budget, and Diana as a whole cannot either
 *   - one KV key turns everything off within seconds, without a deploy
 *
 * A proxy that forwards everything is your key given away with an extra hop
 * in between.
 *
 * On logging: this thing sees every spot that passes through it. Counters and
 * status codes go to the log, nothing else. No callsigns, no positions, no
 * remarks. See log() at the bottom.
 * ==================================================================== */

const VERSION = '1.0.0';

/* ---------------------------------------------------------------- limits */

/* Amateur bands in kHz, generously drawn. The point is to reject a typo — a
 * frequency in MHz instead of kHz, a digit too many — not to police band
 * plans. Allocations differ per ITU region (40m runs to 7300 in the US, 80m to
 * 4000), so the ranges cover the widest case: a legitimate spot from anywhere
 * in the world must get through. */
const BANDS_KHZ = [
  [1800, 2000], [3500, 4000], [5250, 5450], [7000, 7300],
  [10100, 10150], [14000, 14350], [18068, 18168], [21000, 21450],
  [24890, 24990], [28000, 29700], [50000, 54000], [70000, 70500],
  [144000, 148000], [220000, 225000], [430000, 450000],
  [902000, 928000], [1240000, 1300000],
];

const MODES = new Set([
  'CW', 'SSB', 'USB', 'LSB', 'AM', 'FM',
  'DATA', 'DIGI', 'FT8', 'FT4', 'RTTY', 'PSK', 'JS8', 'SSTV',
]);

/* A callsign is hard to pin down with a regular expression — /P, /QRP, /MM,
 * special event calls, three-letter prefixes. So this checks the shape rather
 * than the grammar: letters, digits and slashes, at least one of each of the
 * first two, and the 16 characters the API allows. Anything past that is
 * WWFF's judgement to make, not ours. */
const CALL_RE = /^[A-Z0-9]+(\/[A-Z0-9]+)*$/;

/* WWFF references are <prefix>FF-<four digits>: ONFF-0001, DLFF-0123, GFF-0042. */
const REF_RE = /^[A-Z0-9]{1,4}FF-\d{4}$/;

/* ---------------------------------------------------------------- helpers */

const json = (body, status, extra) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...(extra || {}) },
  });

const num = (v, fallback) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/* The IP address is needed to count per visitor, but storing it would make this
 * Worker hold a list of who spotted what and when. A truncated hash counts just
 * as well and cannot be read back into an address. */
async function ipKey(request) {
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const bytes = new TextEncoder().encode('diana:' + ip);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].slice(0, 8)
    .map(b => b.toString(16).padStart(2, '0')).join('');
}

function corsHeaders(request, env) {
  const origin = request.headers.get('Origin') || '';
  const allowed = (env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!allowed.includes(origin)) return null;
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    /* Two different origins get two different answers from this URL, so any
     * cache in between has to key on it. Leave this out and one visitor's CORS
     * headers can be served to another. */
    'Vary': 'Origin',
  };
}

/* ------------------------------------------------------------ validation */

/* Every validator returns either {ok: true, value} or {ok: false, error}. The
 * error text is meant for a human staring at a form, so it says what is wrong
 * rather than which rule fired. */

function checkCall(raw, field) {
  const v = String(raw || '').trim().toUpperCase();
  if (!v) return { ok: false, error: `${field} is missing` };
  if (v.length > 16) return { ok: false, error: `${field} is longer than 16 characters` };
  if (!CALL_RE.test(v)) return { ok: false, error: `${field} does not look like a callsign` };
  if (!/[0-9]/.test(v) || !/[A-Z]/.test(v)) {
    return { ok: false, error: `${field} needs at least one letter and one digit` };
  }
  return { ok: true, value: v };
}

function checkReference(raw) {
  const v = String(raw || '').trim().toUpperCase();
  if (!v) return { ok: false, error: 'reference is missing' };
  if (!REF_RE.test(v)) {
    return { ok: false, error: 'reference must look like ONFF-0001' };
  }
  return { ok: true, value: v };
}

function checkFrequency(raw) {
  const v = num(raw, null);
  if (v === null) return { ok: false, error: 'frequency_khz is not a number' };
  const inBand = BANDS_KHZ.some(([lo, hi]) => v >= lo && v <= hi);
  if (!inBand) {
    /* The most common mistake by far is MHz where kHz was meant — 14.074
     * instead of 14074 — so say so instead of a bare rejection. */
    const hint = v < 1000 ? ' (did you mean kHz? 14.074 MHz is 14074)' : '';
    return { ok: false, error: `frequency_khz ${v} is not in an amateur band${hint}` };
  }
  return { ok: true, value: v };
}

function checkMode(raw) {
  const v = String(raw || '').trim().toUpperCase();
  if (!v) return { ok: false, error: 'mode is missing' };
  if (!MODES.has(v)) {
    return { ok: false, error: `mode ${v} is not one of ${[...MODES].join(', ')}` };
  }
  return { ok: true, value: v };
}

function checkRemarks(raw) {
  if (raw === undefined || raw === null || raw === '') return { ok: true, value: undefined };
  const v = String(raw).trim();
  if (v.length > 100) return { ok: false, error: 'remarks is longer than 100 characters' };
  return { ok: true, value: v };
}

function checkLatLon(lat, lon) {
  if (lat === undefined && lon === undefined) return { ok: true, value: undefined };
  const la = num(lat, null), lo = num(lon, null);
  /* Half a position is worse than none: it would put the activator on the
   * equator or the Greenwich meridian without anyone noticing. */
  if (la === null || lo === null) return { ok: false, error: 'latitude and longitude must come as a pair' };
  if (la < -90 || la > 90) return { ok: false, error: 'latitude is outside -90..90' };
  if (lo < -180 || lo > 180) return { ok: false, error: 'longitude is outside -180..180' };
  return { ok: true, value: { latitude: la, longitude: lo } };
}

function checkUtc(raw, field) {
  const v = String(raw || '').trim();
  if (!v) return { ok: false, error: `${field} is missing` };
  const t = Date.parse(v);
  if (Number.isNaN(t)) return { ok: false, error: `${field} is not a valid UTC time` };
  return { ok: true, value: v, at: t };
}

/* ------------------------------------------------------------ the payloads */

/* Note what these two functions do NOT do: copy the incoming object. They build
 * a new one field by field. Anything the caller invented — an extra key, a
 * nested object, an attempt at an injection — never reaches WWFF, because it is
 * never picked up. */

function buildSpot(body) {
  const errors = [];
  const out = {};
  const take = (check, key) => {
    if (!check.ok) { errors.push(check.error); return; }
    if (check.value !== undefined) out[key] = check.value;
  };

  take(checkCall(body.activator, 'activator'), 'activator');
  take(checkCall(body.spotter, 'spotter'), 'spotter');
  take(checkFrequency(body.frequency_khz), 'frequency_khz');
  take(checkMode(body.mode), 'mode');
  take(checkReference(body.reference), 'reference');
  take(checkRemarks(body.remarks), 'remarks');

  const pos = checkLatLon(body.latitude, body.longitude);
  if (!pos.ok) errors.push(pos.error);
  else if (pos.value) Object.assign(out, pos.value);

  /* Stamped by us, never taken from the caller: WWFF can see which spots came
   * through Diana, and a caller cannot pretend to be something else. */
  out.source = 'DIANA';
  if (body.dryrun === true) out.dryrun = true;

  return { errors, out };
}

function buildAgenda(body) {
  const errors = [];
  const out = {};
  const take = (check, key) => {
    if (!check.ok) { errors.push(check.error); return; }
    if (check.value !== undefined) out[key] = check.value;
  };

  take(checkCall(body.activator_call, 'activator_call'), 'activator_call');
  take(checkReference(body.reference), 'reference');
  take(checkRemarks(body.remarks), 'remarks');

  const start = checkUtc(body.utc_start, 'utc_start');
  const end = checkUtc(body.utc_end, 'utc_end');
  if (!start.ok) errors.push(start.error); else out.utc_start = start.value;
  if (!end.ok) errors.push(end.error); else out.utc_end = end.value;

  if (start.ok && end.ok) {
    if (end.at <= start.at) errors.push('utc_end is not after utc_start');
    /* An announcement more than a month out is almost always a typo in the
     * year, and it would sit in everyone's agenda until then. Caught here, so
     * it never costs a call to WWFF. */
    const month = 31 * 24 * 3600 * 1000;
    if (start.at > Date.now() + month) errors.push('utc_start is more than a month from now');
    if (start.at < Date.now() - 24 * 3600 * 1000) errors.push('utc_start is in the past');
  }

  /* The pin is what lets the activator edit their own entry later. It is the
   * user's, not ours: we check that it is long enough and pass it on. */
  const pin = String(body.pin || '').trim();
  if (pin.length < 4) errors.push('pin must be at least 4 characters');
  else out.pin = pin;

  const poster = String(body.poster || '').trim();
  if (!poster) errors.push('poster is missing');
  else if (poster.length > 16) errors.push('poster is longer than 16 characters');
  else out.poster = poster.toUpperCase();

  if (body.band !== undefined && body.band !== '') out.band = String(body.band).trim();
  if (body.mode !== undefined && body.mode !== '') {
    take(checkMode(body.mode), 'mode');
  }
  if (body.dryrun === true) out.dryrun = true;

  return { errors, out };
}

/* -------------------------------------------------------- the kill switch */

/* One KV key, read on every request that could reach WWFF. No cacheTtl on
 * purpose: KV's minimum is 60 seconds, and "off within a minute" is not what
 * you want when somebody is abusing the key or WWFF is on the phone. Reads are
 * cheap on the free plan (100k/day); the switch being instant is worth more.
 *
 *   wrangler kv key put --binding DIANA_KV switch off
 *   wrangler kv key delete --binding DIANA_KV switch
 */
async function isOff(env) {
  try {
    const v = await env.DIANA_KV.get('switch');
    return v === 'off';
  } catch {
    /* KV unreachable is not a reason to stop serving. It IS a reason to say so
     * in the log, because the rate limiting below runs on the same store. */
    log('kv_unreachable');
    return false;
  }
}

/* ------------------------------------------------------- rate limiting */

/* Three layers, and they answer different questions:
 *
 *   per IP     — is one person hammering this?
 *   global     — is Diana as a whole about to eat the shared WWFF budget, this minute?
 *   day        — is Diana as a whole approaching Cloudflare's own daily ceiling?
 *
 * The global-per-minute one is the important one day to day: WWFF's budget is
 * shared with every other Spotline client, and Diana hitting its own ceiling is
 * an inconvenience for one user, while Diana emptying WWFF's is everyone's
 * outage. LIMIT_GLOBAL_MINUTE already keeps a full day of accepted spots far
 * below the daily check below — it exists as a second, independent net, not
 * because the first one is expected to fail.
 *
 * Counting happens only here, after validation, for requests that are actually
 * going upstream. A preflight, a rejected form or a blocked origin writes
 * nothing — which is what keeps this inside KV's 1000 writes a day. That
 * same rule is why the daily count below tracks accepted, upstream-bound
 * requests rather than every request this Worker receives: counting every
 * single hit — including the ones a flood of garbage would produce — would
 * blow the write budget long before the count meant anything. What it can
 * honestly promise is this: if Diana's own accepted traffic is approaching a
 * number worth worrying about, this is what notices.
 */
async function overLimit(env, who, kind) {
  const now = Math.floor(Date.now() / 1000);
  const checks = [];

  if (kind === 'spot') {
    const window = num(env.LIMIT_IP_WINDOW, 600);
    checks.push({
      key: `ip:${who}:spot:${Math.floor(now / window)}`,
      max: num(env.LIMIT_IP_SPOTS, 5),
      ttl: window + 60,
      scope: 'ip',
    });
  } else {
    checks.push({
      key: `ip:${who}:agenda:${Math.floor(now / 86400)}`,
      max: num(env.LIMIT_IP_AGENDA, 10),
      ttl: 86400 + 60,
      scope: 'ip',
    });
  }

  checks.push({
    key: `global:${Math.floor(now / 60)}`,
    max: num(env.LIMIT_GLOBAL_MINUTE, 40),
    /* KV refuses a TTL below 60 seconds, so a one-minute bucket gets the
     * minimum and simply lingers a little after it stops being counted. */
    ttl: 60,
    scope: 'global',
  });

  /* Well below Cloudflare's own free-tier ceiling of 100,000 requests a day —
   * a warning that arrives with room to react, not a message that shows up
   * exactly when the real wall is already hit. */
  checks.push({
    key: `global:day:${Math.floor(now / 86400)}`,
    max: num(env.LIMIT_GLOBAL_DAY, 90000),
    ttl: 86400 + 60,
    scope: 'day',
  });

  for (const c of checks) {
    let count = 0;
    try {
      count = num(await env.DIANA_KV.get(c.key), 0);
    } catch {
      /* Cannot read the counter: let the request through rather than block
       * everyone on a KV hiccup. The global ceiling at WWFF's end still holds. */
      log('kv_read_failed', c.scope);
      continue;
    }
    if (count >= c.max) return c.scope;
  }

  /* Increment only once we know the request is going through. This is a
   * read-then-write without a lock, so two requests in the same millisecond can
   * both read the same value and one increment is lost. That is accepted: the
   * cost of being off by one is a spot too many, and the alternative (a Durable
   * Object) is a different pricing tier for a counter that only has to be
   * roughly right. */
  for (const c of checks) {
    try {
      const count = num(await env.DIANA_KV.get(c.key), 0);
      await env.DIANA_KV.put(c.key, String(count + 1), { expirationTtl: c.ttl });
    } catch {
      log('kv_write_failed', c.scope);
    }
  }
  return null;
}

/* --------------------------------------------------------------- upstream */

async function toWwff(env, path, payload) {
  const timeout = num(env.UPSTREAM_TIMEOUT_MS, 8000);
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeout);
  try {
    const r = await fetch(`${env.WWFF_BASE}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        /* The one place the key is used. It goes out over HTTPS to WWFF and
         * appears nowhere else — not in a response, not in a log, not in an
         * error message. */
        'X-API-Key': env.WWFF_API_KEY,
        'User-Agent': `Diana/${VERSION} (+https://diana-onff.github.io)`,
      },
      body: JSON.stringify(payload),
      signal: abort.signal,
    });
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text.slice(0, 500) }; }
    return { status: r.status, data };
  } catch (err) {
    /* An abort is a timeout; anything else is the network. Either way the
     * caller gets a gateway error, not a stack trace. */
    const timedOut = err && err.name === 'AbortError';
    log(timedOut ? 'upstream_timeout' : 'upstream_error');
    return { status: 504, data: { error: timedOut ? 'WWFF did not answer in time' : 'could not reach WWFF' } };
  } finally {
    clearTimeout(timer);
  }
}

/* ------------------------------------------------------------------- log */

/* Everything this Worker records, in one place, so there is exactly one thing
 * to audit. Event names and counts only. If you ever find yourself wanting to
 * add a callsign here to debug something: don't — reproduce it with a dryrun
 * instead. */
function log(event, detail) {
  console.log(JSON.stringify({ event, detail: detail || null, at: new Date().toISOString() }));
}

/* The payload builders are exported so test/validation.mjs can run them under
 * plain node, without Cloudflare, without a key and without the network. That
 * is where the interesting bugs live: every one of these rules exists to keep
 * something from reaching WWFF. */
export { buildSpot, buildAgenda, BANDS_KHZ, MODES };

/* ------------------------------------------------------------------ entry */

async function handlePost(request, env, kind) {
  let body;
  try {
    body = await request.json();
  } catch {
    return { status: 400, data: { error: 'body is not valid JSON' } };
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { status: 400, data: { error: 'body must be a JSON object' } };
  }

  const { errors, out } = kind === 'spot' ? buildSpot(body) : buildAgenda(body);
  if (errors.length) {
    log('rejected_by_validation', errors.length);
    return { status: 400, data: { error: 'this spot was not accepted', details: errors } };
  }

  const who = await ipKey(request);
  const hit = await overLimit(env, who, kind);
  if (hit) {
    log('rate_limited', hit);
    /* The daily ceiling gets its own status and its own wording: 429 with
     * "try again shortly" is honest for a minute-scale limit and misleading
     * for one that clears at midnight UTC. 503 says "not you, not now" — the
     * same signal the kill switch gives — and `limit: 'day'` is the field the
     * app checks to show its own translated explanation instead of this raw
     * text, once the app is the one calling this Worker (Fase 3). */
    if (hit === 'day') {
      return {
        status: 503,
        data: {
          error: 'Diana has reached its shared daily capacity on the free tier this service runs on — please try again tomorrow',
          limit: 'day',
        },
      };
    }
    return {
      status: 429,
      data: {
        error: hit === 'global'
          ? 'Diana as a whole is at its limit for this minute — try again shortly'
          : 'too many requests from this connection — try again later',
      },
      headers: { 'Retry-After': hit === 'global' ? '60' : String(num(env.LIMIT_IP_WINDOW, 600)) },
    };
  }

  /* The upstream paths are configuration, not constants. WWFF's documentation
   * and what a given host actually serves have already disagreed once — the
   * development host answers 404 on the documented agenda path — and hunting
   * that down should be an edit to wrangler.toml, not to this file. */
  const path = kind === 'spot'
    ? (env.SPOT_PATH || '/api/spots/add')
    : (env.AGENDA_PATH || '/api/agenda/store');
  const answer = await toWwff(env, path, out);
  log(answer.status < 300 ? 'forwarded' : 'upstream_refused', answer.status);
  return { status: answer.status, data: answer.data };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request, env);

    /* The browser sends this before any POST carrying Content-Type:
     * application/json. Answer it before anything else — no KV, no counters,
     * nothing that costs a write. */
    if (request.method === 'OPTIONS') {
      return cors
        ? new Response(null, { status: 204, headers: cors })
        : new Response(null, { status: 403 });
    }

    /* Cheap and keyless: lets the app find out whether the service is up and
     * whether the switch is on, without spending anything. */
    if (request.method === 'GET' && url.pathname === '/status') {
      return json(
        {
          service: 'diana-spotline', version: VERSION,
          upstream: env.WWFF_BASE,
          paths: {
            spot: env.SPOT_PATH || '/api/spots/add',
            agenda: env.AGENDA_PATH || '/api/agenda/store',
          },
          enabled: !(await isOff(env)),
        },
        200,
        cors || {}
      );
    }

    const routes = { '/spot': 'spot', '/agenda': 'agenda' };
    const kind = routes[url.pathname];
    if (!kind) return json({ error: 'unknown endpoint' }, 404, cors || {});
    if (request.method !== 'POST') return json({ error: 'use POST' }, 405, cors || {});

    /* A browser request from an origin we do not know gets nothing. Outside a
     * browser this header is forged in a second, which is precisely why the
     * rate limiting above is the real defence and this is only the doorstep. */
    if (request.headers.get('Origin') && !cors) {
      log('blocked_origin');
      return json({ error: 'this origin may not use this service' }, 403);
    }

    if (await isOff(env)) {
      log('switch_off');
      return json(
        { error: 'spotting through Diana is temporarily switched off', enabled: false },
        503,
        cors || {}
      );
    }

    /* Without a key there is nothing to proxy, and finding that out at the
     * first real spot is worse than finding it out now. */
    if (!env.WWFF_API_KEY) {
      log('no_key');
      return json({ error: 'this Worker has no API key yet' }, 500, cors || {});
    }

    const answer = await handlePost(request, env, kind);
    return json(answer.data, answer.status, { ...(cors || {}), ...(answer.headers || {}) });
  },
};
