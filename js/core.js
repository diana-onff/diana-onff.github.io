/* ------------------------------------------------------------------ *
 * Diana — map layer. Steps 2 + 3 of the technical plan.
 * All client-side: no server, no API key, no tracking.
 * ------------------------------------------------------------------ */

const STYLE_URL = s => `https://tiles.openfreemap.org/styles/${s}`;
const $ = id => document.getElementById(id);

/* Version of the app itself. Shown on the splash screen and in Settings, so that
   a report along the lines of "it's behaving oddly" can be tied to a version. */
const APP_VERSION = '1.19.0';
/* Filled in at publish time by build/site.sh: the short commit hash and the date
   of that build. If the placeholder is still there, you are running a copy that
   never went through the build step — locally, or straight out of the repo.
   That is exactly what you want to know when someone reports a problem. */
const BUILD = 'ea9b167 · 15/09/2026';
const BUILD_TXT = BUILD.startsWith('__') ? 'dev' : BUILD;

/* ---------- splash screen ----------
 * It takes a while for 3.7 MB of zone data to arrive and the map to be drawn.
 * Instead of a white page, Diana shows the drawing with a signal over it, and
 * only leaves once there is genuinely something to see. Two rules around that:
 *   - at least 5 s on screen, even if everything is ready at once — otherwise
 *     the screen flashes past without anyone seeing the logo or the version
 *   - gone after 12 s no matter what, because being stuck on a splash screen is
 *     worse than a bare map with an error message on it
 */
const MIN_SPLASH_MS = 5000;
const splashStart = Date.now();
let splashHidden = false;

function splashStep(pct, key){
  const bar = $('splashBar'), txt = $('splashTxt');
  if(bar) bar.style.width = Math.max(8, Math.min(100, pct)) + '%';
  if(txt && key) txt.textContent = t(key);
}
function splashDone(){
  if(splashHidden) return;
  splashHidden = true;
  const wait = Math.max(0, MIN_SPLASH_MS - (Date.now() - splashStart));
  setTimeout(() => {
    const el = $('splash');
    if(!el) return;
    el.classList.add('gone');
    setTimeout(() => el.remove(), 600);   // out of the DOM as well: saves a layer sitting over the map
  }, wait);
}
setTimeout(splashDone, 12000);

/* Callsign prefix → WWFF programme. Diana uses this for one thing: which
   country the spots filter offers first, so a Dutch operator does not have to
   tap past Belgium every time. One tap changes it, so a guess that misses
   costs nothing — which is why prefixes whose programme is genuinely
   ambiguous are left out rather than guessed at. Every code here was checked
   against data/wwff-programs.json (a test keeps it that way): WWFF lists
   England as GXFF and carries no separate Scottish or Welsh programme, so
   G/M/2E all land there. */
