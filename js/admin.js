/* ================================================================== *
 * Admin — sending files to GitHub from within the app itself
 *
 * Everything goes over the GitHub API with a token the administrator fills
 * in themselves. No server of ours is involved.
 *
 * About that token, honestly: what sits in localStorage is readable by
 * anyone who can get at this device and by every script running on this
 * page. That is why "remember" is off unless you tick it, why there is a
 * button to forget it, and why we recommend a fine-grained token that is
 * allowed only this one repository, only contents and pull requests, with
 * a short expiry date.
 * ================================================================== */
const GH = 'https://api.github.com';

const adm = {
  repo:   recall('adm.repo'),                     // public app repo: workflows, data, site
  src:    recall('adm.src'),                      // private source repo: the KMZ files
  branch: recall('adm.branch') || 'main',
  path:   recall('adm.path') || 'incoming/',
  token:  recall('adm.token'),
};

/* Two repositories, one token. If the source field stays empty, everything is
   one repo — that is the setup from before the move, and it has to keep working
   as long as there are still installations configured that way. */
function bronRepo(){ return adm.src || adm.repo; }

/* The admin screen is not visible unless you go looking for it: ?admin=1 in the
   URL, or five taps on the logo. Not security — a threshold. */
function unlockAdmin(){
  document.body.classList.add('admin');
  setTimeout(() => { loadMeta(); toonPr().catch(()=>{}); }, 0);
  $('admRepo').value   = adm.repo;
  $('admSrc').value    = adm.src;
  $('admBranch').value = adm.branch;
  $('admPath').value   = adm.path;
  $('admToken').value  = adm.token;
  $('admRemember').checked = !!adm.token;
  buildEmbed();
  hervatUpload().catch(()=>{});
}
if(new URLSearchParams(location.search).get('admin') === '1' || recall('adm.repo')) unlockAdmin();
(function(){
  let taps = 0, timer = null;
  document.querySelector('.brand').addEventListener('click', () => {
    clearTimeout(timer); timer = setTimeout(() => taps = 0, 2500);
    if(++taps >= 5){ taps = 0; unlockAdmin(); showStatus('in', t('adm.unlocked'), ''); }
  });
})();

