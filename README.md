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

- **Jouer** : 9 bots de 400 à 3200 Elo (Stockfish 18 WASM, force limitée par UCI_Elo, fautes humaines pondérées par leur gravité sous 1320 Elo), mode 2 joueurs sur le même écran, cadences bullet/blitz/rapide avec incrément, pendules, confirmation d'abandon, classement Elo local par cadence, partie en cours et dernière configuration retrouvées au retour.
- **Puzzles** : 120 000 puzzles de la base lichess (CC0), stratifiés de 400 à 3200, chargés hors bundle (fetch lazy), classement puzzle Elo local, indices, séries.
- **Puzzle Rush** : 3 min, 5 min ou survie, difficulté croissante, 3 erreurs éliminatoires, records sauvegardés.
- **Entraîneur d'ouvertures** : page `/ouvertures` (accessible depuis Apprendre), choix de l'ouverture et de la couleur, arbre des variantes lichess, trois modes (prochain coup, suite de coups, variante complète), coups théoriques alternatifs acceptés, Stockfish au-delà de la théorie (indicatif), progression par variante.
- **Analyse** : Stockfish 18 sur la position affichée (3 lignes, jusqu'à la profondeur 22, coupé quand l'app passe en arrière-plan), barre d'évaluation, bilan de partie façon Game Review V2 (Brillant → Gaffe dont Occasion manquée et Gain manqué, précision et Elo estimé par couleur, graphe d'évaluation cliquable), coach post-partie (résumé narratif par phases, commentaires en français générés par règles, navigation par moments clés, retry « trouve mieux » contre le moteur), explorer d'ouvertures (base ECO lichess, 3 800 lignes), partie contre Stockfish pleine force depuis la position affichée, import/export PGN et FEN. Profondeur du bilan réglable (Stats → Réglages).
- **Apprendre** : séances courtes adaptées à ton niveau (finales, tactiques, ouvertures, stratégie) avec un Elo par domaine, « Mes erreurs » pour rejouer les fautes relevées par les bilans, finales jouées jusqu'au bout contre Stockfish (`#/finales`), cours de finales en 14 leçons jouables (`#/apprendre/finales`), entraîneur d'ouvertures (`#/ouvertures`), Mats éclair (`#/mats`, aussi depuis Puzzles) : mater vite comme au bullet, contre la montre contre Stockfish (dame, tour, deux tours, dame + tour, deux fous, fou + cavalier, dame + pion, promotion puis mat, ou mélange des schémas ; positions vérifiées sur les tables de finales), mat en 1, 2, 3 ou mélange en série chronométrée, géométrie du mat (escalier, batteries, diagonale + ligne, dame au contact) et motifs lichess (couloir, étouffé, Anastasie, Boden, Damiano...), avec le réseau de mat dessiné après chaque mat, records et progression.
- **Révision espacée** : carte « À réviser aujourd'hui » sur l'accueil (et ligne dans Apprendre), séance mixte et enchaînée (`#/revision`) des puzzles ratés, des fautes de parties et des variantes d'ouverture à revoir ; calendrier de Leitner J+1, J+3, J+7, J+21 calculé depuis l'historique existant, une réussite espace le prochain passage, un échec ramène à J+1, quatre jours de réussite d'affilée classent l'item acquis ; sans incidence sur les Elo.
- **Import chess.com** : page `/import` : pseudo chess.com (API publique, sans login) → liste des parties récentes → bilan en un tap ; ou coller un lien de partie ; ou Raccourci Apple pour partager depuis l'app chess.com (instructions dans la page).
- **Sons** : set standard lichess (move, capture, fin de partie, low time, réussite/échec puzzle), préchargés via WebAudio.
- **Archive** : toutes les parties sauvegardées (IndexedDB), relecture, bilan en un clic, export PGN global.
- **Stats** : classements par cadence, bilan V/N/D, thèmes d'échiquier, réglages, sauvegarde et restauration de toutes les données (fichier JSON), état du stockage, réinitialisation de l'app.

## Architecture

- React 19 + Vite + TypeScript + Tailwind 4, état client Zustand, persistance Dexie (IndexedDB).
- Moteur : `stockfish` npm (build `lite-single`, mono-thread, pas de COOP/COEP requis), wrapper UCI maison dans `src/lib/engine.ts`.
  Toutes les commandes moteur sont sérialisées par un mutex : deux `go` sans `stop` intermédiaire font trap le WASM.
- Données : `scripts/prepare-data.mjs` regénère `src/data/*.json` depuis les dumps lichess dans `data/` (openings TSV + slice de `lichess_db_puzzle.csv.zst`).
- Debug moteur : ajouter `?debug-uci` à l'URL pour logger le trafic UCI en console.
