/* ================================================================== *
 * Bottom bar and full screens
 * ================================================================== */
document.body.classList.add('has-nav');
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



