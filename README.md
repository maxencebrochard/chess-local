# ChessLocal

Version privée et locale de chess.com.
Tourne dans le navigateur sur Mac et iPhone : calculs et stockage sur l'appareil, sans serveur ChessLocal ni compte à créer.
L'import et les Insights chess.com interrogent son API publique avec ton pseudo ; les bilans Stockfish sont calculés localement.
La navigation reste en place pendant le défilement du contenu ; les gestes en butée des listes, calques et feuilles ne se propagent pas à la page.

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

- **Accueil** : carte Problèmes (résolus et classement puzzles, bouton « Résolvez ! »), quatre cartes Elo (rapide, blitz, bullet, puzzles) vers les stats, tuiles Analyse, Puzzle Rush, Archive (nombre de parties) et chess.com, grand bouton Jouer.
- **Jouer** : 9 bots de 400 à 3200 Elo (Stockfish 18 WASM, force limitée par UCI_Elo, fautes humaines pondérées par leur gravité sous 1320 Elo), mode 2 joueurs sur le même écran, cadences bullet/blitz/rapide avec incrément, pendules, confirmation d'abandon, classement Elo local par cadence, partie en cours et dernière configuration retrouvées au retour.
  Chaque réglage mémorisé invalide revient à sa valeur par défaut à l'ouverture de Jouer : mode contre un bot, Nina, Blancs ou 10 min, selon le réglage concerné.
- **Puzzles** : 120 000 puzzles de la base lichess (CC0), stratifiés de 400 à 3200, chargés hors bundle (fetch lazy), classement puzzle Elo local, indices, séries.
- **Puzzle Rush** : 3 min, 5 min ou survie, difficulté croissante, 3 erreurs éliminatoires, records sauvegardés.
- **Entraîneur d'ouvertures** : page `/ouvertures` (accessible depuis Apprendre), choix de l'ouverture et de la couleur, arbre des variantes lichess, trois modes (prochain coup, suite de coups, variante complète), coups théoriques alternatifs acceptés, Stockfish au-delà de la théorie (indicatif), progression par variante.
- **Analyse** : Stockfish 18 sur la position affichée (3 lignes, jusqu'à la profondeur 22, coupé quand l'app passe en arrière-plan), barre d'évaluation, bilan de partie façon Game Review V2 (Brillant → Gaffe dont Occasion manquée et Gain manqué, précision et Elo estimé par couleur, graphe d'évaluation cliquable), coach post-partie (résumé narratif par phases, commentaires en français générés par règles, navigation par moments clés, retry « trouve mieux » contre le moteur), explorer d'ouvertures (base ECO lichess, 3 800 lignes), partie contre Stockfish pleine force depuis la position affichée, calque « Compte les attaquants » (zone de chaque roi, attaquants contre défenseurs, aussi dans Jouer et dans la partie contre le moteur lancée depuis l'analyse), import/export PGN et FEN. Profondeur du bilan réglable (Stats → Réglages).
- **Apprendre** : séances courtes adaptées à ton niveau (finales, tactiques, ouvertures, stratégie) avec un Elo par domaine, « Mes erreurs » pour rejouer les fautes relevées par les bilans, « Mes attaques manquées » (`#/attaques-manquees`, aussi depuis Stats) : les moments de tes bilans où Stockfish attaquait le roi adverse (mat, sacrifice près du roi, pion contre le roque, pièce vers le roi), à retrouver puis à mener contre Stockfish, finales jouées jusqu'au bout contre Stockfish (`#/finales`), cours de finales en 14 leçons jouables (`#/apprendre/finales`), entraîneur d'ouvertures (`#/ouvertures`), Mats éclair (`#/mats`, aussi depuis Puzzles) : mater vite comme au bullet, contre la montre contre Stockfish (dame, tour, deux tours, dame + tour, deux fous, fou + cavalier, dame + pion contre roi, promotion puis mat, ou mélange des schémas ; positions vérifiées sur les tables de finales), mat en 1, 2, 3 ou mélange en série chronométrée, géométrie du mat (escalier, batteries, diagonale + ligne, dame au contact) et motifs lichess (couloir, étouffé, Anastasie, Boden, Damiano...), avec le réseau de mat dessiné après chaque mat, records et progression, entraîneur d'attaque (`#/attaque` : positions de milieu de partie en roques opposés, même aile ou roi au centre, contre Stockfish bridé à l'Elo choisi de 1320 à pleine force, jusqu'au mat ou à un avantage décisif tenu).
  Le niveau du défenseur est mémorisé ; le changer en cours de partie demande confirmation et recommence la position.
  « Position au hasard » privilégie les positions jamais réussies de la catégorie affichée ; « Conseils » et « Indice » aident à mener l'attaque, et « Plan » montre une suite de Stockfish depuis la position de départ en fin de partie.
  Une fois l'avantage décisif atteint, tu peux conclure ou continuer : la réussite reste acquise, mais seules les réussites obtenues sans indice ni coup repris valident une position et son meilleur niveau battu.
