/* ---------- swipe down to close a panel ----------
 *
 * On a phone that is the gesture people try anyway. The × stays: the gesture is
 * a second route, not a replacement. Downwards only, and only if the panel
 * itself is not scrolling — otherwise it closes while you are reading your way
 * through the text.
 */
function swipeToClose(el, close){
  if(!el) return;
  let y0 = null, dy = 0, moved = false;

  const start = e => {
    const p = e.touches ? e.touches[0] : e;
    // Is the finger inside a part that can still scroll upwards itself? Then
    // this is a scroll, not a close gesture.
    const sc = e.target.closest ? e.target.closest('.scroll,.spotlist,.card,.facts') : null;
    if(sc && sc.scrollTop > 0) return;
    // Already tucked away? Then a touch is meant to bring it back, not to push
    // it further away.
    if(el.classList.contains('minimized')) return;
    y0 = p.clientY; dy = 0; moved = false;
  };
  const move = e => {
    if(y0 == null) return;
    const p = e.touches ? e.touches[0] : e;
    dy = p.clientY - y0;
    if(dy < 0){ dy = 0; return; }            // swiping upwards does nothing
    if(dy > 6){ moved = true; if(e.cancelable) e.preventDefault(); }
    el.style.transition = 'none';
    el.style.transform = `translateY(${dy}px)`;
  };
  const end = () => {
    if(y0 == null) return;
    el.style.transition = '';
    el.style.transform = '';
    const far = dy > Math.min(90, el.offsetHeight * 0.28);
    y0 = null;
    if(moved && far) close();
  };

  el.addEventListener('touchstart', start, {passive:true});
  el.addEventListener('touchmove',  move,  {passive:false});
  el.addEventListener('touchend',   end);
  el.addEventListener('touchcancel',end);
  // With the mouse too, so that it can be tried out on a laptop.
  el.addEventListener('pointerdown', e => { if(e.pointerType==='mouse' && e.button===0) start(e); });
  addEventListener('pointermove', e => { if(y0!=null && e.pointerType==='mouse') move(e); });
  addEventListener('pointerup',   e => { if(y0!=null && e.pointerType==='mouse') end(); });
}

swipeToClose($('sheet'),     closeSheet);
swipeToClose($('spotSheet'), () => $('closeSpot').onclick());
// The heatmap panel is a screen, not a panel: swiping down takes you back to
// the map, just like tapping the map button.
// Swiping down tucks the heatmap panel away without closing the heatmap: the
// tab stays Heatmap and the areas keep their colour. That is the whole point of
// the heatmap — the text is secondary, the map is the main event.
swipeToClose($('viewHeat'),  () => minimizeHeat(true));

function minimizeHeat(aan){
  $('viewHeat').classList.toggle('minimized', !!aan);
}

// Tapping the strip brings it back.
$('viewHeat').addEventListener('click', e => {
  if(!$('viewHeat').classList.contains('minimized')) return;
  e.stopPropagation();
  minimizeHeat(false);
});


