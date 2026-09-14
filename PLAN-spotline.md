# Stappenplan — Spotline-API, proxy, installatie en documentatie

Werkdocument voor de overstap van "spots lezen" naar "spots en agenda's
schrijven" via de officiële WWFF Spotline-API, met een sleutel die geheim
moet blijven terwijl de repository publiek is.

Dit document is in het Nederlands, want het is ons werkdocument. De
documentatie in `docs/` is in het Engels en blijft dat — die is voor
gebruikers en voor wie het project ooit overneemt.

**Documentatie staat niet achteraan.** Elke fase hieronder eindigt met zijn
eigen documentatiestap, in dezelfde pull request als de code. Een fase is pas
af als de uitleg erbij staat. Dat is geen netheid maar zelfbehoud: de reden
waarom een controle er staat, en welke je overwogen en verworpen hebt, is
achteraf niet uit een diff te reconstrueren.

---

## Waar we vandaan komen

Vandaag doet Diana twee dingen met Spotline, en allebei zonder sleutel.

**Lezen** gebeurt met drie statische bestanden op `spots.wwff.co/static/`,
elke 30 seconden opgehaald en gepauzeerd zodra het tabblad verborgen is. Die
host stuurt CORS-headers, dus dat werkt rechtstreeks vanuit de browser.

**Zelf spotten** gebeurt met een echte HTML-formulierpost naar
`/spots/store`, met `target="_blank"`. Dat is een navigatie en geen
datatoegang, dus CORS geldt er niet. De keerzijde: het antwoord is
onleesbaar voor de app. De melding "Spot verstuurd" betekent vandaag
*weggestuurd*, niet *aangekomen*.

Agenda's aanmaken kan helemaal niet.

## Lezen blijft bij de statische bestanden

De API die we kregen heeft drie endpoints: `POST /api/spots/add`,
`POST /api/agenda/store` en `GET /api/references/validate`. **Er zit geen
leesendpoint voor spots bij.** Zelfs als dat er ooit komt, blijven de
statische JSON-bestanden de betere weg om spots binnen te halen:

- geen sleutel nodig, dus geen proxy in het pad van iets dat elke 30 seconden
  gebeurt
- ze tellen niet mee voor de limiet van 100 per minuut — en dat budget is
  precies wat we willen bewaren voor het schrijven
- ze zijn te cachen en werken dus mee met de offline-opzet

De API gebruiken we dus uitsluitend voor de schrijfkant. Dat is meteen de
reden waarom de Worker alleen POST-endpoints krijgt.

## Waar we naartoe gaan

De officiële API lost de schrijfkant op — echte bevestigingen, echte
foutmeldingen, en agenda's die we kunnen aanmaken. Maar hij brengt twee harde
randvoorwaarden mee die het hele ontwerp bepalen.

**Eén sleutel voor de hele toepassing.** Niet één per gebruiker. Wat de app
kan lezen, kan elke gebruiker lezen — er bestaat geen manier om een geheim
te verbergen in een statische site. WWFF zegt het zelf: *keep the API key
server-side*. Er moet dus iets tussen dat wél server-side draait.

**100 aanvragen per minuut en 1000 per uur, per sleutel.** Dat budget delen
alle Diana-gebruikers samen. Een proxy verbergt de sleutel, maar niet het
verbruik: wie het adres kent kan het budget opstoken. Snelheidsbeperking is
daarom geen extraatje maar het eigenlijke werk.

De keuze die daaruit volgt: een **Cloudflare Worker** als dunne, streng
afgebakende doorgang. De code van die Worker mag gerust publiek in de
repository staan — alleen de sleutel woont bij Cloudflare. De repository
hoeft dus niet privé.

## Wat het kost: niets

Diana is een vrijwilligersproject en dat moet het blijven. Nagekeken bij de
bron, september 2026:

| Wat | Gratis? | De grens | Waar wij zitten |
|---|---|---|---|
| GitHub Free **voor organisaties** | ja | onbeperkt publieke repositories | één repository |
| GitHub Pages op een publieke repo | ja, ook voor organisaties | site max 1 GB · 100 GB verkeer per maand (zacht) | site ± 13 MB |
| GitHub Pages builds | ja | 10 per uur (zacht) — geldt **niet** bij een eigen Actions-workflow, en dat is precies wat `pages.yml` is | onbeperkt in de praktijk |
| GitHub Actions op publieke repos | ja | onbeperkt | nachtelijke build + publiceren |
| Cloudflare Workers | ja | 100.000 aanvragen per dag · 10 ms rekentijd per aanvraag | een spot nu en dan |
| Cloudflare Workers KV | ja | 1 GB opslag · 100.000 leesbewerkingen per dag · **1.000 schrijfbewerkingen per dag** | tellers voor de limieten |

Geen betaalkaart nodig, geen proefperiode die afloopt.

Eén getal daarvan raakt het ontwerp: **1.000 KV-schrijfbewerkingen per dag.**
De teller van de snelheidsbeperking mag dus niet bij élke aanvraag schrijven.
Regel voor stap 2.6: alleen tellen wat de validatie doorstaat en werkelijk
naar WWFF gaat. Een preflight, een afgekeurd formulier of een geblokkeerde
herkomst schrijft niets. Onze POST's zijn zeldzaam — een handvol per dag —
dus dan is één schrijfbewerking per doorgelaten aanvraag ruim binnen de
grens. Cloudflare heeft daarnaast één gratis Rate-Limiting-regel; die kan de
grove afscherming doen zonder KV aan te raken.

Het verkeer op Pages is het enige waar je op termijn tegenaan kan lopen:
`wwff-world.geojson` is 9 MB, dus 100 GB per maand is ongeveer elfduizend
keer die laag openen. Die laag is opt-in en staat standaard uit, dus dat
duurt nog even. Als het ooit knelt is de oplossing die laag opsplitsen per
werelddeel, niet betalen.

## Wat er kan lekken, en wat niet

Je vraag was terecht: wordt er door deze opzet iets bereikbaar dat dat nu
niet is? Het korte antwoord is nee, met twee dingen om bewust te doen.

**De API-sleutel raakt GitHub nooit.** Hij woont alleen als versleuteld
secret bij Cloudflare, en komt niet in de repository, niet in een
Actions-secret en niet in de uitgeleverde bundel. Hoe je GitHub-account ook
ingericht is, daar verandert niets aan.

**De repository is vandaag al publiek**, en verhuizen maakt op zich niets
extra zichtbaar. Het bron-KMZ in `source/` gaat wél weg uit het publieke
kanaal — zie Fase −1, stap −1.2.

Wees daarbij eerlijk over wat dat oplevert. **Voor de gegevens niets:**
`onff.geojson` staat op de publieke site en bevat alle grenzen, en elke
bezoeker downloadt dat. Wie de gebieden wil hebben, heeft ze al, in een
handiger formaat dan een KMZ. Het KMZ weghalen beschermt het *bestand*, niet
de *gegevens*.

Wat het wél is: een gebaar naar ONFF, die dat bestand via een groups.io
achter lidmaatschap verspreidt. Door het niet op een tweede publiek kanaal te
zetten respecteer je dat kanaal. Dat is geen schijnbeveiliging zolang je het
zo benoemt — het is netheid, geen slot. Zie ook `LICENSE` en `ADMIN.md §5`.

Twee dingen die je in een organisatie wél anders moet doen:

- **Fine-grained tokens moeten in de organisatie expliciet toegelaten
  worden.** Staat dat niet aan, dan werkt je beheerscherm in de app niet
  meer — het token krijgt geen toegang. Dit is één instelling, maar je vindt
  hem niet als je niet weet dat hij bestaat.
- **Wie schrijfrechten heeft, kan bij de secrets.** Niet door ze te lezen in
  de interface — dat kan niemand — maar door een workflow te schrijven die
  ze uitprint. Zolang jij de enige bent maakt dat niets uit. Voeg je later
  iemand toe, geef die dan leesrechten, of beperk wie workflows mag wijzigen.
  Vermeld dat in de handleiding, want dit is de val waar mensen intrappen
  wanneer een project groeit.

## Wat dit betekent voor het karakter van Diana

Dit doorbreekt gedeeltelijk het uitgangspunt "geen server van ons". De
kaart, de gebieden, de bunkers en het *lezen* van spots blijven statische
bestanden zonder server. Alleen het *schrijven* gaat straks langs de Worker.
Valt die weg, dan blijft alles wat je onderweg nodig hebt werken; je kan
alleen even niet zelf spotten.

De app zelf verhuist niet. Ze blijft één statisch HTML-bestand plus data,
uitgeserveerd door GitHub Pages, installeerbaar op je telefoon, werkend
zonder netwerk. De Worker bevat geen enkele pagina en geen data — het zijn
zo'n honderdvijftig regels die een JSON-berichtje aannemen, nakijken, de
sleutel erbij zetten en doorsturen.

---

# Fase −1 — Diana een eigen huis geven

Dit gaat vóór al de rest, want elk adres dat we later in de app en in de
Worker vastleggen moet meteen het juiste zijn. Een keer verhuizen is werk;
twee keer is dom werk.

**Waarom een organisatie en niet je persoonlijke account.** Vandaag hangt
Diana aan jouw persoon. Wil je er ooit iemand van BOS bij, of het beheer
overdragen, dan moet de repository verhuizen — en dan verandert de URL.
Geïnstalleerde apps en ingesloten iframes op andermans website breken op dat
moment. Een organisatie is gratis, kan publieke Pages uitserveren, en je kan
er later eigenaars aan toevoegen of het geheel overdragen **zonder dat de URL
wijzigt**. Je persoonlijke account blijft bestaan en wordt de eerste eigenaar
van de organisatie; dat hoort zo.

