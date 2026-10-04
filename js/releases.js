/* ---------- What's new: the release overview ----------
 *
 * Opened from Settings ("Wat is er nieuw"), nowhere else: no message after an
 * update, on purpose. Newest version first, a few short lines per version in
 * plain language, and one block for everything before 1.21.0 (the repository's
 * history only goes back to 1.20.0, so the early versions are summed up rather
 * than listed one by one).
 *
 * Written in Dutch and English; every other language shows the English text,
 * so a new version only ever needs these two. The screen's own labels (title,
 * back button) do follow all eight languages.
 *
 * Adding a version: put a new entry at the TOP of RELEASES, with the same
 * number as APP_VERSION in core.js. test_releases.py checks that the newest
 * entry here is the version the app reports.
 */
const RELEASES = [
  { v: '1.30.0', date: '2026-10-04',
    nl: ['Het tabblad Sessie is weg.',
         'Regels heeft twee tabbladen: Regels en Bandplan. Regels toont een selectie uit de officiële WWFF-regels, ook geldig voor ONFF, in alle talen, met een voorbeeld van de juiste naam voor je logbestand.',
         'Veldinfo opent altijd op Gebieden en Regels altijd op Regels.',
         'Condities toont wanneer de cijfers echt opgehaald zijn (bijvoorbeeld "Bijgewerkt om 10:33 (2 u geleden)"). GitHub haalt ze om de paar uur op; de waarschuwing komt pas na 8 uur.',
         'Onderhoud: de GitHub-taken gebruiken de nieuwe versies van hun bouwstenen, zodat ze blijven werken, en de nachtelijke gegevensupdate start op een rustiger moment (02:17 UTC).'],
    en: ['The Session tab has been removed.',
         'Rules has two tabs: Rules and Band plan. Rules shows a selection from the official WWFF rules, also valid for ONFF, in every language, with an example of the right name for your log file.',
         'Field info always opens on Areas, and Rules always on Rules.',
         'Conditions shows when the numbers were really fetched (for example "Updated at 10:33 (2 h ago)"). GitHub fetches them every few hours; the warning only comes after 8 hours.',
         'Maintenance: the GitHub jobs use the new versions of their building blocks, so they keep working, and the nightly data update starts at a quieter moment (02:17 UTC).'] },

  { v: '1.29.2', date: '2026-10-02',
    nl: ['Bij een aankondiging blijven de velden Begin en Einde binnen het kader: naast elkaar als ze allebei passen, anders onder elkaar.'],
    en: ['When announcing an activation, the Start and End fields stay inside the card: side by side when both fit, otherwise one under the other.'] },

  { v: '1.29.1', date: '2026-10-02',
    nl: ['Condities toont nu de officiële Kp per 3 uur, zoals radioamateurs hem gewoonlijk noemen. De schatting per minuut staat er klein onder.',
         'De Kp-wijzer licht ook bij Kp 0 op, en de naald loopt niet meer over de cijfers.'],
    en: ['Conditions now shows the official Kp per 3 hours, as radio amateurs usually quote it. The estimate per minute is shown small underneath.',
         'The Kp dial also lights up at Kp 0, and the needle no longer runs over the numbers.'] },

  { v: '1.29.0', date: '2026-10-02',
    nl: ['"In de buurt" heet nu "Veldinfo", met drie tabbladen: Gebieden, Locatie (het vroegere Info) en het nieuwe Condities.',
         'Condities toont het ruimteweer van NOAA (Kp met een wijzer, SFI, A en zonnevlekken), per band een kleurenbalk van ochtend tot nacht in de kleuren van de Kp-wijzer, met wat "goed" betekent (NVIS, EU of DX) en wat nu geldt, als ruwe indicatie volgens SFI, Kp, seizoen en dagdeel, en zonsopgang en zonsondergang op jouw positie.',
         'De privacypagina spreekt over WWFF in het algemeen, niet enkel over ONFF, en de app heet voortaan "Diana Fauna & Flora".'],
    en: ['"Nearby" is now "Field info", with three tabs: Areas, Location (the former Info) and the new Conditions.',
         'Conditions shows the space weather from NOAA (Kp on a dial, SFI, A and sunspots), per band a colour bar from morning to night in the colours of the Kp dial, with what "good" means (NVIS, EU or DX) and what applies now, as a rough indication from SFI, Kp, season and part of the day, and sunrise and sunset at your position.',
         'The privacy page speaks of WWFF in general, not only ONFF, and the app is now called "Diana Fauna & Flora".'] },

  { v: '1.28.0', date: '2026-10-01',
    nl: ['De knop Kaart onderaan zet de kaart altijd op je eigen positie, ook na het bekijken van een spot of aankondiging. De zoom blijft zoals hij was.',
         'Zonder GPS-positie gaat de kaart naar het midden van je locator uit Instellingen, en de melding zegt dat.',
         'Is je positie onnauwkeuriger dan 30 m of ouder dan 2 minuten, dan zoekt de knop Kaart ook meteen een nieuwe GPS-positie.',
         'De tip over een onnauwkeurige positie leest vlotter.'],
    en: ['The Map button at the bottom always puts the map on your own position, also after looking at a spot or announcement. The zoom stays as it was.',
         'Without a GPS position the map goes to the middle of your locator from Settings, and the message says so.',
         'If your position is less accurate than 30 m or older than 2 minutes, the Map button also looks for a new GPS position right away.',
         'The tip about an inaccurate position reads more smoothly.'] },

  { v: '1.27.0', date: '2026-10-01',
    nl: ['Het kruisje bij een spot of aankondiging die je uit de lijst opende, sluit enkel het infovenster: je blijft op de ingezoomde kaart rond de spot.',
         'Terug naar de lijst gaat met de nieuwe knop "← Terug naar Spots" (of Agenda) bovenaan het infovenster, of met de terugknop van je telefoon, ook als het venster al dicht is.'],
    en: ['The x on a spot or announcement you opened from the list now only closes the info window: you stay on the zoomed-in map around the spot.',
         'Back to the list with the new "← Back to Spots" (or Agenda) button at the top of the info window, or with your phone\'s back button, even with the window already closed.'] },

  { v: '1.26.0', date: '2026-09-28',
    nl: ['Nieuw: dit overzicht, te openen vanuit Instellingen.',
         'De terugknop van je telefoon brengt je van een spot of aankondiging terug naar de lijst waar je vandaan kwam, en van dit overzicht terug naar Instellingen.',
         'Tekst die anderen bij een spot of aankondiging intypen, wordt altijd als gewone tekst getoond.',
         'Het detailscherm van een spot of aankondiging toont ook het aantal QSO\'s van het gebied, of ATNO.'],
    en: ['New: this overview, opened from Settings.',
         "Your phone's back button takes you from a spot or announcement back to the list you came from, and from this overview back to Settings.",
         'Text other people type into a spot or announcement is always shown as plain text.',
         'The detail sheet of a spot or announcement also shows the area\'s QSO count, or ATNO.'] },

  { v: '1.25.0', date: '2026-09-28',
    nl: ['Tik op een spot of aankondiging in de lijst: je ziet hem meteen ingezoomd op de kaart, met de details erbij. Sluiten brengt je terug naar de lijst.',
         'De knop Kaart toont nooit meer ongevraagd de plek van een spot.',
         'Lange detailschermen scrollen volledig, ook terug naar boven.',
         '"Meer info" met de website van het gebied staat nu ook in het gebiedspaneel.',
         'Gedownloade kaartgebieden en gebiedsgegevens blijven bewaard na een update, en de gegevens worden bij elke start ververst.'],
    en: ['Tap a spot or announcement in the list: it opens zoomed in on the map, with its details. Closing takes you back to the list.',
         'The Map button never shows a spot\'s location unasked any more.',
         'Long detail panels scroll all the way, back to the top too.',
         '"More info" with the area\'s website is now in the area panel as well.',
         'Downloaded map areas and area data survive an update, and the data is refreshed on every start.'] },

  { v: '1.24.0', date: '2026-09-28',
    nl: ['"Meer info" bij een spot: de website van het gebied uit de WWFF-lijst. Opent in je browser, Diana blijft open.',
         'Je kan nu op een aankondiging in de agenda tikken: band, mode, gebied en locator.',
         'Enkele QSO-tellingen die verkeerd werden ingelezen, kloppen weer (onder meer ONFF-0103 Scheps).'],
    en: ['"More info" on a spot: the area\'s website from the WWFF directory. Opens in your browser, Diana stays open.',
         'You can now tap an announcement in the agenda: band, mode, area and locator.',
         'A few QSO counts that were read wrongly are right again (among them ONFF-0103 Scheps).'] },

  { v: '1.23.0', date: '2026-09-25',
    nl: ['Bij elke spot en aankondiging het aantal QSO\'s van dat gebied, of ATNO als het nog nooit geactiveerd werd.',
         'Gebieden die de WWFF-lijst op een verkeerde plek zet, staan op de wereldkaart binnen hun eigen grens.',
         'De CQ- en ITU-zone in het gebiedspaneel staan nu even groot als de rest.'],
    en: ['Every spot and announcement shows the area\'s QSO count, or ATNO if it has never been activated.',
         'Areas the WWFF directory puts in the wrong place appear inside their own boundary on the world map.',
         'The CQ and ITU zone in the area panel are now the same size as everything else.'] },

  { v: '1.22.0', date: '2026-09-24',
    nl: ['In de buurt > Info: tijd, locator, positie, CQ- en ITU-zone, ITU-regio en de drie dichtste WWFF-gebieden.',
         'Het gebiedspaneel toont de locator en de CQ/ITU-zone.',
         'Aangekondigde activaties uit andere landen verschijnen ook op de kaart.',
         'Gebieden die bij het inlezen een verkeerd nummer kregen, staan weer juist (bijvoorbeeld ONFF-0253 en 0254).'],
    en: ['Nearby > Info: time, locator, position, CQ and ITU zone, ITU region and the three nearest WWFF areas.',
         'The area panel shows the locator and the CQ/ITU zone.',
         'Announced activations in other countries appear on the map too.',
         'Areas that got a wrong number when read in are right again (for example ONFF-0253 and 0254).'] },

  { v: '1.21.1', date: '2026-09-24',
    nl: ['Een knop om precieze locatie toe te staan, met uitleg per toestel.'],
    en: ['A button to allow precise location, with instructions per device.'] },

  { v: '1.21.0', date: '2026-09-24',
    nl: ['Welkomstscherm bij de eerste start, met de vraag naar je locatie en naar statistieken.',
         'Privacypagina onder Instellingen, en alles op dit toestel in één keer wissen.'],
    en: ['A welcome screen on first start, asking about your location and about statistics.',
         'A privacy page under Settings, and wiping everything on this device in one go.'] },

  { v: '', date: '', earlier: true,
    nl: ['Kaart met de grenzen van de natuurgebieden, zoeken op naam of nummer, en met je GPS: sta ik binnen dit gebied?',
         'Live WWFF-spots en de agenda, wereldwijd of per land, met richting en afstand.',
         'Zelf spotten en een activatie aankondigen via WWFF Spotline.',
         'Meerdere landen met grenzen, de andere landen als punten.',
         'Sessie met GPX-spoor als bewijs, het scherm "In de buurt", het bandplan, en acht talen.',
         'Werkt offline met de laatst opgehaalde gegevens en een vooraf gedownload kaartgebied, en is te installeren als app.'],
    en: ['A map with the boundaries of the nature areas, search by name or number, and with your GPS: am I inside this area?',
         'Live WWFF spots and the agenda, worldwide or per country, with bearing and distance.',
         'Spot yourself and announce an activation through WWFF Spotline.',
         'Several countries with boundaries, the others as points.',
         'Sessions with a GPX track as proof, the Nearby screen, the band plan, and eight languages.',
         'Works offline with the last data it fetched and a map area downloaded beforehand, and can be installed as an app.'] },
];