const kaal = v => v.trim().replace(/^https?:\/\/github\.com\//,'').replace(/\.git$/,'').replace(/\/$/,'');
['admRepo','admSrc','admBranch','admPath'].forEach(id => $(id).addEventListener('input', () => {
  adm.repo   = kaal($('admRepo').value);
  adm.src    = kaal($('admSrc').value);
  adm.branch = $('admBranch').value.trim() || 'main';
  adm.path   = $('admPath').value.trim() || 'incoming/';
  remember('adm.repo', adm.repo); remember('adm.src', adm.src);
  remember('adm.branch', adm.branch); remember('adm.path', adm.path);
  buildEmbed();
}));
$('admToken').addEventListener('input', () => {
  adm.token = $('admToken').value.trim();
  if($('admRemember').checked) remember('adm.token', adm.token);
});
$('admRemember').addEventListener('change', e => {
  if(e.target.checked) remember('adm.token', adm.token);
  else { try{ localStorage.removeItem('diana.adm.token'); }catch{} }
});

async function gh(path, opts){
  const r = await fetch(GH + path, {
    ...opts,
    headers: {
      'Accept':'application/vnd.github+json',
      'X-GitHub-Api-Version':'2022-11-28',
      'Authorization':'Bearer ' + adm.token,
      ...(opts && opts.body ? {'Content-Type':'application/json'} : {}),
      ...(opts && opts.headers || {}),
    }
  });
  const text = await r.text();
  let data = null; try{ data = text ? JSON.parse(text) : null; }catch{}
  if(!r.ok){
    const msg = (data && data.message) || `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

/* Same call, but the file itself instead of the JSON description of it. Only for
   small text files: the contents API refuses anything over one megabyte. */
async function ghRuw(path){
  const r = await fetch(GH + path, {headers:{
    'Accept':'application/vnd.github.raw',
    'X-GitHub-Api-Version':'2022-11-28',
    'Authorization':'Bearer ' + adm.token,
  }});
  if(!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.text();
}

$('admTest').onclick = async () => {
  const fb = $('admFb');
  if(!adm.repo || !adm.token){ fb.textContent = t('adm.needboth'); fb.className='fb bad'; return; }
  fb.textContent = t('adm.testing'); fb.className = 'fb';
  try{
    // Check both repositories, not just the first: a token that is allowed the
    // public repo but not the private one otherwise only fails halfway through
    // a twenty-megabyte upload.
    const uit = [];
    let alles = true;
    for(const naam of [adm.repo, ...(adm.src && adm.src !== adm.repo ? [adm.src] : [])]){
      const repo = await gh(`/repos/${naam}`);
      const ref  = await gh(`/repos/${naam}/git/ref/heads/${adm.branch}`);
      const can  = repo.permissions && (repo.permissions.push || repo.permissions.admin);
      if(!can) alles = false;
      uit.push(`${can ? '✓' : '⚠'} ${repo.full_name} · ${adm.branch} @ ${ref.object.sha.slice(0,7)}`);
    }
    fb.innerHTML = uit.join('<br>') + (alles ? '' : `<br>⚠ ${t('adm.noperm')}`);
    fb.className = 'fb ' + (alles ? 'good' : 'bad');
    $('admSend').disabled = !($('admFile').files && $('admFile').files.length);
  }catch(err){
    fb.textContent = '✗ ' + err.message; fb.className = 'fb bad';
    $('admSend').disabled = true;
  }
};

$('admFile').addEventListener('change', () => {
  $('admSend').disabled = !($('admFile').files.length && adm.repo && adm.token);
});

/* Large files to base64 in chunks — done in one go, the call stack overflows. */
function toBase64(buf){
  const bytes = new Uint8Array(buf);
  let bin = '';
  const CH = 0x8000;
  for(let i=0;i<bytes.length;i+=CH) bin += String.fromCharCode.apply(null, bytes.subarray(i, i+CH));
  return btoa(bin);
}

const STEPS = ['adm.s1','adm.s2','adm.s3','adm.s4','adm.s5','adm.s6','adm.s7','adm.s8','adm.s9'];
function drawSteps(at, err, toelichting){
  $('admSteps').hidden = false;
  $('admSteps').innerHTML = STEPS.map((k,i) => {
    const cls = err && i===at ? 'err' : i < at ? 'done' : i === at ? 'now' : '';
    const mk  = err && i===at ? '✗' : i < at ? '✓' : i === at ? '…' : '·';
    const bij = (!err && i === at && toelichting) ? ` <span class="hint">— ${toelichting}</span>` : '';
    return `<div class="step ${cls}"><span class="mk">${mk}</span><span>${t(k)}${bij}</span></div>`;
  }).join('') + (err ? `<div class="step err"><span class="mk">!</span><span>${err}</span></div>` : '');
}

/* The upload in short:
 *
 *   1-6  the KMZ lands in incoming/ on main of the SOURCE repo. A waiting room,
 *        not a source: the nightly build never looks in there, so a file that
 *        ends up here can never get published of its own accord.
 *   7    start the conversion in the APP repo, with a branch name as the order.
 *   8    wait until that branch exists — that is the sign the build is done.
 *   9    turn it into a pull request.
 *
 * Why the app opens that pull request and not the workflow: a pull request
 * created with the built-in GITHUB_TOKEN starts no workflows. The preview would
 * then never be built. With the administrator's token it is.
 */
const WACHT_MAX = 40;      // 40 × 6 s = four minutes before we give up
const WACHT_MS  = 6000;

function bewaarBezig(gegevens){ remember('adm.bezig', gegevens ? JSON.stringify(gegevens) : ''); }
function huidigBezig(){ try{ return JSON.parse(recall('adm.bezig') || 'null'); }catch{ return null; } }

const slaap = ms => new Promise(r => setTimeout(r, ms));

/* Waits until the build has put its branch down. The workflow commits empty if
   it has to, precisely so that this branch always appears — otherwise "no
   changes" would be indistinguishable here from "build failed". */
async function wachtOpBranch(branch, vanaf){
  for(let poging = vanaf || 0; poging < WACHT_MAX; poging++){
    try{
      await gh(`/repos/${adm.repo}/git/ref/heads/${branch}`);
      return true;
    }catch{}
    drawSteps(7, null, `${t('adm.building')} (${poging + 1}/${WACHT_MAX})`);
    await slaap(WACHT_MS);
  }
  return false;
}

async function opentPr(branch, bestand){
  let rapport = '';
  try{
    rapport = await ghRuw(`/repos/${adm.repo}/contents/report.md?ref=${encodeURIComponent(branch)}`);
  }catch{}
  return gh(`/repos/${adm.repo}/pulls`, {
    method:'POST', body: JSON.stringify({
      title:`Nieuwe ONFF-release: ${bestand}`, head: branch, base: adm.branch,
      body:`Omgezet uit \`incoming/${bestand}\` in de bron-repo, gestart vanuit het beheerscherm van Diana.\n\n`
         + `Kijk naar de preview vóór je merget. Publiceer je, dan verhuist het bronbestand van \`incoming/\` naar \`source/\`.\n\n`
         + (rapport ? `---\n\n${rapport}` : '')})});
}

