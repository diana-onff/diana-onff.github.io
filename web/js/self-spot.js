/* ================================================================== *
 * Screen 3 — reporting a spot yourself via WWFF Spotline
 *
 * The rules below are taken from the page code of
 * spots.wwff.co/spots/create itself, so that we run the same checks before
 * we send anything instead of letting the server refuse it:
 *   callsign    /^[A-Z0-9\/]{3,}$/ and at least one digit
 *   frequency   135.7 … 7,500,000,000 kHz
 *   reference   at least 7 characters, checked via their own endpoint
 *   remark      max 100 characters, plus a word filter on their side
 *   activator, spotter and reference go in CAPITALS
 *
 * Sending happens as an ordinary form post in a new tab. That is allowed
 * cross-origin (forms don't fall under CORS), and the user sees Spotline's
 * own confirmation — more reliable than a fetch whose answer we are not
 * allowed to read anyway.
 * ================================================================== */
/* The Worker is the ordinary route: it holds the API key, checks the payload
 * once more on its own terms, and hands back what Spotline actually said. The
 * form post below it is the fallback from step 3.4 — it still works, it just
 * cannot tell you whether anything arrived. */
const WORKER      = 'https://diana-spotline.diana-onff.workers.dev';
const SPOT_POST   = 'https://spots.wwff.co/spots/store';
const REF_SHAPE   = /^[A-Z0-9]{1,4}FF-\d{4}$/;   // the same rule the Worker applies
const CALL_RE     = /^[A-Z0-9/]{3,}$/;

/* Whether the current form contents have been approved by Spotline. Any edit
 * clears it: a check on a frequency you have since changed says nothing about
 * the spot you are about to send. Declared here, above validateSelf(), because
 * that function reads it and runs during start-up. */
let gecontroleerd = false;

const klassiek = () => recall('self.classic') === '1';


function validCall(v){ return CALL_RE.test(v) && /[0-9]/.test(v); }
function validFreq(v){ const f = parseFloat(v); return !isNaN(f) && f >= 135.7 && f <= 7500000000; }

/* Which band segment goes with this frequency, and does the mode match it? */
function bandCheck(khz, mode){
  const f = parseFloat(khz); if(isNaN(f)) return null;
  for(const b of BANDS){
    if(f < b.lo || f > b.hi) continue;
    const seg = b.seg.find(([,lo,hi]) => f >= lo && f <= hi);
    const family = mode === 'SSB' || mode === 'AM' ? 'SSB'
                 : mode === 'CW' ? 'CW'
                 : mode === 'FM' ? 'FM'
                 : mode ? 'Digi' : null;
    return {band:b.n, seg: seg ? seg[0] : null, ok: !family || !seg || seg[0] === family};
  }
  return {band:null, seg:null, ok:true};
}

function selfPrefill(){
  const ref = selected;
  const z = ref && zones && zones.features.find(f => f.properties.ref === ref);
  if(z){
    $('spReference').value = z.properties.ref;
    $('selfCtx1').textContent = `${z.properties.ref} · ${z.properties.name}`;
    $('selfCtx').hidden = false;
    checkReference();
  } else {
    $('selfCtx').hidden = true;
  }
  if(!$('spActivator').value) $('spActivator').value = recall('activator') || cfg.callp || cfg.call;
  if(!$('spSpotter').value)   $('spSpotter').value   = recall('spotter')   || cfg.call || (cfg.callp||'').split('/')[0];
  validateSelf();
}

/* Reference checking, against our own data instead of the API.
 *
 * There IS a GET /api/references/validate, but calling it while somebody types
 * costs requests from the budget that is shared with every other Spotline
 * client — and it is slower than what we can do here. We already carry the
 * whole WWFF programme list (wwff-programs.json, 7 kB) and all 946 ONFF
 * references, so the answer is instant, free, and better: for an ONFF
 * reference we can show the name of the reserve rather than a bare tick.
 *
 * What we can and cannot say, honestly:
 *   shape wrong           → certain, rejected
 *   programme unknown     → certain, rejected (catches the common prefix typo)
 *   ONFF, and we have it  → certain, with the name
 *   ONFF, and we do not   → certain, rejected
 *   another programme     → the programme exists; the number we do not know
 *                           here unless the world layer happens to be loaded.
 *                           Say so, and let Spotline have the last word.
 */