const PREFIX_PROGRAM = {
  ON:'ONFF', OO:'ONFF', OP:'ONFF', OQ:'ONFF', OR:'ONFF', OS:'ONFF', OT:'ONFF',
  PA:'PAFF', PB:'PAFF', PC:'PAFF', PD:'PAFF', PE:'PAFF', PF:'PAFF', PG:'PAFF',
  PH:'PAFF', PI:'PAFF',
  DA:'DLFF', DB:'DLFF', DC:'DLFF', DD:'DLFF', DE:'DLFF', DF:'DLFF', DG:'DLFF',
  DH:'DLFF', DJ:'DLFF', DK:'DLFF', DL:'DLFF', DM:'DLFF', DN:'DLFF', DO:'DLFF',
  DP:'DLFF', DQ:'DLFF', DR:'DLFF',
  F:'FFF', TM:'FFF', TK:'FFF',
  G:'GXFF', M:'GXFF', '2E':'GXFF',
  OZ:'OZFF', OU:'OZFF', '5P':'OZFF', '5Q':'OZFF',
  I:'IFF', IK:'IFF', IZ:'IFF', IW:'IFF', IU:'IFF',
  EA:'EAFF', EB:'EAFF', EC:'EAFF', ED:'EAFF',
  CT:'CTFF', CR:'CTFF',
  SP:'SPFF', SN:'SPFF', SO:'SPFF', SQ:'SPFF', '3Z':'SPFF',
  OK:'OKFF', OL:'OKFF', OM:'OMFF',
  HA:'HAFF', HG:'HAFF',
  SM:'SMFF', SA:'SMFF', SB:'SMFF', SC:'SMFF', SD:'SMFF', SE:'SMFF', SF:'SMFF',
  SG:'SMFF', SH:'SMFF', SI:'SMFF', SJ:'SMFF', SK:'SMFF', SL:'SMFF',
  LA:'LAFF', LB:'LAFF', LG:'LAFF', LN:'LAFF',
  OH:'OHFF', OF:'OHFF', OG:'OHFF',
  OE:'OEFF', HB:'HBFF', LX:'LXFF',
  EI:'EIFF', EJ:'EIFF',
  YO:'YOFF', YP:'YOFF', YQ:'YOFF', YR:'YOFF',
  LZ:'LZFF', S5:'S5FF', '9A':'9AFF',
  YU:'YUFF', YT:'YUFF',
  SV:'SVFF', SW:'SVFF', SX:'SVFF', SY:'SVFF', SZ:'SVFF',
  TA:'TAFF', TB:'TAFF', TC:'TAFF',
  ES:'ESFF', YL:'YLFF', LY:'LYFF', ER:'ERFF',
  UR:'URFF', UT:'URFF', UU:'URFF', UV:'URFF', UW:'URFF', UX:'URFF', UY:'URFF',
  UZ:'URFF', EM:'URFF', EO:'URFF',
  EW:'EWFF', EU:'EWFF', EV:'EWFF',
  Z3:'Z3FF', E7:'E7FF', ZA:'ZAFF', '4O':'4OFF',
  R:'RFF', UA:'RFF', UB:'RFF', UC:'RFF', UD:'RFF', UE:'RFF', UF:'RFF', UG:'RFF',
  UH:'RFF', UI:'RFF',
  K:'KFF', W:'KFF', N:'KFF',
  VE:'VEFF', VA:'VEFF', VO:'VEFF', VY:'VEFF',
  VK:'VKFF', ZL:'ZLFF',
  JA:'JAFF', JE:'JAFF', JF:'JAFF', JG:'JAFF', JH:'JAFF', JI:'JAFF', JJ:'JAFF',
  JK:'JAFF', JL:'JAFF', JM:'JAFF', JN:'JAFF', JO:'JAFF', JP:'JAFF', JQ:'JAFF',
  JR:'JAFF', JS:'JAFF',
};

/* Which programme goes with a callsign, or null. Up here for the same reason
   as the two lines above: loadData() has to decide which country to put in
   memory before settings.js and spots.js have even run. */
function programForCall(call){
  const c = String(call || '').toUpperCase().split('/')[0];
  for(const len of [3,2,1]){
    const p = PREFIX_PROGRAM[c.slice(0,len)];
    if(p) return p;
  }
  return null;
}

/* A WWFF reference is always "<PROGRAMME>-<number>", and the programme itself
   already ends in FF (ONFF, PAFF, VKFF, …), so the part before the first
   hyphen is the programme code — worldwide, with no table needed. Lives here
   because the data loader needs it before spots.js exists. */
const refProgram = r => (typeof r === 'string' ? r.toUpperCase().split('-')[0] : '');

/* Storage on this device. Sits up here at the top because the language choice,
   the settings and the install screen all three need it — a const further down
   the file is not reachable yet by the time that code runs. */
const remember = (k,v) => { try{ localStorage.setItem('diana.'+k, v==null?'':String(v)); }catch{} };
const recall   = k => { try{ return localStorage.getItem('diana.'+k) || ''; }catch{ return ''; } };

