/* ================================================================== *
 * Screen 3b — announcing an activation (Fase 4)
 *
 * The Worker already knows how to build and rate-limit an agenda payload
 * (buildAgenda() in worker/src/index.js, built in Fase 2 against the same
 * API info as spots) — this screen is the front end for it, reusing the
 * Check/Send pattern from self-spotting above rather than inventing a new
 * one. There is no classic fallback here: unlike /spots/store, there is no
 * documented plain form-post endpoint for agenda entries to fall back to.
 * ================================================================== */
let agGecontroleerd = false;

/* Which screen "← Terug" returns to — wherever the visitor actually came
 * from, not a hardcoded one. Set by whichever entry point opens the screen. */
let agOrigin = 'viewSpots';

function checkAgReference(){
  const v = $('agReference').value.trim().toUpperCase();
  const fb = $('fbAgReference');
  if(v.length < 7){ fb.textContent = v ? t('self.reftooshort') : ''; fb.className = 'fb'; return; }
  const r = refLookup(v);
  fb.textContent = r.text;
  fb.className = 'fb' + (r.cls ? ' ' + r.cls : '');
}

/* The one-month ceiling is enforced by the Worker too (buildAgenda rejects a
 * start more than a month out) — the min/max here just stop the picker from
 * offering a date that would be rejected anyway, and say why up front. */
function agendaGrenzen(){
  const pad = n => String(n).padStart(2,'0');
  const naarLokaal = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const nu = new Date();
  const grens = new Date(nu.getTime() + 31*24*3600*1000);
  $('agStart').min = $('agEnd').min = naarLokaal(nu);
  $('agStart').max = $('agEnd').max = naarLokaal(grens);
}

function validateAgenda(){
  let ok = true;
  const set = (el, good) => {
    el.classList.toggle('bad', !good && el.value.trim() !== '');
    el.classList.toggle('good', good && el.value.trim() !== '');
    if(!good) ok = false;
  };
  const a = $('agActivator'), p = $('agPoster'), r = $('agReference'), pin = $('agPin');
  set(a, validCall(a.value.trim()));
  set(p, validCall(p.value.trim()));
  set(r, r.value.trim().length >= 7);
  set(pin, pin.value.trim().length >= 4);

  const s = $('agStart'), e = $('agEnd');
  let whenMsg = '', whenOk = false;
  if(s.value && e.value){
    const t0 = new Date(s.value).getTime(), t1 = new Date(e.value).getTime();
    if(isNaN(t0) || isNaN(t1)){ whenMsg = ''; }
    else if(t1 <= t0){ whenMsg = t('ag.endbeforestart'); }
    else if(t0 > Date.now() + 31*24*3600*1000){ whenMsg = t('ag.toofar'); }
    else whenOk = true;
  }
  $('fbAgWhen').textContent = whenMsg;
  $('fbAgWhen').className = 'fb' + (whenMsg ? ' bad' : '');
  s.classList.toggle('bad', !!s.value && !whenOk);
  e.classList.toggle('bad', !!e.value && !whenOk);
  if(!whenOk) ok = false;

  $('agCheck').disabled = !ok;
  $('agSend').disabled  = !ok || !agGecontroleerd;
  return ok;
}

function vergeetControleAg(){
  if(!agGecontroleerd) return;
  agGecontroleerd = false;
  $('fbAgSend').textContent = t('self.recheck');
  $('fbAgSend').className = 'fb';
}

/* Local time in, real UTC out — the picker shows the activator's own clock,
 * but what travels to Spotline (and what the label promises) is UTC. */
function agendaVelden(){
  const uit = {
    activator_call: $('agActivator').value.trim().toUpperCase(),
    poster:         $('agPoster').value.trim().toUpperCase(),
    reference:      $('agReference').value.trim().toUpperCase(),
    utc_start:      new Date($('agStart').value).toISOString(),
    utc_end:        new Date($('agEnd').value).toISOString(),
    pin:            $('agPin').value.trim(),
  };
  const band = $('agBand').value.trim(); if(band) uit.band = band;
  const mode = $('agMode').value;        if(mode) uit.mode = mode;
  const rem  = $('agRemarks').value.trim(); if(rem) uit.remarks = rem;
  return uit;
}

async function naarWorkerAgenda(dry){
  const v = agendaVelden();
  const r = await fetch(WORKER + '/agenda', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(dry ? { ...v, dryrun: true } : v),
  });
  let data = null;
  try{ data = await r.json(); }catch{}
  return { status: r.status, data: data || {} };
}

/* Same answers as toonAntwoord() for self-spotting, minus the fallback offer
 * — there is nothing to fall back to here. */
function toonAntwoordAgenda(status, data){
  const fb = $('fbAgSend');
  const zet = (tekst, cls) => { fb.textContent = tekst; fb.className = 'fb' + (cls ? ' ' + cls : ''); };
  if(status === 409){ zet(t('self.dup'), 'good'); return; }
  if(status === 400){
    const uitleg = (data.details && data.details.length) ? data.details.join(' · ') : (data.error || '');
    zet(uitleg, 'bad'); return;
  }
  if(status === 401 || status === 500){ zet(t('self.keyfail'), 'bad'); return; }
  if(status === 429){ zet(t('self.busy'), 'bad'); return; }
  if(status === 503){ zet(data.limit === 'day' ? t('self.dailylimit') : t('self.off'), 'bad'); return; }
  zet(t('self.unreachable'), 'bad');
}

/* The pin is the only way back into an announcement on Spotline's own site —
 * lose it and there is no recovery. Kept locally, per device, next to the
 * reference and date so it means something months later. */
