# Deze map is met opzet leeg

Het bron-KMZ van ONFF staat **niet** in deze publieke repository.

ONFF verspreidt dat bestand via de BOS-groups.io, achter lidmaatschap. Het hoort
dus niet ongevraagd op een publieke URL. Daarom staat het in een aparte, private
repository van dezelfde organisatie, en haalt de build het daar op:

| Instelling | Waar | Wat |
|---|---|---|
| `SOURCE_REPO` | Settings → Secrets and variables → Actions → **Variables** | `diana-onff/diana-source` |
| `SOURCE_TOKEN` | Settings → Secrets and variables → Actions → **Secrets** | fine-grained token, alleen *Contents: read* op die repo |

Staat er toch een `.kmz` in deze map, dan gebruikt de build dat — als vangnet
tijdens een verhuizing. `.gitignore` houdt zo'n bestand tegen bij het committen,
dus dat gebeurt alleen als iemand het bewust forceert.

Wat wél publiek is en blijft: `data/onff.geojson`. Dat zijn de omgezette grenzen,
en dat *is* de app. Deze opzet beschermt het bestand, niet de gegevens erin.