- **Révision espacée** : carte « À réviser aujourd'hui » sur l'accueil (et ligne dans Apprendre), séance mixte et enchaînée (`#/revision`) des puzzles ratés, des fautes de parties et des variantes d'ouverture à revoir ; calendrier de Leitner J+1, J+3, J+7, J+21 calculé depuis l'historique existant, une réussite espace le prochain passage, un échec ramène à J+1, quatre jours de réussite d'affilée classent l'item acquis ; sans incidence sur les Elo.
- **Import chess.com** : page `/import` : pseudo chess.com (API publique, sans login) → liste des parties récentes → bilan en un tap ; ou coller un lien de partie ; ou Raccourci Apple pour partager depuis l'app chess.com (instructions dans la page).
- **Pièces** : cinq jeux au choix (Stats → Réglages, avec aperçu), sur tous les échiquiers : Celtique par défaut (pièces pleines et ombrées), Chessnut, Fantasy, Spatial et Classique.
- **Sons** : façon chess.com, coup joué, coup adverse, prise, roque, échec, promotion, début et fin de partie, temps bas, coup illégal, réussite et échec d'exercice ; en partie, puzzles, Rush, Apprendre, Mats, finales, ouvertures et en avançant dans l'analyse. Volume réglable. Audio déverrouillé au premier geste et recréé après un passage en arrière-plan (exigences d'iOS) ; sur iPhone, le mode silencieux coupe les sons.
- **Archive** : toutes les parties sauvegardées (IndexedDB), relecture, bilan en un clic, export PGN global.
- **Insights** : page `/insights` (depuis Stats et l'accueil) : choix de la cadence et des 10, 25, 50 ou 100 dernières parties, issues de chess.com et/ou des parties ChessLocal contre les bots.
  Bullet, blitz et rapide sont disponibles pour les deux sources ; « Sans limite » exige ChessLocal, car chess.com ne fournit pas cette cadence.
  Les archives chess.com sont parcourues des plus récentes aux plus anciennes jusqu'au nombre demandé ou à épuisement ; si l'historique en contient moins, le nombre trouvé est indiqué.
  Chaque partie reçoit un bilan Stockfish avec progression et estimation de durée ; la série se met en pause en arrière-plan et reprend au retour, et « Annuler » puis « Reprendre » conserve les bilans terminés.
  Le cache est réutilisé à profondeur et compte identiques ; changer le nombre demandé peut changer la profondeur et entraîner un nouveau calcul.
  Le dernier rapport se rouvre hors ligne ; si chess.com est injoignable lors d'une nouvelle série, seules ses parties déjà analysées pour ce pseudo et cette cadence sont disponibles.
  Le rapport propose un résumé du coach par règles, jusqu'à 3 forces et 3 faiblesses chiffrées selon les données disponibles, un plan d'entraînement vers les modules de l'app et des exemples ouverts dans l'Analyse.
  Il couvre la tendance de précision, la précision par phase hors théorie, les ouvertures par couleur, les résultats par couleur et Elo adverse, les erreurs typiques, les attaques sur le roi manquées, la conversion, la défense, les gaffes adverses punies et les résultats juste après une défaite.
  Les mesures de pendule utilisent les annotations `%clk` des PGN chess.com ; ChessLocal n'enregistre pas les temps par coup.
- **Stats** : classements par cadence, bilan V/N/D, thèmes d'échiquier, réglages, sauvegarde et restauration des données IndexedDB et des réglages (fichier JSON), état du stockage, réinitialisation de l'app.
  Les bilans Insights en cache sont inclus dans la sauvegarde, mais pas la configuration ni la sélection du dernier rapport ; une restauration conserve la configuration locale et invalide ce rapport, sans supprimer les bilans restaurés.

## Licences des ressources

Rien ne vient de chess.com.
Pièces : jeux libres, Celtique, Fantasy et Spatial de Maurizio Monge (MIT, repris du dépôt de lichess, Celtique recoloré), Chessnut d'Alexis Luengas (Apache 2.0, « Copyright 2015 Alexis Luengas », repris du dépôt de l'auteur avec son `COPYRIGHT.txt`) ; détail et textes de licence dans `public/pieces/LICENSES.md`.
Classique : pièces SVG standard de Wikimedia Commons dessinées par Cburnett (publiées sous GFDL, CC BY-SA 3.0, BSD 3 clauses et GPL au choix, reprises sous BSD 3 clauses), embarquées par `react-chessboard` (MIT), qui les cite sous CC BY-SA 3.0.
Sons : dérivés des packs Kenney « Impact Sounds » et « Interface Sounds » (CC0 1.0), régénérés par `scripts/make-sounds.sh` ; détail dans `public/sounds/LICENSES.md`.

## Architecture

- React 19 + Vite + TypeScript + Tailwind 4, état client Zustand, persistance Dexie (IndexedDB).
- Moteur : `stockfish` npm (build `lite-single`, mono-thread, pas de COOP/COEP requis), wrapper UCI maison dans `src/lib/engine.ts`.
  Toutes les commandes moteur sont sérialisées par un mutex : deux `go` sans `stop` intermédiaire font trap le WASM.
- Données : les commandes de génération propres à chaque banque sont décrites dans [CLAUDE.md, section Commandes](CLAUDE.md#commandes).
- Debug moteur : ajouter `?debug-uci` à l'URL pour logger le trafic UCI en console.
