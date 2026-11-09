/* ================================================================== *
 * Veldinfo > Condities: space weather and what it means for the bands.
 *
 * The third tab of the Veldinfo screen (nearinfo.js switches the tabs).
 *
 * Numbers: Kp, A, SFI and the sunspot number, from NOAA SWPC only. Not
 * fetched by the app from NOAA itself: a GitHub workflow (conditions.yml)
 * does that every hour and leaves one small file on the "conditions" branch
 * of this repository, read here. The last good copy is kept on this device,
 * so the tab still has something to show without a connection, with its age.
 *
 * Sunrise and sunset: worked out here, for your own position (GPS, otherwise
 * your locator). Nothing is asked of anyone for that, and it works offline.
 *
 * The band strip is Diana's own rough indication, not a forecast from NOAA:
 * a few well-known rules of thumb that link the solar flux, the Kp and day or
 * night to the bands. Said as much under the strip.
 * ================================================================== */
const COND_URL = 'https://raw.githubusercontent.com/diana-onff/diana-onff.github.io/conditions/conditions.json';
const COND_REFRESH_MS = 10 * 60 * 1000;    // never ask again within ten minutes
const COND_OLD_MS = 8 * 3600 * 1000;       // older than this: said out loud (GitHub runs the job every few hours)
const COND_KP_OLD_MS = 12 * 3600 * 1000;   // a Kp block that ended longer ago than this: said separately
const COND_BANDS = ['80', '40', '20', '15', '10'];

function nearCondActive(){ return typeof nearTab !== 'undefined' && nearTab === 'cond'; }

/* ---------- the numbers: fetched, and the last good copy kept ---------- */
let condData = null, condFetchedAt = 0, condLoading = null;
(function condFromDevice(){
  try {
    const s = JSON.parse(recall('cond.last') || 'null');
    if(s && s.data){ condData = s.data; condFetchedAt = 0; }
  } catch(e) {}
})();

function condValid(d){
  return d && typeof d === 'object' && ['kp', 'a', 'sfi', 'ssn'].some(k => d[k] && typeof d[k].value === 'number');
}

function loadConditions(force){
  if(condLoading) return condLoading;
  if(!force && Date.now() - condFetchedAt < COND_REFRESH_MS) return Promise.resolve(condData);
  condLoading = fetch(COND_URL, {cache: 'no-cache'})
    .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
    .then(d => {
      if(!condValid(d)) throw new Error('unexpected content');
      condData = d;
      try { remember('cond.last', JSON.stringify({data: d})); } catch(e) {}
      return d;
    })
    .then(d => { condFetchedAt = Date.now(); return d; })
    .catch(err => {
      console.warn('conditions:', err);
      // Try again a minute from now rather than ten: back in signal, back in data.
      condFetchedAt = Date.now() - COND_REFRESH_MS + 60000;
      return condData;
    })
    .finally(() => { condLoading = null; });
  return condLoading;
}

/* ---------- the sun ----------
   The sunrise equation (as in the astronomical almanacs), accurate to about a
   minute, which is all a planning aid needs. Times are UTC Dates. Returns
   {rise, set}, or {polar: 'day'|'night'} when the sun does not cross the
   horizon that day. `day` is any moment on the UTC date wanted. */
function sunTimes(day, lat, lon){
  const rad = Math.PI / 180, DAY = 86400000;
  const noon = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 12);
  const n = Math.round((noon - Date.UTC(2000, 0, 1, 12)) / DAY);
  const J = n - lon / 360;                                   // mean solar noon
  const M = (357.5291 + 0.98560028 * J) % 360;
  const C = 1.9148 * Math.sin(M * rad) + 0.02 * Math.sin(2 * M * rad) + 0.0003 * Math.sin(3 * M * rad);
  const L = (M + C + 180 + 102.9372) % 360;
  const transit = J + 0.0053 * Math.sin(M * rad) - 0.0069 * Math.sin(2 * L * rad);
  const sinDec = Math.sin(L * rad) * Math.sin(23.4397 * rad);
  const cosDec = Math.cos(Math.asin(sinDec));
  const cosW = (Math.sin(-0.833 * rad) - Math.sin(lat * rad) * sinDec) / (Math.cos(lat * rad) * cosDec);
  if(cosW < -1) return {polar: 'day'};
  if(cosW > 1) return {polar: 'night'};
  const w = Math.acos(cosW) / rad;
  const at = j => new Date(Date.UTC(2000, 0, 1, 12) + j * DAY);
  return {rise: at(transit - w / 360), set: at(transit + w / 360)};
}

