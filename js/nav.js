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

/* ---------- the phone's back button ----------
 * Android's back button (and gesture) walks back through the browser history.
 * Diana is one page, so with nothing in that history back simply closes the
 * app. Where "back" has an obvious meaning inside Diana (a spot opened from the
 * Spots list -> that list; the release overview -> Settings), the screen that
 * opens it calls pushBack(close): one history entry of our own, and back runs
 * `close` instead of leaving. Closed any other way (x, swipe, Escape, the
 * bottom bar), dropBack() takes that entry away again, so the next back press
 * does what it did before. Everywhere else nothing changes.
 *
 * history.back() is not immediate: its popstate arrives later. `ignore` counts
 * the ones we caused ourselves, and a pushBack() that comes in while one is
 * still on its way waits for it (`wanted`), or the entry it pushes would be
 * the one that late back() then removes. */
const backNav = {close: null, entry: false, ignore: 0, wanted: false};
function pushBack(close){
  backNav.close = close;
  if(backNav.entry) return;
  if(backNav.ignore){ backNav.wanted = true; return; }
  history.pushState({diana: 'back'}, '');
  backNav.entry = true;
}
function dropBack(){
  backNav.close = null;
  backNav.wanted = false;
  if(!backNav.entry) return;
  backNav.entry = false;
  backNav.ignore++;
  history.back();
}
// Reloaded (the "new version" toast, or the phone bringing a discarded tab
// back) while one of our entries was on top: the screen it belonged to is gone,
// so take the entry away too, or the next back press would do nothing at all.
if(history.state && history.state.diana === 'back'){ backNav.ignore++; history.back(); }

addEventListener('popstate', () => {
  if(backNav.ignore){
    backNav.ignore--;
    if(backNav.wanted && backNav.close && !backNav.ignore){
      backNav.wanted = false;
      history.pushState({diana: 'back'}, '');
      backNav.entry = true;
    }
    return;
  }
  // The user pressed back while one of our entries was on top.
  backNav.entry = false;
  const close = backNav.close; backNav.close = null;
  if(close) close();
});

$('nav').addEventListener('click', e=>{
  const b=e.target.closest('button[data-view]'); if(!b) return;
  // A spot opened from the Spots list: leaving it through the bottom bar puts
  // the map back where it was instead of returning to the list (spots.js).
  if(typeof dropListReturn === 'function') dropListReturn();
  // Whatever screen had a back entry of its own is being left.
  dropBack();
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