**Beslist:** de organisatie heet **`diana-onff`** en de publieke repository
heet **`diana-onff.github.io`**. Let op de schrijfwijze — GitHub staat in
account- en organisatienamen alleen letters, cijfers en losse koppeltekens
toe. Een underscore wordt geweigerd, dus `onff_app` bestaat niet als naam.

Waarom die repositorynaam. Een repository die exact `<organisatie>.github.io`
heet, wordt door Pages op de **wortel** van het domein gezet in plaats van in
een submap. De app komt daarmee op:

`https://diana-onff.github.io/`

Dus geen `/DIANA/` erachter. Dat scheelt niet alleen tikwerk: elk pad in de
app, elke insluitcode en elke servicewerker-scope wordt er eenvoudiger van, en
het adres is kort genoeg om in een QR-code of op een sheet te zetten. De
previews van pull requests blijven gewoon werken — die komen op
`https://diana-onff.github.io/preview/pr-<nummer>/`.

**Beslist:** we beginnen met een **verse repository**, niet met een
overdracht. De geschiedenis is nu nog testfase — grotendeels "Add files via
upload" van de afgelopen weken — en vers beginnen is de enige manier om het
bron-KMZ ook uit het verleden te krijgen. Die prijs is nu laag en over een
jaar niet meer.

### Stap −1.1 — De organisatie aanmaken

Gratis plan. Als je een e-mailadres hebt dat niet aan één persoon vastzit,
gebruik dat. Meteen daarna één instelling die je anders pas ontdekt als het
misgaat: **Settings → Personal access tokens → toestaan dat fine-grained
tokens deze organisatie mogen benaderen.** Zonder dat werkt het beheerscherm
in de app niet meer.

### Stap −1.2 — Twee repositories

| Repository | Zichtbaarheid | Wat erin zit |
|---|---|---|
| `diana-onff/diana-onff.github.io` | publiek | de app, de workflows, `data/`, `docs/`, `worker/` |
| `diana-onff/diana-source` | **privé** | alleen de KMZ-bestanden van ONFF |

De naam van de publieke repo is niet vrij te kiezen: alleen exact
`diana-onff.github.io` levert het adres zonder submap op. Noem je hem anders,
dan sta je op `https://diana-onff.github.io/<naam>/` en is de winst van
stap −1 weg.

De publieke repo krijgt geen `source/`-map meer. Dat is het punt van de hele
oefening: het bron-KMZ verlaat het publieke kanaal.

Dit blijft gratis, en dat is niet vanzelfsprekend — dus nagekeken:
onbeperkt private repositories op het gratis plan, en **Actions is gratis
voor publieke repositories**. De workflow draait in de publieke repo, dus de
minuten worden daar geteld; dat hij een private repo uitleest verandert daar
niets aan. Zou je álles privé maken, dan val je terug op 2.000 minuten per
maand én werkt Pages niet meer, want dat vraagt op het gratis plan een
publieke repo.

### Stap −1.3 — Een token om de private repo te lezen

De build moet aan het KMZ kunnen. Een fine-grained token met **alleen
Contents: read** op `diana-source`, opgeslagen als secret in de publieke repo
onder bijvoorbeeld `SOURCE_TOKEN`. Meer rechten heeft hij niet nodig.

Dit is meteen het moment om te beseffen wat er in stap −1.1 stond: wie
schrijfrechten heeft op de publieke repo kan een workflow schrijven die dit
token uitprint. Zolang jij de enige bent maakt dat niets uit. Voeg je later
iemand toe, dan is dit de reden om die persoon geen schrijfrechten op
workflows te geven.

### Stap −1.4 — De build laten lezen uit de private repo

`build-data.yml` krijgt een tweede checkout-stap die `diana-source` binnenhaalt
met `SOURCE_TOKEN`, in een aparte map. De stap "Nieuwste KMZ kiezen" zoekt
daar in plaats van in `source/`. `site.sh` verandert niet — die sloot `source/`
al uit, en nu is er niets meer om uit te sluiten.

### Stap −1.5 — De uploadstroom herzien, en de val vermijden

**Dit is de stap waar het mis kan gaan, dus lees hem twee keer.**

Vandaag komt een geüpload KMZ op een branch in dezelfde repo, en dezelfde
pull request bevat zowel het KMZ als de omgezette data. Je kijkt naar de
preview en merget. Met twee repositories valt dat uit elkaar: een pull request
in de private repo kan de workflow in de publieke repo niet starten.

De verleiding is om het KMZ dan maar rechtstreeks op `main` van de private
repo te zetten. **Doe dat niet.** De nachtelijke build kiest het nieuwste KMZ
dat er staat. Upload je iets fouts en wijs je de datawijziging af, dan bouwt
de nacht daarna vrolijk verder met dat foute bestand en commit het resultaat
zelf naar `main`. Precies de bewaking die we hebben ingebouwd, omzeild langs
de achterdeur.

De opzet die dat niet heeft:

1. Het beheerscherm zet het nieuwe bestand in **`incoming/`** op `main` van
   `diana-source`. Een wachtruimte, geen bron.
2. De app start daarna `build-data.yml` in de publieke repo
   (`workflow_dispatch` via de API).
3. De build kijkt eerst in `incoming/`. Staat daar iets, dan bouwt hij dáármee
   en opent een **pull request in de publieke repo** met de nieuwe `data/` en
   het verschillenrapport. Is `incoming/` leeg, dan is het een gewone
   nachtelijke run en kijkt hij alleen naar `source/`.
4. **De nachtelijke build raakt `incoming/` nooit aan.** Een niet-goedgekeurd
   KMZ kan dus nooit vanzelf gepubliceerd worden.
5. Merge je die pull request, dan verplaatst een stap het bestand van
   `incoming/` naar `source/` in de private repo. Sluit je hem zonder mergen,
   dan wordt het uit `incoming/` verwijderd.

Netto is dit zuiverder dan wat we nu hebben: je beoordeelt de **kaart**, niet
de bytes van een KMZ, en het bronbestand promoveert pas als de kaart klopt.

Het beheerderstoken in de app heeft nu twee dingen nodig: schrijfrechten op
`diana-source` en het recht om workflows te starten op
`diana-onff.github.io`. Eén
fine-grained token kan beide repositories van dezelfde organisatie dekken —
nog een reden waarom de organisatie het makkelijker maakt in plaats van
moeilijker.

### Stap −1.6 — Alle adressen nalopen

Het stuk dat mensen vergeten en dat stil kapotgaat:

- de standaardwaarde `ON3VZ/DIANA` in het beheerscherm van de app wordt
  `diana-onff/diana-onff.github.io`
- `docs/USER_GUIDE.md` en `README.md` noemen het adres letterlijk
- `DEPLOY.md` en `ADMIN.md` gebruiken `ON3VZ/DIANA` als voorbeeld
- de insluitcode-generator bouwt zijn iframe uit `location`, dus die volgt
  vanzelf — maar de **al gepubliceerde** iframes bij anderen niet
- straks de toegestane herkomst in de Worker (stap 2.5): dat wordt
  `https://diana-onff.github.io`

**Nagekeken, en het viel mee.** Ik had hier geschreven dat er paden met
`/DIANA/` erin opgespoord moesten worden. Die staan er niet: de app gebruikt
overal relatieve paden (`./data/…`, `sw.js`, en `location.origin +
location.pathname` voor de insluitcode), dus zij verhuist zonder één
wijziging mee.

Wat er wél moest gebeuren, en gedaan is: één plek in `web/index.html` en twee
in `pages.yml` bouwden het Pages-adres als `https://<eigenaar>.github.io/<repo>`.
Voor een repo die exact `<eigenaar>.github.io` heet klopt dat niet — die staat
op de wortel. De regel staat nu in `build/paginabasis.sh` en in `previewUrl()`
in de app. Zonder dat werd de previewlink
`https://diana-onff.github.io/diana-onff.github.io/preview/pr-3/`: een 404 die
er uitziet alsof Pages stuk is.

**Klaar wanneer.** `git grep -i on3vz` levert alleen nog treffers op waar het
over jou als persoon gaat, niet over een adres.

### Stap −1.7 — De instellingen zetten

Die verhuizen niet mee en moeten allemaal opnieuw:

- Actions → General → Workflow permissions op **Read and write**, vóór de
  eerste run
- eerste keer `pages.yml` handmatig draaien om `gh-pages` te laten ontstaan
- Settings → Pages → branch `gh-pages`, map `/ (root)`
- branchbescherming: wél *Block force pushes* en *Restrict deletions*, níét
  "Require a pull request"
- de twee secrets: `SOURCE_TOKEN`, en later niets meer — de API-sleutel gaat
  naar Cloudflare, niet hierheen

### Stap −1.8 — Een bericht voor wie de oude URL gebruikt

Bij een verse repository verwijst het oude adres **niet** door. Wie een iframe
heeft staan of de app geïnstalleerd heeft, moet het weten. Laat de oude
repository voorlopig staan met een `README` die naar het nieuwe adres wijst,
en zet er eventueel een `index.html` op de oude Pages die doorstuurt.

### Stap −1.9 — Documentatie van deze fase

De eerste versie van `docs/INSTALL.md` (zie stap 0.4), en `ARCHITECTURE.md`
uitbreiden met de tweede repository en de nieuwe uploadstroom. Wie het diagram
in §1 leest moet zien dat er nu twee bronnen zijn.

**Een eigen domein** blijft voor later. Dat is de echte verzekering tegen
adreswijzigingen — verhuis je ooit van account of van hosting, dan merkt
niemand het. Het kan er altijd bij en hoeft nu niets te blokkeren.

---

# Fase 0 — Voorbereiding

Geen app-code. Deze stappen doe jij, en ze moeten af zijn voor de rest zin
heeft.

