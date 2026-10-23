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
npm run build          # tsc -b && vite build
npm run check          # lint (oxlint) + typecheck (tsc -b) : à lancer avant tout commit
npm run preview        # sert dist/
```

Les suites incluent des vérifications unitaires sous Node, notamment du calcul pur d'Insights dans `e2e/test_insights.py`.
Les tests sont des suites E2E Playwright en Python (`e2e/test_*.py`), lancées par `e2e/run.py` :

```bash
npm run test:e2e                          # build de prod servi sous /chess-local/ (comme GitHub Pages), toutes les suites
npm run test:e2e -- --suite learn         # une seule suite, nommée d'après son fichier e2e/test_<nom>.py (cumulable : --suite learn --suite touch)
npm run test:e2e:dev                      # serveur de dev : StrictMode double les updaters et révèle les effets de bord mal placés
BASE=https://maxencebrochard.github.io/chess-local npm run test:e2e   # contre la prod déployée, sans serveur local
npm run test:e2e -- --suite all_buttons --live                        # API chess.com réelle au lieu de la fixture, hors gate
npm run test:e2e -- --jobs 1              # une suite à la fois, sortie en direct (défaut : E2E_JOBS, sinon 2, ou 1 sur un seul cœur)
```

Prérequis hors `npm ci` : `pip install -r e2e/requirements.txt`.
Chromium vit dans `~/.local/share/chess-local/ms-playwright`, hors de `~/Library/Caches` que les nettoyages de disque vident : `e2e/run.py` y fixe `PLAYWRIGHT_BROWSERS_PATH` pour les suites et l'installe tout seul s'il manque (`PLAYWRIGHT_SKIP_BROWSER_GC=1`, environ 150 Mo, une fois).
Un `PLAYWRIGHT_BROWSERS_PATH` déjà exporté est respecté.
`e2e/run.py` démarre son propre serveur sur un port libre, vérifie que c'est bien cette app qui répond, surveille le serveur pendant les suites et l'arrête toujours.
Les suites tournent en parallèle sur `--jobs N` workers (ou `E2E_JOBS=N`), avec deux workers par défaut (un sur un seul cœur).
Chacune a son groupe de process et son `TMPDIR` (Chromium compris, tué et nettoyé à la fin) ; en parallèle, sa sortie est imprimée d'un bloc à sa fin, avec un point d'avancement par minute.
En mode dev, `e2e/vite.config.ts` reprend la configuration de l’app et désactive seulement la surveillance des fichiers et HMR : une documentation ou un test modifié ne doit pas recharger la page pendant un geste.
StrictMode reste actif ; `npm run dev` conserve sa configuration habituelle.
En parallèle, les plus longues partent d'abord, d'après `e2e/shots/.durations.json` (dernière durée réussie par suite et par mode, locale) ou à défaut `TYPICAL_S` de `run.py`.
Le bilan donne la durée de chaque suite et la durée totale.
Une suite ne doit donc rien partager avec une autre : port libre pour tout serveur propre, fichiers dans `tempfile`, captures aux noms préfixés par la suite.
Les checks de calcul utilisent le temps CPU ; le contrôle audio combine l'ordre des événements et les budgets décrits dans [l'étude F14](docs/f14-feeling.md).
Ne jamais lancer une suite contre un serveur démarré à la main sur un port fixe : un serveur mort ou fantôme a déjà fait chercher un bug qui n'existait pas.
Le code de sortie est la vérité : non nul dès qu'un check échoue, qu'une page lève une exception (`pageerror`) ou qu'un appel chess.com sort de la fixture.

Écrire une suite : tout passe par `e2e/helpers.py`.
`Checker` porte les checks (`check`, `appears`) et le code de sortie, `mobile_context`/`desktop_context` créent des contextes surveillés (iPhone 14 Pro tactile, `standalone=True` pour le viewport de la PWA installée), `drag_piece` fait un vrai drag TACTILE via CDP.
Un check doit pouvoir échouer : pas de `check(nom, True)`, pas d'attente nue dont l'échec interrompt la suite (utiliser `ck.appears`).
Les contextes pré-remplissent `localStorage['chess-local-settings']` au format Zustand persist (`{state: {...}, version: 2}`) avec `reviewDepth: 'fast'` et les sons coupés.
Changer la forme du store `src/store/settings.ts` impose de mettre à jour `DEFAULT_SETTINGS` dans `e2e/helpers.py`.
L'API chess.com est simulée par `e2e/fixtures/chesscom.json` (parties fictives) : tout nouvel appel réseau doit y être ajouté.
Le gate n'utilise jamais `--live`.
`test_revision.py` sème IndexedDB nativement (après `wait_schema`, l'app ayant créé le schéma de `src/lib/db.ts`), bloque le service worker et remplace `puzzles.json` par une route ; ses dates sont relatives aux jours civils locaux (midi J-n, ou minuit plus une minute pour « aujourd'hui »), jamais « il y a une heure ».
`test_parcours.py` remplace `puzzles.json` par une fixture synthétique (un mat en un connu sous un id et un Elo propres à chaque série et à chaque bande du test de placement), sème `learnSessions` nativement après `wait_schema`, et bundle `scripts/learning-path-entry.ts` avec rolldown pour vérifier la logique pure sous Node.
`test_seance.py` suit le modèle de `test_revision.py` (et 404 sur `puzzles.json` pour le parcours sans puzzles) ; son banc Node tourne sous `TZ=Europe/Paris` pour le cas du passage à l'heure d'été.
`test_accueil.py` sème la base après `wait_schema`, répond 404 à `puzzles.json` en notant chaque demande (l'accueil n'en fait aucune), bloque la chunk du compteur de révision (`REVISION_CHUNK`) pour l'état indisponible et bundle `src/lib/homePlan.ts` avec rolldown pour la priorité et le partage des révisions sous Node (`TZ=Europe/Paris`).
`test_pwa.py` ne tourne que sur le build local : sous-chemin, manifest, service worker, précache, puis redémarrage avec le serveur réellement tué (`set_offline` ne coupe pas le réseau du service worker) et ouverture hors ligne de chaque page paresseuse.
`test_perf.py` (prod uniquement) porte les budgets de performance, CPU ralenti 4x sur iPhone 14 Pro standalone : JS initial en gzip, JS chargé par l'accueil, accueil interactif à froid (latence 4G) et à chaud (service worker), premier puzzle, plus longue tâche pendant un glissé sur Analyse, et présence de chaque fichier du build dans le précache.
Les budgets de temps sont multipliés par la charge mesurée de la machine (boucle de calibration), jamais réduits ; ceux d'octets et de précache sont fixes.
La même suite rejoue un déploiement (build A installé, build B aux chunks renommées servi à sa place) et une chunk introuvable ; le détail des mesures va dans `e2e/shots/perf-metrics.json`.
`test_upgrade.py` (prod uniquement) est le garde-fou de continuité des données : pour chaque ancien build déployé épinglé dans `OLD_BUILDS` (tags `deployed-2026-07-20`, `deployed-2026-10-06`, `deployed-2026-10-15`, `deployed-2026-10-16`, `deployed-2026-10-22`, `deployed-2026-10-22-2`, `deployed-2026-10-23` et `deployed-2026-10-23-2`, extraits de git ; `git fetch origin tag <tag>` s'il manque), il le sert, y crée de vraies données par l'interface dans un profil persistant, bascule sur le build courant sur le même port, vérifie IndexedDB, réglages et chiffres affichés à l'identique, puis restaure une sauvegarde de l'ancien build dans le nouveau ; `E2E_MUTATION=rename-db|clear-ratings|drop-table|clear-settings` sert une copie mutée du nouveau build pour prouver que la suite passe au rouge.
`E2E_MUTATION=truncate-old-precache` fait couper par l'ancien serveur le corps de `puzzles.json` : l'installation du service worker de l'ancien build échoue à chaque fois, et les réessais bornés de `wait_sw_active` (contre les « Cache.put() encountered a network error » ponctuels sous charge) doivent finir en rouge.
Après un déploiement, ajouter le nouveau tag à `OLD_BUILDS` et retirer un build que plus aucun appareil ne porte.
`test_bug_hunt.py` rejoue un scénario utilisateur par bug corrigé lors de la chasse aux bugs (réinitialisation, classes du bilan, liste des coups, barre d'éval, variante d'une partie archivée, date du PGN, worker de finale orphelin) ; `BUG_CASE=<nom>[,<nom>...]` cible des scénarios.
Chaque lancement build dans son propre dossier temporaire, jamais dans `dist/` : deux lancements simultanés ne se gênent pas.
Les captures vont dans `e2e/shots/` (gitignoré).
La suite `apprendre` (`e2e/test_apprendre.py`) mesure le budget de taps d'Apprendre en tapant chaque chemin depuis l'Accueil (quatre au plus, onglet compris) et exige qu'il atteigne chaque route de la famille ; elle vérifie aussi les retours des pages et la liste des moments critiques.
Ses bilans semés vivent dans `e2e/moment_fixtures.py`, partagés avec `ux_audit` ; les séances par domaine s'ouvrent dans les suites par `open_learn_session` et Mes erreurs par `open_mistakes_session` (`helpers.py`).
La suite `ux_audit` photographie les familles de routes et leurs états principaux aux trois formats de référence, avec inventaire DOM dans `e2e/shots/ux-audit/{prod,dev}/`.
Elle lit la table des routes dans l'arbre React monté et échoue si une route déclarée dans `App.tsx` n'a aucun état dans sa matrice : toute nouvelle route s'y ajoute (`UX_AUDIT_FORGET=<chemin>` en fait la preuve par mutation).
Le diagnostic et le plan de refonte différée sont dans [docs/ux-refonte.md](docs/ux-refonte.md), sans changement des routes ni des domaines `learnSessions` dans cette phase.
`E2E_CPU_RATE=40 npm run test:e2e -- --suite cours_roque --suite endgame_course --suite cours_defense` reproduit un CPU ralenti via CDP (facteur 1 par défaut), sans changer les délais des assertions.
Les gestes partagés de ces suites vivent dans `e2e/course_helpers.py` : attendre le titre et le numéro d’étape après navigation, puis le changement de tour après Solution.
Un clic terminé ne garantit pas que React a déjà remplacé le diagramme précédent ; ne pas synchroniser ces transitions avec une pause fixe.


Autres scripts :

- `node scripts/prepare-data.mjs` régénère `public/puzzles.json` et `src/data/openings.json`.
  Il lit `data/puzzles_full.csv` (dump lichess décompressé), absent du repo : seuls les `data/openings_*.tsv` sont versionnés.
- `python3 scripts/verify-endgame-course.py` revérifie `src/data/endgameCourse.json` contre les tables de finales lichess (réseau) et réécrit son tampon `scripts/endgame-course.verified`.
  À lancer après toute modification du cours de finales : sans tampon à jour, `scripts/check-endgame-course.mjs` (suite `endgame_course`) échoue.
- `python3 scripts/verify-attack-course.py` revérifie `src/data/attackCourse.json` (cours « Démolir le roque ») avec Stockfish 18 natif (`STOCKFISH` ou `stockfish` du PATH, mono-thread, profondeurs fixes, cache dans `~/.cache/chess-local/`) et réécrit `keeps`, `close`, `eval` et le tampon `scripts/attack-course.verified`.
  À lancer après toute modification de ce cours : sans tampon à jour, `scripts/check-attack-course.mjs` (suite `cours_roque`) échoue.
  Les cours partagent le moteur `src/lib/lessonCourse.ts`, la page `src/pages/LessonCourse.tsx` et les règles `scripts/course-rules.mjs`.
- `python3 scripts/verify-basics-course.py` revérifie `src/data/basicsCourse.json` (cours « Les bases », `#/apprendre/bases`) avec le même vérificateur (`verify-attack-course.py <json> <tampon>`) et réécrit le tampon `scripts/basics-course.verified`.
  À lancer après toute modification de ce cours : sans tampon à jour, `scripts/check-basics-course.mjs` (suite `parcours`) échoue.
  Les deux tampons portent en second mot le sha de `verify-attack-course.py` : modifier ce vérificateur impose de relancer les deux cours.
  Les règles de contrôle communes à ces deux cours vivent dans `scripts/check-stockfish-course.mjs` ; chaque point d'entrée ne porte que ses ids figés.