function refLookup(v){
  if(!REF_SHAPE.test(v)) return { cls:'bad', text: t('self.refshape') };

  const prog = v.split('-')[0];
  const p = wwffPrograms.find(x => x.program === prog);
  if(!p) return { cls:'bad', text: t('self.refbadprogram') };

  /* ONFF is ours: both the areas with a boundary and the point-only ones. */
  if(prog === 'ONFF'){
    const inZones = zones && zones.features.find(f => f.properties.ref === v);
    const inPts   = noPoly && noPoly.features.find(f => f.properties.ref === v);
    const hit = inZones || inPts;
    if(hit) return { cls:'good', text: '✓ ' + (hit.properties.name || v) };
    return { cls:'bad', text: t('self.refunknown') };
  }

  /* Any other programme: only if the world layer is already in memory can we
   * check the number too. Loading nine megabytes to validate a text field
   * would be a poor trade. Mind the length check — worldPoints starts life as
   * an empty collection, and an empty array would otherwise let us declare
   * every foreign reference unknown. */
  if(worldPoints && worldPoints.features && worldPoints.features.length){
    const hit = worldPoints.features.find(f => f.properties.ref === v);
    if(hit) return { cls:'good', text: '✓ ' + (hit.properties.name || v) };
    return { cls:'bad', text: t('self.refunknown') };
  }

  return { cls:'', text: t('self.refprogram').replace('{c}', p.country) };
}

function checkReference(){
  const v = $('spReference').value.trim().toUpperCase();
  const fb = $('fbReference');
  if(v.length < 7){ fb.textContent = v ? t('self.reftooshort') : ''; fb.className = 'fb'; return; }
  const r = refLookup(v);
  fb.textContent = r.text;
  fb.className = 'fb' + (r.cls ? ' ' + r.cls : '');
}

function validateSelf(){
  let ok = true;
  const set = (el, good, msg, fbId) => {
    el.classList.toggle('bad', !good && el.value.trim() !== '');
    el.classList.toggle('good', good && el.value.trim() !== '');
    if(fbId){ const f = $(fbId); f.textContent = msg || ''; f.className = 'fb' + (msg && !good ? ' bad' : ''); }
    if(!good) ok = false;
  };
  const a = $('spActivator'), sp = $('spSpotter'), r = $('spReference'), f = $('spFreq'), m = $('spMode');
  set(a,  validCall(a.value.trim()),  '');
  set(sp, validCall(sp.value.trim()), '');
  set(r,  r.value.trim().length >= 7, '');

  let msg = '', good = validFreq(f.value.trim());
  if(f.value.trim() && !good) msg = t('self.freqrange');
  else if(good && m.value){
    const bc = bandCheck(f.value.trim(), m.value);
    if(bc && bc.band && bc.seg && !bc.ok) msg = `⚠ ${bc.band}: ${bc.seg}-${t('self.segment')}`;
    else if(bc && bc.band) msg = `${bc.band}${bc.seg ? ' · ' + bc.seg : ''}`;
  }
  set(f, good, msg, 'fbFreq');
  if(!m.value) ok = false;

  /* Two buttons now, and they do not open at the same time. Check needs a form
   * that holds together; Send needs a check that came back good. The one
   * exception is classic mode, where there is nothing to check against
   * because the spot goes straight to Spotline. */
  $('spCheck').disabled = !ok || klassiek();
  $('spSend').disabled  = !ok || (!gecontroleerd && !klassiek());
  return ok;
}

/* ---------------------------------------------------- checking and sending */

