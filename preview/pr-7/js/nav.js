/* ================================================================== *
 * Bottom bar and full screens
 * ================================================================== */
document.body.classList.add('has-nav');

/* The bar's real height varies by device — a safe-area inset for gesture
   navigation adds to it, and so does a larger system text size, both of
   which make it taller than the roughly 62px every other bit of chrome
   above it used to just assume. That assumption used to be hardcoded in
   four separate places (app.css): the version badge sat "70px" up, the
   sliding sheet and the status toast had their own numbers, and the map's
   own controls a fourth — every one of them wrong by exactly however much
   the bar on the phone in your hand differs from the one on the phone the
   number was picked on. Read --nav-h instead of guessing: the actual height
   of the bar, kept in sync here, once at load and again whenever it could
   plausibly have changed — a resize (orientation), or the bar itself
   changing height for a reason a resize would never fire for, such as a
   system font size taking effect after the page already rendered. */
function syncNavHeight(){
  const nav = $('nav');
  if(nav) document.documentElement.style.setProperty('--nav-h', nav.offsetHeight + 'px');
}
syncNavHeight();
window.addEventListener('resize', syncNavHeight);
if(typeof ResizeObserver !== 'undefined') new ResizeObserver(syncNavHeight).observe($('nav'));

$('nav').addEventListener('click', e=>{
  const b=e.target.closest('button[data-view]'); if(!b) return;
  [...$('nav').children].forEach(c=>c.classList.toggle('on',c===b));
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  if(b.dataset.view!=='map'){ $(b.dataset.view).classList.add('on'); toggle(null); }
  else {
    // Home: no panel left open over the map, and nothing still outlined.
    closeSheet();
    $('closeSpot').onclick();
    clearSelection();
  }
  if(b.dataset.view==='viewSpots'){
    startSpots(); renderSpots(); redrawOverlays();
  }
  if(b.dataset.view==='viewNearby') renderNearby();
  if(b.dataset.view==='viewRules') renderRules();
  if(b.dataset.view==='viewSession') renderSession();
  if(b.dataset.view==='viewSelf') selfPrefill();
  if(b.dataset.view==='viewAgendaNew'){ agOrigin = 'viewSpots'; agendaOpen(); }
  if(b.dataset.view==='viewSet') loadSettingsUI();
  if(b.dataset.view==='viewAdmin') buildEmbed();
  // Only update when the map really changes size; a resize on every click costs
  // a frame and buys nothing.
  requestAnimationFrame(()=>{ map.resize(); map.triggerRepaint(); });
});



