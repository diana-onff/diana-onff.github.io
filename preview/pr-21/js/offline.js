/* ---------- offline: service worker + update notice ---------- */
let swReg = null;

if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
  navigator.serviceWorker.register('sw.js').then(reg => {
    swReg = reg;
    // On every start, ask once whether a new release is waiting. The browser
    // normally does this itself, but not reliably for an app that stays open
    // for days on end on a phone.
    reg.update().catch(()=>{});
    reg.addEventListener('updatefound', () => {
      const nieuwe = reg.installing;
      if(!nieuwe) return;
      nieuwe.addEventListener('statechange', () => {
        // "installed" with an existing controller = a new version is waiting
        // alongside the running one. That is the moment to say so instead of
        // quietly pushing it through next time.
        if(nieuwe.state === 'installed' && navigator.serviceWorker.controller)
          meldNieuweVersie();
      });
    });
  }).catch(()=>{});

  // Reload once as soon as the new service worker takes over, never twice — a
  // reload loop is worse than a stale page. And not on the very first
  // installation: there is no old version to replace yet then, and the app
  // would reload itself while you are sitting there looking at it.
  let hadController = !!navigator.serviceWorker.controller;
  let herladen = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if(!hadController){ hadController = true; return; }
    if(herladen) return;
    herladen = true;
    location.reload();
  });
}

function meldNieuweVersie(){
  showStatus('in', t('app.newversion'), t('app.taptoreload'), true);
  const box = $('status');
  if(!box) return;
  box.style.cursor = 'pointer';
  box.addEventListener('click', pasToe, {once:true});
  function pasToe(){
    const wachtend = swReg && (swReg.waiting || swReg.installing);
    if(wachtend) wachtend.postMessage({type:'SKIP_WAITING'});
    else location.reload();
  }
}

/* The button in Settings: check whether there is anything new, and say so even
   when there isn't. Silence after pressing a button reads as a fault. */
$('btnRefresh').onclick = async () => {
  const btn = $('btnRefresh');
  btn.disabled = true;
  try{
    // Fetch the dataset again, around the cache, so that the line in Settings
    // immediately matches what is on the server.
    await loadMeta();
    if(swReg){
      await swReg.update();
      if(swReg.waiting || swReg.installing){ meldNieuweVersie(); return; }
    }
    showStatus('in', t('app.uptodate'), 'v' + APP_VERSION, true);
  }catch(err){
    showStatus('out', t('app.uptodate'), err.message || '', true);
  }finally{
    btn.disabled = false;
  }
};