function vergeetControle(){
  if(!gecontroleerd) return;
  gecontroleerd = false;
  const fb = $('fbSend');
  fb.textContent = t('self.recheck');
  fb.className = 'fb';
  $('spFallback').hidden = true;
}

function spotVelden(){
  const uit = {
    activator:     $('spActivator').value.trim().toUpperCase(),
    spotter:       $('spSpotter').value.trim().toUpperCase(),
    frequency_khz: Number($('spFreq').value.trim()),
    mode:          $('spMode').value,
    reference:     $('spReference').value.trim().toUpperCase(),
  };
  const rem = $('spRemarks').value.trim();
  if(rem) uit.remarks = rem;
  return uit;
}

/* One place where the Worker is called, for both the check and the real send.
 * The only difference between the two is dryrun. */
async function naarWorker(dry){
  const r = await fetch(WORKER + '/spot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(dry ? { ...spotVelden(), dryrun: true } : spotVelden()),
  });
  let data = null;
  try{ data = await r.json(); }catch{}
  return { status: r.status, data: data || {} };
}

/* Turns an answer into something a person on a hilltop can act on. Returns
 * whether the old route is worth offering: for a rejected spot it is not —
 * the same spot would be rejected there too, just without telling you. */
function toonAntwoord(status, data){
  const fb = $('fbSend');
  const zet = (tekst, cls) => { fb.textContent = tekst; fb.className = 'fb' + (cls ? ' ' + cls : ''); };

  if(status === 409){ zet(t('self.dup'), 'good'); return false; }
  if(status === 400){
    const uitleg = (data.details && data.details.length) ? data.details.join(' · ') : (data.error || '');
    zet(uitleg, 'bad');
    return false;
  }
  if(status === 401 || status === 500){ zet(t('self.keyfail'), 'bad'); return true; }
  if(status === 429){ zet(t('self.busy'), 'bad'); return true; }
  if(status === 503){
    /* Two different 503s: the daily ceiling, and the kill switch. The Worker
     * tags them so we do not have to read its English prose. */
    zet(data.limit === 'day' ? t('self.dailylimit') : t('self.off'), 'bad');
    return true;
  }
  zet(t('self.unreachable'), 'bad');
  return true;
}

$('spCheck').onclick = async () => {
  if(!validateSelf()) return;
  $('spCheck').disabled = true;
  $('spFallback').hidden = true;
  const fb = $('fbSend');
  fb.textContent = t('self.checking'); fb.className = 'fb';
  try{
    const { status, data } = await naarWorker(true);
    if(status >= 200 && status < 300){
      gecontroleerd = true;
      fb.textContent = t('self.checkok'); fb.className = 'fb good';
    } else {
      gecontroleerd = false;
      $('spFallback').hidden = !toonAntwoord(status, data);
    }
  }catch{
    /* No network, or the Worker is not answering at all. Nothing was sent, so
     * the old route is still open — and on a hill with one bar that is
     * exactly the moment you want it. */
    gecontroleerd = false;
    fb.textContent = t('self.unreachable'); fb.className = 'fb bad';
    $('spFallback').hidden = false;
  }finally{
    validateSelf();
  }
};

function onthoudRoepnamen(){
  remember('activator', $('spActivator').value.trim());
  remember('spotter',   $('spSpotter').value.trim());
}

/* The fallback from step 3.4: a real form post to another domain, which is
 * allowed where a fetch is not. It works, and it always has — what it cannot
 * do is tell you whether the spot arrived. That is the whole reason the
 * Worker exists, and the whole reason this stays as a way out rather than as
 * the way. */
