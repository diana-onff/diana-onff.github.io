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
  if(!isEmbed && statsConsent() === '') $('consent').hidden = false;
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
function closeConsent(){
  remember('consent.seen', '1');
  consentEl.hidden = true;
}
$('consentYes').onclick = () => { setStatsConsent(true);  closeConsent(); };
$('consentNo').onclick  = () => { setStatsConsent(false); closeConsent(); };
$('consentReadMore').onclick = () => {
  consentEl.hidden = true;      // reappears from privBack above if still undecided
  document.querySelector('#nav button[data-view="viewSet"]').click();
  openPrivacy();
};

if(!isEmbed && recall('consent.seen') !== '1') consentEl.hidden = false;

// A returning visitor's earlier choice takes effect immediately; someone who
// has not decided yet gets no Umami until they do.
applyStatsConsent();
