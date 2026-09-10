/* Order: what the user chose > the browser's language if we speak it > English. */
const LANGS = ['en','nl','fr','de','da','it','es'];
/* Order: ?lang= in the URL, then the choice from Settings, then English.
 *
 * "auto" is an explicit choice to follow the browser language — anyone who
 * chooses nothing gets English, not whatever language their browser happens to
 * report. That keeps the default predictable and the choice in one place:
 * Settings. */
function browserLang(){
  const nav = (navigator.language || 'en').slice(0,2).toLowerCase();
  return STR[nav] ? nav : 'en';
}
function savedLang(){
  try{ return localStorage.getItem('diana.lang') || ''; }catch{ return ''; }
}
function pickLang(){
  const q = new URLSearchParams(location.search).get('lang');
  if(q && STR[q]) return q;
  const saved = savedLang();
  if(saved === 'auto') return browserLang();
  if(saved && STR[saved]) return saved;
  return 'en';
}
let lang = pickLang();
/* What the user chose ('auto', a language code, or nothing = English). Kept
   separate from `lang`, because that is the resolved language of the moment. */
let langPref = savedLang() || 'en';
const t = k => (STR[lang] && STR[lang][k]) || STR.nl[k] || k;
function locale(){ return {nl:'nl-BE',fr:'fr-BE',en:'en-GB',de:'de-DE',da:'da-DK',it:'it-IT',es:'es-ES'}[lang] || 'en-GB'; }

function applyLang(){
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el=>{ el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-ph]').forEach(el=>{ el.placeholder = t(el.dataset.i18nPh); });
  rerender();
}

/* Redraw everything that was drawn with JavaScript — otherwise half the screen
   stays sitting there in the old language. */
function rerender(){
  try{
    if(zones) $('counts').innerHTML = `<b>${zones.features.length}</b> ${t('map.areas')}`
      + (noPoly.features.length ? ` · ${noPoly.features.length} ${t('map.nopolycount')}` : '');
    renderInstall();
    if(selected) select(selected);
    renderSpots();
    renderRules();
    renderSession();
    selfPrefill();
    if(heatLoaded) paintHeat();
    if($('status').classList.contains('show')) $('status').classList.remove('show');
  }catch(err){ console.warn('hertekenen:', err); }
}