function verstuurKlassiek(){
  onthoudRoepnamen();
  const v = spotVelden();
  const form = Object.assign(document.createElement('form'), {
    method:'post', action:SPOT_POST, target:'_blank'
  });
  const velden = {
    activator: v.activator, frequency_khz: $('spFreq').value.trim(), mode: v.mode,
    reference: v.reference, spotter: v.spotter, remarks: v.remarks || '',
  };
  for(const [k, val] of Object.entries(velden)){
    form.appendChild(Object.assign(document.createElement('input'), {type:'hidden', name:k, value:val}));
  }
  document.body.appendChild(form);
  form.submit();
  form.remove();
  showStatus('in', t('self.sent'), `${v.activator} · ${v.reference} · ${velden.frequency_khz} kHz ${v.mode}`);
  $('fbSend').textContent = t('self.fallbackwarn');
  $('fbSend').className = 'fb';
}

$('spFallback').onclick = verstuurKlassiek;

$('spSend').onclick = async () => {
  if(!validateSelf()) return;
  if(klassiek()) return verstuurKlassiek();
  if(!gecontroleerd) return;

  $('spSend').disabled = true;
  $('spFallback').hidden = true;
  const fb = $('fbSend');
  fb.textContent = t('self.sending'); fb.className = 'fb';
  try{
    const { status, data } = await naarWorker(false);
    if(status >= 200 && status < 300){
      onthoudRoepnamen();
      const id = data.spot_id || (data.data && data.data.spot_id);
      fb.textContent = t('self.ok') + (id ? ` · #${id}` : '');
      fb.className = 'fb good';
      showStatus('in', t('self.ok'), `${spotVelden().activator} · ${spotVelden().reference}`);
    } else {
      $('spFallback').hidden = !toonAntwoord(status, data);
    }
  }catch{
    fb.textContent = t('self.unreachable'); fb.className = 'fb bad';
    $('spFallback').hidden = false;
  }finally{
    /* Whatever happened, the approval is spent. Sending the same spot again is
     * a new decision and gets a new check. */
    gecontroleerd = false;
    validateSelf();
  }
};

/* Classic mode: no checking, straight to Spotline. The screen has to say so,
 * otherwise the two buttons and the hint underneath describe a flow that is
 * not the one you are in. */
function pasKlassiekToe(){
  const aan = klassiek();
  $('spCheck').hidden = aan;
  $('spFallback').hidden = true;
  $('spHint').textContent = aan ? t('self.classichint') : t('self.checkhint');
  if(aan){ $('fbSend').textContent = ''; $('fbSend').className = 'fb'; }
  validateSelf();
}

$('setClassic').addEventListener('change', e => {
  remember('self.classic', e.target.checked ? '1' : '');
  gecontroleerd = false;
  pasKlassiekToe();
});

/* The setting survives a restart, so the screen has to come up in the state it
 * was left in — otherwise someone who switched to classic mode last week finds
 * a Check button that does something they deliberately turned off. */
$('setClassic').checked = klassiek();
pasKlassiekToe();

['spActivator','spSpotter','spReference'].forEach(id => {
  $(id).addEventListener('input', e => {
    const p = e.target.selectionStart;
    e.target.value = e.target.value.toUpperCase();
    e.target.setSelectionRange(p, p);
    if(id === 'spReference') checkReference();
    vergeetControle();
    validateSelf();
  });
});
['spFreq','spMode'].forEach(id => $(id).addEventListener('input', () => {
  vergeetControle();
  validateSelf();
}));
$('spRemarks').addEventListener('input', e => {
  $('spCount').textContent = `${e.target.value.length}/100`;
  /* The remark travels with the spot, so a changed remark is a changed spot —
   * even though nothing about it can fail validation. */
  vergeetControle();
  validateSelf();
});
document.querySelectorAll('.chip[data-add]').forEach(c => c.onclick = () => {
  const el = $('spRemarks');
  const add = c.dataset.add;
  if(el.value.includes(add)) return;
  el.value = (el.value ? el.value.replace(/\s*$/, ', ') : '') + add;
  el.value = el.value.slice(0, 100);
  $('spCount').textContent = `${el.value.length}/100`;
});

/* The old send handler used to sit here, posting the form straight to
 * Spotline. It has not disappeared — it moved into verstuurKlassiek() above,
 * where it is now the fallback rather than the only way. */

