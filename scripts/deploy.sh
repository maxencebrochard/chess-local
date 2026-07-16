#!/usr/bin/env bash
# Déploie l'app sur GitHub Pages (branche gh-pages).
set -euo pipefail
cd "$(dirname "$0")/.."

npm run build
cd dist
git init -b gh-pages -q
git add -A
git -c user.name="Maxence Brochard" -c user.email="maxence.brochard@gmail.com" commit -qm "deploy $(date +%Y-%m-%d_%H:%M)"
git push -f https://github.com/maxencebrochard/chess-local.git gh-pages
cd ..
rm -rf dist/.git
echo "Déployé : https://maxencebrochard.github.io/chess-local/"
