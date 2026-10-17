# ChessLocal

Version privée et locale de chess.com.
Tourne dans le navigateur sur Mac et iPhone : calculs et stockage sur l'appareil, sans serveur ChessLocal ni compte à créer.
L'import et les Insights chess.com interrogent son API publique avec ton pseudo ; les bilans Stockfish sont calculés localement.
La navigation reste en place pendant le défilement du contenu ; les gestes en butée des listes, calques et feuilles ne se propagent pas à la page.
Sur écran tactile, les contacts sur les cases proches des bords gauche et droit de l'écran sont réservés à l'échiquier afin d'éviter le geste retour/suivant d'iOS pendant un déplacement de pièce ; le glissé et le clic-clic restent disponibles.
Pour faire défiler un cours depuis un diagramme, commence le geste au centre du diagramme ou dans le contenu autour : ses cases proches des bords de l'écran bloquent aussi le défilement vertical.

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

L’[audit UX et le plan de refonte](docs/ux-refonte.md) décrivent la navigation cible et les lots à intégrer après fusion des fonctionnalités en cours.
La suite `npm run test:e2e -- --suite ux_audit` régénère les captures locales et l’inventaire de l’expérience actuelle.
Le lot 1 améliore le contraste des actions vertes et harmonise en-têtes, tuiles, progressions et états vides ; `ux_foundation` en vérifie le rendu aux trois formats, sans changer la navigation.

Les parcours sont couverts par les suites E2E de production et de développement : `npm run test:e2e` et `npm run test:e2e:dev`.
Les options du lanceur et les prérequis sont décrits dans [les commandes E2E](CLAUDE.md#commandes).
Les mesures de fiabilité et les preuves par mutation sont décrites dans [le bilan Q1](docs/q1-e2e.md).

- **Accueil** : carte Problèmes (résolus et classement puzzles, bouton « Résolvez ! »), quatre cartes Elo (rapide, blitz, bullet, puzzles) vers les stats, tuiles Analyse, Puzzle Rush, Archive (nombre de parties) et chess.com, tuiles Parcours (progression) et Insights, grand bouton Jouer.
- **Jouer** : 9 bots de 400 à 3200 Elo (Stockfish 18 WASM, force limitée par UCI_Elo, fautes humaines pondérées par leur gravité sous 1320 Elo), mode 2 joueurs sur le même écran, cadences bullet/blitz/rapide avec incrément, pendules, confirmation d'abandon, classement Elo local par cadence, partie en cours et dernière configuration retrouvées au retour.
  Chaque réglage mémorisé invalide revient à sa valeur par défaut à l'ouverture de Jouer : mode contre un bot, Nina, Blancs ou 10 min, selon le réglage concerné.
- **Puzzles** : 120 000 puzzles de la base lichess (CC0), stratifiés de 400 à 3200, chargés hors bundle (fetch lazy), classement puzzle Elo local, indices, séries.
- **Puzzle Rush** : 3 min, 5 min ou survie, difficulté croissante, 3 erreurs éliminatoires, records sauvegardés.
- **Entraîneur d'ouvertures** : page `/ouvertures` (accessible depuis Apprendre), choix de l'ouverture et de la couleur, arbre des variantes lichess, trois modes (prochain coup, suite de coups, variante complète), coups théoriques alternatifs acceptés, Stockfish au-delà de la théorie (indicatif), progression par variante.
- **Mon répertoire** : page `/repertoire` (accessible depuis Apprendre), où tu sors de la théorie dans tes parties chess.com, par camp et par cadence.
  Pour chaque ouverture jouée : parties, résultats, coup de sortie typique, coups joués lorsque tu quittes la théorie le premier et coups théoriques attendus, transpositions comprises.
  Une même sortie est regroupée par camp et position et apparaît dans toutes les familles d'ouvertures concernées.
  Le coût d'une sortie est la chute moyenne de chances de gain mesurée dans les bilans Stockfish d'Insights ; sans bilan, la priorité dépend de sa fréquence puis du nombre de défaites.
  Chaque sortie devient une séance « Prochain coup » de l'entraîneur d'ouvertures, dans l'ordre de priorité, avec l'état Corrigée ou À revoir.
  Les parties viennent des bilans d'Insights en cache, hors ligne, et des parties récentes chargées sur demande (3 mois, 200 au plus), gardées le temps de la session.
- **Analyse** : Stockfish 18 sur la position affichée (3 lignes, jusqu'à la profondeur 22, coupé quand l'app passe en arrière-plan), barre d'évaluation, bilan de partie façon Game Review V2 (Brillant → Gaffe dont Occasion manquée et Gain manqué, précision et Elo estimé par couleur, graphe d'évaluation cliquable), moments critiques du bilan (jusqu’à 3 positions, selon la partie : bascules et coups uniques trouvés, à identifier comme plan, menace ou coup forcé puis à rejouer contre Stockfish), coach post-partie (résumé narratif par phases, commentaires en français générés par règles, navigation par moments clés, retry « trouve mieux » contre le moteur), explorer d'ouvertures (base ECO lichess, 3 800 lignes), partie contre Stockfish pleine force depuis la position affichée, calque « Compte les attaquants » (zone de chaque roi, attaquants contre défenseurs, aussi dans Jouer et dans la partie contre le moteur lancée depuis l'analyse), import/export PGN et FEN.
  Profondeur du bilan réglable (Stats → Réglages).
  Dans « Moments critiques », la réponse est expliquée après ton choix, sans révéler le coup à retrouver avant de rejouer ; « Retour au bilan » rouvre le même résumé sans recalcul.
  Les réponses et les tentatives sont enregistrées sans modifier les Elo.
  « Pourquoi ? » sur une faute du bilan (hors imprécisions, pour ton camp ou les deux si inconnu), et dans Mes erreurs après le verdict, déroule la réfutation de Stockfish avec flèches et commentaires fondés sur les motifs vérifiés sur l'échiquier et les évaluations du moteur ; le bilan matériel porte uniquement sur la suite affichée.
  La lecture avance toutes les 1,8 seconde jusqu'au bilan de la suite, avec pause, précédent et suivant ; elle démarre en pause si la réduction des animations est activée.
  Le calcul utilise le réglage courant de profondeur du bilan (Stats → Réglages), avec un minimum de 12, sans conserver la profondeur du bilan d'origine.
  La carte du meilleur coup indique ce qu'il empêche lorsqu'un effet est vérifié ; si le moteur juge le coup joué presque aussi bon ou meilleur, elle le précise.
