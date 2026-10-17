# Q1 : fiabilité et durée des E2E

## Méthode

Ce bilan décrit la campagne Q1 avant le rebase intégrant `defense` et `moments` et avant l'attente du compteur ajoutée à `revision`.
Les effectifs, durées et listes de fichiers ci-dessous sont ceux de cette campagne, pas un inventaire du checkout actuel ni une validation des modifications ultérieures.

La référence est le lancement série du 16 octobre 2026, conservé dans `scratchpad/q1/baseline-serial.log` par le premier agent.
Il totalise 1 507 s, dont 1 498 s de suites, avec un échec intermittent sur la finale d’opposition.
Les 43 minutes initialement signalées correspondaient à une machine beaucoup plus chargée.
Les mesures de reprise sont exécutées sous le verrou commun à trois places, avec deux workers au maximum par lancement.
Les durées ne constituent pas un benchmark à charge constante : les autres worktrees partagent la machine.

## Contrats conservés

Aucune suite utilisateur n’est supprimée.
Les attentes remplacées attendent désormais le résultat observable, avec un délai borné et un échec explicite si le résultat manque.
Le joueur de référence des finales transmet l’historique complet à Stockfish pour éviter les répétitions qu’il ne pouvait pas voir avec la seule position courante.
Le coach mesure son temps CPU pour que le partage du processeur ne ressemble pas à un gel de calcul.
Le lancement parallèle conserve le code de sortie de chaque suite et arrête ses processus, même en cas de délai ou d’interruption.
Les sorties sont regroupées par suite et les durées réussies mémorisées localement pour lancer les suites longues en premier.

## Reproduction

Utiliser Node 22 et les dépendances de `e2e/requirements.txt`.
Chaque commande E2E de cette campagne est précédée du verrou `e2e-lock.sh` défini dans les consignes communes.
Les journaux de reprise sont dans `e2e/shots/q1-*.log`, non versionnés.

## Critères audio et limites

