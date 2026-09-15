/* ================================================================== *
 * Screen 4 — activation session and GPS evidence
 * Entirely local. ONFF requires proof with the log; a track saying
 * "96% of 1h24 inside ONFF-0104" is stronger evidence than a photo.
 * ================================================================== */
const sess = { on:false, t0:null, ref:null, points:[], inside:0, total:0, watch:null, tick:null };

function renderSession(){
  const ref = sess.ref || selected;
  const z = ref && zones && zones.features.find(f=>f.properties.ref===ref);
  $('sessRef').textContent = z ? `${z.properties.ref} · ${z.properties.name}` : t('sess.sub');
  $('sessStart').disabled = !z && !sess.on;
  updateSessionUI();
}

function updateSessionUI(){
  const el=$('sessBanner');
  if(!sess.on){
    el.className='banner out';
    $('sessB1').textContent = t('sess.unknown'); $('sessB2').textContent = t('sess.press');
    return;
  }
  const last = sess.points[sess.points.length-1];
  const inZone = last && last.in;
  el.className = 'banner ' + (inZone?'in':'out');
  $('sessB1').textContent = inZone ? t('sess.inside') : t('sess.outside');
  $('sessB2').textContent = inZone
    ? `${t('sess.pos')} ${sess.ref}`
    : t('sess.outsidesub');
}

function fmtClock(ms){
  const s=Math.floor(ms/1000);
  return [Math.floor(s/3600),Math.floor(s/60)%60,s%60].map(n=>String(n).padStart(2,'0')).join(':');
}

$('sessStart').onclick = ()=>{
  const ref = sess.ref || selected;
  if(!ref){ alert(t('sess.pickfirst')); return; }
  const zone = zones.features.find(f=>f.properties.ref===ref);
  sess.on=true; sess.ref=ref; sess.t0=Date.now(); sess.points=[]; sess.inside=0; sess.total=0;
  $('sessStart').hidden=true; $('sessStop').hidden=false; $('sessGpx').hidden=true; $('sessRec').hidden=false;
  sess.watch = navigator.geolocation.watchPosition(pos=>{
    const {latitude:lat,longitude:lon,accuracy}=pos.coords;
    const inZone = pointInGeom(lon,lat,zone.geometry);
    sess.points.push({lat,lon,acc:accuracy,t:new Date().toISOString(),in:inZone});
    sess.total++; if(inZone) sess.inside++;
    here={lat,lon};
    if(showSpots) paintSpots();
    updateSessionUI();
  }, ()=>{}, {enableHighAccuracy:true, maximumAge:2000, timeout:20000});
  sess.tick = setInterval(()=>{
    $('sessClock').textContent = fmtClock(Date.now()-sess.t0);
    $('sessPts').textContent = `${sess.points.length} ${t('sess.points')}`;
    const pct = sess.total ? Math.round(100*sess.inside/sess.total) : 0;
    const mins = Math.floor((Date.now()-sess.t0)/60000);
    $('sessPct').textContent = `${t('sess.started')} ${new Date(sess.t0).toLocaleTimeString('nl-BE',{hour:'2-digit',minute:'2-digit'})} · ${pct}% ${t('sess.oftime')}`
      + (mins<60 ? ` · ${t('sess.need60')} (${60-mins} ${t('sess.minleft')})` : ` · ${t('sess.ok60')}`);
  }, 1000);
  renderSession();
};

$('sessStop').onclick = ()=>{
  sess.on=false;
  if(sess.watch!=null) navigator.geolocation.clearWatch(sess.watch);
  clearInterval(sess.tick);
  $('sessStop').hidden=true; $('sessGpx').hidden=false; $('sessRec').hidden=true;
  $('sessStart').hidden=false; $('sessStart').textContent = t('sess.restart');
  updateSessionUI();
};

function sessionSummary(){
  const pct = sess.total ? Math.round(100*sess.inside/sess.total) : 0;
  const dur = sess.points.length ? (new Date(sess.points[sess.points.length-1].t) - new Date(sess.points[0].t)) : 0;
  const z = zones.features.find(f=>f.properties.ref===sess.ref);
  return {pct, dur, ref:sess.ref, name:z?z.properties.name:'', n:sess.points.length};
}

function toGPX(){
  const {ref,name} = sessionSummary();
  const pts = sess.points.map(p=>
    `   <trkpt lat="${p.lat.toFixed(6)}" lon="${p.lon.toFixed(6)}"><time>${p.t}</time>`+
    `<extensions><diana:inside>${p.in}</diana:inside><diana:accuracy>${Math.round(p.acc||0)}</diana:accuracy></extensions></trkpt>`
  ).join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Diana" xmlns="http://www.topografix.com/GPX/1/1" xmlns:diana="https://diana.app/ns">
 <metadata><name>${ref} ${name}</name><time>${new Date(sess.t0).toISOString()}</time></metadata>
 <trk><name>${ref} ${name}</name><trkseg>
${pts}
 </trkseg></trk>
</gpx>`;
}

function summaryText(){
  const s=sessionSummary();
  const h=Math.floor(s.dur/3600000), m=Math.round(s.dur%3600000/60000);
  return [
    `Diana — activatiebewijs`,
    ``,
    `Referentie   : ${s.ref} ${s.name}`,
    `Start        : ${new Date(sess.t0).toISOString()}`,
    `Duur         : ${h} u ${m} min`,
    `Meetpunten   : ${s.n}`,
    `Binnen zone  : ${s.pct}% van de meetpunten`,
    ``,
    `ONFF vraagt minstens 60 minuten vanaf de eerste QSO en 44 QSO's`,
    `(behalve bij QRP). Alle apparatuur moet binnen de referentiegrens staan.`,
    ``,
    `Bijgevoegde GPX bevat per meetpunt de tijd, de nauwkeurigheid en of`,
    `het punt binnen de grens viel.`,
  ].join('\n');
}

function download(name, text, type){
  const url = URL.createObjectURL(new Blob([text],{type}));
  const a = Object.assign(document.createElement('a'),{href:url,download:name});
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('sessGpx').onclick = ()=>{
  if(!sess.points.length){ alert(t('sess.nopoints')); return; }
  const stamp = new Date(sess.t0).toISOString().slice(0,10).replace(/-/g,'');
  download(`${sess.ref}_${stamp}.gpx`, toGPX(), 'application/gpx+xml');
  download(`${sess.ref}_${stamp}_bewijs.txt`, summaryText(), 'text/plain');
};

