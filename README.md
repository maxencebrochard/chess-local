# ChessLocal

Version privée et locale de chess.com.
Tourne entièrement sur le Mac : aucun serveur, aucun compte, aucune donnée qui sort de la machine.

## Lancer

```bash
npm install
npm run dev        # http://localhost:5173
```

Ou en version optimisée :

```bash
npm run build
npm run preview
```

## Features

- **Jouer** : 9 bots de 400 à 3200 Elo (Stockfish 18 WASM, force limitée par UCI_Elo + coups aléatoires pour les niveaux faibles), mode 2 joueurs sur le même écran, cadences bullet/blitz/rapide avec incrément, pendules, classement Elo local par cadence.
- **Puzzles** : 120 000 puzzles de la base lichess (CC0), stratifiés de 400 à 3200, chargés hors bundle (fetch lazy), classement puzzle Elo local, indices, séries.
- **Puzzle Rush** : 3 min, 5 min ou survie, difficulté croissante, 3 erreurs éliminatoires, records sauvegardés.
- **Analyse** : Stockfish 18 en continu (3 lignes), barre d'évaluation, bilan de partie façon Game Review (Brillant → Gaffe + précision par couleur), coach post-partie (commentaires en français générés par règles : pièce pendue, mat manqué, meilleur coup ; navigation par moments clés), explorer d'ouvertures (base ECO lichess, 3 800 lignes), import/export PGN et FEN.
- **Sons** : set standard lichess (move, capture, fin de partie, low time, réussite/échec puzzle), préchargés via WebAudio.
- **Archive** : toutes les parties sauvegardées (IndexedDB), relecture, bilan en un clic, export PGN global.
- **Stats** : classements par cadence, bilan V/N/D, thèmes d'échiquier, réglages.

## Architecture

- React 19 + Vite + TypeScript + Tailwind 4, état client Zustand, persistance Dexie (IndexedDB).
- Moteur : `stockfish` npm (build `lite-single`, mono-thread, pas de COOP/COEP requis), wrapper UCI maison dans `src/lib/engine.ts`.
  Toutes les commandes moteur sont sérialisées par un mutex : deux `go` sans `stop` intermédiaire font trap le WASM.
- Données : `scripts/prepare-data.mjs` regénère `src/data/*.json` depuis les dumps lichess dans `data/` (openings TSV + slice de `lichess_db_puzzle.csv.zst`).
- Debug moteur : ajouter `?debug-uci` à l'URL pour logger le trafic UCI en console.
