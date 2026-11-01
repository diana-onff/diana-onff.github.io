# Deze map is met opzet leeg

De bron-KMZ's van de landen staan **niet** in deze publieke repository.

ONFF bijvoorbeeld verspreidt zijn bestand via de BOS-groups.io, achter
lidmaatschap, en andere programma's hebben hun eigen kanalen. Ze horen dus niet
ongevraagd op een publieke URL. Daarom staan ze in een aparte, private
repository van dezelfde organisatie, en haalt de build ze daar op
(`source/<PROG>/` per land, `incoming/` voor een upload die nog op
goedkeuring wacht):

| Instelling | Waar | Wat |
|---|---|---|
| `SOURCE_REPO` | Settings → Secrets and variables → Actions → **Variables** | `diana-onff/diana-source` |
| `SOURCE_TOKEN` | Settings → Secrets and variables → Actions → **Secrets** | fine-grained token, alleen *Contents: read* op die repo |

Staat er toch een `.kmz` in deze map, dan gebruikt de build dat — als vangnet
tijdens een verhuizing. `.gitignore` houdt zo'n bestand tegen bij het committen,
dus dat gebeurt alleen als iemand het bewust forceert.

Wat wél publiek is en blijft: `data/zones/<prog>.geojson`. Dat zijn de omgezette
grenzen, en dat *is* de app. Deze opzet beschermt de bestanden, niet de gegevens
erin.
