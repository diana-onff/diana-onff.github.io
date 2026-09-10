/* ================================================================== *
 * Screen 7 — activation heatmap from the ONFF status sheet
 * ================================================================== */
const SHEET = '1MFZzdq6xJtpvTtOHfRob6Pvxeo2_5YOQSHjVE0wAyac';
const sheetURL = tab => `https://docs.google.com/spreadsheets/d/${SHEET}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(tab)}`;
let heat = null, heatLoaded = false, heatOnMap = false, heatSource = null;

function parseCSV(text){
  const rows=[]; let row=[], cell='', q=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(q){ if(c==='"'){ if(text[i+1]==='"'){cell+='"';i++;} else q=false; } else cell+=c; }
    else if(c==='"') q=true;
    else if(c===','){ row.push(cell); cell=''; }
    else if(c==='\n'){ row.push(cell); rows.push(row); row=[]; cell=''; }
    else if(c!=='\r') cell+=c;
  }
  if(cell||row.length){ row.push(cell); rows.push(row); }
  return rows;
}

async function loadHeat(){
  if(heatLoaded) return;
  const years = []; const now = new Date().getFullYear();
  for(let y=now; y>=now-6; y--) years.push(String(y));
  try{
    const texts = await Promise.all(years.map(y=>
      fetch(sheetURL(y),{cache:'no-store'}).then(r=>r.ok?r.text():'').catch(()=>'')));
    const last = {};   // ref -> {date, qso, count}
    texts.forEach(txt=>{
      if(!txt) return;
      const rows = parseCSV(txt);
      const head = rows[0]||[];
      const iDate = head.findIndex(h=>/activity date/i.test(h));
      const iQso  = head.findIndex(h=>/qso/i.test(h));
      const iRef  = head.findIndex(h=>/onff ref/i.test(h));
      if(iDate<0||iRef<0) return;
      for(const r of rows.slice(1)){
        const ref=(r[iRef]||'').trim(); if(!/^ONFF-\d+/.test(ref)) continue;
        const d = r[iDate]; const qso = parseInt(r[iQso]||'0',10)||0;
        const e = last[ref] || (last[ref]={date:null,qso:0,count:0});
        e.qso += qso; e.count++;
        if(!e.date || d > e.date) e.date = d;
      }
    });
    if(!Object.keys(last).length) throw new Error('geen rijen uit de sheet');
    heat = last; heatLoaded = true; heatSource = 'sheet';
    paintHeat();
  }catch(err){
    // Of all the sources the sheet is the most fragile: a published
    // spreadsheet, not an API. If it fails, then since the WWFF directory there
    // is a second route — number of QSOs and last activation per reference,
    // built along with the last release. Coarser (no years), but it works
    // offline and without third parties.
    const fell = await heatFromActivity();
    if(fell){ paintHeat(); return; }
    $('heatBox').innerHTML = `<p class="hint" style="color:#b45309">${
      (err instanceof TypeError)
        ? t('heat.cors')
        : t('heat.fail')+' '+err.message}</p>`;
  }
}

/* Falls back to data/onff-activity.json, built from the WWFF directory. */
async function heatFromActivity(){
  try{
    const doc = await fetchFirst(['./data/onff-activity.json','../data/onff-activity.json']);
    const out = {};
    const thisYear = new Date().getFullYear();
    for(const [ref, a] of Object.entries(doc.refs || {})){
      if(!a || (!a.q && !a.last)) continue;
      // The directory contains one impossible date (year 1059, say). Don't take
      // that over blindly: it would colour that area in as "never activated in
      // living memory" when all there is is a typo in the source.
      let date = a.last || null;
      const y = date ? parseInt(date.slice(0,4), 10) : null;
      if(!y || y < 1990 || y > thisYear + 1) date = null;
      if(!date && !a.q) continue;
      out[ref] = {date, qso: a.q || 0, count: a.q ? 1 : 0};
    }
    if(!Object.keys(out).length) return false;
    heat = out; heatLoaded = true; heatSource = 'wwff';
    return true;
  }catch{ return false; }
}

