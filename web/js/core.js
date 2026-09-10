/* ------------------------------------------------------------------ *
 * Diana — map layer. Steps 2 + 3 of the technical plan.
 * All client-side: no server, no API key, no tracking.
 * ------------------------------------------------------------------ */

const STYLE_URL = s => `https://tiles.openfreemap.org/styles/${s}`;
const $ = id => document.getElementById(id);

/* Version of the app itself. Shown on the splash screen and in Settings, so that
   a report along the lines of "it's behaving oddly" can be tied to a version. */
const APP_VERSION = '1.7.0';
/* Filled in at publish time by build/site.sh: the short commit hash and the date
   of that build. If the placeholder is still there, you are running a copy that
   never went through the build step — locally, or straight out of the repo.
   That is exactly what you want to know when someone reports a problem. */
const BUILD = '__DIANA_BUILD__';
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

/* Storage on this device. Sits up here at the top because the language choice,
   the settings and the install screen all three need it — a const further down
   the file is not reachable yet by the time that code runs. */
const remember = (k,v) => { try{ localStorage.setItem('diana.'+k, v==null?'':String(v)); }catch{} };
const recall   = k => { try{ return localStorage.getItem('diana.'+k) || ''; }catch{ return ''; } };

