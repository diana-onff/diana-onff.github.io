#!/usr/bin/env bash
# Gives the address at which GitHub Pages serves this repository.
#
# One rule that is easy to get wrong: a repository named exactly
# <owner>.github.io ends up at the ROOT of that domain —
# https://diana-onff.github.io/ — and not in a subdirectory. Every other name
# does go into a subdirectory: https://someone.github.io/repo/.
#
# Anyone who does not make that distinction builds preview links like
# https://diana-onff.github.io/diana-onff.github.io/preview/pr-3/ and those
# give a 404 that looks as if Pages is broken.
#
# Usage:  build/paginabasis.sh <owner> <repo>
# Output: the address without a trailing slash.
set -euo pipefail

EIGENAAR="${1:?owner missing}"
REPO="${2:?repo missing}"

# GitHub names are case-insensitive; the address is always lowercase.
klein() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

E="$(klein "$EIGENAAR")"
R="$(klein "$REPO")"

if [ "$R" = "${E}.github.io" ]; then
  printf 'https://%s.github.io' "$E"
else
  printf 'https://%s.github.io/%s' "$E" "$REPO"
fi