function agendaLijst(){
  try{ return JSON.parse(recall('agendas') || '[]'); }catch{ return []; }
}
function agendaBewaar(item){
  const lijst = agendaLijst();
  lijst.unshift(item);
  remember('agendas', JSON.stringify(lijst.slice(0, 50)));
  renderAgendaSaved();
}
function agendaVerwijder(i){
  const lijst = agendaLijst();
  lijst.splice(i, 1);
  remember('agendas', JSON.stringify(lijst));
  renderAgendaSaved();
}
function renderAgendaSaved(){
  const lijst = agendaLijst();
  $('agSavedCard').hidden = !lijst.length;
  $('agSavedList').innerHTML = lijst.map((it, i) => `
    <div class="spot" style="cursor:default">
      <span class="who"><div class="c">${it.reference}</div>
        <div class="f">${(it.utc_start || '').slice(0,16).replace('T',' ')} UTC · pin ${it.pin}</div></span>
      <button class="btn ghost" data-del="${i}" style="padding:4px 10px">✕</button>
    </div>`).join('');
}
$('agSavedList').addEventListener('click', e => {
  const b = e.target.closest('button[data-del]'); if(!b) return;
  agendaVerwijder(Number(b.dataset.del));
});

$('agCheck').onclick = async () => {
  if(!validateAgenda()) return;
  $('agCheck').disabled = true;
  const fb = $('fbAgSend');
  fb.textContent = t('self.checking'); fb.className = 'fb';
  try{
    const { status, data } = await naarWorkerAgenda(true);
    if(status >= 200 && status < 300){
      agGecontroleerd = true;
      fb.textContent = t('self.checkok'); fb.className = 'fb good';
    } else {
      agGecontroleerd = false;
      toonAntwoordAgenda(status, data);
    }
  }catch{
    agGecontroleerd = false;
    fb.textContent = t('self.unreachable'); fb.className = 'fb bad';
  }finally{
    validateAgenda();
  }
};

$('agSend').onclick = async () => {
  if(!validateAgenda() || !agGecontroleerd) return;
  $('agSend').disabled = true;
  const fb = $('fbAgSend');
  fb.textContent = t('ag.sending'); fb.className = 'fb';
  try{
    const { status, data } = await naarWorkerAgenda(false);
    if(status >= 200 && status < 300){
      const v = agendaVelden();
      const id = data.agenda_id || (data.data && data.data.agenda_id) || null;
      agendaBewaar({ reference: v.reference, utc_start: v.utc_start, pin: v.pin, id });
      fb.textContent = t('ag.ok') + (id ? ` · #${id}` : '');
      fb.className = 'fb good';
      showStatus('in', t('ag.ok'), `${v.activator_call} · ${v.reference}`);
      $('agReference').value = ''; $('agStart').value = ''; $('agEnd').value = '';
      $('agBand').value = ''; $('agMode').value = ''; $('agRemarks').value = ''; $('agPin').value = '';
      $('agCount').textContent = '0/100';
      $('fbAgReference').textContent = ''; $('fbAgReference').className = 'fb';
    } else {
      toonAntwoordAgenda(status, data);
    }
  }catch{
    fb.textContent = t('self.unreachable'); fb.className = 'fb bad';
  }finally{
    agGecontroleerd = false;
    validateAgenda();
  }
};

['agActivator','agPoster','agReference'].forEach(id => {
  $(id).addEventListener('input', e => {
    const p = e.target.selectionStart;
    e.target.value = e.target.value.toUpperCase();
    e.target.setSelectionRange(p, p);
    if(id === 'agReference') checkAgReference();
    vergeetControleAg();
    validateAgenda();
  });
});
['agStart','agEnd','agBand','agMode','agPin'].forEach(id => $(id).addEventListener('input', () => {
  vergeetControleAg();
  validateAgenda();
}));
$('agRemarks').addEventListener('input', e => {
  $('agCount').textContent = `${e.target.value.length}/100`;
  vergeetControleAg();
  validateAgenda();
});

/* Opened from the "+ Aankondigen" button on the Agenda tab of the Spots
 * screen, not from the bottom nav — gaNaarView() does by hand what the nav's
 * own click handler does for its buttons. */
function gaNaarView(id, extra){
  $('viewHeat').classList.remove('minimized');
  document.querySelectorAll('#nav button').forEach(c => c.classList.remove('on'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('on'));
  $(id).classList.add('on');
  toggle(null);
  if(extra) extra();
  requestAnimationFrame(() => { map.resize(); map.triggerRepaint(); });
}

function agendaOpen(){
  const ref = selected;
  const z = ref && zones && zones.features.find(f => f.properties.ref === ref);
  if(z){ $('agReference').value = z.properties.ref; checkAgReference(); }
  if(!$('agActivator').value) $('agActivator').value = recall('activator') || cfg.callp || cfg.call;
  if(!$('agPoster').value)    $('agPoster').value    = recall('spotter')   || cfg.call || (cfg.callp||'').split('/')[0];
  agendaGrenzen();
  renderAgendaSaved();
  validateAgenda();
}

$('agNewOpen').onclick = () => { agOrigin = 'viewSpots'; gaNaarView('viewAgendaNew', agendaOpen); };
$('agFromSelf').onclick = () => { agOrigin = 'viewSelf'; gaNaarView('viewAgendaNew', agendaOpen); };
$('agBack').onclick = () => document.querySelector(`#nav button[data-view="${agOrigin}"]`).click();

