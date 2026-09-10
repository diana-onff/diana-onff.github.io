/* ---------- offline: service worker + downloading an area ---------- */
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

  navigator.serviceWorker.addEventListener('message', e=>{
    if(e.data?.type==='PREFETCH_PROGRESS')
      showStatus('out', t('off.downloading'), `${e.data.done} / ${e.data.total} ${t('off.tiles')}`);
    if(e.data?.type==='PREFETCH_DONE')
      showStatus('in', t('off.saved'), `${e.data.done} ${t('off.tilesoffline')}`);
  });

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
  showStatus('in', t('app.newversion'), t('app.taptoreload'));
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
    showStatus('in', t('app.uptodate'), 'v' + APP_VERSION);
  }catch(err){
    showStatus('out', t('app.uptodate'), err.message || '');
  }finally{
    btn.disabled = false;
  }
};

/* Works out the tiles of the current map viewport at zoom 8 through 14 and lets
   the service worker fetch them. This is the button you press before you set off. */
function prefetchArea(){
  if(!navigator.serviceWorker?.controller){
    showStatus('out', t('off.cannot'), t('off.cannotsub'));
    return;
  }
  const b = map.getBounds(), urls = [];
  const lon2x = (lon,z)=>Math.floor((lon+180)/360*2**z);
  const lat2y = (lat,z)=>Math.floor((1-Math.log(Math.tan(lat*Math.PI/180)+1/Math.cos(lat*Math.PI/180))/Math.PI)/2*2**z);
  for(let z=8; z<=14; z++){
    const x1=lon2x(b.getWest(),z), x2=lon2x(b.getEast(),z);
    const y1=lat2y(b.getNorth(),z), y2=lat2y(b.getSouth(),z);
    if((x2-x1+1)*(y2-y1+1) > 900) continue;         // viewport too large for this zoom level
    for(let x=x1;x<=x2;x++) for(let y=y1;y<=y2;y++)
      urls.push(`https://tiles.openfreemap.org/planet/${z}/${x}/${y}.pbf`);
  }
  if(!urls.length){ showStatus('out', t('off.zoomin'), t('off.zoominsub')); return; }
  showStatus('out', t('off.downloading'), `0 / ${urls.length} ${t('off.tiles')}`);
  navigator.serviceWorker.controller.postMessage({type:'PREFETCH_TILES', urls});
}

