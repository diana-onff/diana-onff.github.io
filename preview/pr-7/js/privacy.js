/* ================================================================== *
 * Privacy: the first-launch consent screen, the Umami gate, and the
 * privacy page itself.
 *
 * Umami is never loaded unconditionally. It is inserted into <head> only
 * once the visitor has said yes, here or later in Settings, and removed
 * the moment they say no. Everything else Diana does (position, settings,
 * self-spotting) needs no consent screen at all: it either never leaves
 * this device, or it is sent only because you tapped a button that says
 * so in as many words.
 * ================================================================== */
const UMAMI_SRC = 'https://cloud.umami.is/script.js';
const UMAMI_ID  = '74231ae3-744a-4618-81d2-59cc10f6d217';
const PRIVACY_UPDATED = '2026-09-24';

const isEmbed = new URLSearchParams(location.search).get('embed') === '1';

/* '1' = yes, '0' = no, '' = not asked yet. Kept separate from the rest of
   cfg in settings.js on purpose: this is a consent record, not a
   preference, and it needs to exist before settings.js has even run. */
const statsConsent = () => recall('consent.stats');

function loadUmami(){
  if(document.getElementById('umamiScript')) return;
  const s = document.createElement('script');
  s.id = 'umamiScript';
  s.defer = true;
  s.src = UMAMI_SRC;
  s.dataset.websiteId = UMAMI_ID;
  document.head.appendChild(s);
}

function unloadUmami(){
  const s = document.getElementById('umamiScript');
  if(s) s.remove();
  // Umami itself sets no cookie, but keeps a little state in localStorage to
  // avoid double-counting a visit. Withdrawing consent clears that too,
  // rather than leaving it sitting there unused.
  try{
    Object.keys(localStorage)
      .filter(k => k.startsWith('umami.'))
      .forEach(k => localStorage.removeItem(k));
  }catch{}
}

function applyStatsConsent(){
  if(statsConsent() === '1') loadUmami(); else unloadUmami();
}

function syncStatsToggle(){
  const on = statsConsent() === '1';
  const off = statsConsent() === '0';
  [$('setStats')].forEach(seg => {
    if(!seg) return;
    [...seg.children].forEach(b => {
      const isYes = b.dataset.stats === '1';
      b.classList.toggle('on', (isYes && on) || (!isYes && off));
    });
  });
}

function setStatsConsent(yes){
  remember('consent.stats', yes ? '1' : '0');
  applyStatsConsent();
  syncStatsToggle();
}

$('setStats').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-stats]'); if(!b) return;
  setStatsConsent(b.dataset.stats === '1');
  showStatus('in', t('privacy.statssaved'), '');
});

/* ---------- privacy page ----------
   Not one of the screens in the bottom bar: it opens over whatever was on
   screen, and its own back button always returns to Settings. */
function openPrivacy(){
  document.querySelectorAll('.view').forEach(v => v.classList.remove('on'));
  [...$('nav').children].forEach(c => c.classList.remove('on'));
  $('viewPrivacy').classList.add('on');
  requestAnimationFrame(() => { map.resize(); map.triggerRepaint(); });
}

const privDate = new Date(PRIVACY_UPDATED);
const privUpdatedEl = $('privUpdated');
if(privUpdatedEl) privUpdatedEl.textContent = isNaN(privDate) ? PRIVACY_UPDATED : privDate.toLocaleDateString(locale());

$('privOpenBtn').onclick = openPrivacy;
$('privBack').onclick = () => {
  document.querySelector('#nav button[data-view="viewSet"]').click();
  // Read the page instead of answering the welcome screen: still ask, once
  // you are done reading, rather than letting the question quietly lapse.
  if(consentPending) consentEl.hidden = false;
};

/* ---------- clear everything on this device ----------
   Removes every diana.* key, the offline caches, and unregisters the
   service worker, then reloads, so Diana genuinely starts over, splash and
   welcome screen included, rather than half-remembering the old device. */
async function clearEverything(){
  if(!confirm(t('privacy.clearconfirm'))) return;
  try{
    Object.keys(localStorage)
      .filter(k => k.startsWith('diana.') || k.startsWith('umami.'))
      .forEach(k => localStorage.removeItem(k));
  }catch{}
  try{ unloadUmami(); }catch{}
  try{
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
  }catch{}
  try{
    if('serviceWorker' in navigator){
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map(r => r.unregister()));
    }
  }catch{}
  showStatus('in', t('privacy.cleared'), '');
  setTimeout(() => location.reload(), 900);
}
$('privClearBtn').onclick = clearEverything;
$('privClearBtn2').onclick = clearEverything;

/* ---------- first-launch consent ----------
   Shown once, unless this is an embed (someone else's iframe has no
   business asking a visitor for consent on Diana's behalf) or the question
   has already been answered on this device. */
const consentEl = $('consent');

/* While the welcome screen is still unanswered, the startup position request
   waits. Otherwise, on a device that has never been asked, the browser's own
   location prompt pops up during the splash screen, before the explanation of
   why Diana wants it is even on screen. The request then comes either from
   the location button below (a tap, which is also what browsers like best)
   or, if that button is never used, the moment the screen is answered. */
