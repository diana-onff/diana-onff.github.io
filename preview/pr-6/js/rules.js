/* ================================================================== *
 * Screen 6 — rules and band plan
 * Frequencies from the WWFF Global Rules §14.7 (not 7130/14262!).
 * ================================================================== */
/* IARU Region 1 HF band plan, per mode. Not the whole band as one block: where
   you may talk and where you may not is exactly what you need out in the field.
   ft8 = the FT8 frequency used worldwide; wwff = the WWFF preference. */
const BANDS = [
  {n:'80m', lo:3500,  hi:3800,  ft8:3573,  wwff:{ssb:3744, cw:3544},
   seg:[['CW',3500,3570],['Digi',3570,3600],['SSB',3600,3800]]},
  {n:'40m', lo:7000,  hi:7200,  ft8:7074,  wwff:{ssb:7144, cw:7024},
   seg:[['CW',7000,7040],['Digi',7040,7050],['SSB',7050,7200]]},
  {n:'30m', lo:10100, hi:10150, ft8:10136, wwff:{cw:10124},
   seg:[['CW',10100,10130],['Digi',10130,10150]]},
  {n:'20m', lo:14000, hi:14350, ft8:14074, wwff:{ssb:14244, cw:14044},
   seg:[['CW',14000,14070],['Digi',14070,14099],['SSB',14101,14350]]},
  {n:'17m', lo:18068, hi:18168, ft8:18100, wwff:{ssb:18144, cw:18084},
   seg:[['CW',18068,18095],['Digi',18095,18109],['SSB',18111,18168]]},
  {n:'15m', lo:21000, hi:21450, ft8:21074, wwff:{ssb:21244, cw:21044},
   seg:[['CW',21000,21070],['Digi',21070,21110],['SSB',21151,21450]]},
  {n:'12m', lo:24890, hi:24990, ft8:24915, wwff:{ssb:24944, cw:24894},
   seg:[['CW',24890,24915],['Digi',24915,24929],['SSB',24931,24990]]},
  {n:'10m', lo:28000, hi:29700, ft8:28074, wwff:{ssb:28444, cw:28044},
   seg:[['CW',28000,28070],['Digi',28070,28190],['SSB',28225,29200],['FM',29200,29700]]},
];
const SEG_COLOR = {CW:'#1b4332', Digi:'#2d6a4f', SSB:'#52b788', FM:'#a7d7bd'};
const mhz = k => (k/1000).toFixed(3);

const RULES = ['qso','dur','bound','call','proof','log'];
function renderRules(){
  $('rulesBody').innerHTML =
    `<tr><td></td><td><b>WWFF</b> · <b>ONFF</b></td></tr>` +
    RULES.map(k=>`<tr><td>${t('rules.'+k)}</td><td>${t('rules.w.'+k)} · <b>${t('rules.o.'+k)}</b></td></tr>`).join('');
  $('bandBox').innerHTML = BANDS.map(b => {
    const span = b.hi - b.lo;
    const bar = b.seg.map(([m,lo,hi]) =>
      `<span class="sg" style="left:${(lo-b.lo)/span*100}%;width:${(hi-lo)/span*100}%;background:${SEG_COLOR[m]}"
             title="${m} ${mhz(lo)}–${mhz(hi)}"></span>`).join('');
    const marks = [
      b.wwff.ssb && `<span class="mk mkw" style="left:${(b.wwff.ssb-b.lo)/span*100}%" title="WWFF SSB"></span>`,
      b.wwff.cw  && `<span class="mk mkw" style="left:${(b.wwff.cw-b.lo)/span*100}%" title="WWFF CW"></span>`,
      b.ft8      && `<span class="mk ft8"  style="left:${(b.ft8-b.lo)/span*100}%" title="FT8"></span>`,
    ].filter(Boolean).join('');
    const rows = b.seg.map(([m,lo,hi]) =>
      `<div class="sgrow"><span class="dot" style="background:${SEG_COLOR[m]}"></span>
        <span class="m">${m}</span><span class="r">${mhz(lo)} – ${mhz(hi)} MHz</span></div>`).join('');
    const wwff = [b.wwff.ssb && `SSB ${mhz(b.wwff.ssb)}`, b.wwff.cw && `CW ${mhz(b.wwff.cw)}`]
                 .filter(Boolean).join(' · ');
    return `<div class="band">
      <div class="bh"><span class="bn">${b.n}</span><span class="br">${mhz(b.lo)} – ${mhz(b.hi)} MHz</span></div>
      <div class="bar">${bar}${marks}</div>
      <div class="sgrows">${rows}</div>
      <div class="wwff">${t('rules.pref')}: ${wwff} &nbsp;·&nbsp; FT8 ${mhz(b.ft8)}</div>
    </div>`;
  }).join('');
}


