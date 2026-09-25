# Plan phase 2 - correctifs issus de la campagne QA du 2026-09-18

## Bilan phase 1
154 constats sur 6 zones : 5 critiques, 40 majeurs, 87 mineurs, 22 cosmétiques.
Rapports détaillés (repro, cause `fichier:ligne`, correctif proposé) : `findings-{play,puzzles,learn,touch,global,analysis}.md` dans ce dossier.
Scripts de repro et captures : sous-dossiers `play/ puzzles/ learn/ touch/ global/ analysis/`.

Contre-vérifiés par le coordinateur (code ou rejeu) : TOUCH-1, LEARN-1, LEARN-2 (théorie), LEARN-5a, LEARN-7, GLOB-1, ANA-1, ANA-11.
Tranché : le plantage de `e2e/test_all_buttons.py` ligne 255 est un artefact de la panne du serveur dev, pas un bug de l'Import.

## Règles du workflow (rappel)
- Un worktree par lot, base `origin/main`, créé via `herdr worktree create`.
- Codex (panneau herdr) challenge le spec, Claude code, codex pilote le gate no-mistakes.
- Gate lancé avec `--skip=pr,ci` (le daemon ouvrirait la PR sous le mauvais compte gh), puis PR créée par Claude avec le token `maxencebrochard`.
- Pas de `--yes` : Claude juge chaque gate, consigne chaque décision.
- `public/engine/*` est intouchable (vendorisé).
- Hooks pre-commit par worktree : écrire les DEUX rapports (outil Write) AVANT, puis `git commit` seul.
- Test de régression E2E écrit en premier (échoue sur la base, passe après).
- Par lot, UN seul subagent relecteur à contexte frais lit les nouveaux tests ET le diff : les deux rapports de hook sortent de sa relecture.
- Chaque worktree a besoin de `npm ci`.
- CONTINUITÉ DES DONNÉES (exigence de Max, 2026-09-18) : aucune mise à jour ne doit faire perdre ses données ni ses scores de puzzles, qui n'existent que sur son iPhone.
  Interdits dans tous les lots : supprimer un store Dexie ou changer une clé primaire, changer les clés de `ratings` ou le nom `chess-local-settings`, monter `version` du persist Zustand sans `migrate`, changer l'origine, le sous-chemin `/chess-local/` ou le `scope` du manifest.
  La suite de montée de version (lot L0b) doit passer dans chaque PR.

## Lots, par ordre de lancement

