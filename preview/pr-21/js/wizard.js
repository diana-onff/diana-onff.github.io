/* ---------- setup wizard and tour ----------
 *
 * Runs once, on a new device, straight after the welcome screen (privacy.js
 * calls startFirstWizard() when that screen is answered). Two parts:
 *
 *   1. Basic settings, one step at a time. Nothing here is stored by the
 *      wizard itself: every answer is written into the matching field in
 *      Settings and goes through that field's own handler, so the wizard can
 *      never disagree with Settings about what was saved, or how.
 *   2. A tour: the real screens one after the other, with a card at the
 *      bottom that says what you are looking at.
 *
 * Settings has a button to run it again; it then starts from the settings
 * you already have. Only the first run sets the defaults it does not ask
 * about: Spots on Worldwide and Field info at 10 km.
 *
 * "wizard.todo" covers an app that is closed halfway through the settings:
 * the wizard comes back on the next start until its last settings step has
 * been reached. The tour never comes back by itself. */

const WZ_LANGS = ['en','nl','fr','de','da','it','es','pt'];
const WZ_TOUR = [
  {view:'map',           title:'nav.map',         n:5, key:'map'},
  {view:'viewSpots',     title:'nav.spots',       n:4, key:'spots'},
  {view:'viewSelf',      title:'nav.self',        n:4, key:'self'},
  {view:'viewAgendaNew', title:'spots.tabagenda', n:3, key:'agenda'},
  {view:'viewNearby',    title:'nav.nearby',      n:3, key:'nearby'},
  {view:'viewRules',     title:'nav.rules',       n:2, key:'rules'},
  {view:'viewSet',       title:'nav.settings',    n:3, key:'set'},
];

const wz = {open:false, first:false, steps:[], i:0, chips:[], tour:-1, countryTimer:null, lang:null};

const wzEsc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* Put a value into a Settings field and let that field's own handler do the
   rest: upper case, validation, saving, and whatever else listens to it. */
function wzSetField(id, value){
  const el = $(id); if(!el) return;
  el.value = value;
  el.dispatchEvent(new Event('input', {bubbles:true}));
}

function openWizard(first){
  if(wz.open) return;
  if(typeof loadSettingsUI === 'function') loadSettingsUI();
  wz.open = true;
  wz.first = !!first;
  // Asked once more only when the answer so far is not yes. Decided now, so
  // the step does not vanish the moment someone taps yes on it.
  const askStats = typeof statsConsent === 'function' && statsConsent() !== '1';
  wz.steps = ['lang', 'station', 'country', 'chips', 'bands'].concat(askStats ? ['stats'] : [], ['done']);
  // A first run starts with empty quick words, unless some were already saved
  // (a wizard picked up again after the app was closed halfway).
  wz.chips = first && !recall('chips') ? ['', '', '', '', ''] : cfg.chips.slice();
  wz.statsWasNo = undefined;
  if(first){
    remember('wizard.todo', '1');
    // The two defaults the wizard does not ask about.
    if(typeof spotFilter !== 'undefined' && spotFilter !== 'all' && typeof setSpotFilter === 'function') setSpotFilter('all');
    // Through the button's own handler, like every other answer here, so the
    // switch in Settings shows it too.
    const km = $('setNearKm') && $('setNearKm').querySelector('.seg[data-km="10"]');
    if(km) km.click(); else { cfg.nearkm = 10; saveSettings(); }
    // Empty quick words are saved right away: typing one word saves all five,
    // and the four untouched ones must not come back as the defaults.
    if(!recall('chips')) wzCommitChips();
  }
  wz.i = 0;
  $('wizard').hidden = false;
  $('wzClose').hidden = wz.first;
  // Run again from Settings: the phone's back button closes it, as it closes
  // any other screen. A first run is not something to back out of.
  if(!wz.first && typeof pushBack === 'function') pushBack(closeWizard);
  wzRender();
}

function startFirstWizard(){
  if(typeof isEmbed !== 'undefined' && isEmbed) return;
  if(recall('wizard.done') === '1') return;
  openWizard(true);
}

function wzCountryOptions(){
  const src = $('setSpotCountry');
  return src && src.options.length ? src.innerHTML : '';
}