/* ---------- the five parts of the day ----------
   Morning, midday, afternoon, evening, night, taken from the sun where you
   stand rather than from the clock, so they hold in summer and winter alike:
     morning    sunrise to two hours before the sun's highest point
     midday     two hours either side of that highest point
     afternoon  up to an hour before sunset
     evening    the twilight around sunset (the grey line), to 1.5 h after it
     night      until the next sunrise
   On a short winter day the middle parts shrink rather than overlap.
   periodAt() says which part `now` is in, and how far into it (0..1), or null
   where the sun does not rise or set that day. */
const COND_PERIODS = 5;
function periodAt(now, lat, lon){
  const H = 3600000, DAY = 86400000;
  const local = now.getTime() + lon / 15 * H;           // the day as it is where you stand
  const days = [-1, 0, 1].map(off => sunTimes(new Date(local + off * DAY), lat, lon));
  if(days.some(d => d.polar)) return null;
  // The day that began with the last sunrise before now.
  let k = days[1].rise <= now ? 1 : 0;
  if(k === 1 && days[2].rise <= now) k = 2;
  const day = days[k];
  const next = k < 2 ? days[k + 1].rise : sunTimes(new Date(local + 2 * DAY), lat, lon).rise;
  if(!next || now < day.rise) return null;
  const rise = +day.rise, set = +day.set, noon = (rise + set) / 2;
  const b = [rise];
  b.push(Math.min(Math.max(rise, noon - 2 * H), set));
  b.push(Math.max(b[1], Math.min(noon + 2 * H, set - H)));
  b.push(Math.max(b[2], set - H));
  b.push(Math.max(b[3], Math.min(set + 1.5 * H, +next)));
  b.push(+next);
  const t = now.getTime();
  for(let i = 0; i < COND_PERIODS; i++){
    if(t < b[i + 1] || i === COND_PERIODS - 1){
      const len = b[i + 1] - b[i];
      return {i, f: len > 0 ? Math.min(1, Math.max(0, (t - b[i]) / len)) : 0};
    }
  }
  return null;
}

/* ---------- the bands: Diana's own rule of thumb ----------
   Per band, a level for each part of the day: 2 good, 1 fair, 0 poor, null
   unknown. Sources of the rules: general amateur radio practice, not any one
   site. What "good" means differs per band, and is said next to it: NVIS
   (close by, up to about 400 km) and Europe on 80 and 40 m, Europe and DX on
   20 m, DX on 15 and 10 m.
   - 80 m: short distances by day (NVIS), at its best in the evening and night.
   - 40 m: usable all day and night.
   - 20 m: the daytime DX band, good into the evening; at night only with a
     fair amount of flux.
   - 15 m and 10 m: need a high solar flux, are best around midday, open later
     in the morning and close soon after sunset.
   - The season: in winter the daytime ionosphere is denser (the "winter
     anomaly"), so the high bands open at a lower flux by day, while the long
     nights close 20 m sooner; in summer it is the other way round, and 20 m
     and 15 m stay open late into the short nights.
   - A raised Kp (geomagnetic unrest) costs the higher bands and polar paths:
     Kp 4 to 6 one step on 20, 15 and 10 m; Kp 7 and up two steps there and
     one step on 80 and 40 m (since 1.30.1; before, Kp 5 already cost every
     band a step, too harsh for NVIS and Europe at mid latitudes). */