### Stap 0.1 — Een eigen sleutel voor Diana vragen

**Waarom.** De sleutel die we nu hebben is die van BOS, en hij is intussen
langs twee mailboxen en een chat gereisd. Als er ooit iets misgaat via Diana
— misbruik, een lek, een lus die op hol slaat — dan wordt die sleutel
ingetrokken en zit iedereen die hem gebruikt zonder. Met een eigen sleutel is
de schade toe te wijzen en te herstellen zonder anderen te raken.

**Wat.** Vraag aan WWFF een aparte sleutel op naam van Diana, en vermeld
erbij dat het om een publieke webapp gaat met een proxy ertussen en eigen
snelheidsbeperking. Dat laatste is precies wat ze willen horen.

**Klaar wanneer.** Je hebt een sleutel die alleen voor Diana gebruikt wordt.
Tot dan werken we volledig op de testomgeving `https://spots-dev.cuf.fi/`.

### Stap 0.2 — Cloudflare klaarzetten

**Waarom.** De Worker is de enige plek waar de sleutel mag staan.

**Een apart account?** Ja, om dezelfde reden als de GitHub-organisatie:
gebruik een account op naam van het project, niet je persoonlijke
Cloudflare-account als je dat al voor iets anders gebruikt. Zet er hetzelfde
e-mailadres achter als de organisatie. Zo hangt niets van Diana aan één
persoonlijke login.

Maak je er niet te druk over: **de Worker is volledig herbouwbaar.** De code
staat in de repository, de sleutel kan opnieuw gezet worden, en `wrangler
deploy` zet hem in één commando ergens anders neer. Het enige wat een
verhuizing kost is een nieuw adres in `web/index.html`. Dat is heel iets
anders dan een repository die je kwijt bent.

**Wat.** Een gratis Cloudflare-account aanmaken (geen betaalgegevens nodig)
en `npm install -g wrangler` op je machine. Daarna `wrangler login`, wat een
browservenster opent waarin je de koppeling goedkeurt. Meer is er niet.

**Klaar wanneer.** `wrangler whoami` toont het juiste account.

### Stap 0.3 — Het adres van de Worker kiezen

**Waarom.** Dat adres komt in de app te staan en is dus zichtbaar. Verhuizen
kan later, maar dan moet er een nieuwe versie van de app uit.

**Wat.** `diana-api.<accountnaam>.workers.dev` is gratis en werkt meteen.
Kies de subdomeinnaam van je Cloudflare-account met dezelfde zorg als de
organisatienaam — ook die zit in de URL.

Een eigen (sub)domein kan later en is dan meteen de goede gelegenheid om het
ook voor de app te doen.

**Klaar wanneer.** Je weet welk adres het wordt.

### Stap 0.4 — Een installatiehandleiding, en die echt uitproberen

**Waarom.** Diana staat nu op jouw account, maar dat is geen eeuwigheid. Ooit
verhuist het naar een BOS-account, of iemand anders neemt het over, of je wil
gewoon een tweede omgeving om in te testen. Op dat moment moet iemand — of
jijzelf over twee jaar — de hele opzet kunnen herbouwen zonder deze chat.

Dat is nu al meer dan "zet de bestanden erin": er zijn twee workflows, een
`gh-pages`-branch, workflowrechten, Pages-instellingen, een optionele
repository-variabele, een bron-KMZ dat niet zomaar publiek mag, een
beheerderstoken met de juiste rechten, en straks een Worker met een geheim.
Elk van die dingen is één keer instellen en daarna onzichtbaar — precies het
soort kennis dat verdwijnt.

**Voor wie.** Geschreven voor iemand die GitHub nog nooit van binnen gezien
heeft. Niet "stel de workflow permissions in", maar "klik rechtsboven op
Settings, dan links op Actions, dan General, scrol naar Workflow
permissions". Elke stap met waar je moet klikken, wat je hoort te zien als
het gelukt is, en wat er misgaat als je hem overslaat. Wie het al kan, leest
eroverheen; wie het niet kan, komt er anders niet doorheen.

**Wat.** Een nieuw `docs/INSTALL.md` dat van nul naar draaiend gaat, en dat
begint bij de organisatie uit Fase −1 — niet bij een bestaande repository:

0. **Een organisatie aanmaken** op het gratis plan, en waarom een organisatie
   en geen persoonlijk account (zie Fase −1). Met de instelling die je anders
   pas ontdekt als het misgaat: fine-grained tokens moeten in de organisatie
   toegelaten worden, anders werkt het beheerscherm niet.
1. **De repository** — kopiëren of forken, wat er wel en niet mee moet. Het
   valstrik-punt vooraan: `.github/` wordt door Windows Explorer verborgen en
   verdwijnt stil bij slepen. Gebruik "Create new file" met het volledige pad.
2. **Instellingen die je één keer zet** — Settings → Actions → General →
   Workflow permissions op *Read and write*, vóór de eerste run. Anders faalt
   zowel de commit naar een pull-request-branch als de push naar `gh-pages`
   met een 403.
3. **De eerste build** — Actions → "Publiceren naar GitHub Pages" → Run
   workflow. Die maakt `gh-pages` aan; pas daarna kan je bij Settings → Pages
   die branch kiezen.
4. **Data bouwen** — een KMZ in `source/` zetten en "ONFF-data bouwen"
   draaien. Wat je hoort te zien in het verslag: aantal gebieden, hoeveel er
   een grens hebben, hoeveel als punt.
5. **Optioneel** — de repository-variabele `ONFF_REFS_CSV` als WWFF de
   directory ooit verplaatst of als je tegen een eigen kopie wil testen.
6. **Het beheerderstoken** — een fine-grained token, alleen deze repository,
   Contents en Pull requests read/write, korte vervaldatum. Met de reden
   waarom er niet meer rechten in mogen.
7. **Branchbescherming** — wél *Block force pushes* en *Restrict deletions*,
   níét "Require a pull request", want dat breekt de nachtelijke commit naar
   `main`. Met de uitleg erbij, anders zet iemand het ooit toch aan.
8. **De Worker** — komt erbij na Fase 2, met een verwijzing naar
   `worker/README.md`.
9. **Wat je moet nakijken als het niet werkt** — de bestaande
   probleemoplossing uit `ADMIN.md §4` hoort hier thuis of moet er in elk
   geval naar verwijzen.

**Klaar wanneer.** Je hebt de handleiding **zelf gevolgd op een lege
repository** en de site draait. Dat is de enige manier om te weten of hij
klopt — een installatiehandleiding die niemand ooit uitgevoerd heeft, is een
verlanglijstje. Reken op één avond, en die avond levert gegarandeerd drie
dingen op die nergens beschreven stonden.

**Tip.** Doe die proefinstallatie in een repository die je daarna weggooit,
en gebruik er een apart wegwerptoken voor.

---

# Fase 1 — De documentatie-achterstand wegwerken

Kan volledig parallel met Fase 0 en heeft niets nodig van Cloudflare of WWFF.

### Stap 1.1 — Wat er niet meer klopt

**Waarom.** Er is de afgelopen weken veel veranderd dat nergens beschreven
staat. Documentatie die niet meer klopt is erger dan geen documentatie, want
ze wordt geloofd.

| Bestand | Wat er moet gebeuren |
|---|---|
| `DEVELOPER.md` | `build-data.yml` beschrijven zoals hij nu écht is; het versiestempel uit `site.sh` erbij — `APP_VERSION` is handmatig, `BUILD` komt van de bouwstap en `sw.js` krijgt per build een eigen cachenaam; de uitvoercontrole die alleen bij de nachtelijke run streng is |
| `ARCHITECTURE.md` | §2.3 herschrijven: CORS op de statische bestanden ís gemeten en werkt, die slag om de arm mag eruit. De service worker staat er nog als cache-first beschreven terwijl pagina en `data/` nu network-first zijn. `spotFilter` heet nu `spotFilter2`, `arcs` heet `arcs2`, en er is een `spots`-sleutel bij |
| `ADMIN.md` | De kaart "Nu live" en het opvolgen van een openstaande pull request in de app — status van de workflows, previewlink, publiceren en afwijzen. Dat is nu de gewone weg; github.com is de uitzondering geworden |
| `USER_GUIDE.md` | De schakelaar voor spots in het lagenmenu, de stippellijnen, het versiemerkje linksonder, de knop "Op updates controleren", en het heatmappaneel dat je kan wegleggen zonder de kleuren te verliezen |
| `DEPLOY.md` | Nalopen op map- en workflownamen, en beslissen wat hierheen verhuist en wat naar het nieuwe `INSTALL.md` gaat — die twee mogen elkaar niet tegenspreken |

**Aanpak.** Dit is begrensd en grotendeels mechanisch: er is een bestaande
tekst, een precieze lijst van wat niet meer klopt, en de code als waarheid.
Goede kandidaat om te laten uitschrijven met een scherpe opdracht, en daarna
na te lezen tegen de code. Dat nalezen is niet optioneel — wie de repository
niet echt gedraaid heeft, schrijft makkelijk iets op dat plausibel klinkt en
niet waar is.

**Klaar wanneer.** Iemand die de repository voor het eerst ziet, kan de
documentatie geloven.

### Stap 1.2 — Alles in het Engels

**Beslist.** Eén taal in de repository, en dat wordt Engels. Dat geldt voor:

- alle documentatie, dus ook `README.md` en de tekst die `report.md` produceert
- alle commentaar in de code — Python, JavaScript, shell, YAML
- de namen van de workflows en van hun stappen, want die staan in de logs die
  je aan iemand anders laat zien