function wzStepHtml(step){
  switch(step){
    case 'lang': return `
      <h2 id="wzTitle">${t('wz.lang.title')}</h2>
      <p>${t('wz.lang.body')}</p>
      <div class="langs" id="wzLangs">${WZ_LANGS.map(l =>
        `<button class="seg${l === lang ? ' on' : ''}" type="button" data-lang="${l}">${l.toUpperCase()}</button>`).join('')}</div>`;
    case 'station': return `
      <h2 id="wzTitle">${t('set.you')}</h2>
      <div class="fgrid">
        <label class="fld"><span>${t('set.call')}</span>
          <input id="wzCall" type="text" autocomplete="off" spellcheck="false" placeholder="ON3VZ" value="${wzEsc(cfg.call)}"></label>
        <label class="fld"><span>${t('set.portable')}</span>
          <input id="wzCallP" type="text" autocomplete="off" spellcheck="false" placeholder="ON3VZ/P" value="${wzEsc(cfg.callp)}"></label>
      </div>
      <p class="why">${t('wz.station.callwhy')}</p>
      <label class="fld"><span>${t('set.grid')}</span>
        <input id="wzGrid" type="text" autocomplete="off" spellcheck="false" placeholder="JO21EE" maxlength="8" value="${wzEsc(cfg.grid)}"></label>
      <div class="fb" id="wzFbGrid"></div>
      <button class="btn ghost wgps" id="wzGps" type="button">${t('set.gridfrom')}</button>
      <p class="why" style="margin-top:12px">${t('wz.station.gridwhy')}</p>`;
    case 'country': {
      const opts = wzCountryOptions();
      return `
      <h2 id="wzTitle">${t('set.countrytitle')}</h2>
      <p>${t('set.countrylead')}</p>
      <label class="fld"><span>${t('set.country')}</span>
        ${opts ? `<select id="wzCountry">${opts}</select>` : `<p class="hint" id="wzCountryWait">${t('spots.loading')}</p>`}</label>
      <p class="why">${t('wz.country.show')}</p>`;
    }
    case 'chips': return `
      <h2 id="wzTitle">${t('self.chipstitle')}</h2>
      <p>${t('self.chipslead')}</p>
      <div class="fgrid">${[0,1,2,3,4].map(i =>
        `<label class="fld"${i === 4 ? ' style="grid-column:1/-1"' : ''}><span>${i + 1}</span>
          <input id="wzChip${i}" type="text" maxlength="24" autocomplete="off" value="${wzEsc(wz.chips[i])}"></label>`).join('')}</div>
      <button class="btn ghost chipsbtn" id="wzChipsDefault" type="button">${t('wz.chips.defaults')}</button>
      <p class="hint" style="margin:10px 2px 0">${t('wz.chips.skip')}</p>`;
    case 'bands': return `
      <h2 id="wzTitle">${t('set.bandstitle')}</h2>
      <p class="why">${t('wz.bands.why')}</p>
      <div class="segs" id="wzBands">
        <button class="seg${cfg.bands === 'full' ? ' on' : ''}" type="button" data-bands="full">${t('set.bandsfull')}</button>
        <button class="seg${cfg.bands === 'short' ? ' on' : ''}" type="button" data-bands="short">${t('set.bandsshort')}</button>
      </div>
      <p class="hint">${t('set.bandsnote')}</p>`;
    case 'stats': {
      const now = statsConsent();
      return `
      <h2 id="wzTitle">${t('consent.statsh')}</h2>
      ${wz.statsWasNo ? `<p class="why">${t('wz.stats.again')}</p>` : ''}
      <p>${t('consent.statsbody')}</p>
      <div class="segs" id="wzStats">
        <button class="seg${now === '1' ? ' on' : ''}" type="button" data-stats="1">${t('privacy.statsyes')}</button>
        <button class="seg${now === '0' ? ' on' : ''}" type="button" data-stats="0">${t('privacy.statsno')}</button>
      </div>`;
    }
    case 'done': return `
      <h2 id="wzTitle">${t('wz.done.title')}</h2>
      <p>${t('wz.done.saved')}</p>
      <p class="why">🔒 ${t('wz.done.storage')}</p>
      <p style="margin-top:14px"><b>${t('wz.done.tourq')}</b></p>
      <div class="wstack">
        <button class="btn" id="wzTourGo" type="button">${t('wz.tourstart')}</button>
        <button class="btn ghost" id="wzTourSkip" type="button">${t('wz.skip')}</button>
      </div>`;
  }
  return '';
}

