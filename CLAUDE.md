# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

ChessLocal : clone privé de chess.com, 100 % client (aucun serveur, aucun compte).
PWA installable sur iPhone, utilisable hors ligne après la première visite.
Déployée sur GitHub Pages sous `/chess-local/`.
Toute l'UI, les commentaires de code et les messages de commit sont en français.

## Commandes

```bash
npm ci                 # requis avant tout : sans node_modules, `oxlint` et `tsc` sont introuvables
npm run dev            # Vite, http://localhost:5173
npm run build          # tsc -b && vite build (le typecheck n'existe que ici, pas de script séparé)
npm run lint           # oxlint (config .oxlintrc.json)
npm run preview        # sert dist/
```

Il n'y a pas de tests unitaires.
Les tests sont des scripts E2E Playwright en Python, un fichier = une suite, lancés un par un :

```bash
npx vite --port 5199               # les suites visent http://localhost:5199 par défaut
python3 e2e/test_learn.py          # Apprendre
python3 e2e/test_v4.py             # entraîneur, analyse mobile, accueil, puzzles
python3 e2e/test_all_buttons.py    # un assert d'effet par bouton de l'app
BASE=https://maxencebrochard.github.io/chess-local python3 e2e/test_learn.py   # contre la prod
```

Chaque suite imprime `[PASS]`/`[FAIL]` par check et écrit ses captures dans `e2e/shots/` (gitignoré).
Elles pré-remplissent `localStorage['chess-local-settings']` au format Zustand persist (`{state: {...}, version: 0}`) avec `reviewDepth: 'fast'` et les sons coupés.
Changer la forme du store `src/store/settings.ts` impose de mettre à jour ces seeds.
`test_all_buttons.py` appelle la vraie API chess.com (réseau requis).

Autres scripts :

- `node scripts/prepare-data.mjs` régénère `public/puzzles.json` et `src/data/openings.json`.
  Il lit `data/puzzles_full.csv` (dump lichess décompressé), absent du repo : seuls les `data/openings_*.tsv` sont versionnés.
- `scripts/deploy.sh` build puis force-push `dist/` sur la branche `gh-pages`.
  Action sortante : ne pas le lancer sans demande explicite.
- `?debug-uci` dans l'URL logge le trafic UCI en console.

## Architecture

Stack : React 19, Vite 8, TypeScript, Tailwind 4, Zustand (réglages), Dexie (IndexedDB), chess.js, react-chessboard, Stockfish 18 WASM.
`src/pages/` contient une page par route, `src/lib/` la logique sans React, `src/components/` les briques partagées.

### Moteur (`src/lib/engine.ts`)

Un `Engine` = un worker Stockfish (`public/engine/`, build `lite-single` mono-thread, donc pas de COOP/COEP).
Toutes les méthodes publiques passent par un mutex (chaîne de promesses) : deux `go` sans `stop` intermédiaire font trap le WASM (`unreachable`).
Ne jamais envoyer de commande UCI en dehors de `exclusive()`.
`searchId` invalide les callbacks `onLines` d'une recherche remplacée : toute nouvelle méthode de recherche doit passer par `attachInfoListener()`.
Les scores sont du point de vue du trait ; les convertir explicitement avant de les afficher côté blanc.

Chaque page crée son moteur paresseusement dans un `useRef` (`engineRef.current ??= new Engine()`) et appelle `quit()` au démontage.
`Play.tsx` en tient deux : celui du bot est bridé par `UCI_LimitStrength`/`UCI_Elo` (`src/lib/bots.ts`), celui du coach live reste à pleine force pour évaluer les coups.
Pour des recherches concurrentes ou des options différentes, créer un second `Engine` plutôt que partager le même.
Sous 1320 Elo (plancher de `UCI_Elo`), la faiblesse des bots vient de coups aléatoires (`randomness`).

### `/analyse` est le hub

Les autres pages y envoient leur contenu par state de navigation :
`navigate('/analyse', { state: { pgn | fen, uci?, viewIndex?, color?, orientation?, label?, review?, returnTo? } })`.
Archive et fin de partie passent par `?game=<id>` (lecture dans Dexie), avec `&review=1` pour lancer le bilan directement.
`Analysis.tsx` consomme `location.state` au montage puis fait `navigate('.', { replace: true, state: null })` pour qu'un refresh ne rejoue pas le chargement.
`returnTo` affiche un bouton retour qui navigue avec `state: { restore: true }` ; `Learn.tsx` restaure alors sa séance depuis `sessionStorage`.

### Pipeline d'évaluation

`review.ts` évalue chaque position en multipv 2 à profondeur fixe, convertit en win% (formule lichess) et classe chaque coup selon la chute de win%.
`MoveClass`, `CLASS_META` (libellés, couleurs, symboles) et les seuils vivent uniquement là.
En dépendent : `coach.ts` (commentaires post-partie générés par règles), `liveCoach.ts` (classe rapide du mode entraîneur), `ReviewSummary`, `EvalGraph`, `MoveList`.
Un bilan écrit les fautes dans la table `mistakes`, rejouées ensuite dans Apprendre → Mes erreurs.

### Persistance

Base Dexie `chess-local` (`src/lib/db.ts`), actuellement en `version(2)`.
Ajouter une table ou un index = nouveau bloc `db.version(n)` qui redéclare tous les stores, plus l'ajout dans `TABLES` de `backup.ts`.
La table `ratings` est unique et indexée par clé texte : cadences (`bullet`, `blitz`, `rapid`, `unlimited`), `puzzle`, et domaines d'Apprendre (`learn-endgame`, `learn-tactic`, ...).
Tous les Elo passent par `applyRating`/`eloUpdate`.
Les réglages sont dans Zustand persist (`localStorage['chess-local-settings']`).
`main.tsx` demande `navigator.storage.persist()` et `backup.ts` exporte/restaure tout : iOS peut purger IndexedDB.

### Chemins et PWA

`base: './'` + `HashRouter` : l'app doit tourner aussi bien à la racine que sous `/chess-local/`.
Tout asset de `public/` se charge via `import.meta.env.BASE_URL` (worker moteur, sons, `puzzles.json`) ; un chemin absolu `/...` casse la prod.
Le service worker précache tout (WASM 7 Mo, puzzles 16 Mo) avec un plafond de 25 Mo par fichier dans `vite.config.ts`.
Un nouvel asset lourd ou une nouvelle extension doit être couvert par `globPatterns`.
`__BUILD__` (horodatage de build) s'affiche en bas de `/import` pour vérifier qu'un iPhone a bien la dernière version.

### Données

`public/puzzles.json` : 120 000 puzzles lichess au format compact `[id, fen, moves, rating, themes]`, hors bundle, chargés une fois par `loadPuzzles()`.
`src/data/*.json` est bundlé : `openings.json` (généré), `endgames.json`, `strategy.json`, `courses.json` (contenu d'Apprendre, écrit à la main, en français).
Les noms d'ouvertures sont en anglais dans les données et traduits à l'affichage par `openingNames.ts`.

### UI

Mobile d'abord : la cible principale est la PWA iPhone en mode standalone (nav basse, `pt-safe`/`pb-safe`, hauteurs en `dvh`), avec une nav latérale à partir de `md`.
Les E2E tournent sur le device `iPhone 14 Pro` et en 1440x900.
Couleurs via les tokens Tailwind `@theme` de `src/index.css` : `surface`, `surface-2`, `surface-3`, `accent`.
`.boardbox` fixe la taille de l'échiquier sur toutes les pages.