Wat **niet** vertaald wordt, en dat is geen inconsistentie: de teksten in de
app zelf. Die zitten in `STR` en horen in zeven talen te bestaan, Nederlands
inbegrepen. Het onderscheid is eenvoudig: wat de gebruiker leest is
meertalig, wat de ontwikkelaar leest is Engels.

**Waarom.** Zodra er een tweede paar handen bijkomt — iemand van BOS, een
WWFF-coördinator uit een ander land, iemand die de app voor zijn eigen
programma wil overnemen — is Nederlands commentaar een muur. Het is nu een
paar uur werk en straks een paar dagen.

**Omvang, eerlijk gemeten.** De grote brok is `index.html`: daar staat het
meeste commentaar, en het is precies het bestand dat in stap 1.3 toch al
opengaat. Die twee horen dus in één beweging.

**Klaar wanneer.** `grep` op een handvol Nederlandse woorden in de
codebestanden levert alleen nog treffers op binnen `STR`.

### Stap 1.3 — JavaScript en CSS uit `index.html` halen

**Beslist.** `web/index.html` wordt opgesplitst:

| Nieuw bestand | Wat erin komt |
|---|---|
| `web/index.html` | alleen de opmaak — het skelet, de panelen, de formulieren |
| `web/app.css` | alles wat nu in `<style>` staat |
| `web/app.js` | alles wat nu in het grote `<script>`-blok staat |

**Waarom.** Eén bestand van meer dan vijfduizend regels is niet meer te
overzien, en elke wijziging raakt het hele bestand — wat elk verschil moeilijk
te lezen maakt en elke samenvoeging een risico. Los van elkaar zijn ze ook
apart te cachen: verandert alleen de opmaak, dan hoeft de JavaScript niet
opnieuw over de lijn.

Of `app.js` daarna nog verder opgesplitst wordt (kaart, spots, beheer,
instellingen) is een aparte beslissing. Ik zou het niet in dezelfde stap doen:
eerst de knip die zeker goed is, dan pas nadenken over de indeling.

**Wat er meeverandert, en waar het stilletjes fout gaat**

Dit is het deel dat mensen vergeten, en het faalt zonder foutmelding:

- `build/site.sh` stempelt nu `'__DIANA_BUILD__'` in `index.html`. Die
  plaatshouder verhuist mee naar `app.js`, dus het script moet daar gaan
  zoeken. Het script telt het aantal vervangingen en stopt bij een ander
  aantal dan één — die controle blijft, en is hier precies het vangnet.
- `web/sw.js` heeft een lijst `SHELL_FILES`. Staan `app.js` en `app.css` daar
  niet in, dan werkt de app online prima en is hij offline stuk. Dat merk je
  pas in het bos, zonder bereik.
- De browsertests in `build/tests/` kijken naar de pagina, niet naar de
  bestandsindeling, dus die zouden ongewijzigd moeten blijven werken. Dat is
  een verwachting, geen zekerheid — ze draaien na afloop allemaal, en dat is
  meteen het bewijs dat de knip klopt.
- De volgorde van laden: `app.js` moet ná de opmaak komen (of met `defer`),
  anders zoekt het script elementen die er nog niet zijn.

**Klaar wanneer.** De elf browsertests draaien groen, het versiestempel staat
weer linksonder in de app, en de app werkt met het vliegtuigicoon aan.

### Stap 1.4 — `docs/MAINTENANCE.md`: het sleutelregister en het onderhoud

**Model: Sonnet.** Begrensd werk — de feiten staan verspreid over `wrangler.toml`,
de workflows, `ADMIN.md` en dit plan, en moeten op één plek samenkomen. Wel
daarna nalezen tegen de werkelijkheid, want een handleiding die één stap mist
laat iemand met een halve installatie achter.

**Waarom.** Er zijn intussen vier verschillende geheimen in omloop, elk op een
andere plek, met een andere levensduur en een ander gevolg als ze verlopen. Nu
weten jij en ik dat nog. Over een half jaar niet meer, en wie het project ooit
overneemt sowieso niet. Een verlopen token dat niemand herkent, ziet er precies
uit als "de app is stuk".

**Het register.** Per sleutel: waar hij staat, wat hij mag, wie hem kan lezen,
wanneer hij verloopt, wat er stilvalt als hij weg is, hoe je hem vervangt, en
hoe je daarna controleert dat het gelukt is.

| Wat | Waar het staat | Wat er stilvalt als hij verloopt |
|---|---|---|
| `SOURCE_TOKEN` | secret in de publieke repo | de nachtelijke build vindt het KMZ niet meer en valt terug op `source/` — met een waarschuwing die niemand leest |
| Het beheerderstoken | in de browser, op jouw toestel (localStorage) | uploaden via de app; de rest blijft werken |
| `WWFF_API_KEY` | Cloudflare secret | spotten en agenda; de kaart blijft gewoon draaien |
| Het wrangler-token | op jouw computer, na `wrangler login` | je kan niet meer deployen — maar de Worker blijft draaien |

En wat er **geen** geheim is, want dat is even belangrijk om op te schrijven:
het KV-namespace-id, `ONFF_REFS_CSV`, en het adres van de Worker. Wie dat niet
weet, gaat die behandelen alsof ze wél geheim zijn, en dat maakt overdragen
onnodig moeilijk.

**Wat er verder in hoort — het is een onderhoudshandleiding, niet alleen een
sleutellijst:**

- De WWFF-sleutel die via e-mail binnenkwam: die is in leesbare tekst door een
  mailbox gegaan. Vraag WWFF om een Diana-eigen sleutel en laat deze intrekken.
  Dat hoort hier als taak te staan, niet als losse herinnering.
- **GitHub zet een geplande workflow na 60 dagen zonder activiteit vanzelf
  stil.** Je krijgt er een mail over. Wie dat niet weet, denkt dat de data
  gewoon niet meer ververst.
- De vervaldatum van elk token in een agenda, met de opdracht om te vernieuwen
  erbij. Een token dat verloopt terwijl jij op vakantie bent, is het scenario
  waar dit document voor bestaat.
- De limieten om in de gaten te houden: KV op 1000 schrijfbewerkingen per dag,
  Actions-minuten, en het gedeelde WWFF-budget.
- De noodschakelaar: hoe je hem bedient, en wanneer je dat zou doen.
- Wat te doen als de nachtelijke build een issue opent — wat de meldingen
  betekenen en welke ernstig zijn.

**Klaar wanneer.** Iemand die het project overneemt en dit document leest, kan
elke sleutel vervangen zonder jou iets te moeten vragen.

**Uitgevoerd op 2026-09-10.** Volledige documentatieronde in één keer:

- **Stap 1.1** (wat er niet meer klopte): `README.md` en `DEPLOY.md`
  herschreven — het publiek/privé-onderscheid, de admin-panel-route, de
  verouderde "geen Cloudflare"-framing en de open vraag aan Luk (die allang
  beslist was) zijn eruit. `DEPLOY.md` is nu een korte oriëntatie die
  doorverwijst naar `INSTALL.md`, `ADMIN.md` en `MAINTENANCE.md` in plaats
  van alles zelf te herhalen — dat voorkomt dat twee documenten weer uit
  elkaar groeien. Alle interne markdown-links (bestand én anker) zijn
  geprogrammeerd nagelopen tegen de echte GitHub-slugificatie; zes waren
  stuk (waaronder een Nederlands anker in `ADMIN.md` naar `DEPLOY.md`, en een
  verwijzing naar een niet-bestaand `CLOUDFLARE.md` vanuit
  `worker/README.md`) en zijn hersteld. `ARCHITECTURE.md`, `DEVELOPER.md`,
  `ADMIN.md`, `SPOTLINE.md` en `USER_GUIDE.md` bleken al grotendeels
  actueel uit eerdere fases; alleen de kapotte kruisverwijzingen erin
  moesten nog gefixt worden.
- **Stap 1.4**: `docs/MAINTENANCE.md` geschreven — het volledige
  sleutelregister (`SOURCE_TOKEN`, `WWFF_API_KEY`, het beheerderstoken,
  wrangler-login), per sleutel waar hij staat/wie hem kan lezen/wat
  stilvalt/hoe je hem vervangt, plus een apart hoofdstuk over het verschil
  tussen een content-admin en een technisch beheerder en hoe je van elk een
  nieuwe toevoegt (en verwijdert), wat géén geheim is, de sluimerende vallen
  (60-dagen-uitschakeling, verlopende tokens), de limieten om in de gaten te
  houden, de noodschakelaar, en wat een mislukte nachtelijke build betekent.
- **Stap 0.4**: eerste versie van `docs/INSTALL.md` geschreven — volledig
  stappenplan van "organisatie aanmaken" tot een draaiende, geverifieerde
  site, met een concreet checkpoint na elke stap en verwijzingen naar
  `ADMIN.md §4` voor de gekende probleemgevallen. **Nog niet afgevinkt
  volgens de eigen "Klaar wanneer"-eis van deze stap**: dit is geschreven,
  niet zelf uitgeprobeerd op een lege repository. Dat blijft een openstaand
  punt — precies zoals hierboven al gewaarschuwd: een installatiehandleiding
  die niemand doorlopen heeft is een verlanglijstje, geen bewezen procedure.

**Bewust nog niet gedaan in deze ronde:** Stap 1.2 (Engelse vertaling van
code- en workflowcommentaar — dat is code, geen documentatie) en Stap 1.3
(die was al lang gedaan, zie Fase 6). Deze ronde ging over de `.md`-bestanden.

---

# Fase 2 — De Worker, tegen de testomgeving

Nog geen enkele wijziging aan de app. Deze fase is af als de keten met `curl`
werkt. Dat is bewust: als hier iets niet klopt, wil je dat weten zonder dat
er ook nog app-code in het spel is.