const COND_SEASON_SHIFT = {           // added to the flux thresholds: morning, midday+afternoon, evening, night
  winter:  [-10, -15, 20, 20],
  summer:  [10, 10, -20, -20],
  equinox: [0, 0, 0, 0],
};
function condSeason(now, lat){
  if(lat == null || Math.abs(lat) < 23) return 'equinox';        // the tropics: no real winter or summer
  const m = now.getUTCMonth() + 1;
  const north = lat > 0;
  if([11, 12, 1, 2].includes(m)) return north ? 'winter' : 'summer';
  if([5, 6, 7, 8].includes(m)) return north ? 'summer' : 'winter';
  return 'equinox';
}
function bandOutlook(sfi, kp, season){
  const f = typeof sfi === 'number' ? sfi : null;
  const [sm, sd, se, sn] = COND_SEASON_SHIFT[season] || COND_SEASON_SHIFT.equinox;
  const flux = (good, fair, s) => f == null ? null : (f >= good + s ? 2 : f >= fair + s ? 1 : 0);
  const atLeast = (fair, s) => f == null ? null : (f >= fair + s ? 1 : 0);
  //             morning              midday               afternoon            evening            night
  const base = {
    '80': [1,                   1,                   1,                   2,                 2],
    '40': [2,                   2,                   2,                   2,                 2],
    '20': [2,                   2,                   2,                   2,                 atLeast(100, sn)],
    '15': [flux(120, 90, sm),   flux(100, 80, sd),   flux(100, 80, sd),   atLeast(130, se),  atLeast(150, sn)],
    '10': [flux(150, 120, sm),  flux(130, 100, sd),  flux(140, 110, sd),  atLeast(170, se),  atLeast(180, sn)],
  };
  const k = typeof kp === 'number' ? kpStep(kp) : 0;
  for(const b of COND_BANDS){
    // Kp is a worldwide value; at the latitude of Belgium a minor storm (G1, G2)
    // costs the high bands and polar paths, while NVIS and Europe on 80 and
    // 40 m hardly notice it. Only a strong storm (Kp 7 and up) costs those too.
    const high = ['20', '15', '10'].includes(b);
    const cut = k >= 7 ? (high ? 2 : 1) : (k >= 4 && high) ? 1 : 0;
    base[b] = base[b].map(v => v == null ? null : Math.max(0, v - cut));
  }
  return base;
}

/* The same three colours as the Kp dial: green good, soft amber fair, dark
   red poor. They also differ clearly in brightness (amber lightest, red
   darkest), so they read without telling red from green. */
const COND_LEVEL_COL = ['#9b2226', '#f2c27b', '#52b788'];
const COND_LEVEL_INK = ['#9b2226', '#b45309', '#2d6a4f'];
const COND_UNKNOWN_COL = '#e3e0d6';

/* Kp comes in thirds: 4.67 is "5-", which already counts as K5 (G1) on the
   NOAA scale. So the step is the rounded value, not the whole number below. */
function kpStep(kp){ return Math.round(kp); }

/* Kp in words and colour, along the NOAA scale (G1 to G5 from Kp 5). The
   dial uses Diana's green while it is quiet and amber as the warning colour;
   red only for a severe storm. `col` is for the dial, `ink` for the word. */
function kpClass(kp){
  const k = kpStep(kp);
  if(k >= 7) return {key: 'cond.kp.storm', g: Math.min(5, k - 4), col: '#9b2226', ink: '#9b2226'};
  if(k >= 5) return {key: 'cond.kp.storm', g: k - 4, col: '#b45309', ink: '#9a3412'};
  if(k >= 4) return {key: 'cond.kp.active', col: '#d97706', ink: '#b45309'};
  if(k >= 3) return {key: 'cond.kp.unsettled', col: '#f2c27b', ink: '#b45309'};
  return {key: 'cond.kp.quiet', col: '#52b788', ink: '#2d6a4f'};
}

/* A half dial from 0 to 9, coloured per Kp step, with a needle. */
function kpGaugeSvg(kp){
  const cx = 100, cy = 96, r = 78, w = 16, rad = Math.PI / 180;
  const pt = (deg, rr) => [cx + rr * Math.cos(deg * rad), cy - rr * Math.sin(deg * rad)];
  let segs = '';
  for(let i = 0; i < 9; i++){
    const a0 = 180 - i * 20, a1 = 180 - (i + 1) * 20 + 0.6;
    const [x0, y0] = pt(a0, r), [x1, y1] = pt(a1, r);
    segs += `<path d="M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}" stroke="${kpClass(i).col}" stroke-width="${w}" fill="none" opacity="${typeof kp === 'number' && i <= kp ? 1 : 0.25}"/>`;
  }
  let ticks = '';
  for(const v of [0, 3, 5, 7, 9]){
    const [x, y] = pt(180 - v * 20, r - w - 6);
    ticks += `<text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" font-size="11" text-anchor="middle" fill="var(--ink-3)">${v}</text>`;
  }
  let needle = '';
  if(typeof kp === 'number'){
    // Shorter than the ring of numbers, so it never runs over one (at Kp 0 it lay across the 0).
    const [x, y] = pt(180 - Math.max(0, Math.min(9, kp)) * 20, r - w - 18);
    needle = `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="var(--ink)" stroke-width="3" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="5" fill="var(--ink)"/>`;
  }
  return `<svg class="kpgauge" viewBox="0 0 200 104" role="img" aria-label="Kp ${typeof kp === 'number' ? kp : '?'}">${segs}${ticks}${needle}</svg>`;
}

/* ---------- drawing the tab ---------- */
function condAgo(ms){
  const min = Math.max(0, Math.round(ms / 60000));
  if(min < 60) return t('cond.minago').replace('{n}', min);
  return t('cond.hourago').replace('{n}', Math.round(min / 60));
}

