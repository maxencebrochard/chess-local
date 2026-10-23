# ChessLocal : audit UX et architecture cible

## Décision validée le 17 octobre 2026

Faire de ChessLocal un outil qui répond à « Que faire maintenant pour progresser ? », avec cinq destinations stables : Accueil, Jouer, Puzzles, Apprendre et Plus.
L’accueil donne une action prioritaire ; Apprendre distingue les parcours guidés des entraînements à la carte ; Plus rassemble les parties, les outils et les réglages.
Max a validé cette architecture (« ok go pour tout »).
La phase 1 ci-dessous est conservée comme diagnostic historique ; le lot 1 est mis en œuvre séparément, sans modification de la navigation.
Les lots 2 et suivants restent différés.
Le [lot 0](#lot-0--réconciliation-après-fusion-complète) réconcilie l’audit avec la base où toutes les features retenues sont fusionnées : chaque route y a sa place cible.

## Actualisation après synchronisation sur main

Base du lot 1 : `ec50256caea3ab4408809bf9aef51ef62051a57a`.
Les données de la phase 1 qui suivent restent celles du premier audit ; les mesures actualisées sont regroupées ici pour conserver leur traçabilité.
L’audit initial relancé échoue sur sept routes nouvelles non couvertes, puis passe après extension de sa matrice : 424 checks, 35 routes, 268 états et 425 captures, sans débordement horizontal.
Les inventaires avant modification visuelle sont conservés dans `e2e/shots/ux-lot1/audit-reconciled/` : 90 états et 133 captures à 393 × 852, 90 et 174 à 393 × 660, 88 et 118 à 1440 × 900.

### Diagnostic chiffré actualisé avant lot 1

La navigation comporte toujours sept onglets de 56 px et des libellés de 10 px sur mobile.
Accueil compte maintenant douze actions hors navigation, treize lorsqu’une révision est due : la tuile Parcours s’est ajoutée.
Apprendre compte vingt actions : Parcours, Séance, quatre domaines, finale jouée, Mes erreurs, révision, attaques manquées, défenses ratées, ouvertures, répertoire, mats, attaque, défense, visualisation et trois cours.
La densité s’est donc accrue ; son regroupement reste la responsabilité du lot 5.

| Écran en 393 × 852 | Hauteur du contenu | Repère |
|---|---:|---|
| Accueil | 804 px | Jouer à y = 728 px, hauteur 60 px |
| Jouer | 1 036 px | Configuration inchangée |
| Apprendre | 1 832 px | Cours Les bases à y = 1 596 px, Finales à 1 672 px, Roque à 1 748 px |
| Cours de finales | 1 707 px | 14 leçons |
| Attaque | 2 530 px | Catégorie initiale |
| Statistiques | 1 842 px | Réglages toujours présents |

À 393 × 660, Apprendre représente désormais 2,99 hauteurs de contenu (1 832 / 612), contre 2,37 lors de la phase 1.
Sur desktop, Apprendre mesure 1 680 px de haut.
Avec révision due et insets simulés, Accueil reste à 665 px de contenu pour 578 px disponibles à 660 px.

### Fonctions effectivement fusionnées

| Fonction | Route / intégration observée | Persistance conservée |
|---|---|---|
| Parcours | `/apprendre/parcours`, `/apprendre/parcours/:id`, placement interne | `learnSessions` domaine `path` |
| Les bases | `/apprendre/bases`, `/apprendre/bases/:id` | `course`, préfixe `bases:` |
| Moments critiques | `/moment-critique`, entrée depuis le bilan | `critical-moment` |
| Mon répertoire | `/repertoire` | `opening-drill`, sans nouvelle table |
| Calcul et visualisation | `/visualisation` | `visualisation` |
| Réfutation | Lecteur dans les bilans et erreurs, sans route propre | Aucune écriture |
| Insights reliés | Liens contextuels vers attaque, défense et listes personnelles | Cache existant |
| Défense | `/defense`, `/defense/:id`, `/defenses-ratees`, `/defenses-ratees/:id` | Domaines existants |
| Lanceur parallèle | `e2e/run.py`, `--jobs 1` ou `2` sous verrou | Journaux et durées locaux |

Aucune route de cours de défense distincte n’était présente dans la base du lot 1 ; le cours « Tenir sous l’attaque » (`/apprendre/defense`) a été fusionné depuis, voir le [lot 0](#lot-0--réconciliation-après-fusion-complète).
Le tableau des branches de la phase 1 reste historique ; seules les intégrations ci-dessus sont constatées sur cette base.

## Lot 0 : réconciliation après fusion complète

Base du lot 0 : `31a2e60` (`origin/main` du 23 octobre 2026), après fusion de toutes les features retenues.
Q3 (chargement des routes à la demande) est encore sur sa branche : le lot 0 ne touche ni `src/App.tsx` ni son mécanisme de chargement.
Aucune route, aucun domaine `learnSessions`, aucune clé de stockage ni aucun écran n’est modifié : seuls l’audit et ce document changent.
Les décisions validées le 17 octobre (cinq onglets, Entraînement en cinq groupes sous Apprendre, Plus avec parties, outils et réglages) sont reprises telles quelles ; chaque route actuelle y reçoit une place.

### Inventaire et contrôle des routes

`src/App.tsx` déclare 45 routes explicites et le repli `*` vers l’accueil, soit 46 entrées.
Le premier audit en comptait 28, le lot 1 en couvrait 35.
Avant le lot 0, d’après la lecture de l’ancienne matrice, dix routes déclarées n’étaient photographiées par aucun état de l’audit : `/seance`, `/convertir`, `/convertir/:id`, `/finales/chrono`, `/structures`, `/structures/:key`, `/apprendre/defense`, `/apprendre/defense/:id`, `/apprendre/structures` et `/apprendre/structures/:id` ; le repli `*` ne l’était pas non plus.
La matrice de `e2e/test_ux_audit.py` les couvre maintenant, avec l’exercice de conversion, une série de Finales au chrono, la leçon d’entrée des deux nouveaux cours, la liste vide de Mes structures et une position de structure absente.

La suite lit la table des routes dans l’app en cours d’exécution, pas dans le texte source.
React Router ne crée pas de fibre par `<Route>` : il lit les éléments enfants de `<Routes>` par `createRoutesFromChildren`.
La fibre de `Routes` porte donc ces éléments dans `memoizedProps.children`, que la suite atteint depuis le nœud `main` rendu, sans dépendre d’aucun nom de composant.
Le contrôle fonctionne sur le build minifié comme en développement, et reste valable si l’`element` d’une route devient un composant chargé à la demande.
Pour chaque route déclarée, un check exige au moins un chemin audité dont la meilleure correspondance, au classement de React Router (segment statique avant paramètre), est cette route : `/finales/chrono` n’est donc pas couverte par `/finales/:id`.
Un check de garde exige au moins 40 routes, dont `/` et `*`, pour qu’un parcours de l’arbre cassé échoue au lieu de passer à vide.
`UX_AUDIT_FORGET=/convertir` retire un chemin de la matrice : la suite échoue alors sur « route /convertir couverte par l’audit » aux trois formats (preuve par mutation, code 1).

Limite : le contrôle s’appuie sur des internes de React (`__reactFiber$`, `memoizedProps`), stables depuis React 16 mais non publics.
Si React les change, ou si un lot remplace `<Routes>` par des objets de route (`useRoutes`, `createHashRouter`), le check de garde échoue bruyamment.
Il faudrait alors lire ces objets de route, ou à défaut analyser `src/App.tsx` avec l’API du compilateur TypeScript (`ts.createSourceFile`, déjà dans `node_modules`) ; un grep du texte source reste exclu.

### Placement cible de chaque route

« Onglet actuel » est l’onglet allumé par `NAV` dans `src/App.tsx` ; « Place cible » applique l’architecture validée.
Les routes restent identiques : le lot 2 ne change que le rattachement et les entrées.

| Route | États audités (préfixe de capture) | Onglet actuel | Place cible | Persistance |
|---|---|---|---|---|
| `/` | `accueil`, `accueil-revision`, insets simulés, focus clavier | Accueil | Accueil | Aucune propre |
| `/seance` | `seance-du-jour` | Accueil | Accueil, carte principale « Ta séance du jour » | `seance`, plus les domaines des étapes |
| `/jouer` | `jouer`, `jouer-local`, `jouer-coach`, `partie`, `abandon-confirmation`, `fin-partie`, `bilan-partie` | Jouer | Jouer : contre un bot, avec le coach (alerte menace), à deux | `games`, `ratings` des cadences, `threat-check` |
| `/puzzles` | `puzzles`, `puzzles-chargement`, `puzzle-fixture`, `puzzle-reussi`, `puzzles-erreur`, `puzzles-reprise` | Puzzles | Puzzles | `puzzleAttempts`, `ratings` `puzzle` |
| `/rush` | `rush`, `rush-exercice`, `rush-resultat` | Puzzles | Puzzles / Rush | `rushScores` |
| `/mats` | `mats`, fiches et exercices `mat-chrono`, `mate-1`, `geo-escalier`, `motif-damiano` | Apprendre | Puzzles / Mats éclair, raccourci depuis Tactique et calcul | `mats` |
| `/apprendre` | `apprendre`, séances et exercices des quatre domaines, `mes-erreurs`, `seance-verdict`, `seance-analyse`, `seance-bilan` | Apprendre | Hub Apprendre ; séance rapide et domaines rangés dans les groupes d’Entraînement ; Mes erreurs dans Réviser mes parties | `endgame`, `tactic`, `opening`, `strategy`, `mistakes` |
| `/apprendre/parcours` | `parcours` | Apprendre | Apprendre / Mon parcours | `path` |
| `/apprendre/parcours/:id` | `parcours-etape`, `parcours-placement` | Apprendre | Apprendre / Mon parcours | `path` |
| `/apprendre/bases`, `/apprendre/bases/:id` | `cours-bases`, `lecon-bases` | Apprendre | Apprendre / Toutes les leçons | `course` `bases:` |
| `/apprendre/finales`, `/apprendre/finales/:id` | `cours-finales`, `lecon-finales` | Apprendre | Toutes les leçons ; « Comprendre » du groupe Finales | `course` `finales:` |
| `/apprendre/roque`, `/apprendre/roque/:id` | `cours-roque`, `lecon-roque` | Apprendre | Toutes les leçons ; lien du groupe Attaque et défense | `course` `roque:` |
| `/apprendre/defense`, `/apprendre/defense/:id` | `cours-defense`, `lecon-defense` | Apprendre | Toutes les leçons ; lien du groupe Attaque et défense | `course` `defense:` |
| `/apprendre/structures`, `/apprendre/structures/:id` | `cours-structures`, `lecon-structures` | Apprendre | Toutes les leçons ; lien du groupe Stratégie | `course` `structures:` |
| `/structures` | `structures` (profil sans partie) | Apprendre | Entraînement / Stratégie « Mes structures de pions » | `structure-play` |
| `/structures/:key` | `structures-absent` | Apprendre | Entraînement / Stratégie | `structure-play` |
| `/ouvertures` | `ouvertures`, `ouverture-fiche`, `ouverture-exercice` | Apprendre | Entraînement / Ouvertures « Mes ouvertures » | `opening-drill` |
| `/repertoire` | `repertoire` | Apprendre | Entraînement / Ouvertures « Mon répertoire » | `opening-drill` (`next:`) |
| `/visualisation` | `visualisation` | Apprendre | Entraînement / Tactique et calcul « Visualiser » | `visualisation` |
| `/attaque`, `/attaque/:id` | `attaque`, `attaque-exercice` | Apprendre | Entraînement / Attaque et défense « Attaquer » | `attack` |
| `/defense`, `/defense/:id` | `defense`, `defense-exercice` | Apprendre | Entraînement / Attaque et défense « Défendre » | `defense` |
| `/convertir`, `/convertir/:id` | `convertir`, `convertir-exercice` | Apprendre | Entraînement / Attaque et défense « Convertir un avantage » | `conversion` |
| `/finales`, `/finales/:id` | `finales`, `finale-exercice` | Apprendre | Entraînement / Finales « Jouer une finale » | `endgame-play` |
| `/finales/chrono` | `finales-chrono`, `finales-chrono-serie` | Apprendre | Entraînement / Finales « Contre la montre » | `endgame-clock` |
| `/revision` | `revision-vide`, `revision-exercice` | Apprendre | Apprendre / Réviser mes parties « À réviser », raccourci Accueil si dû | `revision` et domaines d’origine |
| `/attaques-manquees`, `/attaques-manquees/:id` | `attaques-vide`, `attaques-remplies`, `attaque-personnelle`, `attaque-reussie`, `attaques-manquees-absent`, `analyse-retour` | Apprendre | Réviser mes parties « Attaques » | `missed-attack` |
| `/defenses-ratees`, `/defenses-ratees/:id` | `defenses-vide`, `defenses-remplies`, `defense-personnelle`, `defenses-ratees-absent` | Apprendre | Réviser mes parties « Défenses » | `missed-defense` |
| `/moment-critique` | `moment-vide` | Analyse | Réviser mes parties « Moments critiques », ouvert depuis le bilan | `critical-moment` |
| `/analyse` | `analyse`, `analyse-options`, `analyse-import`, `analyse-import-erreur`, retours d’exercice | Analyse | Plus / Outils et progression « Analyse », raccourcis contextuels conservés | `mistakes` écrites par le bilan |
| `/analyse/jouer` | `position-vide`, `position-jeu` | Analyse | Plus / Analyse, « Jouer contre le moteur » | Partie en cours locale |
| `/archive` | `archive-vide`, `archive-remplie` | Archive | Plus / Mes parties | `games` |
| `/import` | `import`, `import-rempli` | Analyse | Plus / Mes parties « Importer des parties » | Aucune (pseudo dans les réglages) |
| `/stats` | `stats`, `donnees-confirmation` | Stats | Plus / Statistiques ; Réglages et Mes données extraits au lot 3 | Réglages Zustand, sauvegardes |
| `/insights` | `insights-vide` | Stats | Plus / Mon bilan | `reviews` |
| `*` | `route-inconnue` | Aucun | Repli vers Accueil, inchangé | Aucune |

La séance du jour et le parcours jouent aussi des positions d’attaque et de finale, mais sur place (`/seance` et `/apprendre`, même `PositionGame`, mêmes domaines), sans visiter `/attaque/:id` ni `/finales/:id`.
Les routes `/finales/:id`, `/attaque/:id`, `/defense/:id` et `/convertir/:id` n’ont pour entrée que leur catalogue, propriété du groupe d’Entraînement.

### Fonctions sans route propre

| Fonction | Point d’entrée actuel | Place cible |
|---|---|---|
| Séance rapide (bouton Séance d’Apprendre) | `/apprendre`, état interne | Apprendre, entrée secondaire « Séance rapide » tant que la séance du jour ne la remplace pas |
| Test de placement | `/apprendre/parcours/placement` | Mon parcours |
| Finale jouée depuis une étape du parcours | `/apprendre` avec `state.endgame` | Mon parcours, sans changer le domaine `path` |
| Alerte « Qu’est-ce qu’il menace ? » | Jouer, bot et coach, réglage par mode | Jouer / Avec le coach, pas une tuile |
| Résumé des menaces et des attaques manquées | Sections de `/stats` | Plus / Statistiques |
| Réfutation « Pourquoi ? » | Bilan guidé, carte du coach, verdict de `MistakeExercise` | Tactique et calcul « Comprendre une réfutation », toujours attachée à une position |
| Moments critiques du bilan | Fin du résumé de bilan dans `/analyse` | Réviser mes parties, via le bilan |
| Calque « Compte les attaquants » | Options d’Analyse, Jouer, réglage `showAttackers` | Réglages, et bascule contextuelle conservée |
| Thème, pièces, sons et volume, prémouvements, coups légaux, profondeur du bilan | `/stats` section Réglages | Plus / Réglages |
| Coordonnées de l’échiquier | Rendu de `Board`, sans réglage | Socle, aucun écran |
| Exporter, restaurer, réinitialiser | `/stats` section Tes données, bandeau de l’Accueil | Plus / Mes données |
| App iOS Capacitor (haptique, assets locaux) | Coquille native | Socle, aucun écran |

### Domaines `learnSessions` et stockage local

Les 22 domaines écrits aujourd’hui sont listés dans `src/lib/db.ts` ; aucun n’est renommé par la refonte.

| Domaine | Écrit par | Groupe cible |
|---|---|---|
| `endgame`, `tactic`, `opening`, `strategy` | Séances d’Apprendre | Finales, Tactique et calcul, Ouvertures, Stratégie |
| `mistakes` | Mes erreurs | Réviser mes parties |
| `revision` | Révision espacée (puzzles) | Réviser mes parties |
| `missed-attack`, `missed-defense` | Listes personnelles | Réviser mes parties |
| `critical-moment` | Moments critiques | Réviser mes parties |
| `course` | Cinq cours (`bases:`, `finales:`, `roque:`, `defense:`, `structures:`) | Toutes les leçons |
| `path` | Parcours et placement | Mon parcours |
| `seance` | Séance du jour | Accueil |
| `opening-drill` | Entraîneur d’ouvertures, Mon répertoire, révision des variantes | Ouvertures |
| `attack`, `defense`, `conversion` | Entraîneurs d’attaque, de défense et de conversion | Attaque et défense |
| `endgame-play`, `endgame-clock` | Finales jouées, Finales au chrono | Finales |
| `visualisation` | Calcul et visualisation | Tactique et calcul |
| `mats` | Mats éclair | Puzzles |
| `structure-play` | Mes structures de pions | Stratégie |
| `threat-check` | Alerte menace de Jouer | Jouer |

Les clés locales propres à une activité sont `chess-local-attack`, `chess-local-defense`, `chess-local-conversion`, `chess-local-endgame-clock`, `chess-local-mats`, `chess-local-threat-check`, `chess-local-visualisation`, `chess-local-insights-v1`, `chess-local-position-game-v1`, `chess-local-play-game` et `chess-local-puzzle-session`.
Les séances en cours sont dans `learn-session-v1`, `revision-session-v1`, `path-session-v1` et `seance-session-v1`, l’exercice laissé pour l’analyseur dans `exercise-return-v1`.
Toutes figurent dans `APP_LOCAL_KEYS` ou `SESSION_KEYS` de `src/lib/backup.ts` : aucun écart de purge n’est constaté.

### Regroupement exhaustif après lot 0

Ce tableau remplace, pour la mise en œuvre, les colonnes « présentes » et « annoncées » du [regroupement du premier audit](#regroupement-exhaustif-des-fonctions), sans en changer les groupes ni les noms proposés.

| Groupe propriétaire | Fonctions et routes | Raccourcis conservés |
|---|---|---|
| Accueil | Séance du jour `/seance`, révision due, accès Jouer et Puzzles, progression vers Mon bilan | Reprise d’une séance en cours |
| Jouer | `/jouer` : bot, coach avec alerte menace, deux joueurs ; fin de partie vers le bilan | CTA Jouer de l’Accueil |
| Puzzles | `/puzzles`, `/rush`, `/mats` | Mats depuis Tactique et calcul, Rush depuis Insights |
| Apprendre / Mon parcours | `/apprendre/parcours`, `/apprendre/parcours/:id`, placement | Tuile Accueil pendant la transition |
| Apprendre / Toutes les leçons | Cinq cours : Les bases, Cours de finales, Démolir le roque, Tenir sous l’attaque, Structures de pions | Liens depuis les groupes Finales, Attaque et défense, Stratégie |
| Entraînement / Tactique et calcul | Séances Tactiques, `/visualisation`, réfutation expliquée | Mats éclair |
| Entraînement / Attaque et défense | `/attaque`, `/defense`, `/convertir` et leurs fiches | Cours Démolir le roque et Tenir sous l’attaque |
| Entraînement / Finales | Séances Finales, `/finales` et `/finales/:id`, `/finales/chrono` | Cours de finales |
| Entraînement / Ouvertures | Séances Ouvertures, `/ouvertures`, `/repertoire` | Lien de Mon bilan vers le répertoire |
| Entraînement / Stratégie | Séances Stratégie, `/structures` et `/structures/:key` | Cours Structures de pions, qui affiche déjà la carte Mes structures |
| Apprendre / Réviser mes parties | `/revision`, Mes erreurs, `/attaques-manquees`, `/defenses-ratees`, `/moment-critique` | Révision due sur l’Accueil, moments critiques dans le bilan |
| Plus / Mes parties | `/archive`, `/import` | Tuiles de l’Accueil pendant la transition |
| Plus / Outils et progression | `/analyse`, `/analyse/jouer`, `/stats`, `/insights` | Fin de partie, exercices et listes vers l’analyse |
| Plus / Préférences et données | Réglages et Tes données de `/stats` | Bandeau de sauvegarde de l’Accueil |

### Carte de navigation après lot 0

Arbre des entrées actuelles, avant le lot 2 ; `[état]` désigne un état interne sans URL propre.

```text
Accueil /
├─ Problèmes → /puzzles ; Séance du jour → /seance ; À réviser (si dû) → /revision
├─ Quatre classements → /stats ; tuiles Analyse, Puzzle Rush, Archive, chess.com
├─ Parcours → /apprendre/parcours ; Insights → /insights ; CTA Jouer → /jouer
Jouer /jouer [onglet]
├─ Contre un bot / Entraîneur / 2 joueurs [états], alerte menace [état]
└─ Partie → abandon → résultat → /analyse?game=<id>&review=1
Puzzles /puzzles [onglet] → /rush, /mats
Apprendre /apprendre [onglet]
├─ Parcours /apprendre/parcours → /:id, placement
├─ Séance ; Finales ; Tactiques ; Ouvertures ; Stratégie ; Mes erreurs [états]
├─ /finales → /:id ; /finales/chrono
├─ /revision ; /attaques-manquees → /:id ; /defenses-ratees → /:id
├─ /ouvertures ; /repertoire ; /mats ; /attaque → /:id ; /convertir → /:id ; /defense → /:id
├─ /visualisation ; /structures → /:key
└─ Cours /apprendre/{bases,finales,roque,defense,structures} → /:id
   └─ /apprendre/structures affiche aussi la carte → /structures
Analyse /analyse [onglet] → /analyse/jouer, /import, bilan → /moment-critique
Archive /archive [onglet] → /analyse?game=<id>
Stats /stats [onglet] → /insights, /attaques-manquees ; Réglages et Tes données [même URL]
```

Arbre cible, avec les mêmes URL et les hubs `/plus` et `/entrainement` proposés pour les lots 2 et 5 :

```text
Accueil /                      → /seance, /revision, /jouer, /puzzles
Jouer /jouer                   → bot, coach (alerte menace), à deux → bilan
Puzzles /puzzles               → /rush, /mats
Apprendre /apprendre
├─ Mon parcours                → /apprendre/parcours, /:id, placement
├─ Toutes les leçons           → /apprendre/{bases,finales,roque,defense,structures}
├─ Entraînement
│  ├─ Tactique et calcul       → séance Tactiques, /visualisation, raccourci /mats
│  ├─ Attaque et défense       → /attaque, /defense, /convertir
│  ├─ Finales                  → séance Finales, /finales, /finales/chrono
│  ├─ Ouvertures               → séance Ouvertures, /ouvertures, /repertoire
│  └─ Stratégie                → séance Stratégie, /structures
├─ Réviser mes parties         → /revision, Mes erreurs, /attaques-manquees, /defenses-ratees, /moment-critique
└─ Séance rapide               → séance automatique existante
Plus
├─ Mes parties                 → /archive, /import
├─ Outils et progression       → /analyse, /analyse/jouer, /insights, /stats
└─ Réglages, Mes données       → sections actuelles de /stats
```

### Budget de taps des fonctions fusionnées

Mêmes conventions que le [budget de taps actuel](#budget-de-taps-actuel) : profil vierge, activations depuis l’Accueil, défilement non compté.
La colonne cible suppose les lots 2 à 6 livrés selon l’architecture validée ; elle n’est pas mesurée.

| Fonction | Actuel : page / commencer | Cible : page | Chemin cible |
|---|---:|---:|---|
| Séance du jour | 1 / 2 | 1 | Carte principale de l’Accueil |
| Parcours | 1 / 2 | 2 | Apprendre, Continuer |
| Tenir sous l’attaque, Structures de pions, Les bases | 2 / 3 | 3 | Apprendre, Toutes les leçons, cours |
| Convertir l’avantage | 2 / 3 | 4 | Apprendre, Entraînement, Attaque et défense, Convertir |
| Finales au chrono | 2 / 3 | 4 | Apprendre, Entraînement, Finales, Contre la montre |
| Calcul et visualisation | 2 / 3 | 4 | Apprendre, Entraînement, Tactique et calcul, Visualiser |
| Mon répertoire | 2 / variable | 4 | Apprendre, Entraînement, Ouvertures, Mon répertoire |
| Mes structures de pions | 2 / 3 si une partie existe | 4 | Apprendre, Entraînement, Stratégie, Mes structures |
| Moment critique | 1 depuis le bilan | 1 depuis le bilan | Aucune liste propre, voir écarts |
| Alerte menace | 3 (Jouer, Entraîneur, Jouer) | 3 | Jouer, Avec le coach, Jouer |
| Réfutation | 1 depuis un verdict ou un bilan | 1 | Inchangé |
| Insights | 1 | 2 | Plus, Mon bilan |
| Réglages | 1 puis défilement | 2 | Plus, Réglages |

### Écarts constatés

1. Le cours « Tenir sous l’attaque » est fusionné (`/apprendre/defense`), contrairement à la mention du lot 1 selon laquelle aucune route de cours de défense n’existait.
2. Dix routes et le repli `*` échappaient à l’audit avant ce lot ; elles sont couvertes et un check empêche une nouvelle omission.
3. Apprendre compte 25 actions hors navigation, contre 20 au lot 1 et 16 au premier audit : Finales au chrono, Convertir l’avantage, Mes structures de pions et deux cours se sont ajoutés.
4. Apprendre mesure 2 288 px de contenu à 393 × 852, soit 3,74 hauteurs de conteneur à 393 × 660 (612 px), contre 2,99 au lot 1 ; 2 084 px sur desktop.
5. L’Accueil compte 13 actions hors navigation, 14 avec une révision due : la carte Séance du jour s’est ajoutée, et le libellé « Problèmes » avec « Résolvez ! » demeure (constat P1 de vocabulaire inchangé).
6. Les portes Finales sont désormais quatre (cours, séance Finales, Jouer une finale, Finales au chrono), plus les finales du parcours ; le groupe Finales doit les présenter par objectif.
7. « Contre la montre », nom cible de Finales au chrono, décrit déjà le mode chrono de Mats éclair (« contre la montre, mat en N ») ; les deux reposent sur `RunRecorder` de `mates.ts` mais restent deux fonctions distinctes, à nommer sans collision au lot 5.
8. Deux entrées s’appellent Séance : la séance rapide d’Apprendre et la Séance du jour ; le lot 4 doit garder la séance du jour en principal et la séance rapide en secondaire.
9. La séance du jour intègre jusqu’à quatre révisions dues, et l’Accueil affiche aussi la carte « À réviser aujourd’hui » : la règle validée de non-double comptage doit être appliquée au lot 4.
10. `/structures` et `/repertoire` lisent les parties du joueur, mais leur propriétaire validé est Stratégie et Ouvertures ; un raccourci depuis « À partir de mes parties » est permis, le choix d’un second propriétaire reste à confirmer par Max.
11. La carte Mes structures apparaît à la fois sur Apprendre et dans le sommaire du cours Structures de pions : deux raccourcis vers le même propriétaire, à conserver comme lien de cours.
12. `/moment-critique` n’a pas de liste : sans partie analysée il affiche « Aucun moment critique », et la seule entrée est le bilan ; le placer dans Réviser mes parties sans créer de liste demandera un lien vers les parties analysées.
13. `NAV` rattache `/moment-critique` et `/import` à Analyse, `/mats` à Apprendre et `/insights` à Stats ; la cible les rattache respectivement à Réviser mes parties, Plus, Puzzles et Plus.
14. `/stats` héberge maintenant les sections « Attaques manquées » et « Menaces adverses » en plus des Réglages et de Tes données ; le lot 3 n’extrait que les deux dernières.
15. Les entrées vers Insights sont trois (Accueil, Stats, Mon répertoire) et ses plans mènent vers Apprendre, Jouer, Puzzles, Rush, Mats, Finales, Ouvertures, l’attaque, la défense et les deux listes personnelles ; ces liens doivent survivre au renommage « Mon bilan ».
16. L’écran d’accueil de `/seance` offre deux sorties vers l’Accueil (retour d’en-tête et lien « Retour à l’accueil ») : à unifier avec le contrat de retour au lot 4 (`iphone660-seance-du-jour.png`).
17. Les exercices de `/convertir/:id`, comme ceux d’attaque et de défense, gardent les sept onglets sous leurs actions et un retour fléché sans libellé : constat P2 du mode immersif, étendu au lot 8 (`iphone660-convertir-exercice.png`).
18. Aucun débordement horizontal n’est mesuré sur les 304 états ; les autres défauts visuels des nouvelles pages restent à relire dans leurs lots propriétaires.

### Vérification du lot 0

`npm run check` : code 0.
`npm run test:e2e -- --suite ux_audit --jobs 1` : code 0, 774 checks, 46 routes déclarées toutes couvertes, 304 états et 515 captures.
Répartition : 102 états et 164 captures à 393 × 852, 102 et 209 à 393 × 660, 100 et 142 à 1440 × 900.
`npm run test:e2e:dev -- --suite ux_audit --jobs 1` : code 0, 774 checks.
Ces comptes précèdent la relecture du lot, qui transforme deux attentes nues en checks `ck.appears` (accueil avant lecture des routes, séries des Finales au chrono) : deux checks de plus par format.
`UX_AUDIT_FORGET=/convertir npm run test:e2e -- --suite ux_audit --jobs 1` : code 1, trois échecs attendus sur la couverture de `/convertir`.
Les inventaires et la table lue dans l’app sont dans `e2e/shots/ux-audit/{prod,dev}/` (`inventory.json`, `routes.json`).

## Périmètre et méthode

Audit du 17 octobre 2026, référence Git `0b1f6295e1f7051a299d23ce428fb8982f9f0502`, dans le worktree `ux-refonte`.
Le script `e2e/test_ux_audit.py` utilise `e2e/helpers.py`, les données locales et la fixture d’API existante, avec un profil de navigateur jetable par format.
Les formats sont 393 × 852, 393 × 660 et 1440 × 900.
Les deux mobiles utilisent l’émulation tactile iPhone 14 Pro de Chromium et l’option `standalone=True`, avec une hauteur explicitement fixée.
Cette option ne simule ni WebKit, ni l’installation PWA, ni les zones de sécurité matérielles.
Les captures ordinaires ont des insets natifs nuls ; les captures suffixées `insets-simules` réservent artificiellement 59 px en haut et 34 px en bas sur Accueil et Apprendre.
393 × 660 est ici un test de hauteur contrainte, pas une affirmation sur la taille réelle de la PWA installée.
Un passage sur iPhone physique reste un critère de livraison des futurs lots, notamment pour le clavier et VoiceOver.

Les captures et inventaires se trouvent dans `e2e/shots/ux-audit/prod/` et `e2e/shots/ux-audit/dev/`, volontairement ignorés par Git.
`manifest.json` donne la référence et les fixtures ; `inventory.json` donne les écrans, textes, liens, dimensions des contrôles, débordements et chemins des captures.
Le script photographie successivement les conteneurs défilants, car `full_page` ne suffit pas lorsque le document est fixe.
Le script attend la fin naturelle des animations finies et le décodage des images avant la capture.
Les retours d’analyse attendent la position complète de l’échiquier visible, avec disparition des pièces de la position précédente.
Les catalogues utilisent les données réelles ; les positions tirées au hasard ne sont pas des références de comparaison pixel à pixel.
Les verdicts et les retours de séance utilisent une position de mat déterministe.
Les fichiers `*-scrollN-M.png` montrent la suite du contenu, avec recouvrement entre vues.
Les mesures de contrôles incluent les éléments défilés hors du viewport et ne sont pas un décompte des seules actions visibles.
Un contrôle sous un calque peut rester dans le DOM : les chiffres bruts ne constituent pas à eux seuls un audit de cibles réellement accessibles.
Les captures sont régénérables par les commandes documentées en fin de rapport ; elles ne sont pas publiées avec le dépôt.

### Nature des preuves

| Preuve | Ce qu’elle établit | Limite |
|---|---|---|
| Parcours Playwright et marqueurs | Écrans atteints, navigation cliquée, chargement et verdicts | Pas de validation d’ergonomie par des utilisateurs |
| Captures relues | Hiérarchie, densité, coupures, place de l’échiquier | Police et emoji de l’hôte, pas le rendu iOS natif |
| Mesures DOM | Largeurs, tailles, hauteur défilante, liens | Les cibles masquées demandent une interprétation |
| Lecture du code | États internes, persistance, liens conditionnels | Les possibilités théoriques ne sont pas des parcours observés |
| Proposition produit | Architecture, noms et seuils cibles | À vérifier après fusion et sur appareil |

## Diagnostic

### Le problème principal est la concurrence des intentions

La navigation présente sept destinations de même niveau sur mobile : Accueil, Jouer, Puzzles, Apprendre, Analyse, Archive et Stats.
À 393 px, chaque onglet dispose d’environ 56 px de largeur et son texte est en 10 px.
Le problème n’est pas une cible inférieure à 44 px de large, mais la lisibilité et l’effort de distinction de sept choix permanents.
Avec cinq onglets, la largeur théorique passe à 78,6 px, soit 40 % d’espace horizontal supplémentaire par destination.

Le hub Apprendre propose seize entrées d’action : Séance, quatre domaines, finales jouées, Mes erreurs, Révision espacée, attaques manquées, défenses ratées, ouvertures, mats, attaque, défense et deux cours.
Les quatre badges de classement placés avant le bouton ne sont pas des actions et ne sont pas comptés dans ces seize entrées.
La promesse « zéro décision » est contredite par la longue liste qui suit.
Les cours arrivent après les entraîneurs alors qu’un utilisateur qui cherche à apprendre devrait distinguer immédiatement explication, pratique et révision.

L’accueil comporte onze entrées d’action hors navigation lorsque la révision n’est pas due : une carte de puzzles, quatre raccourcis vers la même page Stats, quatre tuiles, Insights et Jouer.
Une révision due ajoute une douzième entrée.
Les valeurs Elo occupent une rangée entière avant les activités secondaires et avant le bouton Jouer.
L’action la plus importante dépend de l’endroit où l’utilisateur regarde : les puzzles dominent en haut et Jouer domine en bas.

### Mesures du profil neuf en 393 × 852

Mesures CSS issues de `prod/inventory.json`, sans zones sûres simulées, avant ajout des parties de test.
Le conteneur principal mesure 804 px de haut, padding compris ; les coordonnées y sont celles du viewport au début de page.

| Écran | Hauteur du contenu | Élément significatif | Coordonnée y / hauteur |
|---|---:|---|---|
| Accueil | 804 px | CTA Jouer | y = 728 px, h = 60 px |
| Jouer | 1 036 px | CTA de lancement | y = 960 px, h = 52 px |
| Apprendre | 1 452 px | Cours de finales | y = 1 292 px, h = 68 px |
| Apprendre | 1 452 px | Démolir le roque | y = 1 368 px, h = 68 px |
| Cours de finales | 1 707 px | Sommaire existant | 14 leçons |
| Attaque | 2 530 px | Catalogue de la catégorie initiale | 30 positions |
| Statistiques | 1 842 px | Réinitialiser l’app | y = 1 784 px, h = 16 px |

Une longue page de catalogue n’est pas un défaut en soi ; c’est la profondeur du choix recommandé et l’absence de regroupement qui pénalisent ici la découverte.
Le bouton de lancement de partie est sous le premier écran, tandis que la page d’accueil laisse une grande zone vide avant son bouton ancré en bas.
Les captures `iphone852-jouer-scroll0-1.png`, `iphone852-apprendre-scroll0-2.png` et `iphone852-stats-scroll0-2.png` permettent de retrouver ces contrôles.

À 393 × 660, le conteneur principal ne mesure plus que 612 px, pour les mêmes 1 452 px de contenu d’Apprendre, soit 2,37 hauteurs de conteneur.
Sur desktop, Apprendre reste une colonne de 1 336 px de contenu pour 900 px de haut : la largeur disponible ne supprime pas le problème de classement.
Dans le profil alimenté à 660 px avec les insets simulés, l’accueil mesure 665 px pour un conteneur de 578 px et son CTA nécessite un défilement.
Ce dernier chiffre combine volontairement une révision due et une hauteur contrainte ; il ne décrit pas le profil neuf.

### Constats à traiter

| Priorité | Constat et conséquence | Preuve locale | Décision |
|---|---|---|---|
| P1 | Sept onglets et petits libellés imposent une navigation dense à chaque écran | `iphone852-accueil.png`, `src/App.tsx` | Cinq onglets, outils dans Plus |
| P1 | Seize actions dans Apprendre sans regroupement par intention | `iphone660-apprendre*.png`, `src/pages/Learn.tsx` | Parcours guidé, hub Entraînement, révision contextualisée |
| P1 | La sélection de neuf bots, du camp et de la cadence précède le lancement | `iphone852-jouer.png` et ses vues défilées | Afficher d’abord la configuration retenue et Jouer ; ouvrir la sélection détaillée à la demande |
| P1 | Trois portes Finales ont des objectifs différents mais proches dans le vocabulaire | Cours, domaine Finales, Finales jusqu’au bout | Un groupe Finales avec « Comprendre », « Exercices », « Jouer une finale » |
| P1 | Les réglages et sauvegardes sont sous Statistiques, difficilement prévisibles | `iphone660-stats-scroll*.png`, `src/pages/Stats.tsx` | Réglages et Mes données dans Plus |
| P1 | « Problèmes », « Puzzles », « Résolvez ! » et le tutoiement cohabitent | `iphone852-accueil.png`, `iphone852-puzzles.png` | Puzzles partout ; infinitifs pour les actions ; tutoiement dans les explications |
| P1 | Les états vides personnels expliquent le bilan mais ne donnent pas de raccourci pour le faire | `iphone852-attaques-vide.png`, `iphone852-defenses-vide.png` | Une action « Analyser une partie » qui mène aux parties |
| P2 | Le hub Mats est rattaché à Apprendre même lorsqu’on vient de Puzzles | `src/App.tsx`, `src/pages/Puzzles.tsx` | Propriétaire Puzzles, retour d’origine explicite |
| P2 | « Insights » ne dit pas ce que l’utilisateur va obtenir | `iphone852-insights-vide.png` | « Mon bilan » avec sous-titre « Ce que tes parties révèlent » |
| P2 | Les retours varient entre flèche, chevron textuel, croix et onglet seul | Cours, ouvertures, attaque, révision | En-tête commun et contrat de retour explicite |
| P2 | Les cours et séances masquent la navigation, mais PositionGame et Mats peuvent garder les sept onglets sous leurs actions | `iphone852-lecon-finales.png`, `iphone852-attaque-exercice.png`, `iphone852-mat-chrono.png` | Mode immersif cohérent pour les activités engagées, sortie explicite vers le contexte |
| P2 | L’import PGN/FEN n’a pas de bouton de fermeture explicite dans son panneau | `iphone852-analyse-import.png`, `src/pages/Analysis.tsx` | Fermer visible, Échap et restitution du focus ; ne pas dépendre du toucher du fond |
| P2 | Certains boutons de fermeture sont des glyphes sans nom métier et certaines cibles font 36 ou 40 px | `src/pages/Learn.tsx:310`, `src/pages/Attack.tsx` | Nom accessible et cible minimale 44 × 44 px |
| P2 | Le chargement de puzzles remplace tout le contenu par un mot | `iphone852-puzzles-chargement.png` | Conserver en-tête et emplacement, état de chargement annoncé |
| P2 | Un état vide personnel répète l’explication à plusieurs endroits, avec des compteurs à zéro | `iphone852-attaques-vide.png` | Un message utile et une action, détails après création du premier bilan |
| P2 | Les emoji mélangent couleurs, silhouettes et significations | Accueil, navigation, Apprendre | Une famille d’icônes originale ou libre, 20/24 px, texte toujours présent |
| P2 | Les pages utilisent plusieurs rayons et niveaux de titres sans rôle stable | `index.css`, `Cta`, pages | Échelle de titres et composants communs, sans nouvelle bibliothèque nécessaire |

P1 signifie obstacle à l’orientation quotidienne ; P2 signifie friction ou incohérence à corriger dans le lot propriétaire.
Ces priorités sont une analyse experte, pas des taux d’échec mesurés auprès d’utilisateurs.
Les défauts de cette phase sont consignés pour la refonte différée conformément au gel des écrans partagés.

### Repères visuels locaux

Les images suivantes sont des captures de ChessLocal générées par la suite, pas des maquettes de la cible ni des ressources de chess.com.
Elles sont visibles dans ce worktree après exécution de l’audit ; les liens ne fonctionneront pas dans un clone dépourvu des captures ignorées.

![Accueil actuel, iPhone 393 × 852](../e2e/shots/ux-audit/prod/iphone852-accueil.png)

![Apprendre actuel, iPhone 393 × 660](../e2e/shots/ux-audit/prod/iphone660-apprendre.png)

![État vide des attaques personnelles](../e2e/shots/ux-audit/prod/iphone852-attaques-vide.png)

![Résultat de partie actuel](../e2e/shots/ux-audit/prod/iphone660-fin-partie.png)

### Ce qui fonctionne et doit rester

L’application dispose déjà d’une palette cohérente, d’un bouton principal partagé `Cta`, d’un échiquier adapté aux gestes tactiles et d’un fonctionnement local sans compte.
Les cours possèdent déjà une progression et une structure par chapitres : il faut les rendre visibles, pas reconstruire leur moteur.
La révision espacée sait déjà prioriser le travail dû et l’analyse sait revenir à certains exercices avec leur contexte.
Le menu latéral desktop et la navigation basse mobile sont des bases adaptées.
Les états « position absente » et « rien à réviser » évitent une page blanche et indiquent une issue.

## Carte de navigation du premier audit

Les chemins ci-dessous étaient les routes de `src/App.tsx` à la référence du premier audit, hors préfixe de déploiement et `#` du HashRouter.
Cet inventaire historique comptait 28 routes explicites et une route de repli `*` vers Accueil.
Les ajouts fusionnés depuis sont décrits dans [l’actualisation après synchronisation](#actualisation-après-synchronisation-sur-main) et la carte complète des 46 routes dans la [carte de navigation après lot 0](#carte-de-navigation-après-lot-0).
L’arbre représente les entrées visibles et les relations de navigation, pas seulement la structure des URL.

```text
Accueil /
├─ Jouer /jouer [onglet + CTA]
│  ├─ Contre un bot / Entraîneur / 2 joueurs [états internes]
│  └─ Partie → confirmation abandon → résultat
│     └─ /analyse?game=<id>&review=1
├─ Puzzles /puzzles [onglet + carte « Problèmes »]
│  ├─ Puzzle → verdict → suite / analyse / continuation
│  ├─ Rush /rush [aussi tuile Accueil]
│  └─ Mats /mats [aussi Apprendre]
│     └─ ?d=<id> → série chrono / mat en N / géométrie / motifs
├─ Apprendre /apprendre [onglet]
│  ├─ Séance ; Finales ; Tactiques ; Ouvertures ; Stratégie ; Mes erreurs
│  │  └─ introduction → exercice → verdict → bilan [même URL]
│  ├─ Révision /revision [aussi Accueil si due]
│  ├─ Cours de finales /apprendre/finales → /:id → ?etape=N
│  ├─ Démolir le roque /apprendre/roque → /:id → ?etape=N
│  ├─ Finales jouées /finales → /:id
│  ├─ Attaque /attaque → /:id
│  ├─ Défense /defense → /:id
│  ├─ Ouvertures /ouvertures → ?famille=...&camp=...&longueur=...
│  │  └─ Prochain coup / Suite / Variante entière [états internes]
│  ├─ Mats /mats [entrée partagée]
│  ├─ Mes attaques manquées /attaques-manquees → /:id
│  └─ Mes défenses ratées /defenses-ratees → /:id
├─ Analyse /analyse [onglet + tuile + destinations contextuelles]
│  ├─ options, import PGN/FEN, bilan et reprise des erreurs
│  ├─ Jouer la position /analyse/jouer
│  └─ Import chess.com /import [aussi Accueil]
├─ Archive /archive [onglet + tuile]
│  └─ Analyse /analyse?game=<id>
└─ Stats /stats [onglet + quatre raccourcis Accueil]
   ├─ Insights /insights [aussi Accueil]
   │  └─ entraînement ciblé /apprendre avec state
   ├─ Mes attaques manquées
   ├─ Réglages [même URL]
   └─ Sauvegarder / restaurer / réinitialiser [même URL]
```

### Budget de taps actuel

Un tap est une activation ; faire défiler ne compte pas comme tap mais reste un effort supplémentaire.
Les minima partent de l’accueil vierge, avec réglages par défaut, sans compter les coups joués.
Les lignes sans scénario cliqué dédié sont déduites des handlers et libellés du code, pas chronométrées.

| Fonction | Atteindre la page ou la fiche | Commencer réellement | Effort supplémentaire |
|---|---:|---:|---|
| Partie contre bot | 1 | 2 | Choix facultatifs de bot/cadence |
| Partie locale ou coach | 1 | 3 | Changement de mode |
| Puzzle | 1 | 1 | Chargement initial |
| Rush | 1 | 2 | Choix de durée |
| Séance automatique | 1 | 3 | Apprendre, Séance, C’est parti |
| Finales / Tactiques / Ouvertures / Stratégie | 1 | 3 | Choix du domaine, introduction |
| Mes erreurs | 1 | 3 | Désactivé sans faute analysée |
| Révision due | 1 | 1 | Carte conditionnelle Accueil |
| Révision via Apprendre | 2 | 2 | Défilement et données nécessaires |
| Cours de finales / Démolir le roque | 2 | 3 | Cours en bas du hub, puis leçon |
| Finales jouées / Attaque / Défense | 2 | 3 | Sélection d’une position |
| Attaques manquées / Défenses ratées | 2 | 3 | Bilan préalable et liste non vide |
| Catalogue d’ouvertures | 2 | 4 | Famille puis mode d’exercice |
| Mats | 2 | 4 | Fiche puis lancement |
| Analyse libre | 1 | 1 | L’import demande ses propres actions |
| Jouer une position analysée, mobile | 1 | 3 | Analyse, Options, Jouer contre le moteur |
| Archive | 1 | 2 pour ouvrir une partie | Liste non vide |
| Import chess.com | 1 | 2 pour charger la liste | Saisie du pseudo hors décompte |
| Stats / Insights | 1 | 1 | Un bilan Insights nécessite des parties |
| Réglages / sauvegardes | 1 | Variable selon contrôle | Défilement de Stats |

La refonte ne doit pas chercher le minimum de taps partout : un tap de plus dans un hub clair peut éviter la recherche dans seize cartes.
Elle doit garder les actions quotidiennes en un tap depuis Accueil et limiter l’accès à un entraînement spécialisé à quatre activations.

### Doublons, retours et impasses

Tactiques et Puzzles partagent la résolution de combinaisons, mais les séances et leurs classements ne sont pas interchangeables.
Le domaine Ouvertures et l’entraîneur d’ouvertures proposent deux expériences distinctes ; les conserver comme modes d’un même groupe, avec leur progression propre.
Les trois variantes de Finales doivent être expliquées par leur objectif plutôt que fusionnées techniquement.
Mes erreurs, attaques manquées, défenses ratées et révision peuvent présenter la même faute sous plusieurs angles ; afficher une source et des filtres communs sans supprimer de données.
Un raccourci vers un propriétaire unique est utile ; deux hubs concurrents pour la même fonction ne le sont pas.
Les états vides d’attaques et de défenses sont des impasses d’action, pas des pièges sans issue : la navigation principale reste disponible, mais l’étape à faire n’est pas cliquable.
Un lien direct vers une position absente a déjà un retour à sa liste ; ce comportement doit être conservé.
Un onglet utilise `replace`, une descente vers une fiche utilise `push`, et l’analyse retourne avec `state.restore` lorsque la page le gère.
La refonte doit tester ces contrats avant tout déplacement de routes.

## Référence chess.com

Consultation publique le 17 octobre 2026 : [Leçons](https://www.chess.com/lessons), [Puzzles](https://www.chess.com/puzzles), [Jouer](https://www.chess.com/play) et [fiche iOS App Store](https://apps.apple.com/us/app/chess-play-learn/id329218549), réponses HTTP 200.
Aucune image, capture, icône, son, feuille de style ou copie de contenu chess.com n’est ajoutée au dépôt.
Les constats web reposent sur la structure HTML publique, sans compte connecté.
La navigation web observée sépare jouer, puzzles, apprentissage et entraînement, puis les contenus communautaires et autres outils.
Le catalogue de leçons organise les contenus par sujet et niveau, avec des collections identifiables et un nombre de leçons.
Cela soutient la distinction entre activité, catalogue et progression, sans imposer à ChessLocal les fonctions sociales ou commerciales de chess.com.

Le schéma mobile Accueil/Jouer/Puzzles/Apprendre/Plus fourni dans la mission sert de référence d’intention.
Je n’ai pas ouvert une session dans l’app iOS : l’ordre exact de ses onglets, ses tests A/B et son accueil personnalisé ne sont pas vérifiés ici.
Les cartes orientées action, les leçons en parcours, la progression visible et le feedback de réussite sont des patterns d’inspiration, pas des reproductions pixel à pixel.

| Pattern retenu | Adaptation ChessLocal | À éviter |
|---|---|---|
| Accueil orienté action | Reprendre ou démarrer une séance utile | Tableau de bord de chiffres sans prochain geste |
| Hubs par activité | Un propriétaire stable pour chaque fonction | Une tuile supplémentaire sur Accueil à chaque feature |
| Leçons en parcours | Continuer une leçon et voir son avancement | Verrouillage artificiel ou faux pourcentage |
| Cartes hiérarchisées | Une action principale, deux secondaires au maximum | Toutes les cartes avec la même importance |
| Feedback immédiat | Verdict, raison courte, prochaine action | Récompense visuelle qui cache l’échiquier ou dépend uniquement du son |
| Navigation persistante | Cinq onglets hors exercice immersif | Reproduire les menus sociaux et abonnements sans besoin local |

## Principes de design

1. Une intention principale par écran, annoncée par son titre et son bouton.
2. Une fonction possède un seul hub propriétaire ; les autres entrées sont des raccourcis.
3. L’activité quotidienne est visible avant les statistiques et le catalogue.
4. Séparer comprendre, pratiquer et revoir sans séparer artificiellement les données.
5. Révéler les réglages spécialisés après le choix de l’activité.
6. Donner à tout état vide une raison simple et une prochaine action utile.
7. Préserver le contexte lors d’un détour vers l’analyse, y compris le camp et l’exercice courant.
8. Garder l’échiquier et la décision immédiate prioritaires sur les petites hauteurs.
9. Décrire le résultat sans culpabiliser : « À revoir » et une explication plutôt qu’un verdict isolé.
10. Conserver les données locales, la compatibilité des sauvegardes et les anciennes URL.

## Architecture cible

### Les cinq onglets

| Onglet | Rôle | Contenu principal |
|---|---|---|
| Accueil | Décider quoi faire maintenant | Reprise, séance du jour, révisions dues, raccourci Jouer |
| Jouer | Choisir et lancer une partie | Bot, coach, deux joueurs, dernière configuration |
| Puzzles | Résoudre et gagner en vitesse | Puzzle libre, Rush, Mats éclair |
| Apprendre | Progresser avec ou sans guide | Parcours, leçons, hub Entraînement, révision |
| Plus | Retrouver les outils et ses données | Mes parties, Analyse, Importer, Mon bilan, Statistiques, Réglages, Mes données |

La barre latérale desktop reprend les mêmes cinq familles et affiche les sous-destinations de Plus au clic.
Analyse reste accessible en un geste depuis une fin de partie ou un exercice ; elle perd seulement son onglet permanent.
Les trois onglets déplacés ne sont pas supprimés du routeur : `/analyse`, `/archive` et `/stats` conservent leurs liens existants.
Les routes proposées `/plus`, `/entrainement` et `/reglages` sont des décisions de phase 2, à intégrer seulement après vérification des branches fusionnées.
Les anciens liens de Stats vers les données continuent d’aboutir au bon contenu pendant la transition.

### Regroupement exhaustif des fonctions

Les colonnes « présentes » et « annoncées » reflètent le premier audit.
Pour leur statut après synchronisation, voir les [fonctions effectivement fusionnées](#fonctions-effectivement-fusionnées).
Le [regroupement exhaustif après lot 0](#regroupement-exhaustif-après-lot-0) place chaque route actuelle dans ces mêmes groupes.

| Groupe propriétaire | Fonctions présentes | Fonctions annoncées à accueillir | Noms proposés |
|---|---|---|---|
| Accueil | Révision due, accès Jouer et Puzzles | Séance du jour | « Ta séance du jour », « Reprendre » |
| Jouer | Bot, entraîneur, deux joueurs | Alerte de menace dans le coach | « Contre un bot », « Avec le coach », « À deux » |
| Puzzles | Puzzles, Rush, mats chrono, mat en N, géométrie, motifs | Aucun catalogue supplémentaire nécessaire | « Puzzles », « Rush », « Mats éclair » |
| Apprendre / Parcours | Cours de finales, Démolir le roque | Parcours, cours de défense | « Continuer mon parcours », « Toutes les leçons » |
| Entraînement / Tactique et calcul | Séances Tactiques, exercices de mats en raccourci | Calcul, visualisation, réfutation expliquée | « Calculer », « Visualiser », « Comprendre une réfutation » |
| Entraînement / Attaque et défense | Attaque, défense, liens vers cours associés | Convertir l’avantage | « Attaquer », « Défendre », « Convertir un avantage » |
| Entraînement / Finales | Exercices courts, finales jouées | Finales chrono | « Exercices », « Jouer une finale », « Contre la montre » |
| Entraînement / Ouvertures | Séance courte, prochain coup, suite, variante entière | Répertoire réel | « Mes ouvertures », « Mon répertoire » |
| Entraînement / Stratégie | Séances Stratégie | Structures de pions | « Plans », « Structures de pions » |
| Apprendre / Réviser mes parties | Mes erreurs, attaques manquées, défenses ratées, révision espacée | Révision élargie, moments critiques | « À réviser », « Erreurs », « Attaques », « Défenses », « Moments critiques » |
| Plus / Mes parties | Archive, import chess.com, ouverture vers analyse | Liens vers répertoire issu des parties | « Mes parties », « Importer des parties » |
| Plus / Outils et progression | Analyse, jeu depuis position, Stats, Insights | Insights vers entraîneurs | « Analyse », « Mon bilan », « Statistiques » |
| Plus / Préférences et données | Pièces, thème, sons, prémouvements, sauvegarde, restauration, réinitialisation | Réglages des nouvelles activités si nécessaires | « Réglages », « Mes données » |

Ce regroupement couvre plus de 25 capacités si l’on compte séparément les modes internes ; le nombre varie selon que l’on compte routes, activités ou modalités.
Une route ne doit donc pas être assimilée à une fonctionnalité indépendante.
La séance automatique actuelle reste accessible comme « Séance rapide » tant que la séance du jour n’est pas fusionnée et que son contrat n’est pas confirmé.
Après fusion, la séance du jour devient l’entrée recommandée ; aucun deuxième ordonnanceur ou calcul de priorité n’est créé par la refonte.
Les révisions dues ne doivent pas être comptées deux fois si la séance du jour les intègre déjà.
« Toutes les leçons » peut présenter les cours par sujet sans exiger qu’un parcours soit choisi.

### Accueil et hub Entraînement

L’accueil suit une priorité déterministe : reprise valide, sinon séance du jour, sinon séance rapide existante.
La reprise affiche le type et le point d’avancement seulement si la feature propriétaire sait réellement les restaurer.
Une révision due est une ligne secondaire avec quantité et action ; si elle est déjà la prochaine étape de la séance du jour, elle n’ajoute pas un deuxième CTA concurrent.
Jouer et Puzzles restent immédiatement accessibles dans la navigation et dans deux raccourcis discrets.
La progression vient après ces actions et mène à Mon bilan.

Le hub Entraînement propose cinq groupes de compétences : Tactique et calcul, Attaque et défense, Finales, Ouvertures, Stratégie.
Une section séparée « À partir de mes parties » conduit aux révisions personnelles.
Chaque groupe affiche son objectif et, au plus, une information de progression pertinente.
Les sous-modes apparaissent après le choix du groupe ; il n’y a pas vingt-cinq tuiles sur une seule page.
Un raccourci « Tout voir » ne doit pas devenir le seul chemin vers les outils moins fréquents.

### Contrat de navigation

Les onglets restent des racines et utilisent le comportement `replace` existant.
Une fiche conserve son URL et une sortie déterministe vers son hub, même ouverte directement.
Les raccourcis contextuels gardent un retour d’origine explicite ; un historique vide ne doit jamais envoyer hors de l’app.
L’analyse ne déclenche pas une nouvelle séance au retour et n’efface pas un résultat déjà acquis.
Une croix ferme une activité immersive ; une flèche remonte dans un catalogue ; les deux ne partagent pas un libellé ambigu.
Le passage entre onglets conserve exactement les comportements de persistance existants tant qu’un lot dédié ne les change pas avec tests.

## Maquettes basse fidélité

Les données entre crochets sont illustratives, pas de nouvelles statistiques à inventer.
À 393 × 660, le contenu secondaire défile et l’action immédiate reste accessible sans traverser l’échiquier.

### Accueil

```text
┌────────────────────────────────────┐
│ zone sûre                          │
│ ChessLocal                         │
│                                    │
│ TA SÉANCE DU JOUR                   │
│ [objectif réel de la séance]        │
│ [durée disponible] · [avancement]   │
│ [         Commencer             ]  │
│                                    │
│ À réviser aujourd’hui    [n]   >    │
│                                    │
│ [ Jouer une partie ] [ Puzzles ]    │
│                                    │
│ Cette semaine                      │
│ [activité réelle]   Voir mon bilan >│
├────────────────────────────────────┤
│ Accueil Jouer Puzzles Apprendre Plus│
│ zone sûre                          │
└────────────────────────────────────┘
```

Une reprise remplace la carte principale au lieu de s’ajouter au-dessus.
Un nouveau profil reçoit une explication brève de la séance, sans chiffres Elo présentés comme une performance acquise.

### Apprendre

```text
┌────────────────────────────────────┐
│ Apprendre                          │
│ Un prochain pas clair              │
│                                    │
│ MON PARCOURS                       │
│ [nom du parcours choisi]           │
│ [■■■■□□□□□□]  [x/y leçons]          │
│ [ Continuer : titre de la leçon ]   │
│                                    │
│ Toutes les leçons               >  │
│ Finales · Attaque · Défense         │
│                                    │
│ S’entraîner à la carte          >  │
│ Choisir une compétence              │
│                                    │
│ Réviser mes parties            >  │
│ [n à revoir ou explication utile]   │
├────────────────────────────────────┤
│ Accueil Jouer Puzzles Apprendre Plus│
└────────────────────────────────────┘
```

Sans parcours, la carte propose « Choisir un parcours », sans masquer le catalogue ni l’entraînement libre.

### Hub Entraînement

```text
┌────────────────────────────────────┐
│ < Apprendre                        │
│ Entraînement                       │
│ Quelle compétence travailler ?     │
│                                    │
│ Tactique et calcul              >  │
│ Trouver, calculer, visualiser       │
│ Attaque et défense              >  │
│ Créer une menace, tenir, convertir  │
│ Finales                         >  │
│ Comprendre et conclure              │
│ Ouvertures                      >  │
│ Connaître ses lignes et ses plans   │
│ Stratégie                       >  │
│ Choisir un plan et une structure    │
│                                    │
│ À PARTIR DE MES PARTIES             │
│ Mes erreurs et révisions        >  │
└────────────────────────────────────┘
```

### Fin de partie

```text
┌────────────────────────────────────┐
│ Partie terminée                    │
│ [résultat] · [raison]               │
│ [adversaire] · [cadence]            │
│ [variation Elo si applicable]       │
│                                    │
│ [       Analyser ma partie      ]  │
│ Comprendre les moments décisifs     │
│                                    │
│ [        Rejouer                ]  │
│ Retour à l’accueil                 │
└────────────────────────────────────┘
```

La proposition priorise l’analyse après une partie, mais ne lance pas Stockfish automatiquement et laisse Rejouer à un geste.
Si le bilan est déjà disponible, le libellé devient « Voir mon bilan ».
La persistance de la partie précède l’activation des actions qui en dépendent.

### Exercice type

```text
┌────────────────────────────────────┐
│ × Quitter  [Compétence]     [2/5]   │
│ [■■■■□□□□□□]                       │
│ Objectif : [consigne précise]       │
│                                    │
│       ÉCHIQUIER ADAPTATIF           │
│       largeur maximale disponible  │
│       hauteur bornée à 660 px      │
│                                    │
│ [Indice]                           │
│------------------------------------│
│ Après tentative :                  │
│ ✓ Réussi · [raison en une phrase]   │
│ [           Suivant             ]  │
│ Réessayer                 Analyser  │
│ zone sûre                          │
└────────────────────────────────────┘
```

Le feedback occupe une zone réservée pour éviter de déplacer l’échiquier après le coup.
Un échec propose « Réessayer » en principal tant que l’utilisateur n’a pas choisi de voir la solution ; une réussite propose « Suivant ».
L’analyse approfondie et les options avancées sont secondaires.
Le retour immersif reste visible même si le moteur calcule ou qu’une donnée manque.

## Système visuel

### Tokens et typographie

Les tokens de `src/index.css` sont conservés comme base ; aucune seconde palette ni police téléchargée n’est nécessaire.

| Token existant | Valeur | Usage cible |
|---|---|---|
| `surface` | `#262421` | Fond de page et exercice |
| `surface-2` | `#312e2b` | Cartes et navigation |
| `surface-3` | `#3c3936` | Contrôles secondaires et zones élevées |
| `accent` | `#81b64c` | Progression, sélection et action principale |
| `accent-hover` | `#8fc45c` | Survol desktop |
| `font-sans` | Segoe UI, Helvetica Neue, ui-sans-serif, system-ui, sans-serif | Police système existante |

Le texte blanc sur l’accent actuel a un contraste calculé de 2,41:1, inférieur à 3:1 pour le grand texte et à 4,5:1 pour le texte normal selon WCAG AA.
Le texte `surface` sur l’accent atteint 6,43:1 ; `neutral-400` sur `surface-2` atteint 5,35:1, contre 2,85:1 pour `neutral-500`.
Ces rapports utilisent la formule de luminance relative sRGB sur couleurs opaques ; les états avec opacité demandent leur propre mesure composée.
Le choix livré pour les accents opaques est décrit dans le [socle visuel du lot 1](#lot-1--socle-visuel-réalisé).
Ne pas utiliser le vert comme unique indice de réussite : ajouter un mot et un symbole.

| Rôle | Tailwind proposé | Règle |
|---|---|---|
| Titre de page | `text-2xl font-bold` | Un seul h1, sans emoji indispensable |
| Titre de section | `text-lg font-semibold` | Groupes d’intention |
| Titre de carte | `text-base font-semibold` | Texte repliable sans troncature |
| Corps | `text-base leading-6` | Explications lisibles |
| Métadonnée | `text-sm text-neutral-400` | Jamais le seul porteur d’une action |
| Navigation | 12 px, graisse 600 | Libellé complet, cinq éléments |
| Valeur de résultat | `text-2xl font-bold tabular-nums` | Priorité ponctuelle, pas quatre scores avant chaque activité |

Utiliser une grille d’espacement de 4 px : 8 entre éléments liés, 12 dans les petites cartes, 16 pour les marges mobiles, 24 entre sections.
Les cartes utilisent `rounded-xl`, les champs `rounded-lg`, les contrôles ronds uniquement pour les icônes isolées.
Les catalogues conservent `max-w-2xl` ; les écrans d’exercice utilisent la hauteur disponible plutôt qu’un catalogue élargi.
Sur desktop, l’échiquier et les actions forment deux colonnes ; les pages de lecture restent bornées pour éviter les lignes trop longues.
Les zones sûres utilisent les helpers CSS existants et ne sont pas codées avec les valeurs simulées de l’audit.

### Contrats des composants communs

| Composant | Responsabilité et contrat | Réutilisation / exclusion |
|---|---|---|
| `PageHeader` | Titre, description facultative, retour nommé de 44 px, action secondaire facultative | Catalogue et hubs ; retour explicite plutôt que `history.back()` aveugle |
| `ActivityCard` | Libellé, objectif bref, progression facultative, lien ou bouton selon l’action | Un élément interactif racine, aucun bouton imbriqué |
| `ProgressBar` | Valeur réelle, total, nom accessible, texte x/y | Reprendre le calcul de progression existant ; pas d’Elo converti en pourcentage |
| `EmptyState` | Titre, raison, une action possible | Distinguer absence de données et erreur réseau ; aucune réussite factice |
| `LoadingState` | Conserver la structure, annoncer le chargement avec `role=status` | Pas de pourcentage inventé ni spinner sans texte |
| `Cta` existant | Action principale / secondaire, cible, contraste, focus et état occupé | Étendre le composant existant au lieu d’un second système de boutons |
| En-tête et pied d’exercice | Quitter, progression, consigne, verdict et prochaine action | Composer autour des lecteurs actuels ; ne pas unifier les moteurs métier |

Les composants déjà livrés et leurs usages sont recensés dans le [socle visuel du lot 1](#lot-1--socle-visuel-réalisé).
`LoadingState` et l’en-tête et pied d’exercice restent des propositions pour les lots suivants ; leurs usages concrets guideront leur extraction.
Les styles de focus doivent être visibles sur fond sombre et ne pas dépendre du hover.
Les listes déroulantes et feuilles doivent restituer le focus à leur déclencheur, offrir Échap sur desktop et ne pas laisser le focus derrière un calque modal.
Les annonces de verdict ne doivent pas répéter chaque coup de l’échiquier à VoiceOver.
Le contrôle clavier de cette phase vérifie l’accès au premier lien de navigation et sa capture de focus, sans prétendre valider tout le parcours au clavier ni VoiceOver.

## Intégration des branches parallèles

Les noms suivants sont présents dans la liste locale des branches ; leur mention ne signifie pas que leur implémentation a été auditée ou validée.
Le périmètre fonctionnel vient de la mission, et aucun fichier d’un autre worktree n’est modifié.

| Branche | Destination cible | Invariant à confirmer après fusion |
|---|---|---|
| `feat/f24-parcours` | Apprendre / Parcours | Identifiants de leçons et reprise réelle |
| `feat/f23-seance-du-jour` | Carte principale Accueil | Source unique de sélection quotidienne |
| `feat/f17-convertir-avantage` | Entraînement / Attaque et défense | Résultat et retour d’activité |
| `feat/f21-calcul-visualisation` | Entraînement / Tactique et calcul | Différencier calcul et visualisation |
| `feat/c5-structures-pions` | Entraînement / Stratégie | Plan et objectif explicités |
| `feat/c2-moments-critiques` | Réviser mes parties | Source, contexte et retour à la partie |
| `feat/c8-refutation-expliquee` | Tactique et calcul, raccourci depuis analyse | Explication attachée à une position |
| `feat/f20-repertoire-reel` | Entraînement / Ouvertures | Répertoire personnel distinct du catalogue |
| `feat/f16-cours-defense` | Toutes les leçons / Défense | Réutilisation du cours et progression |
| `feat/f18-revision-elargie` | À réviser | Pas de nouvelle file concurrente |
| `feat/f19-insights-entraineurs` | Mon bilan | Retour depuis entraînement ciblé |
| `feat/f22-finales-chrono` | Entraînement / Finales | Ne pas dupliquer Mats chrono |
| `feat/c1-alerte-menace` | Jouer / Coach | Alerte contextuelle, pas une tuile de plus |
| `chore/q2-audit-ui`, `feat/ios-app`, `fix/pieces-sons-ios` | Socle partagé | Reprendre leurs corrections de layout et gestes avant de retoucher la coquille |

La réconciliation du lot 1 est consignée dans les [fonctions effectivement fusionnées](#fonctions-effectivement-fusionnées).
Le [lot 0](#lot-0--réconciliation-après-fusion-complète) constate la fusion de toutes ces branches sur `31a2e60`, avec les invariants ci-dessous.

| Branche | Route ou intégration observée par l’audit | Invariant après fusion |
|---|---|---|
| `feat/f24-parcours` | `/apprendre/parcours`, étape, placement | Ids d’étapes figés ; reprise par `path-session-v1` |
| `feat/f23-seance-du-jour` | `/seance`, tuile Accueil | Source unique de sélection (`planSeance`) ; double comptage avec la révision due à traiter au lot 4 |
| `feat/f17-convertir-avantage` | `/convertir`, `/convertir/:id` | Domaine `conversion`, retour vers son catalogue |
| `feat/f21-calcul-visualisation` | `/visualisation` | Domaine `visualisation`, une seule page pour calcul et visualisation |
| `feat/c5-structures-pions` | `/apprendre/structures`, `/structures`, `/structures/:key` | Cours `structures:` et parties `structure-play` distincts |
| `feat/c2-moments-critiques` | `/moment-critique` depuis le bilan | Aucune liste propre (écart 12) |
| `feat/c8-refutation-expliquee` | Lecteur « Pourquoi ? », sans route | Aucune écriture en base |
| `feat/f20-repertoire-reel` | `/repertoire` | Lignes `opening-drill` `next:`, distinct du catalogue |
| `feat/f16-cours-defense` | `/apprendre/defense`, `/:id` | Cours `defense:` réutilisant `LessonCourse` |
| `feat/f18-revision-elargie` | `/revision` | Pas de nouvelle file ni de table |
| `feat/f19-insights-entraineurs` | Plans d’`/insights` vers attaque, défense et listes | Liens conservés au renommage (écart 15) |
| `feat/f22-finales-chrono` | `/finales/chrono` | Domaine `endgame-clock` distinct de `mats` (écart 7) |
| `feat/c1-alerte-menace` | Question dans Jouer, résumé dans Stats | Domaine `threat-check`, aucune tuile |
| `chore/q2-audit-ui`, `feat/ios-app`, `fix/pieces-sons-ios`, coordonnées | Socle (layout, Capacitor, sons, coordonnées) | Aucun écran ni route |
| `chore/q3-perf-pwa` (en cours) | Chargement à la demande des routes d’`App.tsx` | Le contrôle de couverture lit les éléments de route, pas leur chargement |
Un déplacement de menu ne justifie pas de renommer un domaine `learnSessions`, une clé de sauvegarde ou un identifiant de contenu.

## Plan de mise en œuvre

Chaque lot porte un périmètre limité et peut être annulé sans migration de données.
L’ordre indique les dépendances ; les lots 3 à 6 sont séparables une fois le socle et les contrats validés.
Les checks listés sont les critères d’acceptation de chaque lot.
Les résultats du lot 0 sont consignés dans sa [vérification](#vérification-du-lot-0), ceux du lot 1 dans sa [vérification finale](#vérification-finale-du-lot-1), ceux du lot 2 dans sa [vérification](#vérification-du-lot-2), ceux du lot 3 dans sa [vérification](#vérification-du-lot-3), ceux du lot 6 dans sa [vérification](#vérification-du-lot-6) ; ceux des lots suivants restent à établir.

| Lot | Périmètre et propriété | Dépendance | Acceptation E2E |
|---|---|---|---|
| 0. Réconcilier après fusion (fait) | Inventaire routes, états et domaines, mise à jour de cet audit | Toutes les features retenues fusionnées | Audit trois formats, aucune route oubliée, liste des écarts explicite |
| 1. Socle visuel (fait) | `Cta`, en-tête, carte, progression, état vide sur trois usages réels | Réconciliation sur la base du lot 1 | Contraste, focus, 44 px, titres longs, état vide, chargement, captures trois formats |
| 2. Navigation et Plus (fait) | `App.tsx`, nouveau hub Plus, rattachement des routes | Lot 1 | Cinq onglets, aria-current exact, anciens deep links, replace/push, aucun retour hors app, suites shell/all_buttons/edge_navigation |
| 3. Réglages et données (fait) | Extraire la présentation de Stats vers Réglages et Mes données | Lot 2 | Mêmes valeurs persistées ; backup, upgrade, audio_settings, stats ; annulation des actions destructrices |
| 4. Accueil quotidien | `Home.tsx`, adaptateur de lecture du service de séance existant | Lot 2 + séance du jour intégrée | Profil neuf, reprise, dû/non dû, données indisponibles, pas de double comptage, CTA accessible à 660 px |
| 5. Apprendre et Entraînement | Hub guidé, cinq groupes, anciennes entrées conservées | Lot 2 + parcours intégré | Chaque fonction accessible en quatre taps au plus, état vide explicite, suites learn/all_buttons et suites des features déplacées |
| 6. Puzzles et vitesse (fait) | Hub Puzzles, Rush et Mats, retours contextuels | Lot 2 | Réussite/échec, chrono intact, retour vers le bon hub, suites puzzles/mats/continuation |
| 7. Exercice commun, première tranche | En-tête et feedback sur séance Apprendre puis révision | Lots 1 et 5 | Pas de déplacement du board au verdict, réessai non rescoring, analyse puis restauration, suites learn/revision/touch |
| 8. Exercice commun, seconde tranche | Présentation PositionGame et cours sans changer leur logique | Lot 7 | Quitter, reprise, changement d’activité, objectifs et moteur, suites attaque/defense/endgame_play/endgame_course/cours_roque/premove |
| 9. Fin de partie et Mon bilan | Résultat Jouer, accès analyse, libellé Insights | Lots 2 et 7 | Partie enregistrée avant action, replay, analyse et retour, suites all_buttons/insights/coach |
| 10. Validation sur appareil | Aucune feature nouvelle, correction des écarts observés | Lots 3 à 9 | iPhone installé, Safari, clavier, VoiceOver, zones sûres, 660/852/desktop, hors ligne et upgrade |

Chaque lot exécute `npm run check`, sa suite de parcours en production et en développement, et les suites partagées qu’il touche.
Les modifications de la coquille exigent notamment les vérifications de navigation de bord et de viewport existantes.
Une suppression ou fusion fonctionnelle n’entre pas dans ces lots : seuls le classement, les libellés et la présentation changent.

## Décisions prises et limites

Cinq onglets sont retenus pour réduire la densité sans priver les activités quotidiennes d’un accès direct.
Entraînement est un hub d’Apprendre, pas un sixième onglet.
Analyse, statistiques et parties sont regroupées dans Plus, avec des raccourcis contextuels conservés.
Les noms actuels de routes et les domaines persistés restent compatibles.
Le vocabulaire est français, avec Puzzles conservé pour sa cohérence avec l’onglet et la demande de Max.
Le texte produit cible évite les détails moteur qui n’aident pas à choisir une activité.
L’audit ne mesure ni rétention, ni vitesse de progression, ni préférence réelle de Max ; il propose des critères testables de navigation.
Les états de chaque famille sont échantillonnés ; les milliers de positions, toutes les variantes de cours et toutes les pannes de stockage ne sont pas parcourus individuellement.
Les suites métier existantes restent propriétaires de leur validation exhaustive.

## Vérifications historiques de la phase 1

Environnement de validation : Node 22.21.1, Python 3.12 et Playwright 1.56 dans `.venv.local`, ignoré par Git.
`npm ci --include=optional` sous Node 22 et l’installation de `e2e/requirements.txt` ont terminé avec code 0.
Le premier check sous Node 21 avait échoué sur le binding natif oxlint manquant ; la réinstallation sous Node 22 l’a résolu sans modifier le lockfile.

Commandes finales exécutées depuis ce worktree :

```sh
rtk proxy env PATH=/Users/maxencebrochard/.nvm/versions/node/v22.21.1/bin:$PATH npm run check
rtk proxy sh -c 'export PATH="$PWD/.venv.local/bin:/Users/maxencebrochard/.nvm/versions/node/v22.21.1/bin:$PATH"; /private/tmp/claude-501/-Users-maxencebrochard-Documents-side-projects-chess-local/3a76805b-4b21-4040-b4cb-d643ae33629d/scratchpad/e2e-lock.sh npm run test:e2e -- --suite ux_audit > e2e/shots/ux-audit/prod.log 2>&1'
rtk proxy sh -c 'export PATH="$PWD/.venv.local/bin:/Users/maxencebrochard/.nvm/versions/node/v22.21.1/bin:$PATH"; /private/tmp/claude-501/-Users-maxencebrochard-Documents-side-projects-chess-local/3a76805b-4b21-4040-b4cb-d643ae33629d/scratchpad/e2e-lock.sh npm run test:e2e:dev -- --suite ux_audit > e2e/shots/ux-audit/dev-final.log 2>&1'
rtk proxy git diff --check
```

| Vérification | Résultat final |
|---|---|
| `npm run check` | Code 0, lint et typecheck réussis |
| `npm run test:e2e -- --suite ux_audit` | Code 0, 376 checks réussis |
| `npm run test:e2e:dev -- --suite ux_audit` | Code 0, 376 checks réussis |
| `git diff --check` | Code 0, aucune erreur d’espacement |

Chaque mode couvre les 28 routes explicites, 244 états et 379 captures : 82 états en 393 × 852, 82 en 393 × 660 et 80 en 1440 × 900.
Aucun débordement horizontal n’a été mesuré dans ces inventaires.
Les 379 captures de la première passe production ont été relues sur 25 planches ; les 379 captures de la passe développement finale ont également été relues sur 25 planches.
Les six retours d’analyse de la production finale ont été revérifiés dans `prod/review-final-analyse.jpg`.
L’index `dev/review-final-index.json` associe chaque planche finale à ses captures sources.
La relecture comprend Accueil, Jouer, Apprendre, les catalogues et leurs vues défilées, les exercices, les leçons, les résultats, les modales, les états vides, le chargement, l’erreur réseau et les insets simulés.

Deux passes développement intermédiaires se sont arrêtées sur un timeout de capture puis sur un contexte détruit par une navigation ; les relances sous verrou ont terminé sans ces erreurs.
La méthode finale attend les animations finies, le décodage des images et la position complète visible dans les retours d’analyse, au lieu de forcer la fin des animations pendant la capture.
Les anciennes captures intermédiaires de l’analyse montraient des pièces résiduelles alors que le DOM attendu était déjà présent ; ce défaut de prise de vue ne se retrouve pas dans les captures finales relues.
Les journaux finaux sont `e2e/shots/ux-audit/prod.log` et `e2e/shots/ux-audit/dev-final.log`.
Lors de cette phase d’audit initiale, aucun code produit ni helper partagé n’avait changé : les suites métier non touchées n’avaient pas été relancées.
Le succès des checks établit les parcours et la couverture, pas la conformité ergonomique des écrans audités.
La suite de la refonte et sa validation sur iPhone physique restent à réaliser après fusion.

## Lot 1 : socle visuel réalisé

La navigation et les contrats de données restent identiques.
`on-accent` (`#262421`) donne un texte sombre sur les accents opaques, y compris les boutons et badges déjà présents hors `Cta` ; le vert `#81b64c` reste inchangé.
Le contraste du CTA passe de 2,41:1 à 6,43:1, et le survol est vérifié séparément.
`muted` (`#b5b2ae`) porte les descriptions des composants communs ; les autres palettes métier ne sont pas remplacées globalement.
La police système reste locale, les titres de page passent par une échelle de 24 px, les titres de section par 18 px, les titres de carte par 16 px et les descriptions de carte par 14 px.
Le focus clavier commun utilise un contour de 2 px décalé de 3 px.

| Composant | Usages livrés | Invariants |
|---|---|---|
| `Cta` | Tous ses usages existants | Contraste, cible minimale 44 px, type bouton par défaut |
| `PageHeader` | Apprendre, sommaires Bases/Finales/Roque, listes personnelles attaque/défense | Titre non tronqué, retour nommé et destination possédée par la page |
| `ActivityCard` | Quatre tuiles Accueil, quatre domaines Apprendre, trois cours Apprendre, toutes les leçons des sommaires | Lien ou bouton, une seule racine interactive, textes repliables |
| `ProgressBar` | Trois sommaires, trois cartes de cours et carte du parcours | Valeur métier inchangée, nom et valeurs ARIA, texte x/y |
| `EmptyState` | Archive, attaques manquées, défenses ratées | Explication réelle et une action vers Jouer ou Analyse |

Les trois sommaires utilisent déjà `CourseIndex` : leur présentation est consolidée à cet endroit, sans toucher le lecteur de leçon.
Le chargement de leur progression conserve l’en-tête et annonce un statut ; aucun zéro n’est affiché avant lecture de la base.
Les listes personnelles et Archive annoncent aussi leur chargement distinctement de leur état vide.
Le retour de cours conserve son `replace` et la restauration de séance ; les retours des listes personnelles conservent leur `push`.
Le test de cours utilise maintenant le nom accessible explicite « Retour à Apprendre », au lieu de dépendre du glyphe de flèche.
Aucun réglage, domaine, moteur, asset ni police distante n’est ajouté.

La suite `ux_foundation` mesure les couleurs rendues (y compris les fonds transparents composés), vérifie 44 × 44 px, les titres longs, les retours, les actions des états vides, les progressions et le chargement retenu de la base aux trois formats.
Elle vérifie aussi que remettre le texte blanc sur le CTA redonne un contraste de 2,41:1 et serait rejeté.
Les minima de cibles et de contraste concernent les composants livrés dans ce lot ; ils ne constituent pas une déclaration de conformité globale de toutes les interfaces historiques.
Les retouches des lecteurs immersifs et les autres cibles historiques restent dans leurs lots propriétaires.

La régression de 8 px sur Accueil à 660 px avec une révision due a été reproduite par `revision`, puis corrigée en réduisant le padding vertical des quatre tuiles secondaires à 8 px.
Le texte agrandi est conservé.
La relecture du parcours a aussi repéré son numéro blanc sur fond de niveau : ce style dynamique utilise désormais le même texte sombre, avec une mesure E2E dédiée.
Les preuves finales et commandes sont consignées ci-dessous.

### Vérification finale du lot 1

Environnement : Node 22.21.1, Python et Playwright du `.venv.local` existant.
`npm ci --include=optional` : code 0 ; `npm run check` : code 0 (oxlint et tsc), journal `e2e/shots/ux-lot1/check-final.log`.
`git diff --check` : code 0.
Les 31 suites de production ont chacune terminé avec le code 0 lors de leur dernière validation, soit 5 092 checks cumulés en comptant chaque suite une seule fois.
`ux_foundation` termine avec 503 checks en production et 503 en développement ; `parcours` termine avec 391 checks dans chacun des deux modes.

| Suite production | Checks réussis | Dernier journal |
|---|---:|---|
| `all_buttons` | 98 | `prod-final.log` |
| `analysis_robust` | 88 | `prod-shared.log` |
| `archive_import` | 145 | `prod-core.log` |
| `attaque` | 114 | `prod-shared.log` |
| `audio_settings` | 9 | `prod-shared.log` |
| `backup` | 225 | `prod-shared.log` |
| `continuation` | 74 | `prod-shared.log` |
| `cours_roque` | 112 | `prod-core.log` |
| `defense` | 148 | `prod-core.log` |
| `diagnostic_attaque` | 143 | `prod-core.log` |
| `edge_navigation` | 193 | `prod-core.log` |
| `endgame_course` | 109 | `prod-shared.log` |
| `endgame_play` | 86 | `prod-shared.log` |
| `insights` | 354 | `prod-shared.log` |
| `learn` | 73 | `prod-core.log` |
| `mats` | 91 | `prod-shared.log` |
| `moments` | 114 | `prod-shared.log` |
| `openings` | 75 | `prod-shared.log` |
| `parcours` | 391 | `prod-parcours-final.log` |
| `play_lifecycle` | 84 | `prod-shared.log` |
| `puzzles` | 79 | `prod-shared.log` |
| `refutation` | 157 | `prod-shared.log` |
| `repertoire` | 193 | `prod-shared.log` |
| `revision` | 148 | `prod-final.log` |
| `shell` | 98 | `prod-final.log` |
| `touch` | 63 | `prod-shared.log` |
| `ux_audit` | 424 | `prod-final.log` |
| `ux_foundation` | 503 | `prod-foundation-v2.log` |
| `viewport` | 565 | `prod-parcours-final.log` |
| `visualisation` | 134 | `prod-shared.log` |
| `visualisation_layout` | 2 | `prod-shared.log` |


Les commandes E2E sont lancées avec `rtk proxy sh -c`, le PATH préfixé par `$PWD/.venv.local/bin:/Users/maxencebrochard/.nvm/versions/node/v22.21.1/bin`, puis le verrou obligatoire :

```text
/private/tmp/claude-501/-Users-maxencebrochard-Documents-side-projects-chess-local/3a76805b-4b21-4040-b4cb-d643ae33629d/scratchpad/e2e-lock.sh
```

Chaque commande du tableau écrit son stdout et stderr dans le journal indiqué (`> e2e/shots/ux-lot1/<journal> 2>&1`).
La passe finale de développement du seul socle utilise aussi `UX_PHASE=after-dev` pour séparer ses captures.

| Journal dans `e2e/shots/ux-lot1/` | Commande exécutée sous verrou | Code final du lancement |
|---|---|---:|
| `audit-reconciled.log` | `npm run test:e2e -- --suite ux_audit --jobs 1` | 0 |
| `prod-core.log` | `npm run test:e2e -- --suite ux_foundation --suite ux_audit --suite all_buttons --suite learn --suite shell --suite viewport --suite edge_navigation --suite endgame_course --suite cours_roque --suite parcours --suite diagnostic_attaque --suite defense --suite archive_import --jobs 2` | 1 |
| `prod-shared.log` | `npm run test:e2e -- --suite endgame_course --suite analysis_robust --suite backup --suite audio_settings --suite mats --suite visualisation --suite visualisation_layout --suite insights --suite repertoire --suite play_lifecycle --suite puzzles --suite continuation --suite openings --suite touch --suite revision --suite attaque --suite endgame_play --suite moments --suite refutation --jobs 2` | 1 |
| `prod-final.log` | `npm run test:e2e -- --suite revision --suite ux_foundation --suite ux_audit --suite all_buttons --suite shell --suite viewport --jobs 2` | 0 |
| `prod-parcours-final.log` | `npm run test:e2e -- --suite parcours --suite viewport --jobs 2` | 0 |
| `prod-foundation-v2.log` | `npm run test:e2e -- --suite ux_foundation --jobs 1` | 0 |
| `dev-final-v2.log` | `npm run test:e2e:dev -- --suite ux_foundation --suite parcours --jobs 2` | 0 |
| `dev-foundation-v3.log` | `npm run test:e2e:dev -- --suite ux_foundation --jobs 1` | 0 |


Les deux lancements agrégés à code 1 sont conservés comme preuves des défauts trouvés : `prod-core.log` contient l’ancien sélecteur du retour de cours et une mesure pendant transition CSS ; `prod-shared.log` contient le dépassement de 8 px d’Accueil.
Les suites concernées sont relancées avec succès après correction, avec des assertions conservées.
L’audit avant réconciliation était à code 1 (1 échec sur 376 checks, sept routes nouvelles absentes de la matrice).
La première preuve E2E du socle avant produit était à code 1 (56 échecs sur 131 checks), dont le blanc sur vert à 2,41:1.
Une passe intermédiaire de mesure des couleurs a aussi révélé une composition incorrecte des fonds entièrement transparents dans le test ; cette mesure est corrigée avant les résultats finaux.
Aucune assertion n’est remplacée par une constante de succès.

Après lot 1, l’audit couvre 35 routes, 268 états et 433 captures, sans débordement horizontal.
Le profil Accueil avec révision due à 393 × 660 mesure 612 px de contenu pour 612 px disponibles.
Les mesures du socle donnent 6,43:1 pour le CTA et le numéro courant du parcours ; les descriptions sur carte mesurent 6,39:1.
Les cibles des composants testés atteignent au moins 44 × 44 px.

Captures relues : les 15 planches `compare-<format>-1.jpg` à `compare-<format>-5.jpg` (60 vues avant/après), les trois `compare-home-final-<format>.jpg` après correction d’Accueil, les trois `details-<format>.jpg` (titre long, chargement, état vide défilé ou focus) et `parcours-final.jpg`.
Elles sont toutes sous `e2e/shots/ux-lot1/` ; `compare-index.json` relie les premières planches aux sources.
Les vues relues couvrent Accueil, Apprendre, les trois cours, les trois états vides, le verdict de séance, la fin de partie, les deux profils d’Accueil et le parcours aux formats 393 × 852, 393 × 660 et 1440 × 900.
Le défilement des états vides à 660 px conserve leur action entière ; les catalogues restent défilants.
Les captures de fin de partie montrent parfois un coup différent du bot, sans comparaison pixel à pixel de la position aléatoire.

Aucun blocage restant dans le lot 1.
La validation iPhone physique, Safari et VoiceOver reste hors de l’émulation Chromium ; elle appartient au lot 10.
Les autres défauts historiques de navigation, de classement et des lecteurs immersifs restent dans les lots 2 et suivants.

## Lot 2 : navigation réalisée

La barre passe de sept à cinq onglets, dans l’ordre du [tableau cible](#les-cinq-onglets) : Accueil, Jouer, Puzzles, Apprendre et Plus.
Analyse, Archive et Stats perdent leur onglet permanent ; leurs routes, comme toutes les autres, sont inchangées et leurs anciens liens rendent toujours la même page.
Le `match` des onglets applique le [placement cible](#placement-cible-de-chaque-route) et corrige l’écart 13 du lot 0.

| Famille de routes | Onglet avant | Onglet après |
|---|---|---|
| `/`, `/seance` | Accueil | Accueil |
| `/jouer` | Jouer | Jouer |
| `/puzzles`, `/rush` | Puzzles | Puzzles |
| `/mats` | Apprendre | Puzzles |
| `/apprendre` et ses sous-chemins, entraîneurs, listes personnelles, `/revision` | Apprendre | Apprendre |
| `/moment-critique` | Analyse | Apprendre (Réviser mes parties) |
| `/analyse`, `/analyse/jouer`, `/import` | Analyse | Plus |
| `/archive` | Archive | Plus |
| `/stats`, `/insights` | Stats | Plus |
| `/plus` | Aucun (nouvelle route) | Plus |

Un seul élément de la nav porte `aria-current` : `page` sur la racine de l’onglet, `true` sur une route rattachée.
Les cinq onglets restent en `replace` ; les liens du hub sont des descentes en push, si bien que le retour arrière ramène au hub.
Les tuiles Stats, Analyse et Archive de l’Accueil gardent leur `replace` d’anciennes racines : l’Accueil appartient au lot 4.
Aucune page n’ajoute de retour fondé sur `history.back()` : l’onglet Plus reste la sortie déterministe des destinations déplacées, même ouvertes directement.
Les persistances (partie en cours, séances, état des exercices) ne dépendent pas de l’onglet et sont inchangées.

### Hub Plus

`/plus` (`src/pages/More.tsx`) est une racine d’onglet sans retour, construite avec `PageHeader` et `ActivityCard`.
Il présente trois groupes : Parties (Mes parties, Importer des parties), Outils et progression (Analyse, Mon bilan, Statistiques), Réglages et données (Réglages, Mes données).
Le groupe s’appelle « Parties » plutôt que « Mes parties » pour ne pas répéter le titre de sa première carte.
Les destinations sont décrites une seule fois dans `PLUS_GROUPS` de `src/lib/navigation.ts`, partagé avec la nav latérale.
Réglages et Mes données ouvrent `/stats` avec `state.section` ; Stats retient la section, efface aussitôt le state, attend la lecture de la base puis amène le titre en haut de `<main>`.
Ce mécanisme généralise l’ancien `state.backup` de la carte de migration native, toujours accepté ; le lot 3 remplacera ces deux entrées par les pages extraites (fait, voir le [lot 3](#lot-3--réglages-et-données-réalisé)).
Le texte d’aide de la migration native devient « dans la PWA, Plus, Mes données, Exporter tout ».
Les pages gardent leurs titres actuels (« Archive », « Insights ») : leur renommage en « Mes parties » et « Mon bilan » appartient aux lots qui les retouchent.

### Nav latérale

La sous-liste de Plus se déplie dès que l’onglet Plus est allumé, c’est-à-dire au clic sur Plus ou à l’arrivée sur une route rattachée.
Elle est dérivée de la route, sans état ni gestionnaire d’ouverture : aucun cas de liste ouverte sur une autre famille ou fermée sur la sienne.
Ses sept liens sont en `replace`, comme des onglets, et un clic sur la destination courante réarme la frontière d’erreur comme un re-tap d’onglet.
Ils ne portent pas `aria-current`, réservé à l’onglet ; la destination courante est signalée visuellement (`data-selected`).
Les libellés tiennent dans les 176 px de la barre ; « Importer des parties » y devient « Importer ».
Dépliée, la barre compte douze cibles de 44 px, environ 620 px : elle défile seule (`overflow-y-auto`) dans une fenêtre d’ordinateur plus basse.

### Pictogrammes

Les emojis et glyphes de la barre (♞ ♟ 🧩 🎓 🔍 📚 📊) sont remplacés par des SVG inline dessinés pour l’app, sans dépendance ni jeu d’icônes repris (`src/components/NavIcon.tsx`).
Onglets : maison, pion, pièce de puzzle, toque, cercle à points de suspension ; hub : échiquiers empilés, flèche entrante, loupe, courbe encadrée, histogramme, curseurs, cylindre de données.
Grille commune de 24 px, trait de 1,75 px aux bouts et angles arrondis, `currentColor` et `aria-hidden` ; le libellé texte reste le nom accessible.
Actif : couleur accent (accent-light sur la nav latérale) et aplat à 22 % des formes `data-fill`, pour que l’état ne repose pas que sur la couleur.
La nav basse garde exactement sa hauteur de 48 px (mesurée avant et après) avec des pictogrammes de 24 px et des libellés de 12 px en graisse 600, conformes au [système visuel](#tokens-et-typographie) ; la nav latérale utilise 20 px.

### Vérification du lot 2

`npm run check` : code 0.
La suite `shell` vérifie aux trois formats (393 × 660 standalone avec zones sûres émulées, 393 × 852, 1440 × 900) :

- cinq onglets exactement, dans l’ordre, cibles d’au moins 44 × 44 px, libellés sur une ligne, aucun débordement horizontal ;
- pictogrammes SVG de 24 px (20 px sur desktop), grille et trait communs, `aria-hidden`, trait de la couleur du libellé ;
- couleur active mesurée (accent `#81b64c`, accent-light `#b5dc8c` sur desktop), couleur inactive commune et distincte, contraste d’au moins 4,5:1 (5,22:1 à 9,1:1 mesurés), aplat actif à 22 % et contour seul au repos ;
- sur mobile, cinq colonnes égales, pictogramme centré au-dessus du libellé, nav collée en bas et, avec les zones sûres, 34 px de marge basse sous les onglets ;
- 21 familles de routes ouvertes par leur ancien lien : page rendue, URL conservée et un seul `aria-current` sur l’onglet attendu avec la bonne valeur ;
- sur desktop, sous-liste dépliée sur les seules routes de Plus, destination sélectionnée attendue, aucun `aria-current` et cibles de 44 px ;
- hub : titre, trois groupes, sept cartes dans l’ordre avec description et pictogramme, chaque lien en push avec Plus allumé et retour au hub, Réglages et Mes données amenés en haut de l’écran avec le state effacé ;
- sous-liste desktop en `replace`, y compris Réglages et Mes données redemandés depuis `/stats`.

Les scénarios de frontière d’erreur passent désormais par le hub pour atteindre Analyse ; le re-tap de l’onglet courant est vérifié sur l’Accueil, et celui d’une sous-destination courante sur la nav latérale.
Les suites qui tapaient les anciens onglets passent par Plus et la carte du hub (`all_buttons`, `archive_import`, `insights_archives`) ou par l’onglet Plus pour quitter une page (`analysis_robust`, `play_lifecycle`), sans retirer d’assertion.
`insights`, `endgame_play` et `mats` attendent l’onglet de leur nouvelle famille ; `/plus` entre dans la matrice d’`ux_audit`, la tournée d’`ui_audit` et les pages de `viewport`.

| Suite production | Checks réussis |
|---|---:|
| `shell` | 455 |
| `all_buttons` | 101 |
| `edge_navigation` | 193 |
| `viewport` | 649 |
| `ui_audit` | 1 168 |
| `ux_audit` | 792 |
| `ux_foundation` | 524 |
| `ios_app` | 98 |
| `analysis_robust` | 88 |
| `archive_import` | 145 |
| `endgame_play` | 86 |
| `insights` | 354 |
| `insights_archives` | 23 |
| `mats` | 91 |
| `play_lifecycle` | 84 |

Les quinze suites ont été lancées ensemble (`npm run test:e2e -- --suite … --jobs 2`) : code 0, 4 851 checks, sans relance.
`npm run test:e2e:dev -- --suite shell --jobs 1` : code 0, 455 checks.
`ux_audit` lit 47 routes déclarées, toutes couvertes, et produit 307 états et 520 captures.

Preuves par mutation, chacune annulée ensuite :

- `/import` retiré de `PLUS_MATCH` : `shell` à code 1, sept échecs (« /import allume Plus » aux trois formats, sous-liste et sélection desktop, Plus allumé après la carte Importer du hub aux deux formats qui le testent) ;
- onglet actif de la nav basse rendu sans sa variante pleine : `shell` à code 1, deux échecs (« aplat actif » à 393 × 660 et 393 × 852).

Captures relues : `e2e/shots/shell_nav_*.png`, `shell_hub_*.png`, `shell_sidebar_*.png` et les captures `plus` d’`ux_audit` aux trois formats.
La validation sur iPhone physique (rendu des SVG, zone sûre réelle) reste au lot 10.

## Lot 3 : réglages et données réalisé

Stats ne garde que les statistiques : classements, parties contre les bots, puzzles, attaques manquées et menaces adverses.
Ses deux sections de présentation deviennent deux pages de l’onglet Plus, sans changement de `backup.ts`, du store des réglages ni d’aucune clé de stockage.

| Page | Route | Fichier | Contenu |
|---|---|---|---|
| Réglages | `/reglages` | `src/pages/Settings.tsx` | Échiquier (thème, pièces, coups légaux, attaquants), Jeu (prémouvements, alerte « Qu’est-ce qu’il menace ? »), Sons (interrupteur, volume), Analyse (profondeur du bilan) |
| Mes données | `/donnees` | `src/pages/MyData.tsx` | Contenu de l’appareil, stockage protégé, dernier export, Exporter tout, Restaurer, Réinitialiser |

Les routes sont des racines courtes, comme `/plus`, plutôt que des sous-chemins `/plus/...` : le plan nommait déjà `/reglages`, les URL restent françaises et le `match` de Plus reste une liste de racines.
Les deux routes entrent dans `PLUS_MATCH` ; le hub et la sous-liste desktop y mènent directement, sans `state.section`.
Chaque page a un retour « Plus » dans `PageHeader` (push vers `/plus`, comme les sous-pages d’Apprendre vers `/apprendre`).

### Anciens liens

Stats renvoie en `replace` un ancien `state.section` (`reglages`, `donnees`) ou `state.backup` vers la page extraite, avant toute lecture de la base : une entrée d’historique restaurée aboutit au bon contenu.
La carte de migration de l’app native ouvre directement `/donnees`, toujours en `replace` comme l’ancienne racine Stats ; la page tient le titre et la marche à suivre dans le premier écran, sans défilement.
Le texte d’aide « dans la PWA, Plus, Mes données, Exporter tout » décrit désormais le vrai chemin.
`/stats` sans state reste la page Statistiques.

### Valeurs et actions

Les contrôles reprennent ceux de Stats à l’identique (libellés, rôles, `data-testid`), dont « Réinitialiser l’app (tout effacer sur cet appareil)… », et chacun écrit la même clé qu’avant : `chess-local-settings` au format persist, ou `chess-local-threat-check`.
Deux libellés changent volontairement : le titre « Tes données » devient « Mes données » (nom de la nav et du hub Plus, même `data-testid=data-heading`), et « Thème de l’échiquier » devient « Thème », déjà rangé sous la section Échiquier.
L’alerte de menace, jusque-là réglable seulement dans la configuration de Jouer, a ses deux interrupteurs (contre un bot, avec le coach) dans Réglages ; les deux écrans lisent et écrivent la même préférence.
Mes données ajoute le bloc en lecture seule « Sur cet appareil » (`data-testid=stored-counts`, `currentCounts`), relu après une restauration : il remplace le compteur que Stats affichait sur le même écran après une restauration, et n’écrit rien.
Restaurer et Réinitialiser gardent leurs feuilles de confirmation (une pour la restauration, deux pour la réinitialisation, Annuler focalisé, Échap et fond pour annuler, export proposé d’abord) ; aucune modale native n’est introduite.
La réinitialisation passe d’un lien de 12 px à un bouton rouge détouré dans sa propre section, sous la sauvegarde.

### Vérification du lot 3

`npm run check` : code 0.
`backup` ajoute `part_pages` : visiter Stats, Réglages, Plus et Mes données n’écrit ni dans `localStorage` ni dans la base ; Stats ne porte plus aucun réglage ni action sur les données ; Réglages affiche les valeurs semées ; l’alerte de menace n’écrit que `chess-local-threat-check`, au format de Jouer, lu dans les deux sens ; le thème ne change que `themeId` dans `chess-local-settings`.
`shell` vérifie les deux routes (Plus allumé, sous-liste et sélection desktop), les cartes du hub en push avec leur retour « Plus », la sous-liste en `replace` et les trois anciens states (`section` et `backup`) renvoyés en `replace` depuis `/stats`.
`ios_app` vérifie que la carte de migration ouvre `#/donnees` en `replace`, titre et marche à suivre dans le premier écran.
Les suites qui ouvraient Stats pour un réglage ou une action sur les données vont sur la page extraite ; celles qui l’ouvraient seulement pour créer le schéma de la base restent sur `/stats`.
`test_upgrade.py` garde `/stats` pour les anciens builds et passe par `/donnees` pour exporter et restaurer avec le nouveau build ; il n’a pas été lancé dans ce lot.

| Suite production | Checks réussis |
|---|---:|
| `shell` | 499 |
| `backup` | 272 |
| `audio_settings` | 20 |
| `pieces_sons` | 93 |
| `ios_app` | 99 |
| `diagnostic_attaque` | 143 |
| `ui_audit` | 1 231 |
| `ux_audit` | 816 |
| `viewport` | 746 |
| `all_buttons` | 108 |
| `premove` | 78 |
| `learn` | 73 |
| `bug_hunt` | 48 |
| `parcours` | 393 |
| `seance` | 193 |
| `visualisation` | 131 |
| `insights` | 354 |
| `menace` | 99 |
| `revision` | 317 |
| `perf` | 75 |

Toutes les suites ont été lancées avec `--jobs 1`.
`npm run test:e2e:dev -- --suite shell --suite backup --jobs 1` : code 0, 499 et 272 checks.
`perf` ouvre aussi les deux routes ; ses scénarios de chunk périmée cliquaient l’onglet Analyse disparu au lot 2 et passent désormais par la tuile Analyse de l’accueil, qui reste dans le bundle initial.
Son budget d’accueil à froid a échoué une fois (1 594 ms pour 1 462, charge machine à 18) puis est passé à la relance isolée.
`ui_audit` a d’abord relevé la cible « Contre un bot » : collée à la ligne suivante, le pseudo-élément de celle-ci mordait d’un sous-pixel sur sa visée ; les deux interrupteurs sont désormais espacés.

Preuves par mutation, chacune annulée ensuite :

- `/donnees` retiré de `PLUS_MATCH` et redirection des anciens states coupée dans Stats : `shell` à code 1, quinze échecs (Plus non allumé sur `/donnees` aux trois formats, sous-liste et sélection desktop, trois anciens states restés sur `#/stats` sans `replace`) ;
- interrupteurs de l’alerte écrivant `chess-local-threat` au lieu de `chess-local-threat-check` : `backup` à code 1, six échecs de `part_pages` (clé modifiée, format, lecture croisée avec Jouer, aller-retour).

Captures relues : `reglages` et `donnees` d’`ux_audit` aux trois formats, `f10_reglages_*`, `backup_donnees_after_export.png` et `ios_migration_donnees_393x852.png`.

## Lot 6 : puzzles et vitesse réalisé

L’onglet Puzzles réunit trois modes : le puzzle classé (`/puzzles`), Puzzle Rush (`/rush`) et Mats éclair (`/mats`), avec leurs sous-modes inchangés (3 minutes, 5 minutes, Survie ; contre la montre, mat en N, géométrie, motifs).
Aucune logique de score, de chrono, d’Elo ni de persistance n’est modifiée : seuls le classement, les libellés et la présentation changent.

### Décision : `/puzzles` reste le puzzle classé

Deux options étaient ouvertes : un hub sur `/puzzles` avec le puzzle classé un geste plus loin, ou `/puzzles` conservé avec un accès rapide aux autres modes.
La seconde est retenue.
Le puzzle classé est l’activité quotidienne de l’onglet : il reste à zéro geste de l’onglet, mieux que le budget d’un geste.
Les anciennes URL rendent exactement la même page, y compris le retour d’analyse (`returnTo: '/puzzles'`), la tuile Problèmes de l’Accueil (lot 4) et les plans de Mon bilan qui visent `/puzzles`.
Aucune route n’est ajoutée : la matrice d’`ux_audit` reste complète sans changement.

Le « hub » est donc la famille des trois racines sœurs, reliées par un sélecteur commun (`src/components/PuzzleModes.tsx`, liste `PUZZLE_MODES` de `src/lib/navigation.ts`) : Classés, Rush, Mats éclair.
Il est en tête du puzzle classé (au-dessus de l’échiquier, aligné sur lui), du menu du Rush et de l’accueil de Mats éclair, à la même hauteur dans les trois (16 px sous la zone sûre, 24 px sur desktop) : le sélecteur ne saute pas d’un mode à l’autre.
Ses liens sont en `replace`, comme les onglets : ce sont des racines, le retour arrière ne fait pas la navette entre modes et le swipe-back iOS n’a pas de cible parasite.
Le mode courant porte `aria-current="page"`, un fond teinté d’accent et le texte `accent-light`, pas seulement une couleur.
C’est un `div role="navigation"` nommé « Modes de puzzles » plutôt qu’un `<nav>` : même rôle pour les lecteurs d’écran, et `nav a[aria-current]` reste l’unique onglet allumé de la navigation principale.
Les anciens boutons « Puzzle Rush » et « Mats éclair » sous l’échiquier disparaissent : le sélecteur les remplace.

### Contrat de retour

| Écran | Sortie | Forme |
|---|---|---|
| Puzzle classé, menu du Rush, accueil de Mats éclair | Sélecteur des modes, onglets | Racines, `replace` |
| Run de Rush | Croix « Arrêter » (score enregistré), puis Rejouer ou Menu | Immersif, sans sélecteur |
| Fiche d’un schéma de Mats éclair (`?d=`) | Flèche « Retour à Mats éclair », retour arrière | Catalogue, sans sélecteur |
| Série de Mats éclair | Croix et Menu existants | Immersif, sans sélecteur |
| Mats éclair ouvert par le raccourci d’Apprendre | « Retour à Apprendre » en plus du sélecteur | `state.from: 'apprendre'`, conservé par les fiches |
| Erreur ou chargement de `/puzzles` | Sélecteur conservé à sa place | Mats éclair contre la montre reste joignable sans `puzzles.json` |

L’accueil de Mats éclair perd son retour fixe vers Apprendre, devenu faux depuis le lot 2 (Mats appartient à Puzzles) ; le raccourci d’Apprendre est conservé et seul lui ajoute ce retour.
Le state d’entrée suit la fiche (`setParams` avec le même state) : la flèche de la fiche ramène à un accueil qui a toujours son retour vers Apprendre.
Un lien direct vers `/mats` ou une fiche n’a pas ce retour : le sélecteur et l’onglet Puzzles en sont la sortie déterministe.

### Présentation

Le menu du Rush passe sur `PageHeader` et `ActivityCard` : titre sans emoji, une description par mode et le record sous le titre, icônes à largeur fixe pour aligner les textes.
L’accueil de Mats éclair garde ses cartes métier ; son titre perd l’emoji et la fiche reprend le retour nommé commun (`BackButton`, extrait de `PageHeader`).
Sur le puzzle classé, Indice et Réessayer deviennent des `Cta` secondaires : même hauteur, même arrondi et même ombre que Passer et Suivant, au lieu de boutons plus bas et carrés.
Sur desktop, le puzzle classé est aligné en haut comme ses deux voisins, panneau aligné sur le haut de l’échiquier.
À 393 × 660 avec zones sûres, l’échiquier occupe 147 à 528 px pour une zone visible de 71 à 578 px : il reste entier sous le sélecteur, le panneau défile dessous comme avant.
Un `h1` masqué « Puzzles classés » donne un titre à la page, qui n’en avait pas.

### Vérification du lot 6

`npm run check` : code 0.
La suite `puzzles` gagne un scénario « modes » aux trois formats (393 × 660 standalone avec zones sûres émulées, 393 × 852, 1440 × 900) :

- sélecteur présent sur `/puzzles`, `/rush` et `/mats`, rôle navigation nommé hors des `<nav>` d’onglets, trois modes dans l’ordre, un seul `aria-current="page"` sur le mode attendu ;
- cibles d’au moins 44 px, libellés sur une ligne, onglet Puzzles seul allumé, aucun débordement horizontal ;
- sur le puzzle classé : sélecteur au-dessus de l’échiquier, aligné sur ses bords, sous la zone sûre, et échiquier entier visible sans défiler ;
- sélecteur à la même hauteur sur les trois modes ;
- Classés → Rush → Mats éclair → Classés : bonne URL, `history.length` inchangé, et même puzzle classé repris, sans nouveau tirage ;
- anciens boutons Rush et Mats retirés, sélecteur conservé sur l’état d’erreur de `/puzzles` ;
- run de Rush et écran de fin sans sélecteur, la croix ferme le run, Menu ramène au sélecteur.

La suite `mats` vérifie le raccourci d’Apprendre (« Retour à Apprendre » présent, conservé après une fiche et sa flèche « Retour à Mats éclair », retour vers `/apprendre`), l’absence de ce retour depuis l’onglet, et l’entrée par le sélecteur.
Les scénarios existants de réussite, d’échec, de « Passer », de chrono réel du Rush, d’enregistrement des scores et des séries de Mats éclair passent sans modification d’assertion.

`test_perf.py` cliquait encore le lien « Analyse » de l’ancien onglet, retiré au lot 2 : la suite s’arrêtait sur une exception au déploiement d’un nouveau build.
Elle navigue maintenant vers `#/analyse` par un changement de hash (même navigation interne qu’un lien, sans rechargement du document), et ses 73 checks passent.

| Suite production | Checks réussis |
|---|---:|
| `puzzles` | 218 |
| `mats` | 101 |
| `shell` | 455 |
| `all_buttons` | 102 |
| `ui_audit` | 1 168 |
| `ux_audit` | 792 |
| `viewport` | 649 |
| `edge_navigation` | 193 |
| `perf` | 73 |
| `premove` | 78 |
| `continuation` | 74 |

Ces onze suites ont été lancées ensemble après la dernière modification (`npm run test:e2e -- --suite … --jobs 1`) : code 0.
Lancées plus tôt sur le même lot, `ux_foundation` (524), `learn` (73), `touch` (63), `ios_app` (98) et `insights` (354) passent aussi.
`npm run test:e2e:dev -- --suite puzzles --suite mats --jobs 1` : code 0 (StrictMode).
La suite `upgrade` n’est pas lancée sur ce lot : aucune donnée, clé ni version de schéma n’y change.

Preuves par mutation, chacune annulée ensuite :

- liens du sélecteur en push (`replace={false}`) : `puzzles` à code 1, neuf échecs (« replace, history.length stable » pour Rush, Mats et Classés aux trois formats) ;
- raccourci d’Apprendre sans `state.from` : `mats` à code 1, deux échecs (« retour vers Apprendre » à l’arrivée et après la fiche).

Captures relues : `e2e/shots/puzzles_modes_*.png` (trois modes aux trois formats) et les états `puzzles`, `puzzle-fixture`, `puzzle-reussi`, `puzzles-erreur`, `rush`, `rush-resultat`, `mats`, `mat-fiche` d’`ux_audit`.
Points ouverts : la tuile « Problèmes » de l’Accueil et le libellé « Problèmes » des plans de Mon bilan restent à renommer « Puzzles » dans leurs lots (4 et 9) ; le bouton « Menu » de fin de Rush et de Mats éclair garde son libellé, que `test_upgrade.py` vise aussi sur les anciens builds.