### Vague 0 - prérequis, SEUL et en premier
- **L0 infra-tests** : `npm run test:e2e` autonome (démarre son Vite sur un port libre, lance les suites, s'arrête), vrais codes de sortie (`sys.exit(1)` absent de `test_learn.py`), `pageerror` = échec, config `.no-mistakes.yaml` (commandes test et lint).
  Rapatrie aussi les acquis QA dans le repo, sinon ils meurent avec la session : `qa_helpers.py` -> `e2e/helpers.py` (les suites existantes migrent dessus), scripts de repro -> `e2e/qa/`, rapports -> `e2e/qa/findings/`. Les captures restent dehors.
  PAS de contrôle chess.js des données ici : il échouerait sur main aujourd'hui (LEARN-5a est un pat, LEARN-18 a du `Kd3`). Il part dans L4, où il sert de test de régression.
  Pourquoi seul : tous les autres lots en dépendent pour leur test de régression et pour que l'étape test du gate ait un sens.
  Inconnues à lever pendant L0 : schéma de `.no-mistakes.yaml` (chercher un exemple dans les autres repos, `no-mistakes ci-workflow --help`), et si le gate lit cette config depuis la branche testée ou depuis main.
  Plan B si codex pilote mal les gates AXI : Claude lance `axi run`, codex ne fait que challenger les specs.

- **L0b garde-données** (`e2e/test_upgrade.py`, fixtures) : juste après L0, avant tout lot qui touche aux données.
  Montée de version réelle : l'ANCIEN build tel qu'installé chez Max (`origin/gh-pages@388d3ed`, build `2026-07-20 15:15`, extrait par `git archive`) est servi sous `/chess-local/`, on y crée de vraies données par l'interface (puzzle résolu et raté, Rush, partie, réglage), puis le NOUVEAU build est servi sur la MÊME origine (même port, même sous-chemin) dans le même profil navigateur.
  Attendu : le service worker se met à jour, `__BUILD__` change, et toutes les tables (`ratings` dont `puzzle`, `puzzleAttempts`, `rushScores`, `games`, `mistakes`, `learnSessions`) plus les réglages sont identiques, et AFFICHÉS (Elo puzzles, records Rush, archive).
  Second volet : une sauvegarde exportée par l'ancien build se restaure entièrement dans le nouveau (seul filet en cas de vraie réinstallation iOS, qui efface le stockage).

### Vague 1 - critiques, fichiers disjoints, en parallèle (max 3)
- **L1a drag-scroll** (`src/index.css`, `src/components/Board.tsx:117-122`) : TOUCH-1, TOUCH-2, TOUCH-13 (= PLAY-8, PUZ-7, LEARN-25). Plainte numéro 1 de Max : 2 règles CSS + un correctif de style. Test de régression déjà prêt : `verify_touch1.py`. Petit, livré en premier, sans attendre le reste.
- **L1b board-robustesse** (`Board.tsx`, `CourseSheet.tsx`, `index.css`) : TOUCH-7, TOUCH-8, TOUCH-9, TOUCH-10, TOUCH-11, PLAY-14, PUZ-15, ANA-32, PLAY-25, PUZ-25/PLAY-20 (largeur de board multiple de 8 px), LEARN-27. Après L1a (mêmes fichiers).
- **L2 coquille-app** (`src/App.tsx`) : error boundary (filet pour ANA-1 et ANA-2), TOUCH-4 (scroll remis à zéro par route), TOUCH-6 (`NavLink replace`), GLOB-6 (sortie de `/rush` et `/import`), route inconnue, GLOB-9 (barre d'onglets).
- **L3 analyse-crashs** (`src/pages/Analysis.tsx`, `src/lib/review.ts`) : ANA-1, ANA-2, ANA-3, ANA-9, ANA-10, ANA-18, ANA-31, ANA-5.
- **L4 finales-justes** (`src/pages/Learn.tsx` partie finales, `src/data/endgames.json`, `src/data/courses.json`) : LEARN-1, LEARN-2, LEARN-5, LEARN-7, LEARN-11, LEARN-18, LEARN-28, plus le contrôle chess.js des données (pat ou mat involontaire, flèches sur case occupée, notation anglaise) comme test de régression.
  Attention : le correctif proposé pour le diagramme « enfilade » (LEARN-5b) est un brouillon, construire et vérifier la position soi-même.
- **L5 sauvegarde-sûre** (`src/lib/backup.ts`, `src/pages/Stats.tsx`) : GLOB-1, GLOB-2, GLOB-3. PRIORITÉ HAUTE : la sauvegarde est le seul filet de Max en cas de réinstallation iOS, et aujourd'hui « Restaurer » peut tout effacer sans confirmation.

### Vague 2 - majeurs
- **L6 partie-cycle-de-vie** (`src/pages/Play.tsx`) : PLAY-1, PLAY-9 (= ANA-35), PLAY-10, PLAY-4 (persistance de la partie, filet du swipe-back).
- **L7 partie-layout** (`Play.tsx`, `MoveList.tsx`) : PLAY-2 (= TOUCH-3), TOUCH-5, PLAY-3, PLAY-21, PLAY-18. Après L6 (même fichier).
- **L8 chronos** (`Clock.tsx`, `Play.tsx`) : PLAY-6, PLAY-7. Après L7. (PUZ-10 est dans L9 : `PuzzleRush.tsx` ne doit être touché que par un seul lot.)
- **L9 puzzles** (`PuzzlePlayer.tsx`, `Puzzles.tsx`, `PuzzleRush.tsx`) : PUZ-1, PUZ-2, PUZ-3, PUZ-5, PUZ-6, LEARN-6, PUZ-11, PUZ-12, PUZ-13, PUZ-14, PUZ-16, PUZ-17, PUZ-4/PUZ-18 (bandeau compact).
- **L10 séance-apprendre** (`Learn.tsx` hors finales, `repertoire.ts`, `learn.ts`) : LEARN-3, LEARN-4, LEARN-8, LEARN-9, LEARN-10, LEARN-13, LEARN-14, LEARN-15, LEARN-16, LEARN-17, LEARN-21, LEARN-22. Après L4 (même fichier).
- **L11 bilan-qualité** (`review.ts`, `coach.ts`, `Analysis.tsx`) : ANA-11, ANA-15, ANA-16, ANA-28, ANA-7, ANA-12, ANA-13, ANA-20, ANA-21, ANA-38. Après L3.
- **L12 archive-import** (`Archive.tsx`, `Import.tsx`) : ANA-6, ANA-8, ANA-22, ANA-23, ANA-24.

### Vague 3 - mineurs transverses
- **L13 textes-fr** : tirets cadratins dans l'UI et les données (LEARN-26, ANA-36), noms d'ouvertures (PLAY-23, PLAY-15, ANA-17), thèmes de puzzles (PUZ-21), figurines dans lignes moteur et explorer, séparateur décimal, accords.
- **L14 a11y-contrastes** : GLOB-13, PLAY-19, LEARN-24, ANA-33, ANA-34, zones tactiles sous 44 px.
- **L15 reste** : tout constat mineur ou cosmétique non rattaché ci-dessus, regroupé par page.

## Non retenus comme correctifs (à dire à Max)
- PUZ-19 (fuite d'environ 440 noeuds DOM par puzzle) : mesuré en dev seulement, détenteur inconnu. À remesurer sur un build de prod avant tout correctif.
- ANA-4 (variantes en analyse) et PLAY-13 (proposer nulle), PLAY-12 (pièces capturées), PUZ-22 (refonte Rush) : fonctionnalités nouvelles, pas des correctifs. Listées pour décision, non lancées d'office.
- Swipe-back iOS : parades livrées (L2, L6), efficacité à valider sur iPhone.