/* A clock time in local time, with the date in front when it is not today. */
function condClock(d, now){
  const time = d.toLocaleTimeString(locale(), {hour: '2-digit', minute: '2-digit'});
  if(d.toDateString() === now.toDateString()) return time;
  return d.toLocaleDateString(locale(), {day: 'numeric', month: 'short'}) + ' ' + time;
}

function condTime(d){
  const p = n => String(n).padStart(2, '0');
  const local = d.toLocaleTimeString(locale(), {hour: '2-digit', minute: '2-digit'});
  return `${local} <span class="condutc">(${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC)</span>`;
}

function condSunHtml(pos, now){
  if(!pos) return `<p class="hint" style="margin:0">${t('cond.nopos')}</p>`;
  // The day as it is where you stand, not in Greenwich: shift by the
  // longitude (15 degrees an hour), so just after local midnight it is today.
  const s = sunTimes(new Date(now.getTime() + pos.lon / 15 * 3600000), pos.lat, pos.lon);
  if(s.polar) return `<p style="margin:0">${t(s.polar === 'day' ? 'cond.polarday' : 'cond.polarnight')}</p>`;
  const from = pos.from === 'gps' ? t('near.viagps') : t('near.vialocator').replace('{grid}', pos.grid || '');
  return `<div class="condsun">
      <div><div class="k">${t('cond.sunrise')}</div><div class="v" id="condRise">${condTime(s.rise)}</div></div>
      <div><div class="k">${t('cond.sunset')}</div><div class="v" id="condSet">${condTime(s.set)}</div></div>
    </div><p class="hint" style="margin:6px 0 0">${escHtml(from)}</p>`;
}

function renderCond(){
  const box = $('nearCond');
  if(!box) return;
  const d = condData;
  const now = new Date();
  const pos = typeof infoPosition === 'function' ? infoPosition() : null;
  const part = pos ? periodAt(now, pos.lat, pos.lon) : null;
  const val = k => d && d[k] && typeof d[k].value === 'number' ? d[k].value : null;
  const kp = val('kp'), sfi = val('sfi'), kpNow = val('kp_now');

  let html = '';
  if(!d){
    html += `<div class="card"><p style="margin:0">${t('cond.none')}</p></div>`;
  } else {
    const kc = kp == null ? null : kpClass(kp);
    const word = kc ? t(kc.key).replace('{g}', kc.g || '') : '?';
    html += `<div class="card condkp">
        <h4 class="ch">${t('cond.kptitle')}</h4>
        ${kpGaugeSvg(kp)}
        <div class="condkpval"><b id="condKp">${kp == null ? '?' : String(Math.round(kp * 100) / 100)}</b>
          <span class="condword" id="condKpWord" style="color:${kc ? kc.ink : 'var(--ink-3)'}">${escHtml(word)}</span></div>
        ${kpNow == null ? '' : `<p class="hint condkpnow" id="condKpNow">${t('cond.kpnow').replace('{v}', String(Math.round(kpNow * 100) / 100))}</p>`}
        <p class="hint condkpnow" id="condKpGlobal">${t('cond.kpglobal')}</p>
        <div class="condnums">
          <div><div class="k">SFI</div><div class="v" id="condSfi">${sfi ?? '?'}</div></div>
          <div><div class="k">A</div><div class="v" id="condA">${val('a') ?? '?'}</div></div>
          <div><div class="k">${t('cond.ssn')}</div><div class="v" id="condSsn">${val('ssn') ?? '?'}</div></div>
        </div>
      </div>`;

    html += condBandsHtml(bandOutlook(sfi, kp, condSeason(now, pos ? pos.lat : null)), part);
  }

  html += `<div class="card"><h4 class="ch">${t('cond.sun')}</h4>${condSunHtml(pos, now)}</div>`;

  if(d){
    // How old the numbers are: when Diana's GitHub job last fetched them
    // (GitHub starts that job every few hours rather than every hour, see
    // conditions.yml). Said as a clock time and as an age.
    const upd = Date.parse(d.updated || '');
    const age = isFinite(upd) ? now - upd : null;
    const days = ['sfi', 'a', 'ssn'].map(k => d[k] && d[k].date).filter(Boolean).sort();
    if(days.length){
      const shown = new Date(days[0] + 'T12:00:00Z').toLocaleDateString(locale(), {day: 'numeric', month: 'short'});
      html += `<p class="hint" id="condDaily">${t('cond.daily').replace('{date}', escHtml(shown))}</p>`;
    }
    // A Kp kept from an earlier run (its source was down then) carries its own
    // time; when that is well behind, say so separately.
    const kpEnd = d.kp ? Date.parse(d.kp.time || '') : NaN;
    if(isFinite(kpEnd) && now - kpEnd > COND_KP_OLD_MS)
      html += `<p class="hint condold" id="condKpOld">${t('cond.kpold').replace('{time}', escHtml(condClock(new Date(kpEnd), now)))}</p>`;
    html += `<p class="hint${age != null && age > COND_OLD_MS ? ' condold' : ''}" id="condAge">${
      age == null ? '' : (age > COND_OLD_MS ? t('cond.old') : t('cond.updated'))
        .replace('{time}', escHtml(condClock(new Date(upd), now))).replace('{ago}', condAgo(age))
    } ${t('cond.src')}</p>`;
  }
  box.innerHTML = html;
}

