/* ================================================================== *
 * Regels > Regels: a selection from the WWFF Global Rules.
 *
 * The English is the WWFF text itself (v5.10, September 2025), with only
 * small language fixes. Every other language is Diana's own translation and
 * says so, with a link to the official rules: for rules, nobody should take a
 * translation for the official text.
 *
 * Kept here rather than in i18n-strings.js: it is one long text per language,
 * not short labels. A language missing here falls back to English.
 *
 * In a body paragraph:
 *   %EXAMPLE%    the log file name, drawn as an example box (rule 6.8)
 *   %LOGSEARCH%  the link to WWFF Logsearch
 *   %MAIL%       the address for logs from DXCC entities without WWFF
 * Everything here is written by Diana itself, so <b> is used for emphasis.
 * ================================================================== */
const RULES_URL = 'https://wwff.co/wwff_cont/uploads/2025/09/WWFF-Global-Rules-V_5.10.pdf';
const RULES_LOGSEARCH = 'https://wwff.co/logsearch/';
const RULES_MAIL = 'wwfflogs@winqsl.de';

const RULES_TEXT = {
  en: {
    sub: 'A selection from the WWFF rules, also valid for ONFF.',
    official: 'Full official WWFF rules',
    note: null,
    labels: {call: 'callsign', ref: 'reference', date: 'date (YYYYMMDD)', space: 'space'},
    groups: [
      {title: 'The reference area', rules: [
        {n: '3.5', title: 'References bordering another reference area', body: [
          'Activators are only permitted to activate <b>one reference area at a time</b>. There are some instances where a WWFF reference area borders another. Care must be taken to ensure that the <b>correct reference is announced</b>.']},
        {n: '3.6', title: 'References contained within another reference area', body: [
          'In certain cases, a WWFF reference area may be located within, or entirely encompassed by, another WWFF reference area. In such cases, operations shall be conducted under <b>only one WWFF reference area at any given time</b>.',
          'Where the activating position lies within the boundaries of multiple WWFF reference areas (e.g. a Nature Reserve and a Ramsar Reserve), the activator shall <b>select a single reference area</b> under which the operation will be conducted.',
          'Note that a second activity using a different reference number can only be started <b>after completing the first activity</b>.']},
        {n: '4.4', title: 'Working within the boundaries of the reference', body: [
          'While activating a WWFF reference area, <b>all equipment</b> (including antenna(s), transceiver(s), power supply(ies), etc.) must be <b>within the boundaries</b> of the relevant WWFF reference area.',
          'It is not sufficient for part of the station to be within the boundary of the reference area.']},
      ]},
      {title: 'QSOs', rules: [
        {n: '4.7', title: 'Accrual of 44 QSOs over multiple activations', body: [
          'The <b>44 QSOs</b> can be accrued <b>over multiple activations</b>. They do not have to be attained during one activation.',
          'For example: activate a WWFF reference area today and attain 22 QSOs. Then return a week later and attain a further 22 QSOs. You have now qualified the WWFF reference area.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Naming of logs', body: [
          'Electronic logs are to be named in the following way:',
          '%EXAMPLE%',
          'Using this file name is a very simple duplication check. Logs simply named XXFF-0123.adi, for example, trigger the "dupe check" when a log of the same name is uploaded.']},
        {n: '6.9', title: 'Uploading of logs by national co-ordinators', body: [
          'The national co-ordinator and/or log manager will in turn load all relevant information onto the WWFF Logsearch facility, which can be found at: %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs from DXCC entities not represented in WWFF', body: [
          'Logs from park activities in DXCC entities not represented in the current WWFF program can be sent to: %MAIL%.']},
      ]},
    ],
  },

  nl: {
    sub: 'Selectie uit de WWFF-regels, ook geldig voor ONFF.',
    official: 'Volledige officiële WWFF-regels',
    note: 'Vertaling door Diana. De Engelse tekst van WWFF geldt.',
    labels: {call: 'roepnaam', ref: 'referentie', date: 'datum (JJJJMMDD)', space: 'spatie'},
    groups: [
      {title: 'Het gebied', rules: [
        {n: '3.5', title: 'Referenties die aan een andere referentie grenzen', body: [
          'Activators mogen <b>maar één referentiegebied tegelijk</b> activeren. Soms grenst een WWFF-referentiegebied aan een ander. Let er dan goed op dat je de <b>juiste referentie aankondigt</b>.']},
        {n: '3.6', title: 'Referenties binnen een andere referentie', body: [
          'Soms ligt een WWFF-referentiegebied binnen een ander WWFF-referentiegebied, of wordt het er volledig door omsloten. Dan werk je op elk moment <b>onder slechts één WWFF-referentie</b>.',
          'Ligt je activatieplek binnen de grenzen van meerdere WWFF-referentiegebieden (bijvoorbeeld een natuurreservaat en een Ramsargebied), dan <b>kies je één referentiegebied</b> waaronder je de activatie uitvoert.',
          'Een tweede activiteit met een ander referentienummer mag pas beginnen <b>nadat de eerste afgerond is</b>.']},
        {n: '4.4', title: 'Werken binnen de grenzen van de referentie', body: [
          'Tijdens de activatie van een WWFF-referentiegebied moet <b>alle apparatuur</b> (antenne(s), transceiver(s), voeding(en) enzovoort) <b>binnen de grenzen</b> van dat gebied staan.',
          'Het volstaat niet dat een deel van het station binnen de grens staat.']},
      ]},
      {title: 'QSO\'s', rules: [
        {n: '4.7', title: '44 QSO\'s verspreid over meerdere activaties', body: [
          'De <b>44 QSO\'s</b> mag je <b>over meerdere activaties</b> verzamelen. Ze hoeven niet tijdens één activatie gemaakt te worden.',
          'Bijvoorbeeld: je activeert vandaag een WWFF-referentiegebied en maakt 22 QSO\'s. Een week later kom je terug en maak je er nog 22. Dan heb je dat referentiegebied gekwalificeerd.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Naam van de logbestanden', body: [
          'Elektronische logs krijgen een naam volgens dit patroon:',
          '%EXAMPLE%',
          'Die bestandsnaam dient als heel eenvoudige controle op dubbels. Een log met enkel een naam als XXFF-0123.adi zet de "dubbelcontrole" in gang zodra er een log met dezelfde naam opgeladen wordt.']},
        {n: '6.9', title: 'Opladen van logs door de nationale coördinator', body: [
          'De nationale coördinator en/of logbeheerder laadt op zijn beurt alle relevante gegevens op in WWFF Logsearch: %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs uit DXCC-landen zonder WWFF-programma', body: [
          'Logs van activiteiten in parken in DXCC-landen die geen deel uitmaken van het huidige WWFF-programma, kan je sturen naar: %MAIL%.']},
      ]},
    ],
  },

  fr: {
    sub: 'Sélection des règles WWFF, valables aussi pour l\'ONFF.',
    official: 'Règlement officiel complet du WWFF',
    note: 'Traduction par Diana. Le texte anglais du WWFF fait foi.',
    labels: {call: 'indicatif', ref: 'référence', date: 'date (AAAAMMJJ)', space: 'espace'},
    groups: [
      {title: 'La zone de référence', rules: [
        {n: '3.5', title: 'Références limitrophes d\'une autre référence', body: [
          'Les activateurs ne peuvent activer <b>qu\'une seule zone de référence à la fois</b>. Il arrive qu\'une zone de référence WWFF soit limitrophe d\'une autre. Il faut alors veiller à <b>annoncer la bonne référence</b>.']},
        {n: '3.6', title: 'Références situées dans une autre référence', body: [
          'Dans certains cas, une zone de référence WWFF peut se trouver à l\'intérieur d\'une autre zone de référence WWFF, ou être entièrement englobée par celle-ci. L\'activité se déroule alors à tout moment <b>sous une seule référence WWFF</b>.',
          'Si la position d\'activation se trouve dans les limites de plusieurs zones de référence WWFF (par exemple une réserve naturelle et un site Ramsar), l\'activateur <b>choisit une seule zone de référence</b> sous laquelle l\'activité est menée.',
          'Une deuxième activité avec un autre numéro de référence ne peut commencer <b>qu\'après la fin de la première</b>.']},
        {n: '4.4', title: 'Travailler à l\'intérieur des limites de la référence', body: [
          'Pendant l\'activation d\'une zone de référence WWFF, <b>tout l\'équipement</b> (antenne(s), émetteur-récepteur(s), alimentation(s), etc.) doit se trouver <b>à l\'intérieur des limites</b> de cette zone.',
          'Il ne suffit pas qu\'une partie de la station se trouve à l\'intérieur de la limite.']},
      ]},
      {title: 'QSO', rules: [
        {n: '4.7', title: '44 QSO répartis sur plusieurs activations', body: [
          'Les <b>44 QSO</b> peuvent être cumulés <b>sur plusieurs activations</b>. Il n\'est pas nécessaire de les réaliser en une seule activation.',
          'Par exemple : vous activez aujourd\'hui une zone de référence WWFF et faites 22 QSO. Une semaine plus tard, vous revenez et en faites 22 de plus. La zone de référence est alors qualifiée.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Nom des fichiers de log', body: [
          'Les logs électroniques doivent être nommés de la façon suivante :',
          '%EXAMPLE%',
          'Ce nom de fichier sert de contrôle très simple des doublons. Un log nommé simplement XXFF-0123.adi, par exemple, déclenche le « contrôle des doublons » lorsqu\'un log du même nom est envoyé.']},
        {n: '6.9', title: 'Envoi des logs par le coordinateur national', body: [
          'Le coordinateur national et/ou le gestionnaire des logs charge à son tour toutes les informations utiles dans WWFF Logsearch : %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs d\'entités DXCC sans programme WWFF', body: [
          'Les logs d\'activités dans des parcs d\'entités DXCC qui ne font pas partie du programme WWFF actuel peuvent être envoyés à : %MAIL%.']},
      ]},
    ],
  },

  de: {
    sub: 'Auswahl aus den WWFF-Regeln, gilt auch für ONFF.',
    official: 'Vollständige offizielle WWFF-Regeln',
    note: 'Übersetzung von Diana. Maßgeblich ist der englische Text des WWFF.',
    labels: {call: 'Rufzeichen', ref: 'Referenz', date: 'Datum (JJJJMMTT)', space: 'Leerzeichen'},
    groups: [
      {title: 'Das Referenzgebiet', rules: [
        {n: '3.5', title: 'Referenzen, die an eine andere Referenz grenzen', body: [
          'Aktivierer dürfen <b>nur ein Referenzgebiet gleichzeitig</b> aktivieren. Manchmal grenzt ein WWFF-Referenzgebiet an ein anderes. Dann ist darauf zu achten, dass die <b>richtige Referenz angegeben</b> wird.']},
        {n: '3.6', title: 'Referenzen innerhalb einer anderen Referenz', body: [
          'In manchen Fällen liegt ein WWFF-Referenzgebiet innerhalb eines anderen WWFF-Referenzgebiets oder wird ganz davon umschlossen. Dann wird zu jedem Zeitpunkt <b>unter nur einer WWFF-Referenz</b> gefunkt.',
          'Liegt der Standort innerhalb der Grenzen mehrerer WWFF-Referenzgebiete (zum Beispiel ein Naturschutzgebiet und ein Ramsar-Gebiet), <b>wählt der Aktivierer ein einziges Referenzgebiet</b>, unter dem die Aktivität läuft.',
          'Eine zweite Aktivität mit einer anderen Referenznummer darf erst <b>nach Abschluss der ersten</b> beginnen.']},
        {n: '4.4', title: 'Betrieb innerhalb der Grenzen der Referenz', body: [
          'Während der Aktivierung eines WWFF-Referenzgebiets muss sich die <b>gesamte Ausrüstung</b> (Antenne(n), Transceiver, Stromversorgung usw.) <b>innerhalb der Grenzen</b> dieses Gebiets befinden.',
          'Es reicht nicht, wenn sich nur ein Teil der Station innerhalb der Grenze befindet.']},
      ]},
      {title: 'QSOs', rules: [
        {n: '4.7', title: '44 QSOs über mehrere Aktivierungen', body: [
          'Die <b>44 QSOs</b> dürfen <b>über mehrere Aktivierungen</b> gesammelt werden. Sie müssen nicht in einer einzigen Aktivierung erreicht werden.',
          'Zum Beispiel: Du aktivierst heute ein WWFF-Referenzgebiet und machst 22 QSOs. Eine Woche später kommst du zurück und machst weitere 22 QSOs. Damit ist das Referenzgebiet qualifiziert.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Benennung der Logdateien', body: [
          'Elektronische Logs sind wie folgt zu benennen:',
          '%EXAMPLE%',
          'Dieser Dateiname dient als sehr einfache Dublettenprüfung. Logs, die zum Beispiel nur XXFF-0123.adi heißen, lösen die „Dublettenprüfung“ aus, wenn ein Log mit demselben Namen hochgeladen wird.']},
        {n: '6.9', title: 'Hochladen der Logs durch den nationalen Koordinator', body: [
          'Der nationale Koordinator und/oder Logmanager lädt seinerseits alle relevanten Angaben in WWFF Logsearch hoch: %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs aus DXCC-Gebieten ohne WWFF-Programm', body: [
          'Logs von Aktivitäten in Parks in DXCC-Gebieten, die im aktuellen WWFF-Programm nicht vertreten sind, können an folgende Adresse geschickt werden: %MAIL%.']},
      ]},
    ],
  },

  da: {
    sub: 'Udvalg af WWFF-reglerne, gælder også for ONFF.',
    official: 'De fulde officielle WWFF-regler',
    note: 'Oversat af Diana. WWFF\'s engelske tekst er gældende.',
    labels: {call: 'kaldesignal', ref: 'reference', date: 'dato (ÅÅÅÅMMDD)', space: 'mellemrum'},
    groups: [
      {title: 'Referenceområdet', rules: [
        {n: '3.5', title: 'Referencer, der grænser op til en anden reference', body: [
          'Aktivatorer må kun aktivere <b>ét referenceområde ad gangen</b>. Nogle gange grænser et WWFF-referenceområde op til et andet. Så skal man sørge for at <b>annoncere den rigtige reference</b>.']},
        {n: '3.6', title: 'Referencer inden i en anden reference', body: [
          'I visse tilfælde ligger et WWFF-referenceområde inden i et andet WWFF-referenceområde eller er helt omsluttet af det. Så foregår aktiviteten til enhver tid <b>under kun én WWFF-reference</b>.',
          'Ligger aktiveringsstedet inden for grænserne af flere WWFF-referenceområder (f.eks. et naturreservat og et Ramsar-område), <b>vælger aktivatoren ét referenceområde</b>, som aktiviteten foregår under.',
          'En anden aktivitet med et andet referencenummer må først begynde, <b>når den første er afsluttet</b>.']},
        {n: '4.4', title: 'Arbejde inden for referencens grænser', body: [
          'Under aktivering af et WWFF-referenceområde skal <b>alt udstyr</b> (antenne(r), transceiver(e), strømforsyning(er) osv.) være <b>inden for grænserne</b> af området.',
          'Det er ikke nok, at en del af stationen er inden for grænsen.']},
      ]},
      {title: 'QSO\'er', rules: [
        {n: '4.7', title: '44 QSO\'er fordelt over flere aktiveringer', body: [
          'De <b>44 QSO\'er</b> kan samles <b>over flere aktiveringer</b>. De behøver ikke at blive opnået under én aktivering.',
          'For eksempel: Du aktiverer et WWFF-referenceområde i dag og får 22 QSO\'er. En uge senere vender du tilbage og får yderligere 22 QSO\'er. Så er referenceområdet kvalificeret.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Navngivning af logfiler', body: [
          'Elektroniske logs skal navngives på denne måde:',
          '%EXAMPLE%',
          'Filnavnet fungerer som en meget enkel kontrol af dubletter. Logs, der blot hedder f.eks. XXFF-0123.adi, udløser "dublettjekket", når en log med samme navn bliver uploadet.']},
        {n: '6.9', title: 'Upload af logs ved den nationale koordinator', body: [
          'Den nationale koordinator og/eller logansvarlige lægger derefter alle relevante oplysninger ind i WWFF Logsearch: %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs fra DXCC-lande uden WWFF-program', body: [
          'Logs fra parkaktiviteter i DXCC-lande, der ikke er med i det nuværende WWFF-program, kan sendes til: %MAIL%.']},
      ]},
    ],
  },

  it: {
    sub: 'Selezione delle regole WWFF, valide anche per ONFF.',
    official: 'Regolamento ufficiale WWFF completo',
    note: 'Traduzione di Diana. Fa fede il testo inglese del WWFF.',
    labels: {call: 'nominativo', ref: 'referenza', date: 'data (AAAAMMGG)', space: 'spazio'},
    groups: [
      {title: 'L\'area di riferimento', rules: [
        {n: '3.5', title: 'Referenze confinanti con un\'altra referenza', body: [
          'Gli attivatori possono attivare <b>una sola area di riferimento alla volta</b>. In alcuni casi un\'area di riferimento WWFF confina con un\'altra. Bisogna quindi fare attenzione ad <b>annunciare la referenza corretta</b>.']},
        {n: '3.6', title: 'Referenze contenute in un\'altra referenza', body: [
          'In alcuni casi un\'area di riferimento WWFF può trovarsi all\'interno di un\'altra area di riferimento WWFF, o esserne interamente compresa. In questi casi si opera in ogni momento <b>sotto una sola referenza WWFF</b>.',
          'Se la posizione di attivazione si trova entro i confini di più aree di riferimento WWFF (ad esempio una riserva naturale e un sito Ramsar), l\'attivatore <b>sceglie una sola area di riferimento</b> sotto cui condurre l\'attività.',
          'Una seconda attività con un numero di referenza diverso può iniziare solo <b>dopo aver concluso la prima</b>.']},
        {n: '4.4', title: 'Operare entro i confini della referenza', body: [
          'Durante l\'attivazione di un\'area di riferimento WWFF, <b>tutta l\'attrezzatura</b> (antenna/e, ricetrasmettitore/i, alimentazione/i, ecc.) deve trovarsi <b>entro i confini</b> dell\'area.',
          'Non basta che solo una parte della stazione si trovi entro il confine.']},
      ]},
      {title: 'QSO', rules: [
        {n: '4.7', title: '44 QSO distribuiti su più attivazioni', body: [
          'I <b>44 QSO</b> possono essere raccolti <b>in più attivazioni</b>. Non è necessario ottenerli in un\'unica attivazione.',
          'Ad esempio: oggi attivi un\'area di riferimento WWFF e fai 22 QSO. Una settimana dopo torni e ne fai altri 22. A quel punto l\'area di riferimento è qualificata.']},
      ]},
      {title: 'Log', rules: [
        {n: '6.8', title: 'Nome dei file di log', body: [
          'I log elettronici devono essere denominati in questo modo:',
          '%EXAMPLE%',
          'Questo nome di file serve come controllo molto semplice dei duplicati. Un log chiamato semplicemente XXFF-0123.adi, per esempio, fa scattare il "controllo duplicati" quando viene caricato un log con lo stesso nome.']},
        {n: '6.9', title: 'Caricamento dei log da parte del coordinatore nazionale', body: [
          'Il coordinatore nazionale e/o il responsabile dei log carica a sua volta tutte le informazioni rilevanti in WWFF Logsearch: %LOGSEARCH%.']},
        {n: '6.11', title: 'Log da entità DXCC senza programma WWFF', body: [
          'I log di attività in parchi di entità DXCC non rappresentate nell\'attuale programma WWFF possono essere inviati a: %MAIL%.']},
      ]},
    ],
  },

  es: {
    sub: 'Selección de las reglas WWFF, válidas también para ONFF.',
    official: 'Reglamento oficial completo de WWFF',
    note: 'Traducción de Diana. Prevalece el texto en inglés de WWFF.',
    labels: {call: 'indicativo', ref: 'referencia', date: 'fecha (AAAAMMDD)', space: 'espacio'},
    groups: [
      {title: 'El área de referencia', rules: [
        {n: '3.5', title: 'Referencias que lindan con otra referencia', body: [
          'Los activadores solo pueden activar <b>un área de referencia a la vez</b>. A veces un área de referencia WWFF linda con otra. Hay que asegurarse entonces de <b>anunciar la referencia correcta</b>.']},
        {n: '3.6', title: 'Referencias dentro de otra referencia', body: [
          'En algunos casos, un área de referencia WWFF puede estar dentro de otra área de referencia WWFF o quedar totalmente englobada por ella. En esos casos se opera en todo momento <b>bajo una sola referencia WWFF</b>.',
          'Si la posición de activación está dentro de los límites de varias áreas de referencia WWFF (por ejemplo, una reserva natural y un sitio Ramsar), el activador <b>elige una sola área de referencia</b> bajo la que se realiza la actividad.',
          'Una segunda actividad con otro número de referencia solo puede empezar <b>después de terminar la primera</b>.']},
        {n: '4.4', title: 'Operar dentro de los límites de la referencia', body: [
          'Durante la activación de un área de referencia WWFF, <b>todo el equipo</b> (antena(s), transceptor(es), alimentación, etc.) debe estar <b>dentro de los límites</b> del área.',
          'No basta con que solo una parte de la estación esté dentro del límite.']},
      ]},
      {title: 'QSO', rules: [
        {n: '4.7', title: '44 QSO repartidos en varias activaciones', body: [
          'Los <b>44 QSO</b> pueden acumularse <b>en varias activaciones</b>. No hace falta conseguirlos en una sola activación.',
          'Por ejemplo: hoy activas un área de referencia WWFF y haces 22 QSO. Una semana después vuelves y haces otros 22. Con eso el área de referencia queda calificada.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Nombre de los archivos de log', body: [
          'Los logs electrónicos deben nombrarse de esta forma:',
          '%EXAMPLE%',
          'Este nombre de archivo sirve como control muy sencillo de duplicados. Un log llamado simplemente XXFF-0123.adi, por ejemplo, activa el «control de duplicados» cuando se sube un log con el mismo nombre.']},
        {n: '6.9', title: 'Carga de logs por el coordinador nacional', body: [
          'El coordinador nacional y/o el gestor de logs carga a su vez toda la información relevante en WWFF Logsearch: %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs de entidades DXCC sin programa WWFF', body: [
          'Los logs de actividades en parques de entidades DXCC que no forman parte del programa WWFF actual pueden enviarse a: %MAIL%.']},
      ]},
    ],
  },

  pt: {
    sub: 'Seleção das regras WWFF, válidas também para a ONFF.',
    official: 'Regulamento oficial completo da WWFF',
    note: 'Tradução da Diana. Prevalece o texto em inglês da WWFF.',
    labels: {call: 'indicativo', ref: 'referência', date: 'data (AAAAMMDD)', space: 'espaço'},
    groups: [
      {title: 'A área de referência', rules: [
        {n: '3.5', title: 'Referências que fazem fronteira com outra referência', body: [
          'Os ativadores só podem ativar <b>uma área de referência de cada vez</b>. Por vezes, uma área de referência WWFF faz fronteira com outra. É preciso então garantir que se <b>anuncia a referência correta</b>.']},
        {n: '3.6', title: 'Referências dentro de outra referência', body: [
          'Em certos casos, uma área de referência WWFF pode ficar dentro de outra área de referência WWFF, ou ser totalmente abrangida por ela. Nesses casos, opera-se em cada momento <b>sob uma única referência WWFF</b>.',
          'Se a posição de ativação estiver dentro dos limites de várias áreas de referência WWFF (por exemplo, uma reserva natural e um sítio Ramsar), o ativador <b>escolhe uma única área de referência</b> sob a qual decorre a atividade.',
          'Uma segunda atividade com outro número de referência só pode começar <b>depois de concluída a primeira</b>.']},
        {n: '4.4', title: 'Operar dentro dos limites da referência', body: [
          'Durante a ativação de uma área de referência WWFF, <b>todo o equipamento</b> (antena(s), transcetor(es), alimentação, etc.) tem de estar <b>dentro dos limites</b> da área.',
          'Não basta que apenas uma parte da estação esteja dentro do limite.']},
      ]},
      {title: 'QSO', rules: [
        {n: '4.7', title: '44 QSO distribuídos por várias ativações', body: [
          'Os <b>44 QSO</b> podem ser acumulados <b>em várias ativações</b>. Não têm de ser feitos numa só ativação.',
          'Por exemplo: hoje ativa uma área de referência WWFF e faz 22 QSO. Uma semana depois volta e faz mais 22. A área de referência fica então qualificada.']},
      ]},
      {title: 'Logs', rules: [
        {n: '6.8', title: 'Nome dos ficheiros de log', body: [
          'Os logs eletrónicos devem ter o seguinte nome:',
          '%EXAMPLE%',
          'Este nome de ficheiro serve como uma verificação muito simples de duplicados. Um log chamado apenas XXFF-0123.adi, por exemplo, ativa a «verificação de duplicados» quando é carregado um log com o mesmo nome.']},
        {n: '6.9', title: 'Carregamento dos logs pelo coordenador nacional', body: [
          'O coordenador nacional e/ou o gestor de logs carrega, por sua vez, toda a informação relevante no WWFF Logsearch: %LOGSEARCH%.']},
        {n: '6.11', title: 'Logs de entidades DXCC sem programa WWFF', body: [
          'Os logs de atividades em parques de entidades DXCC que não fazem parte do atual programa WWFF podem ser enviados para: %MAIL%.']},
      ]},
    ],
  },
};

/* The log file name of rule 6.8, as an example with each part labelled. The
   pattern is from the WWFF rules and the WWFF log upload tutorial
   ("callsign@xxFF-xxxx YYYYMMDD"), with a space before the date. */
function rulesExampleHtml(L){
  const part = (txt, lbl, cls) => `<span class="rxp ${cls}"><code>${txt}</code><small>${lbl || '&nbsp;'}</small></span>`;
  return `<div class="rulex" aria-label="ON3VZ@ONFF-0104 20261002.adi">${
      part('ON3VZ', L.labels.call, 'c')}${part('@', '', 'at')}${part('ONFF-0104', L.labels.ref, 'r')}${
      part('&nbsp;', L.labels.space, 'sp')}${part('20261002', L.labels.date, 'd')}${part('.adi', '', 'x')}</div>`;
}

function renderRulesText(){
  const box = $('rulesText');
  if(!box) return;
  const L = RULES_TEXT[lang] || RULES_TEXT.en;
  const fill = s => s === '%EXAMPLE%' ? rulesExampleHtml(L)
    : `<p>${s.replace('%LOGSEARCH%', `<a href="${RULES_LOGSEARCH}" target="_blank" rel="noopener">wwff.co/logsearch</a>`)
            .replace('%MAIL%', `<a href="mailto:${RULES_MAIL}">${RULES_MAIL}</a>`)}</p>`;
  box.innerHTML = `<p class="sub" style="margin-top:0">${L.sub}</p>` +
    L.groups.map(g => `<h3 class="rgroup">${g.title}</h3>` + g.rules.map(r => `
      <div class="card rule" data-rule="${r.n}">
        <div class="rhead"><span class="rnum">${r.n}</span><h4>${r.title}</h4></div>
        ${r.body.map(fill).join('')}
      </div>`).join('')).join('') +
    `<p class="hint rsrc">${L.note ? L.note + ' ' : ''}<a href="${RULES_URL}" target="_blank" rel="noopener">${L.official}</a> (WWFF Global Rules v5.10)</p>`;
}
renderRulesText();