$('admSend').onclick = async () => {
  const file = $('admFile').files[0];
  if(!file) return;
  $('admSend').disabled = true;
  const bron   = bronRepo();
  const path   = (adm.path.replace(/^\/|\/$/g,'') + '/' + file.name).replace(/^\//,'');
  const stamp  = new Date().toISOString().slice(0,16).replace(/[-:T]/g,'');
  const branch = `diana-data-${stamp}`;
  let step = 0;
  try{
    drawSteps(step);                                            // 1 fetch the base
    const ref = await gh(`/repos/${bron}/git/ref/heads/${adm.branch}`);
    const baseSha = ref.object.sha;

    drawSteps(++step);                                          // 2 read the file in
    const b64 = toBase64(await file.arrayBuffer());

    drawSteps(++step);                                          // 3 blob
    const blob = await gh(`/repos/${bron}/git/blobs`, {
      method:'POST', body: JSON.stringify({content:b64, encoding:'base64'})});

    drawSteps(++step);                                          // 4 tree
    const baseCommit = await gh(`/repos/${bron}/git/commits/${baseSha}`);
    const tree = await gh(`/repos/${bron}/git/trees`, {
      method:'POST', body: JSON.stringify({base_tree: baseCommit.tree.sha,
        tree:[{path, mode:'100644', type:'blob', sha: blob.sha}]})});

    drawSteps(++step);                                          // 5 commit
    const commit = await gh(`/repos/${bron}/git/commits`, {
      method:'POST', body: JSON.stringify({
        message:`bron: ${file.name} in de wachtruimte gezet via Diana`,
        tree: tree.sha, parents:[baseSha]})});

    drawSteps(++step);                                          // 6 update the waiting room
    await gh(`/repos/${bron}/git/refs/heads/${adm.branch}`, {
      method:'PATCH', body: JSON.stringify({sha: commit.sha})});

    drawSteps(++step);                                          // 7 start the conversion
    await gh(`/repos/${adm.repo}/actions/workflows/build-data.yml/dispatches`, {
      method:'POST', body: JSON.stringify({ref: adm.branch, inputs:{branch}})});
    // From here on there is work under way that outlives the app. Anyone who
    // closes the app while the build is running finds it again on the next
    // opening via hervatUpload().
    bewaarBezig({branch, file: file.name, at: new Date().toISOString()});

    drawSteps(++step);                                          // 8 wait for the branch
    const er = await wachtOpBranch(branch);
    if(!er){ drawSteps(7, t('adm.buildslow')); showStatus('out', t('adm.failed'), t('adm.buildslow')); return; }

    drawSteps(++step);                                          // 9 pull request
    const pr = await opentPr(branch, file.name);

    drawSteps(STEPS.length);
    bewaarBezig(null);
    $('admSteps').innerHTML += `<div class="step done"><span class="mk">→</span>
      <a href="${pr.html_url}" target="_blank" rel="noopener">${t('adm.openpr')} #${pr.number}</a></div>`;
    showStatus('in', t('adm.done'), `#${pr.number} · ${file.name}`);
    bewaarPr(pr, file.name);
    toonPr().catch(()=>{});
  }catch(err){
    drawSteps(step, err.message);
    showStatus('out', t('adm.failed'), err.message);
  }finally{
    $('admSend').disabled = false;
  }
};

/* If you closed the app while the conversion was running, this picks up the
   thread again: the branch does exist by now, only the pull request was never
   made out of it. */
async function hervatUpload(){
  const bezig = huidigBezig();
  if(!bezig || !adm.repo || !adm.token) return;
  if(huidigePr()){ bewaarBezig(null); return; }   // there is already a pull request
  try{
    // Maybe there is already a pull request for this branch — then just pick it up.
    const bestaand = await gh(`/repos/${adm.repo}/pulls?state=open&head=${adm.repo.split('/')[0]}:${encodeURIComponent(bezig.branch)}`);
    if(bestaand && bestaand.length){
      bewaarPr(bestaand[0], bezig.file); bewaarBezig(null);
      showStatus('in', t('adm.resumed'), `#${bestaand[0].number}`);
      toonPr().catch(()=>{});
      return;
    }
    await gh(`/repos/${adm.repo}/git/ref/heads/${bezig.branch}`);   // does the branch exist yet?
    const pr = await opentPr(bezig.branch, bezig.file);
    bewaarPr(pr, bezig.file); bewaarBezig(null);
    showStatus('in', t('adm.resumed'), `#${pr.number}`);
    toonPr().catch(()=>{});
  }catch{
    // Branch does not exist yet: the build is probably still running. Leave it
    // be, opening the app next time will try again.
  }
}

/* ================================================================== *
 * Following up the outstanding upload — without going to github.com
 *
 * After an upload the pull request is the only thing still standing between
 * you and the live site. Everything you need for that is here: are the
 * workflows still running, where is the preview, what does the diff report
 * say, and the two buttons that finish it off. The pull request is kept in
 * localStorage, so you are allowed to close the app in between.
 * ================================================================== */
let prPoll = null;

function bewaarPr(pr, bestand){
  const gegevens = pr ? JSON.stringify({
    number: pr.number, branch: pr.head.ref, url: pr.html_url,
    file: bestand || '', at: new Date().toISOString()
  }) : '';
  remember('adm.pr', gegevens);
}
function huidigePr(){
  try{ return JSON.parse(recall('adm.pr') || 'null'); }catch{ return null; }
}
function stopPrPoll(){ if(prPoll){ clearInterval(prPoll); prPoll = null; } }

function previewUrl(nummer){
  // pages.yml always publishes previews on this same pattern. Mind the
  // exception: a repo named exactly <owner>.github.io sits at the root of the
  // domain and not in a subfolder. Without this rule the preview link becomes
  // .../diana-onff.github.io/preview/pr-3/ and that is a 404. The same rule
  // lives in build/paginabasis.sh — change one, change both.
  const [eigenaar, repo] = (adm.repo || '').split('/');
  if(!eigenaar || !repo) return null;
  const e = eigenaar.toLowerCase();
  const basis = repo.toLowerCase() === `${e}.github.io`
    ? `https://${e}.github.io`
    : `https://${e}.github.io/${repo}`;
  return `${basis}/preview/pr-${nummer}/`;
}

async function toonPr(){
  // Independent of everything below: whatever is still sitting in the waiting
  // room, tracked pull request or not, gets its own chance to be cleaned up.
  renderCleanup().catch(()=>{});

  const opgeslagen = huidigePr();
  const card = $('admPrCard');
  if(!opgeslagen || !adm.repo || !adm.token){ card.hidden = true; stopPrPoll(); return; }
  card.hidden = false;

  let pr;
  try{
    pr = await gh(`/repos/${adm.repo}/pulls/${opgeslagen.number}`);
  }catch{
    $('admPrHead').textContent = t('adm.prgone');
    $('admPrHead').className = 'fb bad';
    bewaarPr(null); stopPrPoll();
    return;
  }

  // Already merged or closed while the app was shut: then there is nothing left
  // to follow up and the card disappears by itself.
  if(pr.state !== 'open'){
    // Handled outside the app — on github.com, or on another device. In that
    // case the source file has not moved from its place yet; that happens here
    // after all, so the waiting room doesn't quietly stay full.
    let bijschrift = '';
    let verplaatst = true;
    try{
      if(await verplaatsBron(opgeslagen.file, !!pr.merged)){
        bijschrift = ' · ' + t(pr.merged ? 'adm.promoted' : 'adm.discarded');
      }
    }catch{
      verplaatst = false;
      bijschrift = ' · ' + t('adm.promotefail');
    }
    $('admPrHead').textContent = (pr.merged ? t('adm.prmerged') : t('adm.prclosed')) + bijschrift;
    $('admPrHead').className = 'fb ' + (verplaatst ? 'good' : 'bad');
    $('admPrMerge').disabled = true;
    stopPrPoll();
    if(verplaatst){
      // Nothing left to retry — the bookkeeping can go.
      $('admPrChecks').innerHTML = '';
      bewaarPr(null); bewaarBezig(null);
    } else {
      // The file is still in incoming/. Keep the record so a refresh — this
      // button, or the cleanup list below — tries the move again instead of
      // forcing a trip to github.com.
      $('admPrChecks').innerHTML =
        `<button class="btn ghost" id="admPrRetryMove">${t('adm.retry')}</button>`;
      $('admPrRetryMove').onclick = () => toonPr().catch(()=>{});
    }
    return;
  }

  const sha = pr.head.sha;
  let runs = [];
  try{
    const r = await gh(`/repos/${adm.repo}/actions/runs?head_sha=${sha}&per_page=20`);
    runs = r.workflow_runs || [];
  }catch{}

  // Per workflow only the newest run: a second push to the same branch leaves
  // the old run standing, and that says nothing about the current state anymore.
  const nieuwste = new Map();
  for(const run of runs) if(!nieuwste.has(run.name)) nieuwste.set(run.name, run);
  const lijst = [...nieuwste.values()];

  const bezig    = lijst.some(r => r.status !== 'completed');
  const mislukt  = lijst.some(r => r.status === 'completed' && r.conclusion !== 'success' && r.conclusion !== 'skipped');
  const klaar    = lijst.length > 0 && !bezig && !mislukt;

  $('admPrHead').innerHTML =
    `#${pr.number} · <a href="${pr.html_url}" target="_blank" rel="noopener">${pr.title}</a>`;
  $('admPrHead').className = 'fb';

  $('admPrChecks').innerHTML = lijst.length
    ? lijst.map(r => {
        const cls = r.status !== 'completed' ? 'now'
                  : (r.conclusion === 'success' || r.conclusion === 'skipped') ? 'done' : 'err';
        const mk  = r.status !== 'completed' ? '…'
                  : (r.conclusion === 'success' || r.conclusion === 'skipped') ? '✓' : '✗';
        return `<div class="step ${cls}"><span class="mk">${mk}</span><span>${r.name}</span></div>`;
      }).join('')
    : `<div class="step now"><span class="mk">…</span><span>${t('adm.prwaiting')}</span></div>`;

  const url = previewUrl(pr.number);
  $('admPrPreview').innerHTML = (klaar && url)
    ? `<a href="${url}" target="_blank" rel="noopener">🗺️ ${t('adm.prpreview')}</a>`
    : `<span class="hint">${bezig ? t('adm.prwaiting') : mislukt ? t('adm.prfailed') : ''}</span>`;

  // The diff report. For an upload out of the waiting room it sits in the body
  // of the pull request itself; for a pull request someone opened by hand, the
  // workflow sticks it underneath as a comment. Show both.
  const schoon = s => s
    .replace('<!-- diana-datarapport -->','')
    .replace(/<\/?(details|summary|sub)>/g,'')
    .replace(/\*\*/g,'')
    .trim();
  try{
    const box = $('admPrReport');
    let tekst = '';
    const opmerkingen = await gh(`/repos/${adm.repo}/issues/${pr.number}/comments`);
    const rapport = (opmerkingen || []).filter(c => (c.body||'').startsWith('<!-- diana-datarapport -->')).pop();
    if(rapport) tekst = schoon(rapport.body);
    else if(pr.body && pr.body.includes('---')) tekst = schoon(pr.body.split('---').slice(1).join('---'));
    box.hidden = false;
    box.textContent = tekst || t('adm.prnoreport');
  }catch{}

  // Publishing is only allowed once everything is green. Merging while the build
  // is still running is exactly the mistake the preview exists to prevent.
  $('admPrMerge').disabled = !klaar;

  stopPrPoll();
  if(bezig) prPoll = setInterval(() => { toonPr().catch(()=>{}); }, 15000);
}

$('admPrRefresh').onclick = () => toonPr().catch(err => showStatus('out', err.message, ''));

/* ---------- clearing out the waiting room ----------
 *
 * After your decision the source file still has to move: on publish from
 * incoming/ to source/, on reject into the bin. That happens here, in the app,
 * with your own token — and not in a workflow. That saves a second write token
 * in the public repo, and that token is exactly the thing you would rather not
 * have sitting there.
 *
 * The file itself does not travel along: git already knows it by its hash, so we
 * only write a new tree pointing at that same hash. Moving twenty megabytes thus
 * costs a mere handful of small calls.
 *
 * The price of this choice: close the app right after publishing and the file
 * stays put in incoming/. Annoying, not dangerous — the nightly build never
 * looks there. The next upload or clean-up puts it right.
 */
async function verplaatsBron(bestand, naarSource){
  if(!bestand) return false;
  const bron = bronRepo();
  const vanaf = `${adm.path.replace(/^\/|\/$/g,'')}/${bestand}`;
  const naar  = `source/${bestand}`;

  const ref  = await gh(`/repos/${bron}/git/ref/heads/${adm.branch}`);
  const base = ref.object.sha;
  const baseCommit = await gh(`/repos/${bron}/git/commits/${base}`);
  const boom = await gh(`/repos/${bron}/git/trees/${baseCommit.tree.sha}?recursive=1`);
  const item = (boom.tree || []).find(x => x.path === vanaf);
  if(!item) return false;                      // already cleared out, nothing to do

  const wijzigingen = [{path: vanaf, mode:'100644', type:'blob', sha: null}];
  if(naarSource) wijzigingen.unshift({path: naar, mode:'100644', type:'blob', sha: item.sha});

  const tree = await gh(`/repos/${bron}/git/trees`, {
    method:'POST', body: JSON.stringify({base_tree: baseCommit.tree.sha, tree: wijzigingen})});
  const commit = await gh(`/repos/${bron}/git/commits`, {
    method:'POST', body: JSON.stringify({
      message: naarSource
        ? `bron: ${bestand} goedgekeurd en naar source/ verplaatst`
        : `bron: ${bestand} afgewezen en uit de wachtruimte verwijderd`,
      tree: tree.sha, parents:[base]})});
  await gh(`/repos/${bron}/git/refs/heads/${adm.branch}`, {
    method:'PATCH', body: JSON.stringify({sha: commit.sha})});
  return true;
}

/* ---------- cleaning up the waiting room by hand ----------
 *
 * Independent of any pull request the app happens to be tracking: a merge or
 * a close done on github.com, a move that failed halfway, a second device —
 * all of those leave incoming/ as the only place that still remembers what
 * is unfinished. This lists it directly from the source repo and lets you
 * finish the job without one of those specific situations having to apply.
 */
async function lijstWachtruimte(){
  const bron = bronRepo();
  const pad  = adm.path.replace(/^\/|\/$/g,'');
  if(!bron || !adm.token || !pad) return [];
  try{
    const items = await gh(`/repos/${bron}/contents/${pad}?ref=${encodeURIComponent(adm.branch)}`);
    return (Array.isArray(items) ? items : []).filter(x => x.type === 'file' && /\.kmz$/i.test(x.name));
  }catch{
    return [];   // no incoming/ yet, or nothing readable — same as "nothing to clean up"
  }
}

async function renderCleanup(){
  const card = $('admCleanupCard');
  if(!bronRepo() || !adm.token){ card.hidden = true; return; }
  const bestanden = await lijstWachtruimte();
  card.hidden = false;
  $('admCleanupList').innerHTML = bestanden.length ? bestanden.map(b => `
    <div style="margin:10px 0;padding:10px;border:1px solid var(--line);border-radius:10px">
      <div style="font-weight:650;margin-bottom:8px;word-break:break-all">${b.name}</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn ghost" data-promote="${b.name}">${t('adm.cleanuppromote')}</button>
        <button class="btn ghost" data-discard="${b.name}">${t('adm.cleanupdiscard')}</button>
      </div>
    </div>`).join('') : `<p class="hint">${t('adm.cleanupempty')}</p>`;
}

$('admCleanupList').addEventListener('click', async (e) => {
  const knop = e.target.closest('[data-promote], [data-discard]');
  if(!knop) return;
  const naarSource = knop.hasAttribute('data-promote');
  const bestand = knop.getAttribute(naarSource ? 'data-promote' : 'data-discard');
  if(!naarSource && !confirm(t('adm.cleanupconfirm'))) return;
  knop.closest('div[style]').querySelectorAll('button').forEach(b => b.disabled = true);
  try{
    await verplaatsBron(bestand, naarSource);
    showStatus('in', t(naarSource ? 'adm.promoted' : 'adm.discarded'), bestand);
  }catch(err){
    showStatus('out', t('adm.failed'), err.message);
  }finally{
    renderCleanup().catch(()=>{});
  }
});

$('admCleanupRefresh').onclick = () => renderCleanup().catch(err => showStatus('out', err.message, ''));

$('admPrMerge').onclick = async () => {
  const opgeslagen = huidigePr();
  if(!opgeslagen) return;
  $('admPrMerge').disabled = true;
  try{
    await gh(`/repos/${adm.repo}/pulls/${opgeslagen.number}/merge`, {
      method:'PUT',
      body: JSON.stringify({merge_method:'merge',
        commit_title:`Nieuwe bronrelease samengevoegd via Diana (#${opgeslagen.number})`})});
    // Cleaning up the branch is allowed to fail — the merge is what counts.
    try{ await gh(`/repos/${adm.repo}/git/refs/heads/${opgeslagen.branch}`, {method:'DELETE'}); }catch{}

    // Only now is the source file promoted. The order is deliberate: first the
    // data is live, only then does the file get to be called a source. The other
    // way round, a failed merge would leave a KMZ in source/ that was never
    // published.
    let bijschrift = `#${opgeslagen.number}`;
    try{
      if(await verplaatsBron(opgeslagen.file, true)) bijschrift += ` · ${t('adm.promoted')}`;
      showStatus('in', t('adm.prmerged'), bijschrift);
      bewaarPr(null); bewaarBezig(null); stopPrPoll();
      $('admPrCard').hidden = true;
    }catch(err){
      // The merge is done and cannot be undone — only the move failed. Leave
      // the bookkeeping in place: a refresh now finds an already-merged pull
      // request and simply tries the move again, exactly as if the merge had
      // happened outside the app.
      showStatus('out', t('adm.promotefail'), err.message);
      toonPr().catch(()=>{});
    }
  }catch(err){
    showStatus('out', t('adm.failed'), err.message);
    $('admPrMerge').disabled = false;
  }
};

$('admPrClose').onclick = async () => {
  const opgeslagen = huidigePr();
  if(!opgeslagen) return;
  if(!confirm(t('adm.prconfirm'))) return;
  try{
    await gh(`/repos/${adm.repo}/pulls/${opgeslagen.number}`, {
      method:'PATCH', body: JSON.stringify({state:'closed'})});
    try{ await gh(`/repos/${adm.repo}/git/refs/heads/${opgeslagen.branch}`, {method:'DELETE'}); }catch{}

    // Rejecting also means: the source file must not be left lying around.
    // Otherwise it is still there a month later and nobody remembers why.
    let bijschrift = `#${opgeslagen.number}`;
    try{
      if(await verplaatsBron(opgeslagen.file, false)) bijschrift += ` · ${t('adm.discarded')}`;
      showStatus('in', t('adm.prclosed'), bijschrift);
      bewaarPr(null); bewaarBezig(null); stopPrPoll();
      $('admPrCard').hidden = true;
    }catch(err){
      // Closed, but the discard itself failed. Same recovery as a failed
      // promotion: keep the record, let a refresh try again.
      showStatus('out', t('adm.promotefail'), err.message);
      toonPr().catch(()=>{});
    }
  }catch(err){
    showStatus('out', t('adm.failed'), err.message);
  }
};

/* ---------- embed code ---------- */
function buildEmbed(){
  const base = location.origin + location.pathname.replace(/[^/]*$/,'');
  const q = ['embed=1'];
  const prov = $('embProv').value.trim(); if(prov) q.push('prov=' + encodeURIComponent(prov));
  const lg   = $('embLang').value.trim(); if(lg)   q.push('lang=' + encodeURIComponent(lg));
  if($('embSpots').checked) q.push('spots=1');
  if($('embWorld').checked) q.push('world=1');
  $('embCode').textContent =
`<iframe src="${base}?${q.join('&')}"
        width="100%" height="600" style="border:0"
        loading="lazy" allow="geolocation"></iframe>`;
}
['embProv','embLang'].forEach(id => $(id).addEventListener('input', buildEmbed));
$('embSpots').addEventListener('change', buildEmbed);
$('embWorld').addEventListener('change', buildEmbed);
$('embCopy').onclick = async () => {
  try{ await navigator.clipboard.writeText($('embCode').textContent);
       showStatus('in', t('adm.copied'), ''); }
  catch{ showStatus('out', t('adm.copyfail'), ''); }
};