/* The band strip: per band one bar from morning to night, its colour running
   from one part of the day into the next, a line where you are now, and on
   the right what applies now in words. Next to each band: what "good" means
   there (NVIS, EU, DX). A tap on a part of a bar adds its words (condTip),
   but nothing needs a tap to be read. */
function condBandsHtml(out, part){
  const level = v => v == null ? COND_UNKNOWN_COL : COND_LEVEL_COL[v];
  const word = v => t(v == null ? 'cond.unknown' : ['cond.poor', 'cond.fair', 'cond.good'][v]);
  const bar = b => {
    const v = out[b];
    // A stop at the middle of each part, so the colour runs smoothly between them.
    const stops = v.map((x, i) => `${level(x)} ${(i * 20 + 4).toFixed(0)}% ${(i * 20 + 16).toFixed(0)}%`).join(', ');
    const cells = v.map((x, i) => `<button type="button" class="condseg" data-band="${b}" data-part="${i}" data-level="${x == null ? 'x' : x}" aria-label="${b} m, ${t('cond.p' + i)}: ${word(x)}"></button>`).join('');
    const mark = part ? `<span class="condnow" style="left:${((part.i + part.f) * 20).toFixed(1)}%"></span>` : '';
    // What applies now, in words, so nothing has to be tapped to read it.
    const now = part ? `<span class="condnowword" data-band="${b}">${t('cond.now')}: <b style="color:${v[part.i] == null ? 'var(--ink-3)' : COND_LEVEL_INK[v[part.i]]}">${word(v[part.i])}</b></span>` : '';
    return `<div class="condrow"><div class="condtop"><span class="condband">${b} m <small>${t('cond.tag' + b)}</small></span>${now}</div><div class="condbar" style="background:linear-gradient(to right, ${stops})">${cells}${mark}</div></div>`;
  };
  const labels = [0, 1, 2, 3, 4].map(i => `<span class="${part && part.i === i ? 'now' : ''}">${t('cond.p' + i)}</span>`).join('');
  const legend = [2, 1, 0].map(v => `<span><i style="background:${COND_LEVEL_COL[v]}"></i>${word(v)}</span>`).join('');
  return `<div class="card">
      <h4 class="ch">${t('cond.bands')}</h4>
      <div class="condstrip">
        <div class="condlabels">${labels}</div>
        ${COND_BANDS.map(bar).join('')}
      </div>
      <div class="condlegend">${legend}</div>
      <p class="hint" style="margin:6px 0 0">${t('cond.reach')}</p>
      <p class="hint" id="condTip" style="margin:6px 0 0"></p>
      <p class="hint" style="margin:6px 0 0">${t(part ? 'cond.bandsnote' : 'cond.bandsnopos')}</p>
    </div>`;
}

/* A tap on a part of a bar: say in words what its colour means. */
$('nearCond').addEventListener('click', e => {
  const seg = e.target.closest('.condseg'); if(!seg) return;
  const v = seg.dataset.level;
  const tip = $('condTip');
  if(tip) tip.textContent = t('cond.tip').replace('{band}', seg.dataset.band)
    .replace('{part}', t('cond.p' + seg.dataset.part))
    .replace('{level}', t(v === 'x' ? 'cond.unknown' : ['cond.poor', 'cond.fair', 'cond.good'][+v]));
});

/* Opening the tab asks for fresh numbers (at most every ten minutes) and
   redraws when they arrive, if the tab is still showing. */
function showCond(){
  renderCond();
  loadConditions().then(() => { if(nearCondActive() && $('viewNearby').classList.contains('on')) renderCond(); });
}