Le contrat audio et ses limites sont décrits dans [l'étude F14](f14-feeling.md) et vérifiés par `immediate_sound` dans `e2e/helpers.py`.

## Preuves par mutation

Les mutations ne touchent que le contexte navigateur, le serveur de test ou le scénario Node du coach.
Le code de l’application reste inchangé.

| Mutation | Régression injectée | Résultat obtenu | Durée totale |
| --- | --- | --- | --- |
| `sound-task` | Départ sonore reporté de 100 ms dans une nouvelle tâche | Exit 1, 7 échecs sur 32 | 25 s |
| `sound-scheduled` | Départ Web Audio programmé 200 ms plus tard | Exit 1, 7 échecs sur 32 | 21 s |
| `return-disabled` | Durée des animations ramenée à zéro | Exit 1, seul le check de retour animé échoue (1/32) | 22 s |
| `coach-cpu` | Une seconde de CPU ajoutée au scénario long (`COACH_TEXTS_ONLY=1`) | Exit 1, seul le seuil CPU échoue (1/88), 1 000 ms mesurées | 28 s |
| `truncate-old-precache` | Corps HTTP de `puzzles.json` tronqué à chaque tentative | Exit 1, 8 échecs sur 21 ; aucun des quatre anciens builds ne passe | 163 s |

Le lancement final de `truncate-old-precache` donne exit 1, 8 échecs sur 21 checks, en 163 s dont 157 s pour la suite.
Chaque ancien build s’arrête après cinq tentatives infructueuses, avant de prétendre tester une montée de version sans ancien service worker.
Le journal est `e2e/shots/q1-precache-final.log`.

## Contrat du lanceur

La suite `runner` lance de vrais sous-processus avec un succès, un échec, une troisième tâche en attente et une tâche qui dépasse son délai.
Elle vérifie huit invariants : conservation des succès, conservation de l’échec, arrêt au délai, durées complètes, chevauchement, capacité bornée, dossiers isolés supprimés et absence de processus survivants.
La tâche lente crée aussi un enfant qui ignore SIGTERM et un enfant détaché, comme Chromium.
`npm run test:e2e -- --suite runner --jobs 1` donne exit 0, 8 checks, en 16 s dont 10 s pour la suite.
Les échecs imprimés par les sous-processus synthétiques sont attendus ; le résultat de `runner` est vert.

## Durées avant et après

Les deux passages complets finaux sont verts : 34 suites contre 33 auparavant, la suite `runner` étant nouvelle.
Le premier prend 767 s (12 min 47 s), soit 49,1 % de moins que les 1 507 s de référence.
Le deuxième prend 810 s (13 min 30 s), soit 46,3 % de moins.
La somme des durées des suites vaut respectivement 1 518 s et 1 599 s, contre 1 498,2 s dans la référence.
Le gain total vient surtout du parallélisme borné ; les attentes conditionnelles réduisent aussi `all_buttons`, `learn` et `v4`.
La référence comporte trois échecs dans `endgames` ; les deux nouveaux passages sont entièrement verts.
Cette comparaison mesure des campagnes sur la même machine partagée, sans prétendre isoler une charge constante.
Les secondes après sont arrondies par le lanceur ; leur somme affichée peut donc différer de la somme calculée avant arrondi.

| Suite | Avant série (s) | Après 1 (s) | Après 2 (s) | Checks avant / après 1 / après 2 |
| --- | ---: | ---: | ---: | --- |
| `all_buttons` | 69.5 | 57 | 57 | 97 / 98 / 97 |
| `analysis_robust` | 109.2 | 112 | 113 | 88 / 88 / 88 |
| `archive_import` | 22.1 | 23 | 27 | 145 / 145 / 145 |
| `attaque` | 27.7 | 28 | 27 | 106 / 114 / 114 |
| `audio_settings` | 9.1 | 9 | 10 | 9 / 9 / 9 |
| `backup` | 9.1 | 10 | 11 | 225 / 225 / 225 |
| `bots` | 20.6 | 24 | 28 | 93 / 93 / 93 |
| `coach` | 87.1 | 93 | 93 | 138 / 138 / 138 |
| `continuation` | 33.8 | 34 | 36 | 74 / 74 / 74 |
| `cours_roque` | 85.6 | 86 | 88 | 112 / 112 / 112 |
| `diagnostic_attaque` | 38.7 | 39 | 40 | 143 / 143 / 143 |
| `edge_navigation` | 48.8 | 48 | 50 | 193 / 193 / 193 |
| `endgame_course` | 114.3 | 115 | 115 | 109 / 109 / 109 |
| `endgame_play` | 20.1 | 20 | 23 | 86 / 86 / 86 |
| `endgames` | 32.7 | 46 | 59 | 26 / 28 / 28 |
| `feeling` | 15.1 | 13 | 14 | 30 / 32 / 32 |
| `insights` | 36.3 | 39 | 46 | 223 / 223 / 223 |
| `insights_archives` | 9.6 | 11 | 11 | 23 / 23 / 23 |
| `learn` | 69.1 | 58 | 57 | 66 / 66 / 66 |
| `mats` | 54.9 | 53 | 53 | 91 / 91 / 91 |
| `names_fr` | 12.6 | 13 | 14 | 29 / 29 / 29 |
| `openings` | 39.3 | 34 | 40 | 75 / 75 / 75 |
| `pieces_sons` | 45.8 | 47 | 48 | 86 / 86 / 86 |
| `play_lifecycle` | 57.3 | 59 | 58 | 84 / 84 / 84 |
| `premove` | 47.8 | 49 | 50 | 78 / 78 / 78 |
| `puzzles` | 36.2 | 37 | 37 | 79 / 79 / 79 |
| `pwa` | 3.5 | 4 | 5 | 41 / 41 / 41 |
| `revision` | 36.8 | 38 | 39 | 147 / 147 / 147 |
| `runner` | - | 11 | 11 | - / 8 / 8 |
| `shell` | 33.7 | 34 | 35 | 98 / 98 / 98 |
| `touch` | 19.1 | 18 | 21 | 63 / 63 / 63 |
| `upgrade` | 73 | 82 | 78 | 989 / 989 / 989 |
| `v4` | 26.2 | 17 | 19 | 28 / 28 / 28 |
| `viewport` | 153.5 | 155 | 186 | 519 / 519 / 519 |

Aucune suite existante n’est supprimée, et aucun nombre de checks par suite ne baisse par rapport à la référence dans ces deux passages.
Le nombre de checks d’attaque peut varier selon les positions parcourues ; les assertions et le parcours de cette suite n’ont pas été modifiés.
Dans `all_buttons`, le check de réessai dépend du verdict du puzzle, ce qui explique 98 puis 97 checks.
Les finales vont maintenant jusqu’au résultat attendu, au lieu de s’arrêter sur une répétition due au joueur de test sans historique.
`upgrade` passe deux fois ses 989 checks, sans réessai d’installation dans ces deux journaux.
`feeling` passe deux fois ses 32 checks, après les deux mutations audio rouges.

## Rechargements intempestifs en développement

Le premier passage dev a été perturbé pendant la rédaction du bilan : `<main>` disparaissait au milieu d’un geste de `viewport`.
Une relance isolée a reproduit l’échec en 8 s.
Une trace des navigations a ensuite relié l’échec à la modification d’un fichier surveillé : `touch docs/q1-e2e.md` provoquait une reconnexion Vite et un nouveau document encore vide (`readyState=interactive`) à la même URL.
Ce rechargement pouvait aussi laisser `analysis_robust` attendre un bilan dans une page réinitialisée.
Il ne s’agissait pas d’une régression du composant d’échiquier.

Le serveur E2E dev utilise désormais `e2e/vite.config.ts`, qui fusionne la configuration normale avec `server.watch=null` et `server.hmr=false`.
Le mode développement et React StrictMode restent actifs ; le serveur de développement utilisé manuellement garde sa surveillance et HMR.
La campagne dev perturbée a été arrêtée proprement et n’est pas comptée comme une validation réussie.
Les journaux de reproduction sont `q1-viewport-dev-repro.log` et `q1-viewport-dev-trace.log` dans `e2e/shots/`.

Après correction, la même trace passe : exit 0, 519 checks, 162 s au total, malgré des modifications de documentation et un nouveau `touch docs/q1-e2e.md` pendant les gestes.
Le journal est `e2e/shots/q1-viewport-dev-fixed.log`.
Le diagnostic ajouté temporairement à `test_viewport.py` a été retiré : ses assertions restent inchangées.

## Vérifications finales

Les commandes utilisent Node 22.21.1 et le Python 3.12 de `.venv`.
Toutes les commandes E2E ont été exécutées sous le verrou commun à trois places, avec au plus deux workers.
Les deux commandes prod ont été enchaînées par `e2e/shots/q1-validation-final.py` sous un seul verrou ; leurs codes individuels sont enregistrés dans `q1-validation-final.json`.
La dernière commande dev a été exécutée séparément après correction de HMR.

| Commande | Résultat exact |
| --- | --- |
| `npm run check` | Exit 0 : lint et typecheck |
| `git diff --check` | Exit 0 |
| Analyse `ast.parse` de tous les `e2e/*.py` | Exit 0 |
| `npm run test:e2e -- --jobs 2`, passage 1 | Exit 0, 34 suites, 4 414 checks, 767 s |
| `npm run test:e2e -- --jobs 2`, passage 2 | Exit 0, 34 suites, 4 413 checks, 810 s |
| `npm run test:e2e:dev -- --jobs 2`, après correction HMR | Exit 0, 32 suites, 3 383 checks, 744 s ; PWA et upgrade ignorées car spécifiques au build prod |
| `npm run test:e2e -- --suite runner --jobs 1` | Exit 0, 8 checks, 16 s |
| `E2E_MUTATION=sound-task npm run test:e2e -- --suite feeling --jobs 1` | Exit 1 attendu, 7 échecs sur 32, 25 s |
| `E2E_MUTATION=sound-scheduled npm run test:e2e -- --suite feeling --jobs 1` | Exit 1 attendu, 7 échecs sur 32, 21 s |
| `E2E_MUTATION=return-disabled npm run test:e2e -- --suite feeling --jobs 1` | Exit 1 attendu, 1 échec sur 32, 22 s |
| `E2E_MUTATION=truncate-old-precache npm run test:e2e -- --suite upgrade --jobs 1` | Exit 1 attendu, 8 échecs sur 21, 163 s |
| `COACH_TEXTS_ONLY=1 E2E_MUTATION=coach-cpu npm run test:e2e -- --suite coach --jobs 1` | Exit 1 attendu, 1 échec sur 88, 28 s |
| `python3 e2e/shots/q1-trace-runner.py`, avant correction avec fichier touché | Exit 1, 1 échec sur 60, 21 s |
| Même trace après correction avec fichiers modifiés | Exit 0, 519 checks, 162 s |

Le lancement dev initial est conservé comme diagnostic dans `q1-dev-final.log`, mais arrêté volontairement après la reproduction du rechargement : exit 1, campagne incomplète.
Le résultat dev valide est `q1-dev-fixed.log`, avec exit 0 enregistré dans `q1-dev-fixed.exit`.
Les captures finales relues sont `f14_drag_tactile.png` (393 × 852), `viewport_393x660_analyse.png` (393 × 660) et `f14_drag_souris.png` (1440 × 900), dans `e2e/shots/`.
Aucune anomalie visuelle supplémentaire n’y a été relevée.

## Fichiers et décisions

Créés : `docs/q1-e2e.md`, `e2e/test_runner.py`, `e2e/vite.config.ts`.
Modifiés : `.gitignore`, `CLAUDE.md`, `README.md`, `docs/f14-feeling.md`, `e2e/run.py`, `e2e/helpers.py`, `e2e/coach_texts.mjs`, `e2e/test_all_buttons.py`, `e2e/test_coach.py`, `e2e/test_endgames.py`, `e2e/test_feeling.py`, `e2e/test_learn.py`, `e2e/test_upgrade.py`, `e2e/test_v4.py`.
Le spec et son état final restent dans les métadonnées Git propres au worktree.

Le challenge existant n’a pas été refait, conformément aux consignes de reprise.
Ses amendements sur les groupes de processus, Chromium détaché, les durées atomiques, l’ordre des suites, le préchargement audio et les mutations ont été conservés et vérifiés.
Le blocage général des service workers a été écarté pour préserver la couverture PWA.
Les décisions de reprise sont deux workers par défaut, le contrat de sous-processus réels, les mutations supplémentaires d’animation et de CPU, ainsi que la désactivation de HMR uniquement dans les E2E dev après reproduction.
Aucun comportement de l’application ni format de données utilisateur n’a été modifié.
Il ne reste aucun travail requis dans le périmètre Q1 ; les limites des mesures de charge et de latence acoustique sont précisées plus haut.
Aucun commit, push, gate ou PR n’a été effectué.