function wzRender(){
  if(!wz.open) return;
  const step = wz.steps[wz.i];
  const last = step === 'done';
  wz.lang = lang;
  if(step === 'stats' && wz.statsWasNo === undefined) wz.statsWasNo = statsConsent() === '0';
  $('wzStep').textContent = t('wz.stepof').replace('{n}', wz.i + 1).replace('{m}', wz.steps.length);
  $('wzBody').innerHTML = wzStepHtml(step);
  $('wzBack').textContent = t('wz.back');
  $('wzNext').textContent = t('wz.next');
  $('wzBack').hidden = wz.i === 0;
  // The last settings step has its own two buttons (tour or no tour).
  $('wzNext').hidden = last;
  if(last) $('wzBack').hidden = true;
  $('wzFoot').innerHTML = last ? '' : `🔒 <span>${t('wz.foot')}</span>`;
  $('wzFoot').hidden = last;
  wzWire(step);
  if(last){
    // Reaching this step is finishing the settings part: from here on a
    // restart no longer brings the wizard back.
    remember('wizard.todo', '');
    remember('wizard.done', '1');
  }
  const card = document.querySelector('#wizard .wcard');
  if(card) card.scrollTop = 0;
}

function wzCheckGrid(){
  const v = ($('wzGrid').value || '').trim().toUpperCase();
  const ok = !v || GRID_RE.test(v);
  $('wzFbGrid').textContent = ok ? '' : t('set.gridbad');
  $('wzFbGrid').className = 'fb' + (ok ? '' : ' bad');
  $('wzGrid').className = !v ? '' : (ok ? 'good' : 'bad');
}

function wzWire(step){
  clearTimeout(wz.countryTimer);
  if(step === 'lang'){
    $('wzLangs').addEventListener('click', e => {
      const b = e.target.closest('.seg[data-lang]'); if(!b) return;
      const target = $('setLang').querySelector(`.seg[data-lang="${b.dataset.lang}"]`);
      if(target) target.click();          // saves and re-translates; rerender() redraws this step
    });
  }
  if(step === 'station'){
    [['wzCall','setCall'], ['wzCallP','setCallP'], ['wzGrid','setGrid']].forEach(([mine, theirs]) => {
      $(mine).addEventListener('input', e => {
        const pos = e.target.selectionStart;
        e.target.value = e.target.value.toUpperCase();
        e.target.setSelectionRange(pos, pos);
        wzSetField(theirs, e.target.value);
        if(mine === 'wzGrid') wzCheckGrid();
      });
    });
    wzCheckGrid();
    $('wzGps').onclick = () => {
      if(!navigator.geolocation){ $('wzFbGrid').textContent = t('wz.gpsfail'); return; }
      const btn = $('wzGps');
      btn.disabled = true;
      $('wzFbGrid').textContent = t('wz.gpsbusy'); $('wzFbGrid').className = 'fb';
      let got = false;
      const end = () => {
        if(!btn.isConnected) return;
        btn.disabled = false;
        if(!got){ $('wzFbGrid').textContent = t('wz.gpsfail'); $('wzFbGrid').className = 'fb bad'; }
      };
      bestFix(pos => {
        got = true;
        const g = locator(pos.coords.latitude, pos.coords.longitude);
        wzSetField('setGrid', g);
        if($('wzGrid')){ $('wzGrid').value = cfg.grid; wzCheckGrid(); }
      }, null, end, end);
    };
  }
  if(step === 'country'){
    const sel = $('wzCountry');
    if(sel){
      sel.value = homeCountry();
      sel.addEventListener('change', () => setHomeCountry(sel.value));
    } else {
      // The country list arrives with the data; wait for it on this step only.
      wz.countryTimer = setTimeout(() => { if(wz.open && wz.steps[wz.i] === 'country') wzRender(); }, 700);
    }
  }
  if(step === 'chips'){
    [0,1,2,3,4].forEach(i => $('wzChip' + i).addEventListener('input', e => {
      wz.chips[i] = e.target.value;
      wzSetField('setChip' + (i + 1), e.target.value);
    }));
    $('wzChipsDefault').onclick = () => {
      wz.chips = CHIP_DEFAULTS.slice();
      wz.chips.forEach((v, i) => { $('wzChip' + i).value = v; });
      wzCommitChips();
    };
  }
  if(step === 'bands'){
    $('wzBands').addEventListener('click', e => {
      const b = e.target.closest('.seg[data-bands]'); if(!b) return;
      const target = $('setBands').querySelector(`.seg[data-bands="${b.dataset.bands}"]`);
      if(target) target.click();
      [...$('wzBands').children].forEach(c => c.classList.toggle('on', c === b));
    });
  }
  if(step === 'stats'){
    $('wzStats').addEventListener('click', e => {
      const b = e.target.closest('.seg[data-stats]'); if(!b) return;
      setStatsConsent(b.dataset.stats === '1');
      [...$('wzStats').children].forEach(c => c.classList.toggle('on', c === b));
    });
  }
  if(step === 'done'){
    $('wzTourGo').onclick = () => { closeWizard(); startTour(); };
    $('wzTourSkip').onclick = () => closeWizard();
  }
}