- `node scripts/check-learning-path.mjs` contrôle `src/data/learningPath.json` (parcours d'apprentissage) : ids figés, ordre des niveaux, références et viviers de puzzles, avec la vraie logique de l'app bundlée par rolldown depuis `scripts/learning-path-entry.ts` (suite `parcours`).
- `WORKERS=2 python3 scripts/verify-structures-course.py` revérifie `src/data/structuresCourse.json` (cours « Structures de pions », `#/apprendre/structures`) avec la plomberie moteur de `verify-attack-course.py` (importée par chemin, cache `~/.cache/chess-local/structures-eval.json`) et réécrit `keeps`, `close`, `eval` et le tampon `scripts/structures-course.verified`.
  Ses lignes ont le résultat `plan` : les critères et seuils vérifiés sont décrits dans le docstring de `scripts/verify-structures-course.py`.
  Le tampon porte le sha du JSON et des deux vérificateurs : modifier `verify-attack-course.py` impose de relancer aussi celui-ci, sinon `scripts/check-structures-course.mjs` (suite `structures`) échoue.
- `python3 scripts/verify-defense-course.py` revérifie `src/data/defenseCourse.json` (cours « Tenir sous l'attaque », pendant défensif du précédent : l'élève joue le camp attaqué) avec Stockfish 18 natif (même table de hachage, profondeur 24 pour tous les verdicts, `WORKERS` moteurs mono-thread, 2 par défaut, cache `~/.cache/chess-local/defense-eval.json`) et réécrit `keeps`, `close`, `eval`, `failsEval` et le tampon `scripts/defense-course.verified`.
  Paliers de ligne : `hold` (l'élève à -0,5 au moins), `edge` (+1), `win` (+2) ; claims `hold-w`/`hold-b` ; `threat` = mat en un de l'attaquant à trait inversé, revérifié par le contrôle.
  À lancer après toute modification de ce cours : sans tampon à jour, `scripts/check-defense-course.mjs` (suite `cours_defense`) échoue.
- `python3 scripts/prepare-mates.py` régénère `src/data/mateDrills.json` (positions « contre la montre » de /mats, vérifiées sur `tablebase.lichess.ovh`, réseau requis).
- `python3 scripts/prepare-endgame-clock.py` régénère `src/data/endgameClock.json` (banque des Finales au chrono) : familles reprises par id de `src/data/endgames.json` ou écrites dans le script, chacune déclinée en miroir a-h et couleurs inversées, chaque variante sondée sur `tablebase.lichess.ovh` (cache partagé `~/.cache/chess-local/tablebase.json`, réseau requis sinon) avec une ligne optimale des tables, puis tamponnée dans `scripts/endgame-clock.verified`.
  À relancer après toute modification de ses familles ou des finales qu'il reprend : `--check` (hors ligne, suite `finales_chrono`) échoue sinon.
- `node scripts/prepare-mates-index.mjs` régénère `src/data/mateIndex.json` (puzzles classés par géométrie de mat avec `src/lib/mateNet.ts`) : à relancer après `prepare-data.mjs` ; la suite `mats` vérifie qu'il est à jour (`--check`).
- `python3 scripts/prepare-attacks.py` régénère `src/data/attacks.json` (banque de l'entraîneur d'attaque) : parties lichess des puzzles d'attaque (API publique, cache `data/lichess-puzzle-games.jsonl` non versionné), positions reculées avant la combinaison et triées par Stockfish natif (`STOCKFISH`, sinon celui du PATH).
  Thème, consigne et plan sont calculés par `scripts/attack_facts.py`, que la suite `attaque` réutilise ; `--relabel` les recalcule sans moteur.
- `python3 scripts/prepare-defenses.py` régénère `src/data/defenses.json` (banque de l'entraîneur de défense) : mêmes puzzles et même cache lichess que l'attaque, positions reculées de 1, 3 ou 5 demi-coups (défenseur au trait, avant le coup qui a craqué), gardées si Stockfish natif les juge défendables avec un seul bon coup et sous une vraie menace (coup nul), cache d'évals `data/defense-evals.jsonl` non versionné, clés incluant les seuils.
  `scripts/attack_facts.py` prend l'attaquant en paramètre (`att`, défaut le camp au trait) ; les phrases vues du défenseur sont dans `scripts/defense_facts.py`, que la suite `defense` réutilise ; `--relabel` les recalcule sans moteur.
  Le script affiche les rejets par critère et par catégorie ; le calibrage retenu est noté dans son docstring.
- `python3 scripts/prepare-visualisation.py` régénère `src/data/visualisation.json` (banque de « Calcul et visualisation ») depuis `public/puzzles.json` et réécrit son tampon `scripts/visualisation.verified`.
  Le meilleur coup de chaque position finale est confirmé par Stockfish natif (au plus deux processus mono-thread, cache de reprise dans `~/.cache/chess-local/`) ; sans tampon à jour, `scripts/check-visualisation.mjs` (suite `visualisation`) échoue.
- `python3 scripts/prepare-conversions.py` régénère `src/data/conversions.json` (banque de « Convertir l'avantage ») : puzzles lichess `advantage` de `public/puzzles.json` (aucun réseau), solution jouée puis suite de Stockfish natif jusqu'à une position calme, triées à +2..+4,5 sans tactique qui rafle (cache `data/conversion-evals.jsonl` non versionné, clé versionnée par `CRITERIA`).
  Catégorie, thème, consigne et plan sont calculés par `scripts/conversion_facts.py`, que la suite `convertir` réutilise ; `--relabel` les recalcule sans moteur ; `source.uci` garde les coups ajoutés, rejoués par la suite.
- `scripts/deploy.sh` build puis force-push `dist/` sur la branche `gh-pages`.
  Action sortante : ne pas le lancer sans demande explicite.
  Le push final est en HTTPS et échoue avec le compte GitHub par défaut de la machine ; `set -e` arrête alors le script avant `rm -rf dist/.git`, le commit reste dans `dist/`.
  Depuis `dist/`, le push peut se faire en SSH : `git push -f git@github.com:maxencebrochard/chess-local.git gh-pages`, puis `rm -rf dist/.git` depuis la racine.
  Poser ensuite le tag du déploiement, seule poignée durable sur ce commit (la branche est réécrite à chaque déploiement) : `git fetch origin gh-pages && git tag deployed-AAAA-MM-JJ FETCH_HEAD && git push origin tag deployed-AAAA-MM-JJ`.
  La date du tag est le jour UTC du `__BUILD__` (affiché en bas de `/import`), que `test_upgrade.py` recoupe.
  Un second déploiement le même jour UTC prend le suffixe `-2` (puis `-3`...) : `deployed-AAAA-MM-JJ-2`.
- `?debug-uci` dans l'URL logge le trafic UCI en console.
- `npm run ios:sync` construit le web puis le copie dans le projet Xcode `ios/` (Capacitor 8, SPM) ; `npm run ios:open` ouvre Xcode.
  Il faut Xcode 26 ou plus : voir `docs/ios-app.md`.
- `node scripts/bench-bots.mjs --preset chain --games 80 --out bench.jsonl` mesure l'Elo des bots (parties bot contre bot, Bradley-Terry ancré sur Iris = 1600, IC 95 % par bootstrap).
  Il exécute la vraie `bots.ts` et la vraie classe `Engine` sur le même WASM, dans Node ; compter environ une heure.
  À relancer après tout changement de style ou d'Elo d'un bot faible.

## Architecture

Stack : React 19, Vite 8, TypeScript, Tailwind 4, Zustand (réglages), Dexie (IndexedDB), chess.js, react-chessboard, Stockfish 18 WASM.
`src/pages/` contient une page par route, `src/lib/` la logique sans React, `src/components/` les briques partagées.

### Moteur (`src/lib/engine.ts`)

Un `Engine` = un worker Stockfish (`public/engine/`, build `lite-single` mono-thread, donc pas de COOP/COEP).
Les commandes UCI passent par un mutex (chaîne de promesses) : deux `go` sans `stop` intermédiaire font trap le WASM (`unreachable`).
Ne jamais envoyer de commande UCI en dehors de `exclusive()`.
`searchId` invalide les callbacks `onLines` d'une recherche remplacée : toute nouvelle méthode de recherche doit passer par `attachInfoListener()`.
Les scores sont du point de vue du trait ; les convertir explicitement avant de les afficher côté blanc.

Chaque page crée son moteur paresseusement dans un `useRef` (`engineRef.current ??= new Engine()`) et appelle `quit()` au démontage.
`Play.tsx` en tient deux : celui du bot est bridé par `UCI_LimitStrength`/`UCI_Elo` (`src/lib/bots.ts`), celui du coach live reste à pleine force pour évaluer les coups.
Pour des recherches concurrentes ou des options différentes, créer un second `Engine` plutôt que partager le même.
Sous 1320 Elo (plancher de `UCI_Elo`), un bot a un `style` : Stockfish pleine force à profondeur fixe en MultiPV, puis tirage pondéré par la perte (`pickWeakMove`), sans jamais rater un coup qui s'impose.
Toute la décision passe par `chooseBotMove` de `bots.ts` ; les styles sont calibrés par `scripts/bench-bots.mjs`.

### `/analyse` est le hub

Les autres pages y envoient leur contenu par state de navigation :
`navigate('/analyse', { state: { pgn | fen, uci?, viewIndex?, color?, orientation?, label?, review?, returnTo?, returnLabel? } })`.
La séance du jour (`/seance`) y envoie ses puzzles, fautes et variantes avec `returnTo: '/seance'` et « Retour à la séance ».
Archive et fin de partie passent par `?game=<id>` (lecture dans Dexie), avec `&review=1` pour lancer le bilan directement.
`Analysis.tsx` consomme `location.state` au montage puis fait `navigate('.', { replace: true, state: null })` pour qu'un refresh ne rejoue pas le chargement.
`returnTo` affiche un bouton retour (libellé `returnLabel`, « Retour à l'exercice » par défaut) qui navigue avec `state: { restore: true }` ; `Learn.tsx` et `Revision.tsx` restaurent alors leur séance depuis `sessionStorage`.
Tout écran d'exercice donne accès à l'analyse de sa position et son retour rend l'exercice tel qu'il était : même position, même progression, verdict déjà écrit jamais réécrit, chrono jamais relancé.
Chaque écran garde son état là où il le garde déjà : `learn-session-v1`, `revision-session-v1`, `path-session-v1`, `seance-session-v1`, le puzzle classé dans `localStorage`, la partie de `PositionGame` dans `chess-local-position-game-v1`.
Les écrans sans séance persistée écrivent juste avant `navigate('/analyse')` une entrée de `lib/exerciseReturn.ts` (`stashExercise(écran, état)`, clé unique `exercise-return-v1`) et ne la relisent qu'au retour (`readExercise`, `state.restore`) : drill de l'entraîneur d'ouvertures et sorties de « Mon répertoire », bilans du Puzzle Rush, des Mats éclair (puzzles et contre la montre) et des Finales au chrono, série de visualisation, étape de leçon (avec l'origine « séance » et le coup atteint dans une ligne).
`OpeningDrill` rend son verdict à l'appelant (`DrillSnapshot` passé à `onAnalyse`) et le reprend par sa prop `snapshot` sans réécrire : révision, séance du jour et parcours reprennent ainsi une variante jugée sur son verdict ; un état sans ce verdict (version antérieure) reprend à l'item suivant.
Une série de visualisation reprise garde sa ligne `learnSessions` (`RunRecorder` construit avec l'id déjà écrit).
Un écran efface `exercise-return-v1` au montage, après l'avoir lu : un autre retour vers lui (lien d'analyse sans reprise, comme « Partie » du répertoire) ne reprend jamais un état périmé.
Au retour de l'analyseur sur le dernier item d'une série du parcours, son verdict revient avant l'écran d'enregistrement (« Voir le résultat » enregistre).
Règle d'équité, celle des puzzles classés : l'analyse ne s'ouvre qu'après le verdict dans un exercice noté ou chronométré (puzzle classé, Apprendre, révision, parcours, drills, visualisation, parties de `PositionGame`) ; Puzzle Rush, Mats éclair et Finales au chrono ne la proposent qu'au bilan de la série close.
Les leçons des cours, non notées, l'ouvrent à toute étape avec échiquier ; l'alerte menace de Jouer reste sans analyse pendant la partie, sa position se relit dans le bilan de fin de partie.
Les suites de chaque famille vérifient l'aller-retour (position transmise, restauration exacte, aucune écriture de plus) : `puzzles`, `mats`, `finales_chrono`, `visualisation`, `openings`, `repertoire`, `revision`, `seance`, `parcours`, `endgame_course`, en plus de `learn` et des suites de `PositionGame`.
Partie contre Stockfish depuis une position : `components/PositionGame.tsx` (logique pure dans `lib/positionGame.ts`), utilisé par `/attaque/:id` (`pages/Attack.tsx`), `/defense/:id` (`pages/Defense.tsx`), `/convertir/:id` (`pages/Convert.tsx`), `/finales/:id` (finales jouées jusqu'au bout, `pages/Endgames.tsx`), `/analyse/jouer` (bouton « Jouer contre le moteur » de l'analyse, `pages/PositionPlay.tsx`), `/attaques-manquees/:id`, `/defenses-ratees/:id` et `/moment-critique` (moments critiques du bilan, `pages/CriticalMoment.tsx`).
Elle est présentée avec l'habillage commun d'exercice (en-tête, bande adversaire et compteurs au-dessus de l'échiquier, objectif et actions de jeu dans la zone de décision, coups et légende en `below`, leçon ou conseils dans une feuille `InfoSheet`) ; son ton de verdict est dérivé à l'affichage, `data-verdict` garde le jugement de l'objectif et `data-tone` le ton.
La partie en cours est rejouée depuis `localStorage['chess-local-position-game-v1']` ; les résultats des finales vont dans `learnSessions` (domaine `endgame-play`, hors Elo).
Un seul emplacement de persistance : une tentative en cours écrasée par une autre partie passe par `recordReplaced` (`lib/attempts.ts`), qui aiguille selon le préfixe de clé (`attaque:`, `defense:` et `convertir:` notées abandonnées) ; tout appelant de `PositionGame` lui passe `onReplace={recordReplaced}`.
L'entraîneur de défense (`/defense`, `lib/defense.ts`) utilise l'objectif `hold` de `PositionGame` (prop `hold: { moves, floorCp }`, 12 coups, plancher -3) : après chaque réponse de Stockfish, l'oracle à pleine force évalue la position ; strictement sous le plancher (ou mat contre le joueur) deux tours de suite donne la fin `collapsed`, et au 12e coup une éval de confirmation d'une seconde, échiquier bloqué, décide `held` ou `collapsed`.
La partie s'arrête sur ces deux fins, sans Continuer ni Annuler ; une nulle de l'échiquier ou un gain réussissent aussi, pas de bouton Nulle ; la série sous le plancher est persistée avec la partie (`holdFall`).
Ses niveaux sont ceux de l'attaque (`LEVELS`, 2100 par défaut), mémorisés sous `localStorage['chess-local-defense']`, purgé par la réinitialisation.
Chaque tentative est une ligne `learnSessions` du domaine `defense` (format dans `db.ts` : `outcome` parmi `held | draw | win | mated | collapsed | resign | abandon`, Elo de l'attaquant dans `attackerElo`), sans Elo et ignorée par `pickNextDomain`.
« Convertir l'avantage » (`lib/conversion.ts`) réutilise les niveaux, le bridage et les statistiques de `attack.ts` : domaine `conversion` (mêmes champs que `attack`), niveau dans `localStorage['chess-local-conversion']`, réussite au mat ou à +8 tenu deux tours (`CONVERT_DECISIVE_CP`), toute nulle est un échec.
Finales au chrono (`/finales/chrono`, `pages/EndgameClock.tsx`, `components/EndgameClockRun.tsx`, logique pure dans `lib/endgameClock.ts`) : une famille de finales théoriques ou le mélange, en série jusqu'au premier raté, contre Stockfish pleine force (`movetime` 150 ms).
La pendule du joueur seule (`components/usePlayerClock.ts`, partagée avec le contre la montre de Mats éclair) ne tourne qu'à son trait, ajoute l'incrément après chaque coup et débite 100 ms par prémouvement.
Gain : mat, roi adverse nu face à dame ou tour, ou promotion en dame qui survit à la réponse avec 3 points d'avance ; raté au drapeau, à une nulle, ou après trois réponses où le moteur s'estime à -0,50 ou mieux.
Nulle : toute nulle par les règles, ou 15 coups tenus quand le moteur ne voit ni mat ni plus de +1,50 ; ces seuils sont validés par la suite `finales_chrono` sur les lignes optimales des tables.
Le coup du moteur reste au temps (150 ms), mais ces deux verdicts viennent d'une seconde recherche de la position, à `VERDICT_NODES` nœuds (100 000) après `ucinewgame` : même score sur tout appareil et sous charge, et la suite les rejoue avec exactement cette recherche (`Solver.score`).
Changer `VERDICT_NODES` impose de relancer la suite : à 10 000 nœuds la banque passe encore, le réglage garde de la marge (pire nulle +63, pire gain +170).
Une ligne `learnSessions` par série (domaine `endgame-clock`, `RunRecorder` de `mates.ts`), la cadence choisie dans `localStorage['chess-local-endgame-clock']`.

### Pipeline d'évaluation

`review.ts` évalue chaque position en multipv 2 à profondeur fixe, convertit en win% (formule lichess) et classe chaque coup selon la chute de win%.
Les nulles du bilan sont détectées avec l’historique complet ; le sacrifice utilise l’échange statique légal de `motifs.ts`, et un coup unique ne reçoit ni « Très bon » ni « Brillant ».
`MoveClass`, `CLASS_META` (libellés, couleurs, symboles) et les seuils vivent uniquement là.
En dépendent : `coach.ts` (commentaires post-partie générés par règles), `liveCoach.ts` (classe rapide du mode entraîneur), `ReviewSummary`, `EvalGraph`, `MoveList`.
Modifier la ligne analysée détache sa clé et son libellé de la partie archivée, tout en conservant le camp du joueur.
Un bilan lancé dans Analyse écrit les fautes dans la table `mistakes`, rejouées ensuite dans Apprendre → Mes erreurs.
Le résumé du bilan se termine par « Moments critiques » (`components/CriticalMoments.tsx`, inséré par Analysis via la prop `extra` de `ReviewSummary`) : `criticalMoments.ts`, pur et testé sous Node par `test_moments.py`, retient au plus 3 coups du joueur, les plus grosses chutes de win% (au moins 10 points, coup différent de celui de Stockfish) et les coups uniques trouvés (2e coup à plus de 20 points, lu dans `winPctSecond` de `ReviewedMove`).
La réponse à « Plan, menace ou coup forcé ? » se déduit de l'échiquier : coup forcé si un seul coup tient ou si le meilleur coup mate, sinon menace (échec, ou coup nul : mat en 1, prise gagnant au moins 2 points par `see`, promotion libre), sinon plan.
Rejouer ouvre `/moment-critique` (`pages/CriticalMoment.tsx`, PositionGame avec `keyMove`) ; la sortie rouvre l'analyse avec `state.bilan`, que `restorableBilan` n'accepte que s'il correspond coup pour coup au PGN, et le résumé revient sans recalcul ni réécriture des fautes.
Le state de l'exercice est construit par `momentState` (`criticalMoments.ts`), le même depuis le bilan et depuis la liste « Moments critiques » (`#/apprendre/moments-critiques`, `pages/MomentsList.tsx`).
La liste relit le cache des bilans d'Insights (`reviews`, parties `local:` et `chesscom:` de tous pseudos) par `loadMomentGames`, sans moteur ni écriture : le bilan lancé dans l'analyse n'étant pas conservé, ses moments n'y figurent pas.
Elle passe `from: 'liste'`, gardé dans le `back` de la partie persistée : la sortie revient à la liste (même après rechargement) et « Voir le bilan » rouvre l'analyse, dont le retour mène à la liste ; une partie de l'app y prend la clé `game:<id>` de l'Archive.
Les résultats vont dans `learnSessions` (domaine `critical-moment`, format d'`itemId` documenté dans `db.ts`), hors Elo ; `pickNextDomain` les ignore.
« Pourquoi ? » (`components/RefutationPlayer.tsx`, ouvert depuis le bilan guidé, la carte du coach et `MistakeExercise` après le verdict) déroule la réfutation : un `Engine` dédié cherche la ligne après le coup fautif puis l'éval après le bon coup (réglage décrit dans le [README](README.md#features)), sans jamais chercher une position finie, et `quit({ immediate: true })` détruit le worker au démontage.
`lib/refutation.ts`, pur, en tire les faits de chaque demi-coup (motifs.ts, bilan matériel cumulé sur la ligne réelle, jamais d'estimation d'échange) et une phrase par fait ; seules les fautes `EXPLAINED_CLASSES` du camp du joueur (les deux si inconnu) ont le bouton, et rien n'est écrit en base.
La suite `refutation` revérifie chaque fait et chaque phrase sur environ 2 000 puzzles lichess (coup fautif puis réfutation réelle) contre un oracle python-chess.
`kingAttack.ts` (chess.js seul) relit ces fautes pour « Mes attaques manquées » (`/attaques-manquees`) : le type d'attaque (mat, sacrifice près du roi, pion contre le roque, pièce vers le roi) est recalculé sur l'échiquier depuis `fenBefore` et `bestUci`, jamais stocké ; seules les lignes avec `color` (camp du joueur connu du bilan) comptent, `gameKey` identifie la partie.
« Mes défenses ratées » (`/defenses-ratees`, `missedDefense` du même module) relit les mêmes lignes avec `color` et une classe `mistake` ou `blunder` : sur `fenBefore`, le joueur au trait, au moins deux pièces adverses visent la zone de son roi et au moins autant que ses défenseurs (`zoneCounts`), l'adversaire a au moins trois pièces, et son roi est roqué ou au centre.
L'exercice reprend exactement celui des attaques manquées (retrouver `bestUci`, `keyMove`), noté dans le domaine `missed-defense` ; une même faute peut figurer dans les deux listes.
Le même module porte le calque « Compte les attaquants » (réglage `showAttackers`) : zone = anneau du roi de Stockfish (3x3 ramené dans b-g / 2-7), compte des seules pièces ; la suite `diagnostic_attaque` le vérifie contre un oracle python-chess.
Insights (`/insights`) réutilise `reviewGame` (paramètre `pause` pour suspendre la série quand la page est masquée), met les bilans en cache dans `reviews` (clé `chesscom:<id>` ou `local:<id>`, une profondeur par rapport) et calcule tout dans `insights.ts`, pur et testé sous Node par `test_insights.py` ; il n'écrit jamais dans `mistakes`.
Les plans d’Insights relient l’attaque à `/attaque` et `/attaques-manquees`, et la défense du roi à `/defense` et `/defenses-ratees`, en réutilisant les boutons de `Finding.plan`.
`kingDefense` compte les coups du joueur de classe `mistake` ou `blunder` reconnus par `missedDefense`, les parties concernées et leur perte cumulée de win%, avec trois exemples au plus.
La faiblesse `roi-attaque` exige cinq parties analysées et au moins deux fautes dans deux parties distinctes ; sa sévérité est la part de l’avantage perdu, sans filtre de phase supplémentaire.
Les listes personnelles restent indépendantes du cache Insights et le diagnostic d’attaque y utilise ses propres critères ; lancer un bilan dans Analyse depuis un exemple les alimente en conservant le camp du joueur.
Les structures de pions (`src/lib/structures.ts`, pur, chess.js seul) sont reconnues sur les seuls pions, pour un camp « porteur » : `e2e/structures_oracle.py` en est la réécriture python-chess, comparée par `test_structures.py` sur toutes les positions des ouvertures et un échantillon de puzzles ; changer une règle impose de changer l'oracle.
« Mes structures de pions » (`/structures`, `src/lib/myStructures.ts`) relit `games` (parties contre un bot) et `reviews` (source `chesscom` seulement, tous pseudos), repère chaque structure au milieu de partie (`structuresInGame` : demi-coup 10, trois pièces par camp sauf la majorité, quatre positions stables) et propose la première position de la série au trait du joueur ; `/structures/:key` la joue avec `PositionGame` et écrit le domaine `structure-play` (contrat dans `db.ts`), ignoré par `pickNextDomain` et la révision.
L'entraîneur d'ouvertures (`/ouvertures`, `src/lib/openingTrainer.ts`) enregistre ses tentatives dans `learnSessions` avec le domaine `opening-drill` (format d'`itemId` documenté dans `db.ts`) ; `pickNextDomain` les ignore.
« Mon répertoire » (`/repertoire`, `src/pages/MyRepertoire.tsx`, calcul pur dans `src/lib/myRepertoire.ts`, testé sous Node par `test_repertoire.py`) lit les parties chess.com du pseudo des réglages : lignes `reviews` d'Insights (`validRow`) et, sur demande, `fetchRecentGames(user, 3, 200)`, gardées en mémoire de module pour la session (les parties chargées ne sont pas persistées).
La théorie y est un ensemble de positions d'`openings.json` (placement, trait, roques) : une transposition reste théorique, contrairement à l'arbre préfixe de l'entraîneur et à la classe `book` de `review.ts`.
Une sortie est une position théorique (camp + position) où le joueur a joué hors théorie ; son coût est la chute de win% du coup de sortie dans les bilans cohérents (coûteuse à partir de 7, seuil de l'imprécision).
Chaque sortie se travaille dans `OpeningDrill` en mode `next` sur une famille synthétique (construction documentée dans `drillLines`, `src/lib/myRepertoire.ts`) ; les tentatives s'écrivent avec `recordDrill`, domaine `opening-drill`, format d'itemId dans `db.ts`, sans Elo ; `modeStats` ne rattache une position `next` qu'à une famille dans laquelle elle est déjà entrée, et la révision espacée ne reprend pas ces positions (seulement `full:`).
La révision espacée (`/revision`, `src/lib/revision.ts`) n'a pas de table : l'échéance de chaque item raté (puzzle, faute, variante `full`, attaque manquée, défense ratée) se calcule depuis son historique daté (`puzzleAttempts`, `learnSessions`, `mistakes`), agrégé par jour civil local, avec une échelle de Leitner `[1, 3, 7, 21]` jours ; un item en retard de plus de 30 jours sort de la file.
Un résultat de révision s'écrit là où l'écran d'origine écrit (`scoreItem('mistakes')` + `mistakes.update`, `recordDrill`, ou le domaine `revision` pour les puzzles), jamais dans un Elo.
Les attaques manquées et défenses ratées utilisent les diagnostics de `kingAttack.ts` et leurs domaines `missed-attack` et `missed-defense`, avec une échéance indépendante par domaine et faute.
L’échec initial est la date de la faute ; seules les tentatives dont `itemId` et `fen` correspondent à la faute courante alimentent ensuite ce calendrier.
La séance réutilise `MistakeExercise` (meilleur coup, mat ou alternative suffisamment bonne), puis `recordMissedAttack` ou `recordMissedDefense`, sans modifier la faute ni son calendrier classique.
Une faute supprimée ou modifiée pendant une séance ne peut pas recevoir de nouveau résultat spécialisé.
Le compteur de l'accueil ne charge jamais `puzzles.json` ; seule la séance le fait.
L'accueil (`src/pages/Home.tsx`, lot 4 du plan UX) décide sa carte principale avec `src/lib/homePlan.ts`, pur et testé sous Node par `test_accueil.py` : séance du jour en cours (`readStoredSeance`), sinon partie de Jouer en cours (`readStoredGame` de `lib/playSession.ts`, partagé avec `Play.tsx`), sinon séance du jour, sinon, faite aujourd'hui, séance rapide d'Apprendre (`state: { quick: true }`).
Aucun second ordonnanceur : les révisions dues déjà comptées par la séance sont celles non jugées de la séance en cours, ou celles qu'en reprendrait une nouvelle (`buildReviewSession` sur `revisionBlockSize` de `seance.ts`) ; la ligne « À réviser aujourd'hui » affiche le total dû (`data-review-count`) et nomme cette part (`data-review-in-seance`).
`data-review-ready` attend la file et la série de jours (`unavailable` si le compteur ne charge pas) ; `data-testid=home` marque l'accueil pour les suites.
La séance du jour (`/seance`, `src/pages/Seance.tsx`) enchaîne 10 à 15 minutes de blocs courts : révision due, puzzles classés, variante ratée, attaque ou finale.
Son planificateur est pur (`src/lib/seance.ts`, banc Node de `test_seance.py`) : poids des faiblesses par domaine (70 % Insights si un rapport en cache de moins de 30 jours couvre au moins 5 parties, 30 % résultats des 14 derniers jours lissés, ou ces résultats seuls), budget par minutes estimées de `BLOCK_META`.
`src/lib/seanceRun.ts` charge les données et matérialise le plan en étapes sérialisables ; chaque étape joue le lecteur de son écran d'origine (`PuzzlePlayer`, `MistakeExercise`, `OpeningDrill`, `PositionGame` avec `attackGameProps`/`endgameGameProps`) et écrit via ses fonctions (`recordReview`, `recordRatedPuzzle`, `recordDrill`, `recordAttempt`, `recordEndgamePlay`).
Un nouveau type de bloc s'ajoute par `BLOCK_META`, `planSeance`, `MATERIALIZE` (seanceRun.ts) et `RENDER` (Seance.tsx), tous typés `Record<BlockKind, ...>`.
Une séance menée au bilan écrit une ligne `learnSessions` du domaine `seance` (série de jours civils consécutifs, sans Elo) ; `pickNextDomain` l'ignore.

### Hub Apprendre

`/apprendre` (`pages/Learn.tsx`) est un hub guidé : carte Mon parcours, puis Toutes les leçons (`/apprendre/lecons`, `pages/Lessons.tsx`), S'entraîner à la carte (`/apprendre/entrainement`) et Réviser mes parties (`/apprendre/mes-parties`, `pages/ReviewMyGames.tsx`), et la Séance rapide (séance automatique) en secondaire.
Les sous-pages sont des routes, pas des dépliages : retour arrière, lien direct et rechargement marchent ; les groupes vivent sous `/apprendre/entrainement/<groupe>` (`pages/Training.tsx`), jamais directement sous `/apprendre` où `finales`, `defense` et `structures` sont des cours.
Les cinq groupes (Tactique et calcul, Attaque et défense, Finales, Ouvertures, Stratégie), leurs activités, leurs cours « Pour comprendre » et leur seule information de progression sont décrits une fois dans `TRAINING_GROUPS` de `lib/navigation.ts`, avec les retours (`groupBack`, `LESSONS_BACK`, `REVIEW_BACK`).
Mes structures reste sous Stratégie et Mon répertoire sous Ouvertures ; un nouvel entraîneur s'ajoute à un groupe et au tableau du budget de `test_apprendre.py`.
Une séance de domaine s'ouvre toujours sur `/apprendre` : le groupe (ou Réviser mes parties pour Mes erreurs) y navigue en `replace` avec `state: { domain, returnTo, returnLabel }`, un écran de préparation remplace le hub, ✕ et la fin de séance rendent la main au groupe, et « Encore une séance » rejoue le même domaine.
Une séance impossible à construire revient à la page d'origine avec `state.sessionFailed` (`useSessionFailed`).
Chaque page d'activité a un retour vers son groupe propriétaire, même ouverte directement ; un cours ouvert depuis un groupe (`state.from`, slug du groupe, suivi par ses leçons) y revient, sinon vers Toutes les leçons ; Mats éclair ouvert depuis Tactique et calcul (`from: 'tactique'`) y revient.

### Parcours d'apprentissage

`#/apprendre/parcours` (`pages/LearningPath.tsx`) : carte verticale des étapes en quatre niveaux, entrée en tête d'Apprendre et tuile de progression sur l'Accueil.
Une étape réunit une leçon d'un cours (`lesson: '<slug>:<id>'`, ouverte avec `?parcours=<étape>` pour que ✕ et le bilan y ramènent), ou un cours détaillé de `courses.json` (`read`), puis un exercice : série de puzzles par thème, série de variantes complètes de l'entraîneur d'ouvertures (`OpeningDrill`, qui écrit aussi `opening-drill`), ou finale contre Stockfish jouée par la séance d'Apprendre (`state: { endgame, returnTo, returnLabel, pathStep }`).
La logique de validation est définie par `computePath` dans `src/lib/learningPath.ts`, sur les faits lus par `src/lib/learningPathStore.ts` ; les cours détaillés `read`, affichés dans l'étape, n'ont pas de ligne de complétion `course`.
Une étape est jouable si la précédente est validée ou acquise ; le test de placement (`#/apprendre/parcours/placement`, 3 puzzles par niveau, 2 pour le valider, arrêt au premier niveau manqué) rend acquis les niveaux réussis, le meilleur test comptant.
Domaine `learnSessions` `path` (sans Elo) : une ligne par série notée jouée jusqu'au bout (`score`, `success` au seuil), par finale réussie depuis l'étape, ou par test de placement (`itemId: 'placement'`, `score` = niveaux acquis).
La série en cours survit au rechargement et à l'aller-retour vers l'analyseur dans `path-session-v1` ; un `pathStep` porté par la séance de finale d'Apprendre valide l'étape à toute réussite, même après Réessayer.
Les finales de `#/finales/:id` (`endgame-play`) ne valident pas d'étape ; les puzzles ratés du parcours n'entrent pas dans la révision espacée, les variantes ratées si, comme dans l'entraîneur.

### Alerte « Qu'est-ce qu'il menace ? » (`src/lib/threat.ts`)

Dans Jouer (bot et entraîneur), après chaque coup du bot, `findThreat` cherche la menace par coup nul sur le moteur pleine force du coach (`coachEngineRef`, créé aussi en mode bot) : P (joueur au trait), N (P avec le trait rendu au bot), P_prev (avant son coup, cherchée seulement si la menace n'est pas liée au coup sur l'échiquier).
Menace = au moins 2 points de matériel gagnés sur la ligne de N (reprise légale après la prise finale déduite par SEE), ou un mat en 1 ou 2 rejoué sur l'échiquier, créée par le coup (pièce qui vient de jouer, découverte, sinon 200 cp d'éval de plus qu'en P_prev) ; pas de question si P annonce un mat (pour l'un ou l'autre) ; vetos sans moteur : échec, reprise sans perte (SEE), partie finie.
`judgeThreat` est pur ; `e2e/test_menace.py` le rejuge avec un oracle python-chess sur les scores du harnais Node `e2e/threat_cases.mjs` (vrai WASM via `scripts/bots-node.mjs`, entrée `e2e/threat_entry.ts`).
Réglage hors persist Zustand : `localStorage['chess-local-threat-check']` (`{bot, coach}`, défaut `{bot: false, coach: true}`), dans `APP_LOCAL_KEYS` ; les contextes E2E le pré-remplissent à `{bot: false, coach: false}` (`threat_prefs=None` garde le défaut de l'app).
Indisponible en bullet ; en mode bot, la pendule du joueur attend l'analyse et la réponse et la partie n'est pas classée ; en mode entraîneur, seule une menace révélée déclasse la partie.
`Board.onSquareTap` (échiquier non jouable, prémouvement coupé) reçoit les touchers pendant la question ; `threatPly` de l'instantané de partie évite de reposer une question répondue.
Poser une question ramène au direct si le joueur consultait l’historique pendant l’analyse ; l’échiquier entraîneur réserve la hauteur des commandes pour garder ses quatre coins accessibles sur petit écran.
Chaque réponse écrit une ligne `learnSessions` domaine `threat-check` (hors Elo, ignorée par `pickNextDomain` et la révision), résumée dans Statistiques (`/stats`, onglet Plus) ; la page Réglages porte aussi ses deux interrupteurs (bot et entraîneur).

### Persistance

Base Dexie `chess-local` (`src/lib/db.ts`), actuellement en `version(3)` (table `reviews` : cache des bilans d'Insights).
Ajouter une table ou un index = nouveau bloc `db.version(n)` qui redéclare tous les stores, plus l'ajout dans `TABLES` de `backup.ts`.
La table `ratings` est unique et indexée par clé texte : cadences (`bullet`, `blitz`, `rapid`, `unlimited`), `puzzle`, et domaines d'Apprendre (`learn-endgame`, `learn-tactic`, ...).
Tous les Elo passent par `applyRating`/`eloUpdate`.
Les réglages sont dans Zustand persist (`localStorage['chess-local-settings']`).
La migration persist des réglages (version 2) est partagée avec l’import des sauvegardes : une version 0 ou absente avec `celtique` (ancien défaut implicite) donne `wikimedia`, et sans `pieceSet` donne le défaut `atelier`, comme une montée de version locale.
Un jeu enregistré n'est jamais remplacé par `atelier` : seuls les stockages sans `pieceSet` (nouvel utilisateur compris) le reçoivent.
Un choix `celtique` enregistré en version 1 est conservé ; cette version persist est indépendante de la version du schéma de sauvegarde.
L’import valide ensuite les types (dont `premoves`, booléen sinon défaut) et les valeurs contre les listes réelles de l’application.
Les réglages s'affichent dans la page Réglages (`/reglages`, `src/pages/Settings.tsx`), qui écrit aussi `chess-local-threat-check` comme l'écran de Jouer ; sauvegarde, restauration et réinitialisation vivent dans Mes données (`/donnees`, `src/pages/MyData.tsx`), au-dessus de `backup.ts`.
Ces deux pages ne sont que de la présentation : clés et formats persistés sont ceux de l'ancienne page Stats, vérifiés par `part_pages` de `test_backup.py`.
Les séances en cours d'Apprendre, de révision, du parcours d'apprentissage et de la séance du jour vivent dans `sessionStorage` (`learn-session-v1`, `revision-session-v1`, `path-session-v1`, `seance-session-v1`), comme l'exercice laissé pour l'analyseur (`exercise-return-v1`) : `importBackup` et `resetApp` effacent ces cinq clés, et seulement elles.
`resetApp` efface aussi les clés locales de Jouer, Puzzles et Mats éclair, exportées par leurs modules de logique.
`main.tsx` demande `navigator.storage.persist()` ; iOS peut purger IndexedDB, et le périmètre des sauvegardes de `backup.ts` est décrit dans [README.md, section Features](README.md#features).

### Chemins et PWA

`base: './'` + `HashRouter` : l'app doit tourner aussi bien à la racine que sous `/chess-local/`.
Tout asset de `public/` se charge via `import.meta.env.BASE_URL` (worker moteur, sons, pièces, `puzzles.json`) ; un chemin absolu `/...` casse la prod.
Le service worker précache tout (WASM 7 Mo, puzzles 16 Mo) avec un plafond de 25 Mo par fichier dans `vite.config.ts`.
Un nouvel asset lourd ou une nouvelle extension doit être couvert par `globPatterns`.
Les pages sont découpées par route : `App.tsx` les charge par `lazyPage` (`src/lib/lazyPage.ts`), sous un `Suspense` placé dans la frontière d'erreur ; seul l'accueil est dans le bundle initial.
Une nouvelle page passe par `lazyPage`, et tout autre import dynamique d'une chunk précachée par `loadChunk` ; les deux protègent contre une chunk périmée après un déploiement.
Seul l'import du pilote haptique natif (`lib/native.ts`, hors précache) reste un `import()` nu.
Dès qu'un nouveau service worker a pris la main (`controllerchange` avec un contrôleur précédent), la prochaine chunk à charger recharge l'app au lieu d'importer, l'URL et le state de navigation étant conservés ; un import qui échoue quand même recharge une seule fois (garde `sessionStorage['chess-local-chunk-reload']`), puis remonte à la frontière d'erreur.
Conséquence assumée : après une mise à jour en arrière-plan, la première page pas encore ouverte dans la session recharge l'app ; tout ce qui doit y survivre est déjà persisté (partie en cours, séances, puzzle en cours).
Une page qui en ouvre une autre avec une horloge Playwright figée doit avancer cette horloge : React dévoile le contenu suspendu sur une minuterie (voir `test_premove.py`).
Les cours écrits passent par `lazyCourse` (`pages/CoursePages.tsx`) : la page `LessonCourse` et le JSON de chaque cours arrivent avec sa route, chaque cours dans sa chunk.
L'accueil ne doit importer statiquement aucun module lourd : le compteur de révision (`revision.ts`, qui tire `openings.json`) et la progression du parcours (`learningPathStore.ts`) sont deux imports dynamiques indépendants, après le premier affichage (`data-path-ready` marque la progression connue) ; `learningPath.ts` ne tire aucun cours, les leçons des étapes se résolvent dans `lib/pathLessons.ts`, et la carte de séance lit `lib/seanceSession.ts`, sans les banques de `seanceRun.ts`, comme la reprise de partie lit `lib/playSession.ts` sans chess.js ni la liste des bots (le nom du bot est dans l'instantané).
Les chunks de la couche native (`assets/native-*`) restent hors précache ; le contrôle de précache de `test_perf.py` les exclut explicitement.
`__BUILD__` (horodatage de build) s'affiche en bas de `/import` pour vérifier qu'un iPhone a bien la dernière version.

### App iOS (Capacitor)

`ios/` et `capacitor.config.ts` empaquettent le même build web dans une `WKWebView` ; étude, intensités haptiques et marche à suivre dans `docs/ios-app.md`.
`src/lib/native.ts` détecte le runtime natif (`window.Capacitor.isNativePlatform`, posé par la native-bridge) et expose `haptic(kind)`, no-op synchrone sur le web.
Le plugin n'est chargé que par `import('./nativeHaptics')` en natif ; ne jamais importer `@capacitor/*` statiquement : son repli web appellerait `navigator.vibrate` et la PWA changerait.
`vite.config.ts` préfixe les chunks de `@capacitor/*` et du pilote par `assets/native-`, puis les exclut du précache.
`Board` émet un retour pour un geste de l'utilisateur sur cet échiquier (saisie, pose acceptée, prise, refus, prémouvement en file puis exécuté) et, plus léger via `playComputerMove`, pour un coup du camp opposé à `movableColor` ; jamais pour une navigation ou un saut de position.
La migration PWA vers app passe par la sauvegarde de `backup.ts` (origines différentes) : carte de l'accueil en natif tant que la clé `chess-local-native-migration` est absente, posée par « Non merci » ou une restauration réussie, effacée par la réinitialisation.
En natif, l'export sans feuille de partage annonce un échec au lieu d'un faux téléchargement.
Règle de version : l'app ne se met pas à jour seule, et `inspectBackup` refuse une sauvegarde plus récente que son schéma ; ne pas déployer un nouveau `db.version(n)` sur le web avant un build de l'app qui le porte.
`e2e/test_ios_app.py` simule la native-bridge par `CAPACITOR_IOS` de `helpers.py` (`haptic_log` lit les appels) et vérifie aussi que la PWA ne charge ni ne précache le chunk natif.

### Pièces et sons

Les jeux de pièces sont des SVG documentés dans `public/pieces/<jeu>/` (liste dans `src/lib/pieces.ts`, réglage `pieceSet`), rendus en `<img>` par `Board` via l'option `pieces` de react-chessboard ; `classique` = pièces intégrées à la lib.
Les jeux qui dessinent jusqu'au bord de la case portent une échelle (`scale` de `PIECE_SETS`), appliquée par `PieceIcon` au seul dessin sur l'échiquier, avant le recentrage de `pieceCenters.json` : les coins des coordonnées restent libres pour tous les jeux (suite `coordinates`), et le conteneur `.board-piece`, donc le glissé, garde la taille de la case.
Les sons (`public/sounds/`, `scripts/make-sounds.sh` pour les notifications Kenney CC0 et `scripts/extract-video-sounds.py` pour les impacts de la vidéo autorisée par Max) passent tous par `src/lib/sounds.ts`, qui lit lui-même `playSounds` et `soundVolume` : pas de test du réglage aux appels.
`Board` porte le ressenti tactile partagé : clone à 1,7, dessin décalé de 0,85 case au-dessus du contact, disque de visée et retour animé des refus.
Le décalage vit sur `.board-piece` via `--piece-lift`, car déplacer le rectangle du clone serait compensé par le recentrage de dnd-kit.
La cible vient des callbacks de collision de react-chessboard, jamais de la position du dessin décalé.
La souris conserve son échelle 1,2 et son cadre de destination ; les animations respectent `prefers-reduced-motion`.
`e2e/test_feeling.py` vérifie la géométrie pendant le geste CDP et l'audio horodaté à la pose ; les mesures sonores et limites sont dans `docs/f14-feeling.md`.
Les conditions du son automatique de coup (`lastMove`, `silent` et anti-empilement partagé) sont documentées auprès de l'effet dans `src/components/Board.tsx`.
Une page qui joue ses sons de coup elle-même (Jouer, finales jouées) ou affiche un saut de position (réessai de l'analyse) lui passe `silent`, comme les diagrammes ; la position qui suit un `silent` reste muette.
Tout coup de l'ordinateur (bot, Stockfish, réponse précalculée, amorce) passe par `playComputerMove` de `sounds.ts` : son adverse et, dans l'app native, impact léger (moyen pour une prise, un échec ou une promotion), indépendant du réglage des sons.
Les pages qui jouent leurs sons (Jouer, PositionGame, finales au chrono, Mats éclair) l'appellent pour le coup adverse ; `Board` l'appelle quand le coup qu'il sonne n'est pas du camp `movableColor`.
Sans `movableColor` (navigation de l'analyse, lecture d'une ligne), le son reste seul ; un saut de position, un `silent` ou une reprise de partie ne donnent ni son ni haptique.
La suite `coup_ordinateur` le vérifie pour chaque famille d'écran (son relu par python-chess, journal haptique de `CAPACITOR_IOS`).
Aucun asset de chess.com, et toute ressource ajoutée doit avoir sa licence ou autorisation documentée dans le `LICENSES.md` de son dossier : le dépôt est public.

### Prémouvements

`Board.allowPremove` est un opt-in explicite, avec `movableColor` obligatoire ; le propriétaire le coupe en revue d'historique, en fin de partie ou pendant une action bloquante.
`interactive` conserve son rôle de permission de jouer immédiatement ; le Board peut préparer un coup adverse quand `allowPremove` est actif même si `interactive` est faux.
Play (bot et entraîneur), PositionGame (attaque, défense, conversion, finales, analyse/jouer), EngineContinuation en mode jouer, ChronoRun et les Finales au chrono l'activent ; puzzles, plans et exercices à solution unique restent exclus.
La file locale contient un seul coup non persisté, même sur ordinateur : deux cases rouges, pièce au départ, aucun son à la saisie, annulation par toucher sur une case ou Échap, remplacement par un nouveau glissé.
`lib/premove.ts` valide uniquement la géométrie : échec, occupation et obstacles sont ignorés à la saisie, car le coup adverse peut libérer une case ou offrir une prise ; les droits de roque et le sens des pions restent requis.
Après exactement un coup adverse, chess.js revalide entièrement le coup, promotion en dame, puis le Board consomme la file avant d'appeler `onMove(from, to, promotion, true)` une seule fois.
Un coup illégal est oublié sans bruit ; retour arrière, changement de position, désactivation du réglage ou changement de camp vident aussi la file.
Le quatrième argument distingue un prémouvement pour les propriétaires de pendule : Play, ChronoRun et les Finales au chrono débitent 100 ms avant le coup, sans débit sur une annulation ; si le temps est insuffisant, le drapeau tombe sans jouer.
Ce coût reprend la [règle officielle vérifiée le 15 octobre 2026](https://support.chess.com/en/articles/8562432-what-are-pre-moves-and-how-do-they-work), avec une fin au drapeau simplifiée, sans affichage intermédiaire bloqué à 0,1 s.
Les modes illimités n'ont aucun débit ; le temps réel de traitement reste soumis à la pendule existante.
Les sons existants restent propriétaires de l'exécution ; le son automatique du Board exempte le prémouvement de l'anti-empilement de 60 ms pour ne pas le perdre juste après la réponse moteur.
`settings.premoves` vaut true par défaut, le merge Zustand conserve les anciens stockages sans clé et le nettoyage des sauvegardes récupère automatiquement ce défaut.
`e2e/test_premove.py` contrôle les gestes iPhone, la file, le son, les refus, la promotion, la pendule, les réglages et l'exclusion des puzzles ; `PREMOVE_CASE` permet de cibler un scénario pour les preuves par mutation.
La vidéo de référence et les extractions intermédiaires restent exclusivement dans un dossier temporaire hors dépôt.
Les MP3 finaux et les SVG Atelier redessinés sont autorisés par Max (17 octobre 2026), provenance dans les LICENSES.md.
`PieceIcon` centre les silhouettes via les marges mesurées par `scripts/center-pieces.py`, communes au plateau et aux aperçus.
`Play` remet `<main>` en haut par un seul effet, à chaque passage réglages ↔ partie et à chaque nouvelle partie, pour ne pas hériter du défilement de la configuration sur petit écran (`piece_viewport`).
`e2e/test_piece_centers.py` contrôle les pixels peints à ±2 % de case ; ne pas compter deux fois le transform CSS lors de la rasterisation des SVG intégrés.
Les coordonnées de l'échiquier ont une taille de 19 % de la case (9 à 15 px, via `--board-square` posé par `Board`) et collent à leur coin.
`e2e/test_coordinates.py` mesure l'encre de chaque glyphe contre l'encre des pièces, dans les deux orientations et aux trois formats : aucun recouvrement pour les sept jeux, sous les douze pièces possibles.

### Données

`public/puzzles.json` : 120 000 puzzles lichess au format compact `[id, fen, moves, rating, themes]`, hors bundle, chargés une fois par `loadPuzzles()`.
`src/data/*.json` est bundlé : `openings.json` (généré), `endgameClock.json` (généré, Finales au chrono), `endgames.json`, `strategy.json`, `courses.json` (contenu d'Apprendre, écrit à la main, en français), `endgameCourse.json` (cours de finales, `#/apprendre/finales`), `attackCourse.json` (cours « Démolir le roque », `#/apprendre/roque`), `basicsCourse.json` (cours « Les bases », `#/apprendre/bases`), `defenseCourse.json` (cours « Tenir sous l'attaque », `#/apprendre/defense`), `learningPath.json` (parcours d'apprentissage), `structuresCourse.json` (cours « Structures de pions », `#/apprendre/structures`, un chapitre par id de structure), `defenses.json` (généré, banque de l’entraîneur de défense, `#/defense`), `attacks.json` (généré, banque de l'entraîneur d'attaque, `#/attaque`), `conversions.json` (généré, banque de « Convertir l'avantage », `#/convertir`), `visualisation.json` (généré, banque de « Calcul et visualisation », chargée par `import()`).
Une leçon terminée est une ligne `learnSessions` `{ domain: 'course', itemId: '<slug>:<id>' }` (`finales:`, `roque:`, `bases:`, `structures:`, `defense:`) : les ids de leçons sont figés (`FROZEN_IDS` du contrôle).
`learningPath.json` (parcours d'apprentissage, `#/apprendre/parcours`) décrit quatre niveaux d'étapes ; ses ids d'étapes et de niveaux sont figés (`FROZEN_STEPS`, `FROZEN_LEVELS` de `check-learning-path.mjs`).
Les noms d'ouvertures sont en anglais dans les données et traduits à l'affichage par `openingNames.ts`.

### UI

Mobile d'abord : la cible principale est la PWA iPhone en mode standalone (nav basse, `pt-safe`/`pb-safe`, hauteurs en `dvh`), avec une nav latérale à partir de `md`.
Les E2E tournent sur le device `iPhone 14 Pro` et en 1440x900.
Couleurs via les tokens Tailwind `@theme` de `src/index.css` : `surface`, `surface-2`, `surface-3`, `accent`.
Le token `accent-light` sert au texte vert sur fond teinté d'accent (`bg-accent/15` ou `/20`), où l'accent pur reste sous le contraste AA.
Le lot 1 du [plan UX](docs/ux-refonte.md) ajoute `on-accent` (texte sombre sur un fond `accent` opaque, contraste 6,43:1) et `muted` (descriptions lisibles sur les surfaces).
Ne pas remettre `text-white` sur un `bg-accent` opaque ; les variantes translucides conservent leur couleur métier.
`Cta` conserve les variantes primaire/secondaire, avec cible minimale 44 px, type bouton par défaut et focus clavier visible.
`PageHeader` porte titre 24 px, description et retour de 44 px : la page lui passe son callback pour conserver destination, state et replace/push.
`ActivityCard` fournit une racine lien ou bouton, un titre de 16 px et une description de 14 px, sans interaction imbriquée ni troncature.
`ProgressBar` reçoit les valeurs métier réelles et un nom accessible ; ne pas afficher une progression de zéro pendant une lecture inconnue.
`EmptyState` distingue absence de données et chargement, avec une explication et un lien d’action.
Ces composants sont appliqués aux tuiles Accueil/Apprendre, aux sommaires communs de cours, à la progression du parcours et aux états vides Archive/attaques/défenses personnelles.
La suite `ux_foundation` vérifie contraste rendu, focus, dimensions, titres longs, retours, états vides et chargement aux trois formats ; ses captures restent dans `e2e/shots/ux-lot1/`.
Le lot 2 livre la navigation à cinq onglets (`NAV` de `src/App.tsx`) : Accueil, Jouer, Puzzles, Apprendre et Plus ; la réorganisation d’Apprendre reste différée au lot 5.
Le `match` de chaque onglet suit le « Placement cible de chaque route » du plan : `/mats` allume Puzzles, `/moment-critique` Apprendre, et `/analyse` (sous-chemins compris), `/archive`, `/import`, `/stats`, `/insights`, `/reglages` et `/donnees` allument Plus ; un seul `aria-current` dans la nav, toujours sur un onglet.
Les routes restent identiques et les anciens liens fonctionnent ; les onglets restent en `replace`, les liens du hub `/plus` (`src/pages/More.tsx`) sont des descentes en push.
Les destinations de Plus vivent dans `PLUS_GROUPS` de `src/lib/navigation.ts`, partagé par le hub et la nav latérale.
Le lot 3 donne leurs pages à Réglages (`/reglages`) et Mes données (`/donnees`), avec un retour « Plus » dans `PageHeader` ; Stats renvoie en `replace` les anciens `state.section` (`reglages`, `donnees`) et `state.backup` vers ces pages, et la carte de migration native ouvre directement `/donnees`.
La nav latérale déplie la sous-liste de Plus dès que l’onglet Plus est allumé (dérivée de la route, sans état), en `replace` et sans `aria-current` : sélection visuelle par `data-selected`.
Les pictogrammes de nav et du hub sont des SVG inline dessinés pour l’app (`src/components/NavIcon.tsx`) : grille 24, trait 1,75, `currentColor`, `aria-hidden`, aplat à 22 % des formes `data-fill` quand l’onglet est actif (`.nav-icon-active` de `src/index.css`) ; la nav basse garde 48 px de haut, libellés en 12 px.
Les tests visent les onglets par `nav a[data-nav-tab]` et les cartes du hub par `main a[data-plus='<icône>']` ; la suite `shell` vérifie onglets, familles de routes, hub, sous-liste et pictogrammes aux trois formats.
Le lot 6 fait de l'onglet Puzzles trois racines sœurs : `/puzzles` reste le puzzle classé (aucun geste de plus), `/rush` et `/mats` ; `PuzzleModes` (`src/components/PuzzleModes.tsx`, liste `PUZZLE_MODES` de `navigation.ts`) les relie en tête de chacune, en `replace` comme les onglets.
C'est un `div role="navigation"` et non un `<nav>` : `nav a[aria-current]` reste réservé aux onglets ; les tests visent les modes par `main [data-puzzle-mode='<puzzles|rush|mats>']`.
Il est absent des écrans immersifs (run de Rush, série et fiche de Mats éclair, qui gardent leur croix ou leur flèche « Retour à Mats éclair ») ; le raccourci du groupe Tactique et calcul ouvre `/mats` avec `state.from: 'tactique'`, qui ajoute « Retour à Tactique et calcul » et suit les fiches.
Les lots 7 et 8 donnent aux exercices un habillage commun (`src/components/Exercise.tsx`, purement présentationnel) : `ExerciseScreen` (plein écran z-40, zones sûres, colonne `h-full`), `ExerciseHeader` (croix nommée, titre, « n/N » dans le `h1` et barre des exercices jugés seulement pour une série, `counterProps` pour les marqueurs, action à droite, `wideAction` pour une puce de niveau), `ExerciseStage` (bande `above` de 28 px facultative, échiquier, zone de décision, `below`) et `ExerciseFeedback`.
Ils habillent la séance d'Apprendre, la révision, la séance du jour, les séries du parcours, `OpeningDrill` (tous ses écrans), `PositionGame` (toutes ses pages) et les lignes des cours (`LessonCourse`, avec `fluid`).
L'échiquier est le plus grand carré qui laisse la zone de décision visible (`.exercise-stage`, conteneur de taille, `--exercise-zone` de hauteur fixe dans `src/index.css`, prop `zone` pour une zone plus haute) : avant le coup la zone porte la consigne et, pour une partie ou un drill, la rangée d'actions de jeu (`promptActions`) ; après le verdict, un ton, un titre, une explication, une note (classement, échéance) et les actions ; rien de ce qui change au verdict ne déplace l'échiquier.
`ExerciseVerdict.tone` a trois valeurs, toujours un symbole et un mot : `success` (« ✓ Réussi », vert), `review` (« ✗ À revoir », ambre, échec franc), `neutral` (« ◐ », bleu ciel : nulle, abandon, défense tenue au moins à moitié, variante non comptée) ; `label` remplace le mot par le titre de l'écran.
Par défaut une réussite ou une issue neutre met Suivant (`nextLabel`) en principal, un échec Réessayer s'il est fourni ; Analyser et « Pourquoi ? » restent secondaires ; `actions` remplace ce jeu (PositionGame : Rejouer, Autre finale, Annuler, Analyser, Plan, Conclure).
Desktop (`lg`) : la scène passe en deux colonnes, échiquier jusqu'à 720 px à gauche, zone de décision puis `below` dans un panneau de 22rem à droite, en-tête au-dessus des deux ; les cours suivent la même disposition.
L'explication est calculée par l'exercice au verdict, sans dévoiler la solution d'un échec, et persistée avec la séance (`reason` de `learn-session-v1` et `revision-session-v1`) pour revenir identique de l'analyse ; la séance du jour la recalcule sans le détail du coup au retour.
`MistakeExercise` accepte `bare` (seul l'échiquier ; consigne `MistakeConsigne`, vérification `onChecking` et « Pourquoi ? » via `refutedUci` de `lib/refutation.ts` passent au propriétaire).
La suite `exercice` vérifie, aux trois formats, l'échiquier immobile au pixel (jeu, réponse de Stockfish, vérification, verdict, réessai, Rejouer, rechargement, retour d'analyse), la zone visible sous la zone sûre ou à droite sur desktop, les tons et libellés, les cibles, « Pourquoi ? », l'absence d'écriture au réessai, la reprise d'une partie, Quitter, `recordReplaced` et une ligne de cours.
Texte secondaire en `text-neutral-400` au plus sombre : `text-neutral-500` ne reste que sur les chevrons décoratifs `aria-hidden`.
Cibles tactiles de 44 px au moins (`min-h-11`, `h-11 w-11`) ; les sous-pages d'Apprendre (hubs, cours, entraîneurs, Calcul et visualisation, Mon répertoire, Mes structures, listes personnelles et moments critiques) et la séance du jour ont leur retour dans `PageHeader`.
`.safe-top-band` (`App.tsx`, z-45) masque sous l'heure et la Dynamic Island ce qui défile dans `<main>` et dans les calques z-40 ; les voiles de modale sont en z-50 pour l'assombrir, et un calque z-50 ne fait pas défiler son contenu sous sa marge haute.
Un changement d'état qui remplace l'écran sans changer de route (réglages et partie de Jouer) remet `<main>` en haut ; aucun `scrollIntoView` dans un scroller imbriqué, il ferait aussi défiler `<main>`.
La suite `ui_audit` (`e2e/test_ui_audit.py`) parcourt chaque route et ses états principaux en PWA standalone (safe areas émulées), en 393x660 et en 1440x900, capture dans `e2e/shots/ui_audit/` et échoue sur un débordement horizontal, un texte coupé, une cible tactile sous 44 px, un contraste sous WCAG AA, une faute de typographie française ou une commande sous l'encoche ; ses exceptions sont nommées dans `ALLOW`, `UI_AUDIT_MUTATION` prouve que chaque check peut échouer.
`.boardbox` fixe la taille de la plupart des échiquiers ; les cours utilisent leur propre conteneur.
`main.tsx` annule le `touchstart` natif dans les 25 px des bords du viewport sur les cases `[data-board] [data-square]`, pour empêcher les gestes précédent/suivant de WebKit depuis tout échiquier sans couper les événements de react-chessboard.
`Board` porte toujours `data-board`, indépendamment de sa propriété `interactive` et des classes de mise en page : la protection couvre aussi la réflexion du moteur et les diagrammes.
La prévention reste ciblée : l'annulation globale casse les boutons et le défilement vertical près du bord ; les diagrammes de cours restent défilables depuis leur centre et l'historique n'est pas modifié.
La suite `edge_navigation` vérifie en contexte mobile standalone les contacts CDP annulés aux deux bords (dont 20 px du bord réel du viewport) et les coups par glissé sur Analyse, les exercices de `LessonCourse`, Jouer et les puzzles.
Elle vérifie aussi les coups par glissé central non annulé, le clic-clic, les boutons, le défilement du contenu et le défilement vertical depuis le centre d’un diagramme de cours.
Les contacts au bord sont aussi annulés sur les diagrammes et pendant la réflexion du moteur, quand l’échiquier est momentanément non jouable.