let consentPending = !isEmbed && recall('consent.seen') !== '1';
let locateAsked = false;       // the location button has been used
let locateDeferred = false;    // the startup request is waiting on us

/* Called by applyHomeView() in settings.js instead of locating right away.
   true = "not now, privacy.js will take care of it". */
function holdLocateForConsent(){
  if(!consentPending) return false;
  if(!locateAsked) locateDeferred = true;
  return true;
}
function releaseLocate(){
  if(!locateDeferred) return;
  locateDeferred = false;
  locate(true);
}

function closeConsent(){
  remember('consent.seen', '1');
  consentPending = false;
  consentEl.hidden = true;
  releaseLocate();
}
$('consentYes').onclick = () => { setStatsConsent(true);  closeConsent(); };
$('consentNo').onclick  = () => { setStatsConsent(false); closeConsent(); };
$('consentReadMore').onclick = () => {
  consentEl.hidden = true;      // reappears from privBack above if still undecided
  document.querySelector('#nav button[data-view="viewSet"]').click();
  openPrivacy();
};

/* ---------- location: permission and precision ----------
   A web page can ask for the most precise position the browser will give,
   and Diana always does (enableHighAccuracy in geo.js). Whether that is the
   exact position or a deliberately blurred "approximate" one is decided by
   the person holding the phone, in the browser or phone settings, and no
   page can overrule that choice or even read it directly. What a page CAN
   see is the permission state, and how wide the fixes turn out to be. So
   this shows both, and when a fix stays wide, the steps to switch precise
   location on for the platform in hand. */
let geoPerm = 'unknown';        // 'granted' | 'prompt' | 'denied' | 'unknown'
let locDenied = false;          // a request came back refused (browsers without the Permissions API)

if(navigator.permissions && navigator.permissions.query){
  navigator.permissions.query({name:'geolocation'}).then(st => {
    geoPerm = st.state;
    syncLocState();
    st.onchange = () => { geoPerm = st.state; if(geoPerm !== 'denied') locDenied = false; syncLocState(); };
  }).catch(() => {});
}

/* geo.js reports a refused request here; a PositionError code 1 is a refusal,
   anything else (timeout, no signal) is not a permission question. */
function noteLocError(err){
  if(err && err.code === 1) locDenied = true;
  syncLocState();
}

function locSteps(){
  const p = platform();
  if(p === 'ios') return t('loc.steps.ios');
  if(p === 'iosother') return t('loc.steps.iosother');
  if(p === 'android') return t('loc.steps.android');
  return t('loc.steps.desktop');
}

/* What to say about location right now. Globals from geo.js are read with a
   typeof guard: geo.js loads after this file, and the Permissions API answer
   can in principle arrive before it has. */
function locView(){
  const run   = typeof fixRun  !== 'undefined' ? fixRun  : null;
  const last  = typeof lastFix !== 'undefined' ? lastFix : null;
  const ring  = typeof ringFix !== 'undefined' ? ringFix : null;
  const limit = typeof FIX_HINT_M !== 'undefined' ? FIX_HINT_M : 75;
  const searching = !!run && !(run.run && run.run.answered);
  const m = a => String(Math.round(a));

  if(geoPerm === 'denied' || locDenied) return {msg: t('loc.denied'), steps: true, kind: 'bad'};
  if(searching) return {msg: ring && ring.acc != null ? t('loc.searching').replace('{a}', m(ring.acc)) : t('loc.searchingnofix'), kind: ''};
  if(last && last.acc != null){
    if(last.acc > limit) return {msg: t('loc.coarse').replace('{a}', m(last.acc)), steps: true, indoors: true, kind: 'warn'};
    return {msg: t('loc.good').replace('{a}', m(last.acc)), kind: 'good'};
  }
  if(geoPerm === 'granted') return {msg: t('loc.granted'), kind: 'good'};
  if(geoPerm === 'prompt')  return {msg: t('loc.prompt'), kind: ''};
  return {msg: '', kind: ''};
}

function paintLocState(box){
  if(!box) return;
  const v = locView();
  box.textContent = '';
  if(!v.msg) return;
  const p = document.createElement('div');
  p.className = 'locmsg' + (v.kind ? ' ' + v.kind : '');
  p.textContent = v.msg;
  box.appendChild(p);
  if(v.indoors){
    const i = document.createElement('div');
    i.className = 'locstep';
    i.textContent = t('loc.indoors');
    box.appendChild(i);
  }
  if(v.steps){
    const s = document.createElement('div');
    s.className = 'locstep';
    s.textContent = locSteps();
    box.appendChild(s);
  }
}

/* Called from geo.js on every position, from the Permissions API, and from
   rerender() in i18n.js when the language changes. */
function syncLocState(){
  paintLocState($('consentLocState'));
  paintLocState($('privLocState'));
}

function askLocation(){
  locateAsked = true;
  locateDeferred = false;
  locDenied = false;
  locate(false);
  syncLocState();
}
$('consentLoc').onclick = askLocation;
$('privLocBtn').onclick = askLocation;

if(consentPending) consentEl.hidden = false;
syncLocState();

// A returning visitor's earlier choice takes effect immediately; someone who
// has not decided yet gets no Umami until they do.
applyStatsConsent();