Alles in deze fase draait tegen `https://spots-dev.cuf.fi/`, met
`"dryrun": true` om te valideren zonder op te slaan.

### Stap 2.1 — De map `worker/` in de repository

**Waarom.** De Worker hoort bij het project en verdient dezelfde
zichtbaarheid als de rest. Alleen de sleutel hoort er niet in.

**Wat.** Een `worker/` map met `wrangler.toml`, `src/index.js` en een eigen
`README.md`. In `wrangler.toml` staat het doeladres als gewone variabele
(dev of productie), zodat overschakelen één regel is. De sleutel staat er
**niet** in — die komt in stap 2.2.

**Klaar wanneer.** `wrangler deploy` zet een Worker neer die op elk verzoek
`{"error":"nog niets"}` antwoordt.

### Stap 2.2 — De sleutel erin, één keer, door jou

**Waarom.** Dit is het hele punt van de oefening.

**Wat.**

```
cd worker
wrangler secret put WWFF_API_KEY
```

Dat vraagt de waarde interactief, slaat hem versleuteld op bij Cloudflare en
toont hem nooit meer. In de code staat alleen `env.WWFF_API_KEY`.

**Klaar wanneer.** De Worker kan de sleutel lezen; `git grep` op de
repository vindt hem nergens.

### Stap 2.3 — `POST /spot`, met een strenge poort ervoor

**Waarom.** Een proxy die alles doorlaat is je sleutel weggeven met een extra
stap ertussen. De waarde zit in wat hij *weigert*.

**Wat.** Eén endpoint dat precies de vijf verplichte velden en de vier
optionele aanneemt — `activator`, `spotter`, `frequency_khz`, `mode`,
`reference`, plus `remarks`, `latitude`, `longitude`, `dryrun`. Al de rest
wordt weggegooid, niet doorgestuurd. `source` zetten we zelf vast op `DIANA`,
zodat WWFF kan zien waar een spot vandaan komt.

Daarvoor de controles die lokaal kunnen: callsign hoogstens 16 tekens en op
het juiste patroon, frequentie een getal binnen de amateurbanden, mode uit
een lijst, referentie op `^[A-Z0-9]{2,6}FF-\d{4}$`, opmerking hoogstens 100
tekens. Alles wat de Worker zelf afkeurt, kost niets van het gedeelde budget.

**Klaar wanneer.** Een geldige `curl` levert een 201 met `spot_id`, een
onvolledige een 400 met leesbare uitleg, en `"dryrun": true` een 200 zonder
dat er iets opgeslagen wordt.

### Stap 2.4 — `POST /agenda`

**Wat.** `activator_call`, `reference`, `utc_start`, `utc_end`, `pin`,
`poster`, plus optioneel `band`, `mode`, `remarks`, `dryrun`. Extra
controles: einde ná begin, begin binnen een maand vanaf nu, pin minstens vier
tekens, tijden in geldig UTC.

**Klaar wanneer.** Een geldige `curl` levert een 201 met `agenda_id`; een
begin over twee maanden wordt door de Worker zelf geweigerd zonder dat er een
aanvraag naar WWFF gaat.

### Stap 2.5 — CORS en de preflight

**Waarom.** De app stuurt `Content-Type: application/json`, dus de browser
stuurt eerst een `OPTIONS`. Zonder antwoord daarop komt er nooit een POST.

**Wat.** `Access-Control-Allow-Origin` beperkt tot jouw eigen adressen —
`https://diana-onff.github.io` en later je eigen domein — en een nette
`OPTIONS`-afhandeling. Buiten een browser is een `Origin`-header te
vervalsen, dus dit is een drempel en geen slot. Het echte slot is stap 2.6.

**Klaar wanneer.** Vanuit de gepubliceerde app lukt een aanvraag, vanuit een
willekeurige andere pagina niet.

### Stap 2.6 — Snelheidsbeperking, twee lagen

**Waarom.** De belangrijkste stap van de hele fase. Eén script kan het
gedeelde budget leegtrekken en daarmee ook alle andere Spotline-gebruikers
blokkeren.

**Wat.**

- **Per IP:** ongeveer vijf spots per tien minuten en een handvol agenda's
  per dag. Ruim voor een echte activator, krap voor een script.
- **Globaal:** een harde bovengrens voor Diana als geheel, bewust ver onder
  die van WWFF — bijvoorbeeld veertig per minuut.

Voor de tellers is Cloudflare KV genoeg; een Durable Object is exacter maar
hier overdreven. **Let op de eigen limiet van KV: 1.000 schrijfbewerkingen
per dag op het gratis plan.** Alleen tellen wat de validatie doorstaat en
werkelijk naar WWFF gaat — een preflight, een afgekeurd formulier of een
geblokkeerde herkomst schrijft niets. Voor de grove afscherming kan de gratis
Rate-Limiting-regel van Cloudflare zelf dienen, die raakt KV niet aan.

**Klaar wanneer.** Een lus van honderd aanvragen loopt tegen een 429 aan van
de Worker, niet van WWFF.

### Stap 2.7 — De noodschakelaar

**Waarom.** Als WWFF ooit belt, of er blijkt misbruik, wil je binnen tien
seconden kunnen stoppen. Niet eerst een build draaien.

**Wat.** Een vlag in KV die de Worker bij elk verzoek uitleest. Staat hij
uit, dan antwoordt de Worker met een nette 503 en een uitleg die de app aan
de gebruiker kan tonen.

**Klaar wanneer.** `wrangler kv key put` zet het geheel aan en uit terwijl het
draait.

### Stap 2.8 — Uitloggen wat er niet in mag

**Waarom.** Een proxy ziet alles wat erdoor gaat. Dat is precies de reden om
er zorgvuldig mee te zijn.

**Wat.** Alleen tellers en statuscodes in de logs. Geen callsigns, geen
posities, geen opmerkingen.

**Klaar wanneer.** Er staat niets in de logs waarvan een gebruiker zou
schrikken.

### Stap 2.9 — Documentatie van deze fase

Een nieuw `docs/SPOTLINE.md`: welke API, waarom er een proxy is, hoe de
sleutel beheerd wordt, wat de limieten zijn en waarom juist die, en hoe je de
noodschakelaar bedient. Plus `worker/README.md` voor wie de Worker moet
onderhouden. En in `INSTALL.md` het punt over de Worker invullen.

---

# Fase 3 — Zelf spotten via de Worker

### Stap 3.1 — Referenties controleren zonder de API

**Waarom.** Er ís een `GET /api/references/validate`, maar die aanroepen
tijdens het typen kost aanvragen uit het gedeelde budget, en langzaam ook nog.
We hebben de volledige WWFF-directory al in `data/` staan.

**Wat.** De controle verhuist naar de app zelf, tegen onze eigen gegevens.
Onmiddellijk antwoord, nul verbruik. De validate-endpoint gebruiken we hooguit
één keer per build als controle dat onze eigen lijst nog klopt. Dit vervangt
meteen de aanroep naar het ongedocumenteerde
`spots.wwff.co/api/references/validate` die nu in `ARCHITECTURE.md` staat.

**Klaar wanneer.** Een fout referentienummer wordt afgekeurd voor je klaar
bent met typen, zonder netwerkverkeer.

### Stap 3.2 — Controleren, dan versturen

**Wat.** De knop "Controleren" stuurt met `"dryrun": true` en toont wat WWFF
ervan vindt. Pas daarna wordt "Versturen" actief. Niet automatisch allebei —
dat verdubbelt het verbruik zonder dat iemand er iets aan heeft.

### Stap 3.3 — Echte bevestigingen en echte fouten

**Wat.** Bij een 201 tonen we het `spot_id`, en de melding zegt *aangekomen*
in plaats van *weggestuurd*. Bij een 400 de uitleg van WWFF zelf, bij een 401
een duidelijke melding dat de proxy een sleutelprobleem heeft — jouw probleem,
niet dat van de gebruiker — en bij een **409 dubbele spot** een geruststellende
melding in plaats van een fout. Dat laatste is precies wat je nodig hebt bij
een wankele verbinding op een berg: je drukt twee keer, en de app zegt "die
stond er al".

### Stap 3.4 — De terugval

**Wat.** De bestaande formulierpost naar `/spots/store` blijft in de code als
terugval, met een zichtbare melding dat je dan geen bevestiging krijgt.

**Klaar wanneer.** Met de Worker uitgeschakeld kan je nog altijd spotten.

### Stap 3.5 — Tests

Een `build/tests/test_spot.py` in dezelfde stijl als de rest, met een
nagebootste Worker: 201, 400, 409, 503 en een netwerkfout. De test mag nooit
de echte API raken.

### Stap 3.6 — Documentatie van deze fase

`USER_GUIDE.md`: spotten geeft nu een echte bevestiging, en wat de
foutmeldingen betekenen. `ARCHITECTURE.md` §2.3 krijgt de schrijfkant erbij.

---

# Fase 4 — Agenda aanmaken

### Stap 4.1 — Het scherm

**Wat.** Activator, referentie, begin en einde in UTC, banden, modes,
opmerking. De referentie wordt gecontroleerd zoals in stap 3.1, en het
formulier vult zichzelf zoveel mogelijk in vanuit wat de app al weet.

**Klaar wanneer.** Je kan een activatie voor volgende zaterdag aankondigen
zonder naar de website te gaan.

### Stap 4.2 — De pin bewaren

**Waarom.** Die pin heb je nodig om je agenda later via het web te bewerken,
en je bent hem kwijt precies wanneer je hem nodig hebt.

**Wat.** De app bewaart per aangemaakte agenda het `agenda_id`, de referentie,
de datum en de pin lokaal, en toont dat lijstje in het scherm.

### Stap 4.3 — De grens van een maand

