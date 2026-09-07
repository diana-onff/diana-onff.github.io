#!/usr/bin/env bash
# Geeft het adres waarop GitHub Pages deze repository uitserveert.
#
# Eén regel die je makkelijk fout hebt: een repository die exact
# <eigenaar>.github.io heet, komt op de WORTEL van dat domein te staan —
# https://diana-onff.github.io/ — en niet in een submap. Elke andere naam
# komt wel in een submap: https://iemand.github.io/repo/.
#
# Wie dat verschil niet maakt, bouwt previewlinks als
# https://diana-onff.github.io/diana-onff.github.io/preview/pr-3/ en die
# geven een 404 die er uitziet alsof Pages stuk is.
#
# Gebruik:  build/paginabasis.sh <eigenaar> <repo>
# Uitvoer:  het adres zonder afsluitende schuine streep.
set -euo pipefail

EIGENAAR="${1:?eigenaar ontbreekt}"
REPO="${2:?repo ontbreekt}"

# GitHub-namen zijn hoofdletterongevoelig; het adres is altijd kleine letters.
klein() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

E="$(klein "$EIGENAAR")"
R="$(klein "$REPO")"

if [ "$R" = "${E}.github.io" ]; then
  printf 'https://%s.github.io' "$E"
else
  printf 'https://%s.github.io/%s' "$E" "$REPO"
fi
