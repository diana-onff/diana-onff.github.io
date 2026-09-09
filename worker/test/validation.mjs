/* Unit tests for the part of the Worker that decides what never leaves the
 * building. Runs under plain node — no Cloudflare, no API key, no network:
 *
 *   node worker/test/validation.mjs
 *
 * Every case here is a thing that must NOT reach WWFF, or a legitimate spot
 * that must. When one of these goes red, someone widened a rule.
 */
import { buildSpot, buildAgenda } from '../src/index.js';

let passed = 0, failed = 0;

function ok(condition, what) {
  if (condition) { passed++; console.log(`  ✓ ${what}`); }
  else { failed++; console.log(`  ✗ ${what}`); }
}

const inOneHour = new Date(Date.now() + 3600e3).toISOString();
const inTwoHours = new Date(Date.now() + 7200e3).toISOString();

const goodSpot = {
  activator: 'on3vz/p', spotter: 'ON3VZ',
  frequency_khz: 14285, mode: 'ssb', reference: 'onff-0104',
};

console.log('\n[1] a valid spot gets through and is normalised');
{
  const { errors, out } = buildSpot(goodSpot);
  ok(errors.length === 0, `no errors (${errors.join('; ') || 'none'})`);
  ok(out.activator === 'ON3VZ/P', 'callsign uppercased');
  ok(out.reference === 'ONFF-0104', 'reference uppercased');
  ok(out.mode === 'SSB', 'mode uppercased');
  ok(out.source === 'DIANA', 'source is stamped by us');
  ok(out.dryrun === undefined, 'dryrun absent unless asked for');
}

console.log('\n[2] unknown fields are dropped, not forwarded');
{
  const { out } = buildSpot({ ...goodSpot, source: 'SOMEONE_ELSE', admin: true, extra: { a: 1 } });
  ok(out.source === 'DIANA', 'a caller cannot overwrite source');
  ok(out.admin === undefined, 'admin is gone');
  ok(out.extra === undefined, 'extra is gone');
  ok(Object.keys(out).length === 6, `only the known fields remain (${Object.keys(out).join(', ')})`);
}

console.log('\n[3] frequencies');
{
  ok(buildSpot({ ...goodSpot, frequency_khz: 14.285 }).errors.length === 1, 'MHz instead of kHz is refused');
  ok(/did you mean kHz/.test(buildSpot({ ...goodSpot, frequency_khz: 14.285 }).errors[0]), 'and the message says why');
  ok(buildSpot({ ...goodSpot, frequency_khz: 12345 }).errors.length === 1, 'outside any band is refused');
  ok(buildSpot({ ...goodSpot, frequency_khz: 'abc' }).errors.length === 1, 'not a number is refused');
  ok(buildSpot({ ...goodSpot, frequency_khz: 7180 }).errors.length === 0, '40m passes');
  ok(buildSpot({ ...goodSpot, frequency_khz: 7250 }).errors.length === 0, 'US 40m passes too');
  ok(buildSpot({ ...goodSpot, frequency_khz: 145500 }).errors.length === 0, '2m passes');
}

console.log('\n[4] callsigns and references');
{
  ok(buildSpot({ ...goodSpot, activator: '' }).errors.length === 1, 'empty callsign refused');
  ok(buildSpot({ ...goodSpot, activator: 'ABCDEFGHIJKLMNOPQ' }).errors.length === 1, 'over 16 characters refused');
  ok(buildSpot({ ...goodSpot, activator: 'ONLYLETTERS' }).errors.length === 1, 'no digit refused');
  ok(buildSpot({ ...goodSpot, activator: '12345' }).errors.length === 1, 'no letter refused');
  ok(buildSpot({ ...goodSpot, activator: 'ON3VZ/P/QRP' }).errors.length === 0, 'multiple suffixes allowed');
  ok(buildSpot({ ...goodSpot, reference: 'ONFF-104' }).errors.length === 1, 'three digits refused');
  ok(buildSpot({ ...goodSpot, reference: 'ON-0104' }).errors.length === 1, 'missing FF refused');
  ok(buildSpot({ ...goodSpot, reference: 'DLFF-0123' }).errors.length === 0, 'another country passes');
}

console.log('\n[5] remarks and position');
{
  ok(buildSpot({ ...goodSpot, remarks: 'x'.repeat(101) }).errors.length === 1, 'over 100 characters refused');
  ok(buildSpot({ ...goodSpot, remarks: 'QRV until 16:00' }).out.remarks === 'QRV until 16:00', 'normal remark kept');
  ok(buildSpot({ ...goodSpot, latitude: 51.1 }).errors.length === 1, 'half a position refused');
  ok(buildSpot({ ...goodSpot, latitude: 91, longitude: 4 }).errors.length === 1, 'latitude out of range refused');
  ok(buildSpot({ ...goodSpot, latitude: 51.1, longitude: 4.4 }).errors.length === 0, 'a full position passes');
}

console.log('\n[6] errors accumulate instead of stopping at the first');
{
  const { errors } = buildSpot({ activator: '', frequency_khz: 1, mode: 'TELEPATHY', reference: 'nope' });
  ok(errors.length >= 4, `${errors.length} problems reported at once`);
}

console.log('\n[7] agenda');
{
  const good = {
    activator_call: 'ON3VZ/P', reference: 'ONFF-0104',
    utc_start: inOneHour, utc_end: inTwoHours, pin: '1234', poster: 'ON3VZ',
  };
  ok(buildAgenda(good).errors.length === 0, `a valid entry passes (${buildAgenda(good).errors.join('; ') || 'none'})`);
  ok(buildAgenda({ ...good, utc_end: good.utc_start }).errors.length === 1, 'end equal to start refused');
  ok(buildAgenda({ ...good, pin: '12' }).errors.length === 1, 'short pin refused');
  ok(buildAgenda({ ...good, utc_start: new Date(Date.now() + 60 * 86400e3).toISOString(),
                            utc_end: new Date(Date.now() + 60 * 86400e3 + 3600e3).toISOString() }).errors.length === 1,
     'two months out refused (year typo)');
  ok(buildAgenda({ ...good, utc_start: new Date(Date.now() - 7 * 86400e3).toISOString() }).errors.length >= 1,
     'a start in the past refused');
  ok(buildAgenda({ ...good, utc_start: 'tomorrow-ish' }).errors.length >= 1, 'unparseable time refused');
}

console.log('\n[8] dryrun is passed through when explicitly true');
{
  ok(buildSpot({ ...goodSpot, dryrun: true }).out.dryrun === true, 'dryrun: true survives');
  ok(buildSpot({ ...goodSpot, dryrun: 'true' }).out.dryrun === undefined, 'the string "true" does not');
}

console.log(`\n${failed === 0 ? 'ALL OK' : 'FAILED'} — ${passed} passed, ${failed} failed\n`);
process.exit(failed === 0 ? 0 : 1);