- **Parcours d'apprentissage** : `#/apprendre/parcours`, en tête d'Apprendre et depuis l'accueil, façon chess.com Path : 37 étapes en quatre niveaux (Débutant 800, Intermédiaire 1200, Confirmé 1600, Avancé 2000), chacune une courte leçon (cours « Les bases », de finales, « Démolir le roque » ou cours détaillé) suivie d'exercices à réussir (puzzles par thème, variantes d'ouverture, finale contre Stockfish).
  Les étapes se débloquent dans l'ordre, avec coche et étoiles, reprise sur l'étape en cours, et une leçon déjà terminée dans son cours compte.
  Chaque exercice doit atteindre l'objectif affiché : seuil de réussites pour les puzzles et variantes, gain ou nulle demandée pour une finale.
  Consulter « Solution » dans une leçon ne suffit pas à valider l'étape : ses exercices restent à réussir.
  Un test de placement optionnel (3 puzzles par niveau) permet de sauter les niveaux déjà maîtrisés.
  Pour les séries du parcours, le placement et les séances d'Apprendre, le résultat n'est confirmé qu'après son enregistrement local ; en cas d'échec, il reste en attente et le bouton « Réessayer l’enregistrement » permet de sauvegarder sans rejouer.
- **Apprendre** : séances courtes adaptées à ton niveau (finales, tactiques, ouvertures, stratégie) avec un Elo par domaine, « Mes erreurs » pour rejouer les fautes relevées par les bilans, « Mes attaques manquées » (`#/attaques-manquees`, aussi depuis Stats) : les moments de tes bilans où Stockfish attaquait le roi adverse (mat, sacrifice près du roi, pion contre le roque, pièce vers le roi), à retrouver puis à mener contre Stockfish, finales jouées jusqu'au bout contre Stockfish (`#/finales`), cours de finales en 14 leçons jouables (`#/apprendre/finales`), cours « Tenir sous l'attaque » en 13 leçons jouables (`#/apprendre/defense`) : échanger les attaquants, contre-attaquer au centre, ne pas toucher aux pions du roque, ramener un défenseur, fuir avec le roi, rendre du matériel, contre le sacrifice grec et la tempête de pions, sur des positions de parties lichess où chaque défense qui tient est vérifiée par Stockfish 18, cours « Les bases » (`#/apprendre/bases` : valeur des pièces, menaces, développement, tours sur la septième, verdicts vérifiés par Stockfish), entraîneur d'ouvertures (`#/ouvertures`), Mats éclair (`#/mats`, aussi depuis Puzzles) : mater vite comme au bullet, contre la montre contre Stockfish (dame, tour, deux tours, dame + tour, deux fous, fou + cavalier, dame + pion contre roi, promotion puis mat, ou mélange des schémas ; positions vérifiées sur les tables de finales), mat en 1, 2, 3 ou mélange en série chronométrée, géométrie du mat (escalier, batteries, diagonale + ligne, dame au contact) et motifs lichess (couloir, étouffé, Anastasie, Boden, Damiano...), avec le réseau de mat dessiné après chaque mat, records et progression, entraîneur d'attaque (`#/attaque` : positions de milieu de partie en roques opposés, même aile ou roi au centre, contre Stockfish bridé à l'Elo choisi de 1320 à pleine force, jusqu'au mat ou à un avantage décisif tenu).
  Le niveau du défenseur est mémorisé ; le changer en cours de partie demande confirmation et recommence la position.
  « Position au hasard » privilégie les positions jamais réussies de la catégorie affichée ; « Conseils » et « Indice » aident à mener l'attaque, et « Plan » montre une suite de Stockfish depuis la position de départ en fin de partie.
  Une fois l'avantage décisif atteint, tu peux conclure ou continuer : la réussite reste acquise, mais seules les réussites obtenues sans indice ni coup repris valident une position et son meilleur niveau battu.
  Entraîneur de défense (`#/defense`), le pendant de l'attaque : des positions de parties lichess où ton roi subit une vraie attaque mais où un coup précis tient encore, dans les mêmes catégories, contre Stockfish bridé à l'Elo choisi (2100 par défaut, mémorisé à part).
  La défense est réussie si tu tiens 12 coups sans que l'éval passe sous -3, ou si la partie finit en nulle ou en gain ; elle cède si l'éval reste sous -3 deux tours de suite, ou au mat ; un compteur « Coup 5/12 » suit la tentative.
  « Mes défenses ratées » (`#/defenses-ratees`) reprend les erreurs de tes bilans jouées pendant que l'adversaire attaquait ton roi, avec le coup de défense de Stockfish à retrouver.
- **Calcul et visualisation** (`#/visualisation`, depuis Apprendre) : une position figée, une ligne de 2, 4, 6 ou 8 demi-coups annoncée en notation sans bouger les pièces (visible, ou coup par coup puis cachée), puis une question sur la position d'arrivée imaginée : où est passée une pièce, quelle pièce est en prise, quel est le meilleur coup (confirmé par Stockfish), mat en un ou pas.
  On répond en touchant l'échiquier de départ, ou avec Oui/Non pour le mat en un, puis la position finale et la correction s'affichent ; trois erreurs terminent la série, avec un record par longueur et par affichage.
  Le module est hors Elo, sans limite de temps pour répondre ni révision espacée.
- **Structures de pions** : cours « Structures de pions » (`#/apprendre/structures`), un chapitre par structure typique : pion dame isolé (avec et contre), pions pendants, Carlsbad, étau de Maroczy, hérisson, chaînes bloquées française et est-indienne, Stonewall, Caro-Kann / slave, majorité à l'aile dame.
  Chaque leçon montre les plans des deux camps, les cases clés, les ruptures et les pièces bien ou mal placées, puis fait jouer le plan ; chaque coup des exercices est vérifié hors ligne par Stockfish 18.
  « Mes structures de pions » (`#/structures`, depuis Apprendre et le sommaire du cours) repère ces structures dans tes parties contre les bots et dans tes parties chess.com déjà passées au bilan par Insights, sans aucun appel réseau.
  Elle classe tes structures par fréquence, donne tes résultats (victoires, nulles, défaites) et le nombre de parties jouées avec ou contre chaque structure.
  Pour chaque structure repérée dans une partie, elle propose une position au trait du joueur dans sa première apparition stable retenue, à rejouer contre Stockfish bridé à l'Elo choisi, avec le plan de la structure en rappel.
- **Révision espacée** : carte « À réviser aujourd'hui » sur l'accueil (et ligne dans Apprendre), séance mixte et enchaînée (`#/revision`) des puzzles ratés, des fautes de parties et des variantes d'ouverture à revoir ; calendrier de Leitner J+1, J+3, J+7, J+21 calculé depuis l'historique existant, une réussite espace le prochain passage, un échec ramène à J+1, quatre jours de réussite d'affilée classent l'item acquis ; sans incidence sur les Elo.
- **Import chess.com** : page `/import` : pseudo chess.com (API publique, sans login) → liste des parties récentes → bilan en un tap ; ou coller un lien de partie ; ou Raccourci Apple pour partager depuis l'app chess.com (instructions dans la page).
- **Pièces** : sept jeux au choix (Stats → Réglages, avec aperçu), sur tous les échiquiers : Atelier par défaut, Wikimedia, Celtique, Chessnut, Fantasy, Spatial et Classique.
- **Déplacement tactile** : pièce soulevée à 1,7 fois sa taille et décalée au-dessus du doigt, disque translucide sur la case visée, destinations légales discrètes et retour animé des coups refusés sur tous les échiquiers interactifs.
  La souris conserve son glissé centré ; le clic-clic et la préférence de réduction des animations sont respectés.
- **Prémouvements** : prépare un coup par glissé ou clic-clic pendant la réflexion du moteur, avec deux cases rouges et la pièce toujours au départ.
  Le coup se joue automatiquement s'il reste légal, avec son et surlignage jaune ; sinon il est annulé silencieusement.
  Un seul coup prévu, annulable par un toucher sur l'échiquier, promotion en dame et coût de 0,1 seconde dans les modes chronométrés.
  Disponibles contre les bots, dans les parties depuis une position, les continuations contre moteur et les mats contre la montre, hors historique et fin de partie.
  Activés par défaut dans Stats → Réglages → Prémouvements ; absents des puzzles et exercices à solution unique.
- **Sons** : impacts extraits de la vidéo autorisée par Max pour les coups, prises, roques, échecs, promotions et refus ; notifications libres Kenney pour le début et la fin de partie, le temps bas et les résultats d'exercice.
  Ils accompagnent les parties, puzzles, Rush, Apprendre, Mats, finales, ouvertures et l'avance dans l'analyse, avec un volume réglable.
  L'audio est déverrouillé au premier geste et recréé après un passage en arrière-plan ; sur iPhone, le mode silencieux coupe les sons.
  L’extraction reproductible et la comparaison mesurée sont décrites dans [l'étude F14](docs/f14-feeling.md).
- **Archive** : toutes les parties sauvegardées (IndexedDB), relecture, bilan en un clic, export PGN global.
- **Insights** : page `/insights` (depuis Stats et l'accueil) : choix de la cadence et des 10, 25, 50 ou 100 dernières parties, issues de chess.com et/ou des parties ChessLocal contre les bots.
  Bullet, blitz et rapide sont disponibles pour les deux sources ; « Sans limite » exige ChessLocal, car chess.com ne fournit pas cette cadence.
  Les archives chess.com sont parcourues des plus récentes aux plus anciennes jusqu'au nombre demandé ou à épuisement ; si l'historique en contient moins, le nombre trouvé est indiqué.
  Chaque partie reçoit un bilan Stockfish avec progression et estimation de durée ; la série se met en pause en arrière-plan et reprend au retour, et « Annuler » puis « Reprendre » conserve les bilans terminés.
  Le cache est réutilisé à profondeur et compte identiques ; changer le nombre demandé peut changer la profondeur et entraîner un nouveau calcul.
  Le dernier rapport se rouvre hors ligne ; si chess.com est injoignable lors d'une nouvelle série, seules ses parties déjà analysées pour ce pseudo et cette cadence sont disponibles.
  Le rapport propose un résumé du coach par règles, jusqu'à 3 forces et 3 faiblesses chiffrées selon les données disponibles, un plan d'entraînement vers les modules de l'app et des exemples ouverts dans l'Analyse en conservant ton camp pour le bilan.
  Il couvre la tendance de précision, la précision par phase hors théorie, les ouvertures par couleur, les résultats par couleur et Elo adverse, les erreurs typiques, les attaques sur le roi manquées, la conversion, la défense, les gaffes adverses punies et les résultats juste après une défaite.
  Chaque faiblesse propose un entraînement adapté : attaque, défense, finales, ouvertures ou tactique.
  « Tu t’effondres quand ton roi est attaqué » compte tes erreurs et gaffes commises sous une attaque réelle du roi dans les bilans en cache, à partir de cinq parties analysées et de deux parties concernées.
  Ses boutons ouvrent l’entraîneur de défense et « Mes défenses ratées » ; l’attaque renvoie aussi vers son entraîneur et « Mes attaques manquées ».
  Les listes personnelles proviennent des bilans lancés dans Analyse, accessibles depuis les exemples ; leurs critères d’attaque diffèrent de ceux d’Insights.
  Les mesures de pendule utilisent les annotations `%clk` des PGN chess.com ; ChessLocal n'enregistre pas les temps par coup.
- **Stats** : classements par cadence, bilan V/N/D, thèmes d'échiquier, réglages, sauvegarde et restauration des données IndexedDB et des réglages (fichier JSON), état du stockage, réinitialisation de l'app.
  Les bilans Insights en cache sont inclus dans la sauvegarde, mais pas la configuration ni la sélection du dernier rapport ; une restauration conserve la configuration locale et invalide ce rapport, sans supprimer les bilans restaurés.
  Les résultats et records de Calcul et visualisation sont inclus dans la sauvegarde ; ses préférences de longueur et d'affichage restent sur l'appareil, hors sauvegarde, et sont effacées par la réinitialisation de l'app.

## Licences des ressources

Rien ne vient de chess.com.
Wikimedia : [Chess_Pieces_Sprite.svg](https://commons.wikimedia.org/wiki/File:Chess_Pieces_Sprite.svg) de jurgenwesterhof d’après Cburnett, découpé en 12 SVG vectoriels, dérivés sous [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
Pièces : jeux libres, Celtique, Fantasy et Spatial de Maurizio Monge (MIT, repris du dépôt de lichess, Celtique recoloré), Chessnut d'Alexis Luengas (Apache 2.0, « Copyright 2015 Alexis Luengas », repris du dépôt de l'auteur avec son `COPYRIGHT.txt`) ; détail et textes de licence dans `public/pieces/LICENSES.md`.
Classique : pièces SVG standard de Wikimedia Commons dessinées par Cburnett (publiées sous GFDL, CC BY-SA 3.0, BSD 3 clauses et GPL au choix, reprises sous BSD 3 clauses), embarquées par `react-chessboard` (MIT), qui les cite sous CC BY-SA 3.0.
Atelier et sons de coup : extrait d'une vidéo fournie par Max (2026-10-17), réutilisation autorisée par Max.
Les pièces sont redessinées en SVG, les sons extraits par `scripts/extract-video-sounds.py`.
Les anciens jeux restent sélectionnables ; Atelier n’est attribué qu’aux profils sans jeu enregistré, et la migration v2 conserve le jeu choisi, les autres réglages et les données.
Les notifications dérivent des packs Kenney « Impact Sounds » et « Interface Sounds » (CC0 1.0), régénérés par `scripts/make-sounds.sh` ; détail dans `public/sounds/LICENSES.md`.

## Architecture

- React 19 + Vite + TypeScript + Tailwind 4, état client Zustand, persistance Dexie (IndexedDB).
- Moteur : `stockfish` npm (build `lite-single`, mono-thread, pas de COOP/COEP requis), wrapper UCI maison dans `src/lib/engine.ts`.
  Toutes les commandes moteur sont sérialisées par un mutex : deux `go` sans `stop` intermédiaire font trap le WASM.
- Données : les commandes de génération propres à chaque banque sont décrites dans [CLAUDE.md, section Commandes](CLAUDE.md#commandes).
- Debug moteur : ajouter `?debug-uci` à l'URL pour logger le trafic UCI en console.