function renderReleases(){
  const box = $('relList'); if(!box) return;
  const text = r => (lang === 'nl' ? r.nl : r.en) || r.en || [];
  const when = d => {
    const dt = new Date(d + 'T12:00:00');
    return isNaN(dt) ? '' : dt.toLocaleDateString(locale(), {day:'numeric', month:'long', year:'numeric'});
  };
  box.innerHTML = RELEASES.map(r => `
    <div class="card rel${r.v === APP_VERSION ? ' current' : ''}">
      <div class="relhead">
        <b>${r.earlier ? escH(t('rel.earlier')) : escH(r.v)}</b>
        ${r.v === APP_VERSION ? `<span class="pill">${escH(t('rel.current'))}</span>` : ''}
        <span class="reldate">${r.earlier ? '' : escH(when(r.date))}</span>
      </div>
      <ul>${text(r).map(li => `<li>${escH(li)}</li>`).join('')}</ul>
    </div>`).join('');
}

/* Like the privacy page: not a screen in the bottom bar, opened from Settings,
   and back always leads to Settings (the phone's back button too, see
   pushBack() in nav.js). */
function openReleases(){
  document.querySelectorAll('.view').forEach(v => v.classList.remove('on'));
  [...$('nav').children].forEach(c => c.classList.remove('on'));
  renderReleases();
  const view = $('viewReleases');
  view.classList.add('on');
  view.scrollTop = 0;
  pushBack(closeReleases);
}
function closeReleases(){
  if(!$('viewReleases').classList.contains('on')) return;
  document.querySelector('#nav button[data-view="viewSet"]').click();
}
$('relOpenBtn').onclick = openReleases;
$('relBack').onclick = closeReleases;
$('relBackTop').onclick = closeReleases;