**Wat.** De datumkiezer laat niets verder dan een maand toe en zegt waarom.

### Stap 4.4 — Tests

Zelfde aanpak als 3.5, met de randgevallen: einde vóór begin, begin over twee
maanden, pin te kort.

### Stap 4.5 — Documentatie van deze fase

`USER_GUIDE.md` en `ARCHITECTURE.md` voor het agendascherm en het bewaren van
de pin.

---

# Fase 5 — Naar productie

### Stap 5.1 — De Diana-sleutel erin

`wrangler secret put WWFF_API_KEY` met de sleutel uit stap 0.1, en het
doeladres in `wrangler.toml` van dev naar `https://spots.wwff.co`.

### Stap 5.2 — Limieten scherp zetten

Op de testomgeving mochten ze ruim staan. Nu niet meer. De waarden vastleggen
met een korte verantwoording in `worker/README.md`: waarom deze getallen, en
wat je zou aanpassen als het te krap blijkt.

### Stap 5.3 — De noodschakelaar echt uitproberen

Een noodrem die je nooit getest hebt, is geen noodrem. Uitzetten, kijken wat
de app doet, weer aanzetten. De app hoort een nette melding te tonen en terug
te vallen op de formulierpost.

### Stap 5.4 — Opvolging

Eén keer per week even naar de Cloudflare-tellers kijken, de eerste maand.
Niet meer dan dat — als de limieten kloppen, hoor je er niets van.

### Stap 5.5 — Documentatie van deze fase

`DEPLOY.md` en `INSTALL.md`: de Worker hoort bij de eerste opzet van een
nieuwe omgeving, net als Pages en de workflowrechten. En `docs/SPOTLINE.md`
bijwerken van dev naar productie.

---

# Fase 6 — `app.js` en `app.css` verder opsplitsen in modules (later, nog niet uitvoeren)