/* Writes all five, also the ones left empty: on a first run the fields start
   empty on purpose, and empty has to be what gets saved, not the defaults
   Diana would otherwise fall back on. */
function wzCommitChips(){
  wz.chips.forEach((v, i) => wzSetField('setChip' + (i + 1), v));
}

function closeWizard(){
  wz.open = false;
  clearTimeout(wz.countryTimer);
  $('wizard').hidden = true;
  if(typeof dropBack === 'function') dropBack();
}
$('wzClose').onclick = closeWizard;

$('wzNext').onclick = () => {
  const step = wz.steps[wz.i];
  if(step === 'chips') wzCommitChips();
  if(wz.i < wz.steps.length - 1){ wz.i++; wzRender(); }
};
$('wzBack').onclick = () => {
  if(wz.i > 0){ wz.i--; wzRender(); }
};

/* ---------- the tour ---------- */
function navButton(view){ return document.querySelector(`#nav button[data-view="${view}"]`); }

function startTour(){
  // The tour shows the real screens, so the splash screen cannot still be
  // lying over them (it normally goes once the map is drawn, or after 12 s).
  if(typeof splashDone === 'function') splashDone();
  wz.tour = 0;
  $('wzTour').hidden = false;
  tourRender();
}

function tourRender(){
  if(wz.tour < 0) return;
  const s = WZ_TOUR[wz.tour];
  const b = navButton(s.view);
  if(b && !b.classList.contains('on')) b.click();
  // The bottom bar drops any back entry when it switches screens; the tour
  // puts its own back in place each time, so back ends the tour.
  if(typeof pushBack === 'function') pushBack(endTour);
  document.querySelectorAll('#nav button.wzhl').forEach(x => x.classList.remove('wzhl'));
  if(b) b.classList.add('wzhl');
  $('wzTTitle').textContent = t(s.title);
  $('wzTStep').textContent = t('wz.stepof').replace('{n}', wz.tour + 1).replace('{m}', WZ_TOUR.length);
  const items = [];
  for(let i = 1; i <= s.n; i++) items.push(`<li>${t(`wz.t.${s.key}.${i}`)}</li>`);
  $('wzTList').innerHTML = items.join('');
  const last = wz.tour === WZ_TOUR.length - 1;
  $('wzTNext').textContent = last ? t('wz.finish') : t('wz.next');
  $('wzTSkip').textContent = t('wz.skip');
  $('wzTSkip').hidden = last;
}

function endTour(){
  if(wz.tour < 0) return;
  wz.tour = -1;
  $('wzTour').hidden = true;
  document.querySelectorAll('#nav button.wzhl').forEach(x => x.classList.remove('wzhl'));
  const m = navButton('map');
  if(m) m.click();
}

$('wzTNext').onclick = () => {
  if(wz.tour >= WZ_TOUR.length - 1) return endTour();
  wz.tour++;
  tourRender();
};
$('wzTSkip').onclick = endTour;

/* Called from rerender() in i18n.js. That also runs when the data has finished
   loading, not only after a language change, so the step is only redrawn when
   the language really changed: redrawing it would throw away the focus and
   the open keyboard of someone who is typing a callsign at that moment. */
function wizardRerender(){
  if(wz.open && wz.lang !== lang) wzRender();
  if(wz.tour >= 0) tourRender();
}

$('wzRerun').onclick = () => openWizard(false);

// Closed halfway through the settings last time: carry on where it matters.
if(recall('wizard.todo') === '1' && recall('consent.seen') === '1'
   && !(typeof isEmbed !== 'undefined' && isEmbed)) openWizard(true);
