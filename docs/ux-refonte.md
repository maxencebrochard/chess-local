# ChessLocal : audit UX et architecture cible

## Décision validée le 17 octobre 2026

Faire de ChessLocal un outil qui répond à « Que faire maintenant pour progresser ? », avec cinq destinations stables : Accueil, Jouer, Puzzles, Apprendre et Plus.
L’accueil donne une action prioritaire ; Apprendre distingue les parcours guidés des entraînements à la carte ; Plus rassemble les parties, les outils et les réglages.
Max a validé cette architecture (« ok go pour tout »).
La phase 1 ci-dessous est conservée comme diagnostic historique ; le lot 1 est mis en œuvre séparément, sans modification de la navigation.
Les lots 2 et suivants restent différés.

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

Aucune route de cours de défense distincte n’est présente dans cette base : ne pas confondre l’entraîneur de défense fusionné et une future route de cours.
Le tableau des branches de la phase 1 reste historique ; seules les intégrations ci-dessus sont constatées sur cette base.

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

## Carte réelle de navigation

Les chemins ci-dessous sont les routes de `src/App.tsx`, hors préfixe de déploiement et `#` du HashRouter.
Il existe 28 routes explicites et une route de repli `*` vers Accueil.
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
Les 28 routes actuelles ne doivent donc pas être présentées comme 28 fonctionnalités indépendantes.
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
Privilégier un texte sombre sur le vert existant, ou assombrir le fond de bouton avec un token sémantique testé, sans changer silencieusement la couleur d’accent partout.
Ne pas utiliser le vert comme unique indice de réussite : ajouter un mot et un symbole.

| Rôle | Tailwind proposé | Règle |
|---|---|---|
| Titre de page | `text-2xl font-bold` | Un seul h1, sans emoji indispensable |
| Titre de section | `text-lg font-semibold` | Groupes d’intention |
| Titre de carte | `text-base font-semibold` | Deux lignes maximum sans perte d’information |
| Corps | `text-base leading-6` | Explications lisibles |
| Métadonnée | `text-sm text-neutral-400` | Jamais le seul porteur d’une action |
| Navigation | 12 px, graisse 600 | Libellé complet, cinq éléments |
| Valeur de résultat | `text-2xl font-bold tabular-nums` | Priorité ponctuelle, pas quatre scores avant chaque activité |

Utiliser une grille d’espacement de 4 px : 8 entre éléments liés, 12 dans les petites cartes, 16 pour les marges mobiles, 24 entre sections.
Les cartes utilisent `rounded-xl`, les champs `rounded-lg`, les contrôles ronds uniquement pour les icônes isolées.
Les catalogues conservent `max-w-2xl` ; les écrans d’exercice utilisent la hauteur disponible plutôt qu’un catalogue élargi.
Sur desktop, l’échiquier et les actions forment deux colonnes ; les pages de lecture restent bornées pour éviter les lignes trop longues.
Les zones sûres utilisent les helpers CSS existants et ne sont pas codées avec les valeurs simulées de l’audit.

### Composants à consolider après fusion

| Composant | Responsabilité et contrat | Réutilisation / exclusion |
|---|---|---|
| `PageHeader` | Titre, description facultative, retour nommé de 44 px, action secondaire facultative | Catalogue et hubs ; retour explicite plutôt que `history.back()` aveugle |
| `ActivityCard` | Libellé, objectif bref, progression facultative, lien ou bouton selon l’action | Un élément interactif racine, aucun bouton imbriqué |
| `ProgressBar` | Valeur réelle, total, nom accessible, texte x/y | Reprendre le calcul de progression existant ; pas d’Elo converti en pourcentage |
| `EmptyState` | Titre, raison, une action possible | Distinguer absence de données et erreur réseau ; aucune réussite factice |
| `LoadingState` | Conserver la structure, annoncer le chargement avec `role=status` | Pas de pourcentage inventé ni spinner sans texte |
| `Cta` existant | Action principale / secondaire, cible, contraste, focus et état occupé | Étendre le composant existant au lieu d’un second système de boutons |
| En-tête et pied d’exercice | Quitter, progression, consigne, verdict et prochaine action | Composer autour des lecteurs actuels ; ne pas unifier les moteurs métier |

Aucun composant n’est créé maintenant : les trois premiers usages concrets et le contrat des branches fusionnées doivent guider leur extraction.
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

Le premier lot de refonte doit recenser les routes et domaines réellement fusionnés et actualiser ce tableau.
Un déplacement de menu ne justifie pas de renommer un domaine `learnSessions`, une clé de sauvegarde ou un identifiant de contenu.

## Plan de mise en œuvre

Chaque lot porte un périmètre limité et peut être annulé sans migration de données.
L’ordre indique les dépendances ; les lots 3 à 6 sont séparables une fois le socle et les contrats validés.
Les checks listés sont des obligations futures, pas des tests déjà exécutés dans cette phase.

| Lot | Périmètre et propriété | Dépendance | Acceptation E2E |
|---|---|---|---|
| 0. Réconcilier après fusion | Inventaire routes, états et domaines, mise à jour de cet audit | Toutes les features retenues fusionnées | Audit trois formats, aucune route oubliée, liste des écarts explicite |
| 1. Socle visuel (fait) | `Cta`, en-tête, carte, progression, état vide sur trois usages réels | Lot 0 | Contraste, focus, 44 px, titres longs, état vide, chargement, captures trois formats |
| 2. Navigation et Plus | `App.tsx`, nouveau hub Plus, rattachement des routes | Lot 1 | Cinq onglets, aria-current exact, anciens deep links, replace/push, aucun retour hors app, suites shell/all_buttons/edge_navigation |
| 3. Réglages et données | Extraire la présentation de Stats vers Réglages et Mes données | Lot 2 | Mêmes valeurs persistées ; backup, upgrade, audio_settings, stats ; annulation des actions destructrices |
| 4. Accueil quotidien | `Home.tsx`, adaptateur de lecture du service de séance existant | Lot 2 + séance du jour intégrée | Profil neuf, reprise, dû/non dû, données indisponibles, pas de double comptage, CTA accessible à 660 px |
| 5. Apprendre et Entraînement | Hub guidé, cinq groupes, anciennes entrées conservées | Lot 2 + parcours intégré | Chaque fonction accessible en quatre taps au plus, état vide explicite, suites learn/all_buttons et suites des features déplacées |
| 6. Puzzles et vitesse | Hub Puzzles, Rush et Mats, retours contextuels | Lot 2 | Réussite/échec, chrono intact, retour vers le bon hub, suites puzzles/mats/continuation |
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

## Vérifications de cette phase

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
Aucun code produit ni helper partagé n’a changé : les suites métier non touchées n’ont pas été relancées.
Le succès des checks établit les parcours et la couverture, pas la conformité ergonomique des écrans audités.
La refonte et sa validation sur iPhone physique restent à réaliser après fusion.

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