**Nog niet uitvoeren.** Deze fase staat hier genoteerd zodat ze niet vergeten
wordt tegen dat de rest van dit plan is afgewerkt. Bij Stap 1.3 werd deze
vraag bewust opengelaten ("Of `app.js` daarna nog verder opgesplitst wordt is
een aparte beslissing... eerst de knip die zeker goed is, dan pas nadenken
over de indeling") — dit is die beslissing: ja, en wel zo.

### Stap 6.1 — JavaScript per functionaliteit, niet in één bestand

**Wat.** `web/app.js` (na Stap 1.3 al één apart bestand, maar nog steeds
bijna vijfduizend regels) wordt verder opgesplitst in een map, bijvoorbeeld
`web/js/`, met per functionaliteit of module een eigen bestand — kaart,
spots, beheerscherm, instellingen, service-worker-registratie, en wat verder
logisch samenhoort. Alle functies van één functionaliteit horen dan in
hetzelfde bestand. Dit is **herordenen, geen herschrijven**: geen enkele
functie verandert van inhoud of gedrag.

**Waarom.** Eenvoudiger onderhoud, en het helpt een volgende ontwikkelaar
sneller zijn weg te vinden in de code. Een wijziging aan bijvoorbeeld het
beheerscherm raakt dan ook niet toevallig de kaartcode in dezelfde diff.

**Wat er meeverandert.** `web/index.html` verwijst dan naar de losse
bestanden in plaats van naar één `app.js` — de laadvolgorde (of een
module-aanpak) moet behouden blijven zodat functies die van elkaar afhangen
niet stuklopen. Ook `web/sw.js` (`SHELL_FILES`) en `build/site.sh` (het
versiestempel, nu gezocht in `app.js`) moeten mee-aangepast worden naar de
nieuwe bestandsnamen en -mappen.

### Stap 6.2 — CSS in een eigen map

**Wat.** `web/app.css` verhuist naar een eigen map, bijvoorbeeld `web/css/`,
en mag daar eventueel ook verder opgesplitst worden per onderdeel van de app.
`web/index.html` verwijst daarna naar de nieuwe locatie(s).

**Klaar wanneer (voor beide stappen).** De elf browsertests draaien nog
altijd groen, de app werkt nog altijd offline (vliegtuigicoon aan), en er is
geen enkele functionele wijziging — enkel een andere bestandsindeling.

---

# Wat waar staat, samengevat

| Wat | Waar | Publiek? |
|---|---|---|
| De API-sleutel | Cloudflare secret | nee, en nergens anders |
| Het bron-KMZ | `diana-onff/diana-source` | **nee**, privé |
| Het leestoken voor die repo | secret in `diana-onff/diana-onff.github.io` | nee |
| De app, de data, de workflows | `diana-onff/diana-onff.github.io` | ja |
| De Worker-code | `worker/` in de publieke repo | ja, mag |
| Het adres van de Worker | in `web/index.html` | ja, onvermijdelijk |
| De limieten en de noodschakelaar | Cloudflare KV | nee |
| De omgezette grenzen | `data/onff.geojson` | ja — dat ís de app |

De regel die alles samenvat: **een geheim mag gebruikt worden om iets op te
halen, nooit om in de uitgeleverde bundel terecht te komen.** Dat geldt voor
de Worker, en het gold al voor `ONFF_REFS_CSV` in de nachtelijke build.

# Volgorde en tijd

Fase −1 gaat vóór alles, want elk adres dat we daarna vastleggen moet meteen
het juiste zijn. Vraag om dat stappenplan wanneer je eraan begint.

Fase 0 is jouw huiswerk. Stap 0.4 — de installatiehandleiding schrijven en
uitproberen — is daarvan het grootste stuk en het minst leuke, maar het is de
enige stap die het project overdraagbaar maakt.

Fase 1 kan daar volledig parallel mee lopen.

Fase 2 is het echte werk en staat los van de app: die kan af zijn voor er één
regel in `web/index.html` verandert. Fase 3 is klein zodra Fase 2 werkt.
Fase 4 is het meeste nieuw scherm en het minste risico. Fase 5 is een halve
dag, waarvan de helft testen.

---

**Uitgevoerd op 2026-09-13 — v1.8.0.** Vier dingen in één release, op vraag van
Kristof:

- **Banden-dropdown bij aankondigen.** Het veld "Band" was vrije tekst met
  "20m" als voorbeeld; iedereen verzon dus zijn eigen schrijfwijze. Nu een
  keuzelijst, met in Instellingen de keuze tussen de volledige lijst (160m tot
  23cm — activaties op 2m en 70cm bestaan) en enkel de zes HF-banden. Die lijst
  staat bewust los van `BANDS` in `rules.js`: die draagt bandgrenzen en
  WWFF-frequenties voor het bandplan en stopt bij 10m.
- **Vijf eigen snelknoppen bij een spot.** De drie vaste chips ("5W QRP",
  "EFHW", "QSY soon") zijn vervangen door vijf vrij invulbare velden in
  Instellingen, met `5W / QRP / EFHW / QSY soon / Vertical` als startwaarden.
  Ze worden als één JSON-sleutel bewaard, niet als vijf losse: anders is een
  veld dat je bewust leegmaakt niet te onderscheiden van een veld dat nooit is
  ingevuld, en kruipt de standaardwaarde er bij de volgende start weer in. Op
  het spotscherm staat een discreet ⚙ achteraan de rij dat rechtstreeks naar
  die instelling springt.
- **Spotslijst leest nu nieuwste eerst.** `renderSpots()` sorteerde op afstand
  zodra er een GPS-fix was, en duwde daarbij de ouderdom van de rij af om
  plaats te maken voor de peiling. Op een lijst die om de 30 s ververst en
  enkel het laatste uur toont, is "wanneer" net wat je komt lezen. Nu altijd
  op tijd gesorteerd, met ouderdom én afstand op dezelfde rij.
- **Heatmap eruit, "In de buurt" erin.** Zie `docs/ARCHITECTURE.md §2.2` voor
  de volledige redenering; kort: de heatmap las een gepubliceerde Google Sheet
  met één tabblad per jaar, ging zeven jaar terug, en kon "niet geactiveerd"
  niet onderscheiden van "staat niet in deze sheet". Resultaat: 205
  referenties met cijfers en 741 als "nooit geactiveerd" rood gekleurd, van de
  946 — terwijl `data/onff-activity.json`, dat al in dezelfde release
  meereist, er 926 met QSO-totaal én laatste activatie heeft. ONFF-0002 heeft
  2343 QSO's en een activatie in 2024 en werd als nooit aangeraakt getoond.
  Het nieuwe scherm toont de 25 dichtstbijzijnde referenties met afstand,
  peiling, QSO-aantal en laatste activatie, te ordenen op afstand / langst
  onaangeroerd / minste QSO's, en leest enkel dat lokale bestand. Meegenomen:
  de kleuring van de gebieden op de kaart verdwijnt mee (bewuste keuze,
  minste werk), net als het paneel dat je half kon wegschuiven — een gewoon
  volledig scherm heeft niets weg te schuiven. `nearby.js` laadt niets zelf
  maar gebruikt `activityOf()` uit `map-data.js`, zodat de regel over de ene
  onmogelijke datum (jaar 1059) op één plaats staat.

Tests: `test_heat.py` vervangen door `test_nearby.py` (18 checks, met
ONFF-0002 bij naam als regressiewacht en een controle dat er niets meer naar
Google Sheets vertrekt); `test_swipe.py` sectie 4 herschreven; band-, chip- en
sorteercontroles toegevoegd aan `test_agenda.py`, `test_spot.py` en
`test_spotsfilter.py`. Volledige suite groen (`test_directory.py` vraagt een
lokale `wwff_directory.csv` en slaat over — geen regressie). Documentatie
bijgewerkt: `README.md`, `docs/ARCHITECTURE.md` (§2.2 herschreven als
beslissing in plaats van beschrijving), `docs/USER_GUIDE.md`,
`docs/DEVELOPER.md`, `docs/INSTALL.md`, `build/tests/README.md`. Alle interne
markdown-links opnieuw geprogrammeerd nagelopen: allemaal geldig.

**Nog open, bewust niet meegenomen:** de 17 `adm.*`-sleutels die in fr/de/da/
it/es ontbreken en daar naar het Nederlands terugvallen (bestond al voor deze
ronde), en punt 2 van de GPS-fix (`watchPosition()` met een
nauwkeurigheidsdrempel, voor het koude-fix-probleem uit Waasmunster).

---

**Uitgevoerd op 2026-09-13 — v1.9.0.** Punt 2 van de GPS-fix, plus twee dingen
die eruit volgden.

- **De positie zelf, niet de rand** (`geo.js`). Punt 1 (v1.7.1) ging over de
  foutmarge rond een grens. Dit gaat over de fix die binnenkomt. Diana vroeg
  met `getCurrentPosition` één keer om een positie en nam het eerste antwoord,
  met `maximumAge: 5000` erbij, zodat zelfs een fix van seconden oud meetelde.
  Een GPS-chip die net wakker wordt heeft nog geen satellieten en het
  antwoord komt dan uit wifi en zendmasten — honderden meters mis, met
  dezelfde stelligheid gebracht. Dat was Waasmunster: de grenscontrole klopte,
  de positie niet. Nu `watchPosition` met `maximumAge: 0`: de fixes komen in
  golven binnen, de marker volgt mee, maar de vraag "sta ik erin" wordt pas
  beantwoord als de nauwkeurigheid onder 25 m zit, of na 12 s met de scherpste
  die we kregen — en die gaat dan met haar echte foutmarge door `evaluate()`,
  dus ±400 m geeft "te dichtbij om te zeggen" in plaats van een stellige
  leugen. Daarna stopt de watch, anders kost hij de hele namiddag batterij.
  Nieuw `bestFix()` is de enige manier waarop Diana nog een positie vraagt;
  ook "locator uit GPS overnemen" in Instellingen liep in dezelfde val en
  gebruikt hem nu. Onderweg gevonden: nauwkeurigheid `0` las ik eerst als
  "onbekend", waardoor er 12 s gewacht werd op een fix die volgens de browser
  al perfect was — nul is een getal, geen ontbrekende waarde.
- **Straal voor "In de buurt" instelbaar** (10/25/50/100 km, standaard 25).
  Was een vast aantal van 25 stuks; de kop toonde daardoor de afstand van de
  verste in plaats van een straal. Boven de honderd rijen kapt het scherm af,
  en dan staat dat in de kop ("100 / 217") met een knop "Toon 100 meer" die
  eronder aanvult — geen pagina 2, want wegnavigeren van wat je aan het lezen
  bent en je plek terugzoeken is op een telefoon in een veld erger dan langer
  scrollen. Instellingen staat nu ook rechts als laatste in de balk.
- **Banden op de agenda zijn meervoudig.** Nagekeken in de echte
  `agendas.json` van Spotline: élke aankondiging daar zet meerdere banden in
  dat ene veld, komma en spatie, aflopende golflengte ("40m, 20m, 17m, 15m").
  Eén band was dus de uitzondering, en Diana deed precies dat. Nu een rij
  aantikbare chips; de selectie vertrekt in bandvolgorde, niet in de volgorde
  waarin je tikte. Bij spotten blijft het één band — dat is één signaal op één
  frequentie op één moment.

Tests: nieuw `test_gps_watch.py` (17 checks) met een nagebootste geolocatie die
van grof naar fijn convergeert, op een punt waar grof en fijn aan
weerszijden van een echte ONFF-grens vallen; `getCurrentPosition` gooit daarin
een fout, zodat terugvallen op één keer vragen meteen opvalt. Verder
uitgebreid: `test_nearby.py` (straal, afkapping, "toon meer"),
`test_agenda.py` (meerdere banden, bandvolgorde, behoud bij wisselen van
lijst). Volledige suite groen. `USER_GUIDE.md` en `DEVELOPER.md` bijgewerkt.

**Nog open:** de 17 `adm.*`-sleutels die in fr/de/da/it/es naar het Nederlands
terugvallen (bestond al voor deze ronde).

---

**Uitgevoerd op 2026-09-13 — v1.9.1.** Eerste steen van de landenuitbreiding,
het stuk dat geen voorbeeldbestand nodig heeft.

De spotsfilter had twee waarden die hetzelfde deden: `'onff'` én de
programmacode `'ONFF'`. Dat eerste was een speciaal geval voor het ene land
waarmee Diana toevallig begon. Het is weg; de eerste knop draagt nu een echte
programmacode, standaard die van je roepnaam (PA0… → PAFF, DL1… → DLFF, ON3…
→ ONFF), en volgt mee zodra je in Instellingen een ander land kiest. Wat
onder de oude waarde bewaard stond wordt bij het lezen omgezet.

Nieuw `PREFIX_PROGRAM` in `settings.js`, naast het bestaande `PREFIX_HOME`.
Bewust geen gok waar het twijfelachtig is: WWFF heeft in zijn eigen lijst
alleen GXFF (Engeland) en geen aparte Schotse of Welshe ploeg, dus G/M/2E
gaan daarheen. Een test controleert elke code in die tabel tegen
`wwff-programs.json` — een verzonnen programmacode zou de lijst stilletjes
leegfilteren.

Gedragsverandering die een bestaande test omkeerde: vroeger was géén knop
actief zodra je in Instellingen een land koos, want de knop kón alleen ONFF
tonen. Nu toont hij dat land en staat hij aan.

Nog te doen voor de landenuitbreiding, in volgorde: (1) de pijplijn per land
maken — `bron/<PROG>/` in de privé-repo, `data/zones/<prog>.geojson` plus een
`data/countries.json` met wat beschikbaar is, per land bouwen zodat een kapot
bestand de rest niet meesleurt; (2) tweede land erbij zodra er een
voorbeeldbestand is, met het inlaadscherm, meerdere landen tegelijk, bewuste
offline-keuze per land, en punten verbergen waar een vlak bestaat; (3)
adminpagina met verplichte landkeuze bij uploaden en PR naar
`incoming/<PROG>/`.

---

**Uitgevoerd op 2026-09-13 — v1.10.0. Ronde 1 van de landenuitbreiding: de
pijplijn generiek, ONFF nog altijd het enige land.** Bewust niets zichtbaars
veranderd, zodat een afwijkend formaat bij het eerste buitenlandse bestand aan
het licht komt op een moment dat er nog niets stuk kan.

- **Buildscript per land.** `--program` bestond al maar betekende "welke
  voorvoegsels uit de directory"; nu bepaalt het ook hoe referenties in het
  KMZ herkend worden (`REF_RE` stond hardgecodeerd op ONFF) en hoe de uitvoer
  heet. Eén land per run, uitvoer naar `data/zones/<prog>.geojson` en
  broertjes. Een code die geen WWFF-programma is, stopt de build.
- **`data/countries.json`**, samengevoegd en nooit herschreven: een build voor
  Nederland leest het manifest, vervangt zijn eigen regel en zet de rest terug.
  Dat is het enige gedeelde bestand en dus de enige plek waar een slordige
  herschrijving België kon laten verdwijnen — vandaar een test die niets
  anders doet dan twee landen bouwen en kijken of de eerste de tweede
  overleeft.
- **Vlak verslaat punt, nu ook in de data.** Het wereldpuntenbestand liet
  alleen het land weg dat op dat moment gebouwd werd, dus na een
  PAFF-build stonden de Belgische referenties er weer als stip in. Nu wordt
  alles uit het manifest weggelaten, en de app filtert er bij het tekenen nog
  eens overheen voor het geval het wereldbestand ouder is dan een land.
- **De app leest het manifest** en laadt meerdere landen tegelijk in dezelfde
  `zones`/`index`/`activity`. Standaard het land van je roepnaam, want alles
  laden is geen optie — één land is megabytes. Een land dat niet laadt sleurt
  de andere niet mee. Zonder manifest valt hij terug op de oude Belgische
  bestandsnamen, zodat app en data in willekeurige volgorde bijgewerkt kunnen
  worden zonder lege kaart tussenin.
- **Workflow** loopt over `bron/source/<PROG>/`-mappen, elk zijn nieuwste KMZ.
  Een los KMZ in de map wordt nog altijd als ONFF gelezen, zodat de
  bronrepo niet op dezelfde dag herschikt hoeft te worden. De uitvoercontrole
  leest het manifest in plaats van één vaste bestandsnaam, en klaagt
  uitdrukkelijk als een land dat erin staat zijn bestand kwijt is.
- **Service worker** bewaart het manifest en de globale bestanden vooraf; de
  landbestanden worden bij het eerste ophalen gecachet. Ze allemaal vooraf
  binnenhalen zou Zweden meesleuren voor twee Belgische reservaten — de
  bewuste offline-keuze per land is ronde 2.

Ook meegenomen, gemeld tijdens de rit: de spotsfilter sprong terug naar België
zodra je Wereldwijd aantikte. "Welk land staat op de knop" was gelijkgesteld
aan "welk filter staat aan", en op Wereldwijd is er geen filter, dus viel hij
terug op de roepnaam. Het laatst gekozen land wordt nu apart onthouden.

Nieuwe tests: `test_countries.py` (25 checks, bouwt twee miniatuurlanden uit
een zelfgemaakt KMZ en een nagemaakte directory) en `test_multicountry.py`
(16 checks, de app met een verzonnen tweede land erbij). Volledige suite groen:
17 bestanden, 357 checks.

**Na het uploaden:** de eerstvolgende nachtelijke build schrijft
`data/countries.json` en `data/zones/*`. Tot dan draait de app op de
terugvalweg. De oude `data/onff*.json`/`geojson` blijven staan tot je ze
weggooit — dat mag zodra die eerste build geslaagd is.

Ronde 2 (tweede land, inlaadscherm, offline-keuze) wacht op een
voorbeeldbestand; ronde 3 is de adminpagina met verplichte landkeuze.

---

**Uitgevoerd op 2026-09-13 — v1.11.0. Ronde 3 vervroegd: de adminpagina vraagt
nu naar het land.** Naar aanleiding van de vraag "heb je al iets voor de
adminpagina" — het antwoord was nee, maar bij het nakijken bleek er een
valstrik te zijn ontstaan. Na ronde 1 leest de build een los KMZ in de
wachtruimte als ONFF. Upload je daar een Duits bestand, dan zou dat als
Belgisch omgezet worden. Het loopt stuk in plaats van rommel te maken (nul
gevonden referenties → de uitvoercontrole faalt), maar het hoort niet te
kunnen, en de landkeuze hangt niet af van het voorbeeldbestand. Dus meteen
gedaan.

- **Landkeuze bij het uploaden, verplicht.** Elk WWFF-programma staat in de
  lijst, met de landen die Diana al heeft bovenaan. Bewust géén
  voorselectie: een verkeerde gok zet de release van het ene land boven op
  die van het andere. Zolang er geen land gekozen is, blijft de verzendknop
  dicht.
- **Een map per land**, aan beide kanten: het bestand belandt in
  `incoming/<PROG>/` en verhuist bij publiceren naar `source/<PROG>/`. De
  verplaatsfunctie werkt nu op een pad binnen de wachtruimte in plaats van op
  een kale bestandsnaam, dus de landmap reist vanzelf mee. Een bestand van
  vóór deze indeling — kale naam — gaat nog altijd rechtstreeks naar
  `source/`.
- **De opruimkaart kijkt in de landmappen.** Die luisterde alleen naar het
  bovenste niveau van `incoming/` en zou met landmappen leeg gebleven zijn
  terwijl er bestanden stonden te wachten. Nu één boomopvraging die alles
  vindt, op welke diepte dan ook.
- De pull request draagt het land in titel en tekst.
- De workflow hoefde niet aangepast: de landontdekking uit ronde 1 loopt al
  over `<map>/*/` en vindt `incoming/DLFF/` vanzelf.

Nieuwe test `test_adminupload.py` (14 checks): GitHub is vervangen door een
recorder, dus geen token en geen netwerk, en er wordt gecontroleerd wélke
paden de pagina schrijft — een fout daarin schrijft in de verkeerde map van
een echte repo. Volledige suite groen: 18 bestanden, 371 checks.

Blijft over voor ronde 2: het inlaadscherm om landen te kiezen, de bewuste
offline-keuze per land, en het tweede land zelf — dat wacht op een
voorbeeldbestand.

---

**Uitgevoerd op 2026-09-14 — v1.11.2.** Twee meldingen uit het veld.

- **"Nieuwe versie beschikbaar" bleef onzichtbaar** tot je terugging naar de
  kaart. De meldingsbalk stond op z-index 6 en de volledige schermen op 8, dus
  Instellingen lag er gewoon overheen — en je vraagt die controle nu net vanuit
  Instellingen. Eerste poging: de balk naar 9. Dat brak het aankondigingsscherm,
  want de bevestiging na het versturen dekte dan de knoppen eronder af; de
  agenda-test liep vast op een knop die niet meer aanklikbaar was. Nu heeft
  alleen een melding die over de app zélf gaat (nieuwe versie, up-to-date, of
  de fout bij het controleren) een extra klasse die hem boven de schermen tilt.
  De rest blijft eronder, waar hij hoort.
- **Een gebied bleef oranje omlijnd** na "In de buurt" → gebied kiezen → Map.
  Map is het beginscherm en daar hoort niets uitgelicht te staan. Bij het
  repareren bleek er al een `clearSelection()` te bestaan die alleen de
  omlijning wiste en níét de selectie — en die wordt aangeroepen door
  `selectPoint()`, meteen nadat die een selectie heeft gezét. Mijn tweede
  functie met dezelfde naam won stilzwijgend en deed het verkeerde. Nu twee
  eerlijke namen: `clearOutline()` voor wat de oude deed, `clearSelection()`
  voor beide, en de Map-knop sluit ook de open panelen.

Mijn eigen testlus las ondertussen een afgebroken run als geslaagd: geen
kruisjes betekent niet geslaagd. `test_agenda` zakte van 42 naar 26 controles
en meldde toch OK — dat is hoe de regressie hierboven bijna meeging in de zip.
De lus eist nu "ALL OK" in de uitvoer. 18 bestanden, 377 controles, allemaal
echt tot het einde gedraaid.

---

**Uitgevoerd op 2026-09-14 — v1.12.0.** Twee echte
voorbeeldbestanden binnen: een volledige OZFF-export (Denemarken, 331
gebieden) en een DLFF-export (Duitsland, 1326 plaatsmerken). Onderzocht of
`kmz2geojson.py` ze zonder wijziging zou verwerken — dat is niet zo, en het
maakt meteen concreet waarom een controle bij het inlezen nodig is (zie
hieronder).

- **DLFF (Duitsland)**: zou wél doorlopen. Eén platte map "DLFF-Gebiete" met
  alle 1326 plaatsmerken er rechtstreeks in, elk keurig "DLFF-nnnn Naam", vier
  cijfers, één referentie met twee polygoondelen (DLFF-0915, hoort samengevoegd
  te worden — dat doet de bestaande code al). Enige gemis: geen tussenliggende
  mappen per Bundesland, dus elk gebied krijgt letterlijk "DLFF-Gebiete" als
  provincie in plaats van de Duitse deelstaat. Geen blokkerend probleem, wel
  een cosmetisch gat.
- **OZFF (Denemarken)**: zou vastlopen. `kmz2geojson.py` verwacht dat de KML
  begint met `<Document>` aan de wortel; dit bestand begint met `<Folder>`
  ("OZFF") met daarin 331 losse `<Document>`-knopen, één per gebied, elk met
  een propere "OZFF-nnnn Naam" (vier cijfers, allemaal kloppend). Zonder
  aanpassing stopt het script meteen met "KML has no Document root" — en zelfs
  als dat opgevangen wordt, zoekt de huidige lus alleen naar `<Folder>` als
  provincieniveau, en OZFF heeft daar geen enkele onder zitten: nul gebieden
  zouden weggeschreven worden, in plaats van een foutmelding.
- Referentienummers zelf zijn in beide bestanden 100% schoon (vier cijfers,
  overal), dus dat deel van de aanname klopt nog steeds wereldwijd.

**Wat er daarna gebouwd is.**

- **Drie vormen lezen in plaats van één.** De wortel mag nu `<Document>` óf
  `<Folder>` zijn. Mappen één niveau lager zijn provincies *als er meer dan
  één is* — een indeling in één is geen indeling, en `DLFF-Gebiete` in alle
  1326 Duitse gebieden als provincie schrijven leest als informatie terwijl
  het er geen is. Wat buiten die mappen hangt (de Deense vorm) wordt als één
  naamloze groep meegenomen in plaats van stilzwijgend overgeslagen. Het
  referentienummer wordt nog altijd op dezelfde manier gezocht, en dat dekt
  alle drie de vormen zonder te weten welke het is.
- **Een weigering met een reden.** Levert een omzetting nul gebieden op, dan
  stopt het script vóór er iets geschreven wordt, met exitcode 2 en een zin:
  welk programma de gebieden wél dragen ("dit is DLFF, je stuurde het als
  OZFF"), of dat er geen enkel gebied in zit, of een voorbeeld van de namen
  als de gebieden geen nummer dragen. Die zin gaat ook in `report.md`, zodat
  hij in de pull request en in het adminscherm terechtkomt en niet alleen in
  het logboek van de Action. De workflow verzamelt hem nu ook vóór hij de job
  laat falen.
- **Kristofs punt: controle bij het uploaden.** Het adminscherm pakt de KMZ
  op je eigen toestel uit — een KMZ is een zip — en leest het KML door tot de
  vraag beslist is. Eén geval sluit de verzendknop: er staan referenties van
  een ánder programma in en geen enkele van het jouwe. Dat is het enige geval
  waarin we het zeker weten. Niets gevonden, een onleesbare zip, een browser
  zonder `DecompressionStream`: dat wordt gezegd en je mag alsnog versturen.
  Een controle die niet te vertrouwen is om gelijk te hebben, mag niet
  vertrouwd worden om nee te zeggen.

Gemeten aan de echte bestanden: Denemarken 325 gebieden (1,35 MB), Duitsland
1325 (13,05 MB — 3,75 MB over de lijn), België onveranderd 946 met exact
dezelfde provincietelling als ervoor. De zes OZFF-gebieden die niet meekomen
hebben werkelijk geen polygoon in het bestand; die worden punten zodra de
WWFF-directory erbij komt.

Wat er níét in zit: de Duitse deelstaat en de Deense regio als provincie. Die
staan niet in de bestanden, dus daar is geen bron voor — beide landen krijgen
een leeg provincieveld in plaats van een verzonnen waarde.

Nieuwe test `test_kmlshapes.py` (23 checks, geen browser): alle drie de
vormen, plus het verkeerde land, gebieden zonder nummer en een bestand zonder
gebieden. `test_adminupload.py` kreeg de controle vóór het versturen erbij (21
checks). Volledige suite: 19 bestanden, 407 checks, allemaal tot "ALL OK"
gedraaid; `test_directory.py` slaat zichzelf over zolang er geen lokale
`wwff_directory.csv` is, zoals altijd.