let heatMetric = 'recency';

/* Colour scales. Green = well served, red = wants attention. */
const RECENCY_BUCKETS = [[0.5,'#16a34a'],[1,'#84cc16'],[2,'#facc15'],[4,'#f59e0b']];
const QSO_BUCKETS     = [[10000,'#16a34a'],[2000,'#84cc16'],[500,'#facc15'],[100,'#f59e0b']];

function yearsSince(ref){
  const e = heat && heat[ref];
  if(!e || !e.date) return 99;
  return (Date.now() - new Date(e.date)) / (365.25*24*3600*1000);
}
function qsoTotal(ref){ return (heat && heat[ref] && heat[ref].qso) || 0; }

/* Builds the colour expression for the fill layer. */
function heatExpression(){
  const refs = Object.keys(heat || {});
  const expr = ['case'];
  if(heatMetric === 'recency'){
    for(const [yr,col] of RECENCY_BUCKETS){
      const list = refs.filter(r => yearsSince(r) < yr);
      if(list.length) expr.push(['in',['get','ref'],['literal',list]], col);
    }
  } else {
    for(const [min,col] of QSO_BUCKETS){
      const list = refs.filter(r => qsoTotal(r) >= min);
      if(list.length) expr.push(['in',['get','ref'],['literal',list]], col);
    }
  }
  expr.push('#dc2626');                     // never activated, or very rarely
  return expr.length > 2 ? expr : '#dc2626';
}

function applyHeatPaint(on){
  heatOnMap = !!on;
  if(!map.getLayer('onff-fill')) return;
  map.setPaintProperty('onff-fill','fill-color', on && heat ? heatExpression() : '#2d6a4f');
  map.triggerRepaint();
  map.setPaintProperty('onff-fill','fill-opacity',
    on ? 0.75 : ['interpolate',['linear'],['zoom'],
                 7,  ['case',['boolean',['feature-state','sel'],false],0.42,0.20],
                 12, ['case',['boolean',['feature-state','sel'],false],0.45,0.28]]);
}

function paintHeat(){
  if(!zones || !heat) return;
  const refs = Object.keys(heat);
  const known = zones.features.filter(f => heat[f.properties.ref]);
  const totalQso = refs.reduce((a,r)=>a+qsoTotal(r),0);

  $('heatBox').innerHTML = `
    <div class="srow"><span><b>${known.length}</b> ${t('heat.activated')}</span>
      <span class="r">${zones.features.length - known.length} ${t('heat.never')}</span></div>
    <div class="legend"><span>${heatMetric==='recency'?t('heat.long'):t('heat.few')}</span>
      <span class="ramp"></span>
      <span>${heatMetric==='recency'?t('heat.recent'):t('heat.many')}</span></div>
    ${heatMetric==='qso' ? `<p class="hint">${totalQso.toLocaleString(locale())} ${t('heat.qsototal')}</p>` : ''}
    ${heatSource==='wwff' ? `<p class="hint">${t('heat.viawwff')}</p>` : ''}`;

  applyHeatPaint(true);

  const worst = zones.features
    .map(f => ({ref:f.properties.ref, name:f.properties.name,
                y:yearsSince(f.properties.ref), q:qsoTotal(f.properties.ref)}))
    .sort((a,b) => heatMetric==='recency' ? b.y - a.y : a.q - b.q)
    .slice(0,12);
  $('negList').innerHTML = worst.map(n => {
    const right = heatMetric==='recency'
      ? (n.y > 90 ? t('heat.neveryet') : `${Math.floor(n.y)} ${t('heat.yearsago')}`)
      : `${n.q} QSO${n.q===1?'':"'s"}`;
    return `<div class="neg"><span>${n.ref} · ${n.name}</span><span class="nr">${right}</span></div>`;
  }).join('');
  $('heatNeg').hidden = false;
}

$('heatMetric').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-metric]'); if(!b) return;
  heatMetric = b.dataset.metric;
  [...$('heatMetric').children].forEach(c => c.classList.toggle('on', c===b));
  paintHeat();
});

