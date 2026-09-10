/* ---------- GPS: am I inside the zone? ---------- */
function pointInRing(x,y,ring){
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [xi,yi]=ring[i], [xj,yj]=ring[j];
    if(((yi>y)!==(yj>y)) && (x < (xj-xi)*(y-yi)/(yj-yi)+xi)) inside=!inside;
  }
  return inside;
}
function pointInGeom(x,y,geom){
  for(const poly of geom.coordinates){
    if(pointInRing(x,y,poly[0])){
      let inHole=false;
      for(let h=1;h<poly.length;h++) if(pointInRing(x,y,poly[h])) inHole=true;
      if(!inHole) return true;
    }
  }
  return false;
}
function haversine(lat1,lon1,lat2,lon2){
  const R=6371000, t=Math.PI/180;
  const a=Math.sin((lat2-lat1)*t/2)**2 +
          Math.cos(lat1*t)*Math.cos(lat2*t)*Math.sin((lon2-lon1)*t/2)**2;
  return 2*R*Math.asin(Math.sqrt(a));
}
function distanceToZone(lat,lon,f){
  // Shortest distance to an edge point. Plenty good enough for "how far are you from the boundary".
  let best=Infinity;
  for(const poly of f.geometry.coordinates)
    for(const [x,y] of poly[0]){
      const d=haversine(lat,lon,y,x);
      if(d<best) best=d;
    }
  return best;
}
function locate(quiet){
  // quiet: called at startup instead of by a tap on ◎. No searching message and
  // no error message then — anyone who doesn't share their location ought to
  // simply see a map, not a complaint.
  if(!navigator.geolocation){ if(!quiet) showStatus('out', t('gps.none'), t('gps.nonesub')); return; }
  if(!quiet) showStatus('out', t('gps.searching'), '');
  navigator.geolocation.getCurrentPosition(pos=>{
    const {latitude:lat, longitude:lon, accuracy} = pos.coords;
    here = {lat, lon};
    marker.setLngLat([lon,lat]).addTo(map);
    map.easeTo({center:[lon,lat], zoom:Math.max(map.getZoom(),12)});
    evaluate(lat,lon,accuracy);
    renderSpots();
    // By now the arc lines have already been drawn from the centre of your
    // locator square — that is the only starting point there is at startup. As
    // soon as the GPS answers that no longer holds, so we draw them again.
    // Without this they stay skewed until you happen to switch tabs.
    if(showSpots) paintSpots();
  }, err=>{
    if(!quiet) showStatus('out', t('gps.failed'), err.message);
  }, {enableHighAccuracy:true, timeout:12000, maximumAge:5000});
}
function evaluate(lat,lon,accuracy){
  // Only real boundaries take part in "am I inside it". A point without a
  // polygon has no inside — you can't ask that question about it.
  const cand = index.filter(z => z.bbox &&
                                 lon>=z.bbox[0]-0.02 && lon<=z.bbox[2]+0.02 &&
                                 lat>=z.bbox[1]-0.02 && lat<=z.bbox[3]+0.02);
  const inside=[];
  for(const z of cand){
    const f = zones.features.find(x=>x.properties.ref===z.ref);
    if(pointInGeom(lon,lat,f.geometry)) inside.push(f);
  }
  const acc = Math.round(accuracy||0);
  if(inside.length){
    // Edge case: are you so close to the boundary that the GPS error could flip the answer?
    const edge = Math.min(...inside.map(f=>distanceToZone(lat,lon,f)));
    const names = inside.map(f=>`${f.properties.ref} ${f.properties.name}`).join(' · ');
    if(edge < acc){
      showStatus('near', t('gps.nearedge').replace('{ref}', inside[0].properties.ref),
        t('gps.nearedgesub').replace('{d}', Math.round(edge)).replace('{a}', acc));
    } else {
      showStatus('in', inside.length>1 ? t('gps.inmany').replace('{n}', inside.length) : t('gps.inone'),
        `${names} — ${t('gps.toedge').replace('{d}', Math.round(edge))}`);
    }
    select(inside[0].properties.ref, inside.map(f=>f.properties.ref));
  } else {
    let best=null,bd=Infinity;
    for(const z of index){
      const zlat = z.lat ?? (z.bbox ? (z.bbox[1]+z.bbox[3])/2 : null);
      const zlon = z.lon ?? (z.bbox ? (z.bbox[0]+z.bbox[2])/2 : null);
      if(zlat==null || zlon==null) continue;
      const d=haversine(lat,lon,zlat,zlon);
      if(d<bd){bd=d;best=z;}
    }
    if(!best){ showStatus('out', t('gps.outside'), ''); return; }
    // For a reference without a boundary there is no boundary to measure a
    // distance to; then the distance to the point is the most honest answer we
    // have.
    const f = zones.features.find(x=>x.properties.ref===best.ref);
    const edge = f ? distanceToZone(lat,lon,f) : bd;
    const dist = edge>1500 ? (edge/1000).toFixed(1)+' km' : Math.round(edge)+' m';
    showStatus('out', t('gps.outside'),
      `${t('gps.nearest')}: ${best.ref} ${best.name} — ${dist}${f?'':' ('+t('zone.nopoly')+')'}.`);
  }
}
function showStatus(kind,t1,t2){
  const el=$('status');
  el.className='status show '+kind;
  $('stT1').textContent=t1; $('stT2').textContent=t2;
}
/* Every message has to be dismissable — it sits over the map. */
function hideStatus(){ $('status').className='status'; }
$('stClose').onclick = hideStatus;
const marker = new maplibregl.Marker({color:'#1b4332'});

/* our own locate button, down at the bottom with the zoom buttons */
class LocateControl{
  onAdd(){ const d=document.createElement('div');
    d.className='maplibregl-ctrl maplibregl-ctrl-group';
    d.innerHTML='<button type="button" title="Waar sta ik?" style="font-size:15px">◎</button>';
    d.onclick=()=>locate(); return d; }
  onRemove(){}
}
map.addControl(new LocateControl(),'bottom-right');

/* Esc closes everything */
addEventListener('keydown', e=>{ if(e.key==='Escape'){ toggle(null); closeSheet(); $('closeSpot').onclick(); }});
