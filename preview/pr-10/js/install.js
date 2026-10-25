/* ================================================================== *
 * Putting Diana on the device
 *
 * Chrome-like browsers hand us `beforeinstallprompt`: we hold on to it and play
 * it back when the user asks for it. Safari on iOS does not give us that — there
 * is no install API there, only Share → Add to Home Screen. So we show, per
 * platform, what is genuinely possible, instead of a button that does nothing.
 * ================================================================== */
let deferredInstall = null;

const isStandalone = () =>
  matchMedia('(display-mode: standalone)').matches ||
  matchMedia('(display-mode: minimal-ui)').matches ||
  navigator.standalone === true;

function platform(){
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) ||
              (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if(ios) return /CriOS|FxiOS|EdgiOS|OPiOS/.test(ua) ? 'iosother' : 'ios';
  if(/Android/.test(ua)) return 'android';
  if(/Firefox\//.test(ua)) return 'firefox';
  if(/Safari\//.test(ua) && !/Chrome|Chromium|Edg\//.test(ua)) return 'safari';
  return 'desktop';
}

function renderInstall(){
  const btn = $('instBtn'), how = $('instHow'), card = $('instCard');
  if(!btn || !card) return;

  if(isStandalone() || recall('installed') === '1'){
    btn.hidden = true;
    how.innerHTML = '✓ ' + t('inst.done');
    return;
  }
  if(deferredInstall){
    btn.hidden = false;
    how.innerHTML = '';        // the browser handles it itself; explanation is just noise then
    return;
  }
  btn.hidden = true;
  how.innerHTML = t('inst.' + platform());
}

function showInstallBar(){
  // Ask once. Anyone who dismisses it never sees it again; Settings stays put.
  if(recall('inst.asked') === '1' || isStandalone()) return;
  if(document.body.classList.contains('embed')) return;
  $('instBar').hidden = false;
}
function hideInstallBar(){ $('instBar').hidden = true; }

addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredInstall = e;
  renderInstall();
  showInstallBar();
});

addEventListener('appinstalled', () => {
  deferredInstall = null;
  remember('installed','1');
  hideInstallBar();
  renderInstall();
});

async function runInstall(){
  if(!deferredInstall){ renderInstall(); return; }
  hideInstallBar();
  remember('inst.asked','1');
  const prompt = deferredInstall;
  deferredInstall = null;                 // a prompt event can only be used once
  try{
    prompt.prompt();
    const { outcome } = await prompt.userChoice;
    if(outcome === 'accepted') remember('installed','1');
    else $('instFb').textContent = t('inst.declined');
  }catch(err){
    console.warn('installeren:', err);
    $('instFb').textContent = t('inst.declined');
  }
  renderInstall();
}

$('instBtn').onclick   = runInstall;
$('instBarGo').onclick = runInstall;
$('instBarNo').onclick = () => { remember('inst.asked','1'); hideInstallBar(); };
renderInstall();


