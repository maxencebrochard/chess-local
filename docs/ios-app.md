# App iOS : étude et plan

Étude du 16 octobre 2026, en réponse à la demande de Max : une app iOS pour améliorer le ressenti.
Elle complète `docs/f14-feeling.md`, qui mesure le ressenti actuel de la PWA et en liste les limites sur iPhone.

## Ce qui limite la PWA aujourd'hui

- Aucune haptique : `navigator.vibrate` n'existe pas dans Safari iOS, ni en PWA installée.
- Rafraîchissement : WebKit limite `requestAnimationFrame` et le rendu des pages à 60 images/s par défaut sur iPhone, et une PWA installée ne peut pas lever cette limite ([bug 272226](https://bugs.webkit.org/show_bug.cgi?id=272226)) ; le glissé d'une pièce suit donc le doigt à 60 Hz sur un écran ProMotion à 120 Hz.
- Son : Web Audio passe par le même WebKit, avec un contexte à déverrouiller à chaque geste et à recréer après l'arrière-plan (`src/lib/sounds.ts`), et il obéit au bouton silencieux.
- Gestes système : WebKit décide du geste précédent/suivant dès un contact au bord ; `main.tsx` annule les `touchstart` dans les 25 px des bords sur les échiquiers.
- Stockage : IndexedDB d'une PWA peut être purgé par iOS ; `navigator.storage.persist()` est demandé, sans garantie, et la sauvegarde manuelle reste le seul filet.

## Option A : coquille Capacitor autour de la PWA

L'app web actuelle est empaquetée telle quelle dans une `WKWebView` (Capacitor 8), avec des plugins natifs appelés depuis TypeScript.

Gain de ressenti attendu :

- Haptique réelle via `UIImpactFeedbackGenerator` et `UINotificationFeedbackGenerator` (plugin officiel `@capacitor/haptics`) : saisie, pose, prise, refus, prémouvement.
  C'est le gain le plus net et le plus sûr : chess.com sur iPhone s'appuie sur ce même retour.
- Gestes de bord : `allowsBackForwardNavigationGestures` vaut `false` par défaut dans une `WKWebView`, et Capacitor coupe aussi le rebond du défilement ; il n'y a plus de geste précédent/suivant à combattre.
  Le correctif des 25 px reste en place, inoffensif, car la PWA en a toujours besoin.
- Stockage : les données vivent dans le conteneur de l'app et suivent ses mises à jour ; elles disparaissent à la désinstallation, comme pour la PWA à la suppression de l'icône.
  Le comportement exact d'éviction de WebKit dans une app reste à vérifier sur l'appareil ; la sauvegarde manuelle reste disponible.
- 120 Hz : aucun gain à attendre ; la limite de WebKit s'applique aussi aux `WKWebView` ([bug 294338](https://bugs.webkit.org/show_bug.cgi?id=294338)).
  `CADisableMinimumFrameDurationOnPhone` est posé dans `Info.plist`, sans effet garanti sur le contenu web.
- Latence du son : même pile Web Audio que la PWA, donc a priori identique ; à mesurer sur l'appareil avant de remplacer quoi que ce soit.

Coût : faible, l'essentiel du code est déjà écrit et testé.
Maintenance : une seule base de code ; la PWA GitHub Pages et l'app partagent tout, et les suites E2E existantes continuent de couvrir la logique et l'interface web, mais pas le runtime iOS réel.
Stockfish : le WASM `lite-single` actuel doit tourner dans un Worker servi par le schéma `capacitor://`, dont le gestionnaire d'assets déclare `application/wasm`.
Ce fonctionnement reste à valider sur iPhone ; les tests Chromium ne le prouvent pas.
Le multithread WASM exigerait l'isolation cross-origin, que Capacitor ne fournit pas par défaut ; un Stockfish natif multithread reste possible plus tard par un plugin qui parle UCI en texte sous la classe `Engine` existante.
Migration : changement d'origine, donc export puis restauration de la sauvegarde existante (voir plus bas).
Distribution : Xcode, un compte Apple Developer, TestFlight.
Mises à jour : chaque changement web demande un nouveau build et une nouvelle installation ; la PWA continue de se mettre à jour seule.

## Option B : app native SwiftUI

Échiquier en SwiftUI, Stockfish compilé en natif, toutes les pages réécrites.

Gain de ressenti attendu : le maximum.
Un rendu natif peut viser 120 Hz sur les appareils ProMotion, avec une haptique fine (`CHHapticEngine`), du son par `AVAudioEngine`, des gestes maîtrisés et Stockfish multithread natif.
La fluidité, la latence audio et le gain de force restent à mesurer sur l'appareil.

Coût : très élevé ; environ 9 000 lignes de pages et toute la logique de `src/lib/` (bilan, coach, révision, insights, cours, sauvegarde) à réécrire.
Maintenance : deux bases de code à garder identiques, ou abandon de la PWA ; les suites E2E Playwright ne couvrent plus l'app.
Migration : la plus délicate ; il faudrait réimplémenter fidèlement `inspectBackup`, les tables Dexie, les réglages et toutes les règles de `backup.ts`, sous peine de perte de données.
Distribution et mises à jour : comme l'option A.

## Option C : hybride, WKWebView et échiquier natif

L'app reste web, mais l'échiquier est une vue native posée par-dessus la `WKWebView` aux emplacements des échiquiers.

Gain de ressenti attendu : glissé à 120 Hz et haptique native sur l'échiquier, le reste comme l'option A.

Coût : élevé.
Maintenance : la pire des trois ; deux rendus de l'échiquier à garder synchronisés (géométrie du glissé, file de prémouvement, flèches, pastilles, calque des attaquants, sons, promotion), une synchronisation de position et de défilement entre la vue native et la page, et des tests E2E natifs supplémentaires à maintenir (XCUITest).
Migration et Stockfish : comme l'option A.

## Recommandation

Option A, Capacitor.
Elle apporte tout de suite le gain le plus net (haptique) et supprime les gestes de bord, sans seconde base de code, en réutilisant la validation et la restauration transactionnelle existantes.
Elle garde la PWA, les tests E2E et la logique éprouvée de sauvegarde comme socle commun.
B ne vaut sa réécriture que si le 120 Hz et Stockfish natif deviennent prioritaires, et C cumule les inconvénients des deux.
Si, sur l'appareil, le glissé à 60 Hz se révèle le facteur limitant, mesurer d'abord un prototype d'échiquier natif limité à l'écran Jouer.
Un plugin Stockfish natif répondrait séparément à un besoin de force du moteur, sans améliorer directement la fluidité du glissé.

## Ce qui est prêt

- `capacitor.config.ts` : identifiant `io.github.maxencebrochard.chesslocal`, dossier web `dist`, fond `#262421`.
- `ios/` : projet Xcode généré par `npx cap add ios --packagemanager SPM`, sans CocoaPods, qui a fonctionné sans Xcode.
  `Info.plist` ajusté (barre d'état claire, `CADisableMinimumFrameDurationOnPhone`, `arm64`), icône 1024 px tirée de `public/pwa-512-maskable.png` et écran de lancement uni `#262421`.
  Le plugin cœur SystemBars est réglé en `DARK` dans `capacitor.config.ts`, sinon il repasserait la barre d'état en style par défaut, illisible sur le fond sombre en mode clair.
- `src/lib/native.ts` : détection du runtime natif et haptique, no-op synchrone sur le web.
  Le plugin est chargé par import dynamique (`src/lib/nativeHaptics.ts`), seulement en natif : le bundle principal de la PWA n'importe rien de Capacitor.
  `vite.config.ts` préfixe les chunks de `@capacitor/*` et de ce pilote par `assets/native-`, puis les exclut du précache : la PWA ne le télécharge jamais, et c'est le même build qui part sur GitHub Pages et dans l'app.
- Haptique branchée dans `Board` pour les gestes de l'utilisateur, et dans `playComputerMove` (`src/lib/sounds.ts`) pour les coups de l'ordinateur.
- Carte de migration sur l'accueil natif jusqu'à une restauration réussie ou « Non merci ».
- Suite E2E `ios_app`, qui simule le pont natif de Capacitor.

### Intensités haptiques

| Geste | Retour | Raison |
|---|---|---|
| Saisie d'une pièce (début de glissé ou sélection par toucher) | impact léger | Confirme la prise en main sans fatiguer, il revient à chaque coup |
| Pose d'un coup accepté (glissé ou clic-clic) | impact moyen | Le contact principal, plus marqué que la saisie |
| Pose d'une prise, en passant compris | impact fort | Distingue la prise au toucher, comme le son plus brillant |
| Promotion | moyen, ou fort si la promotion prend | Émis au choix de la pièce, quand le coup part vraiment |
| Refus (case interdite) | notification « erreur » | Motif triple distinct d'un impact, comme le son grave de refus |
| Prémouvement mis en file | tic de sélection | La mise en file reste sans son et la pièce reste au départ ; la sélection conserve son impact léger |
| Prémouvement exécuté | moyen ou fort | Un seul retour, au moment où le coup est réellement joué |
| Coup de l'ordinateur (bot, Stockfish, réponse d'un puzzle ou d'un cours, amorce) | impact léger | Signale la réponse sans regarder l'écran, plus discret que la pose du joueur |
| Coup de l'ordinateur qui prend, fait échec ou promeut | impact moyen | Un cran plus marqué, comme le son de prise ou d'échec |

Le retour d'un coup de l'ordinateur part avec son son, depuis `playComputerMove`, et ne dépend pas du réglage des sons : le bouton silencieux coupe Web Audio, pas les vibrations.
Aucun retour pour la navigation de l'analyse, la lecture d'une ligne (« Pourquoi ? », « Voir la suite »), un saut de position ou la reprise d'une partie interrompue.
Une pièce reposée sur sa case conserve le retour de saisie, sans retour de pose.
Un coup refusé par la page elle-même (`onMove` qui retourne faux, par exemple une ouverture hors répertoire) ne vibre pas ; un coup faux de puzzle, accepté puis repris, vibre à la pose comme il sonne.
La saisie par toucher vibre au relâché, moment où react-chessboard signale le toucher ; une sélection par toucher suivie d'un glissé de la même pièce donne deux saisies.
Le plugin crée un générateur iOS à chaque appel, sans `prepare()` préalable : le premier retour peut arriver quelques millisecondes plus tard, à mesurer sur l'appareil.
Il n'y a pas de réglage dédié, la forme des réglages restant inchangée ; iOS coupe ces retours quand « Vibrations système » est désactivé dans Réglages, Sons et vibrations.
Un réglage dédié pourra venir avec la migration de réglages correspondante si le besoin apparaît.

## Migration des données PWA vers l'app

La PWA (`https://maxencebrochard.github.io/chess-local/`) et l'app (`capacitor://localhost`) n'ont pas la même origine : l'app démarre avec une base vide, et aucun code ne peut lire le stockage de l'autre.
La sauvegarde complète existante est donc le chemin, déjà vérifiée par les suites `backup` et `upgrade` : une transaction, validation complète avant écriture, réglages nettoyés.

1. Dans la PWA, Plus, Mes données, « Exporter tout », puis « Enregistrer dans Fichiers ».
2. Dans l'app, l'accueil affiche « Récupérer tes données » jusqu'à une restauration réussie ou « Non merci » (la croix), même si un puzzle a déjà été joué dans l'app.
   La carte reste compacte pour que Jouer reste entièrement visible au-dessus de la navigation sur un petit iPhone.
3. La carte ouvre Stats sur Tes données, où l'app seule affiche la marche à suivre ; « Restaurer » ouvre le sélecteur de fichiers d'iOS, puis l'écran de confirmation habituel affiche ce qui sera restauré.
   La restauration remplace tout ce qui a été fait dans l'app avant elle, et Stats le dit.
4. Après une restauration réussie, la carte disparaît (clé `chess-local-native-migration` posée).
5. « Non merci » masque la carte pour un nouveau départ ; la réinitialisation efface la clé et la carte revient.

Ne voyagent pas, car hors sauvegarde par conception : la partie en cours contre le moteur, le niveau du défenseur de l'entraîneur d'attaque et la configuration d'Insights.
Garder la PWA installée tant que l'app n'a pas été vérifiée, puis ne plus jouer que dans l'app : les deux stockages ne se synchronisent pas, et une nouvelle sauvegarde peut être refaite à tout moment.

Décalage de versions : la PWA se met à jour seule, l'app seulement à la réinstallation, et `inspectBackup` refuse une sauvegarde d'un schéma plus récent.
Règle : ne pas déployer un nouveau `db.version(n)` sur le web avant d'avoir installé un build de l'app qui le porte (règle reprise dans CLAUDE.md).

Export depuis l'app : il passe par la feuille de partage, si la `WKWebView` expose `navigator.share` avec fichiers.
Sans elle, Capacitor n'ayant pas de gestionnaire de téléchargements, l'app annonce un échec au lieu d'un faux succès ; la phase suivante passerait alors par `@capacitor/filesystem` et `@capacitor/share`.
La suite `ios_app` joue ce parcours de bout en bout : export réel dans un contexte web, restauration dans un contexte natif simulé, comptes et réglages comparés.

Améliorations possibles après la première installation :

- Ouvrir une sauvegarde depuis la feuille de partage (« Ouvrir dans ChessLocal ») : types de documents dans `Info.plist` et lecture du fichier par `@capacitor/app` et `@capacitor/filesystem`.
- Sauvegarde automatique dans le dossier Documents de l'app, visible dans Fichiers, par `@capacitor/filesystem`.

## Vérifié sur iPhone le 22 octobre 2026

Premier build réel, sur l'iPhone 17 de Max (iOS 26.6.1), avec Xcode 27.1.

- Compilation par `xcodebuild`, signée avec l'équipe personnelle gratuite : le profil vaut 7 jours, puis l'app expire et se réinstalle depuis le Mac.
- Le certificat de développeur s'approuve une fois sur l'iPhone, dans Réglages > Général > VPN et gestion de l'appareil.
- Installation par `devicectl` en USB, puis par le Wi-Fi (réseau local) après un premier appairage.
- La console native a révélé que le gestionnaire du schéma `capacitor://` sert les assets avec un statut 0 : `sounds.ts` et `puzzles.ts` le prenaient pour une erreur, aucun son ni puzzle ne se chargeait.
  Corrigé par `assetResponseOk` (`src/lib/assetResponse.ts`), couvert par la suite `ios_app` ; la console n'affiche plus d'erreur de son ensuite.

## Reste à vérifier sur iPhone

Par Max, sur l'appareil :

- Haptique : ressenti à chaque geste du tableau ci-dessus, et coupure avec « Vibrations système ».
- Coups de l'ordinateur (signalés sans son ni vibration le 23 octobre 2026) : impact léger à chaque réponse du bot, de Stockfish et des puzzles, et son adverse audible.
  En émulation, le son de chaque réponse part sur un contexte audio actif (suite `coup_ordinateur`) ; si l'iPhone reste muet, la console de l'inspecteur Safari affiche « Son abandonné » avec l'état du contexte au moment du coup.
- Son après le correctif du statut 0 : sons réellement entendus, déverrouillage au premier geste, retour après verrouillage, bouton silencieux, et effet sur la musique d'une autre app.
- Stockfish : Worker et WASM chargés sous `capacitor://`, analyse et bots jouent ; `?debug-uci` ne s'ajoute pas à l'URL d'une app, ouvrir l'inspecteur Safari (Développement, nom de l'iPhone) en build Debug.
- Stockage : comportement d'éviction de WebKit dans l'app.
- Safe areas : `viewport-fit=cover` et `pt-safe`/`pb-safe` en plein écran, barre d'état lisible sur le fond sombre.
- Service worker : absent sous `capacitor://`, l'enregistrement doit échouer en silence, les assets étant déjà locaux.
- Migration : export depuis la PWA, restauration dans l'app, chiffres identiques sur Stats et l'accueil.
- Export depuis l'app : la feuille de partage s'ouvre avec le fichier (sinon, phase suivante ci-dessus) ; c'est le filet avant une désinstallation.
- Stats : la ligne « Stockage protégé » et son texte sont écrits pour la PWA ; noter ce que `navigator.storage.persisted()` répond dans l'app et adapter le texte en conséquence.
- Appui long sur une pièce : aucun menu ni aperçu WebKit (`allowsLinkPreview` est coupé).

## Ce que Max doit faire

1. Utiliser Node.js 22.12 ou plus récent (Node 22 LTS recommandé), requis par Vite et Capacitor.
   Installer Xcode 26 ou plus récent depuis l'App Store (Capacitor 8 l'exige), l'ouvrir une fois pour accepter la licence et installer la plateforme iOS, puis `sudo xcode-select -s /Applications/Xcode.app`.
2. Prendre le compte Apple Developer (99 € par an) avec son Apple ID.
   Sans compte payant, la signature gratuite fonctionne mais l'app expire au bout de 7 jours et doit être réinstallée depuis le Mac.
   Avec le compte, une installation de développement dure un an, et TestFlight installe sans câble des builds valables 90 jours.
3. Depuis le worktree ou `main` une fois fusionné :

   ```bash
   npm ci
   npm run ios:sync      # build web puis copie dans ios/App/App/public
   npm run ios:open      # ouvre ios/App/App.xcodeproj dans Xcode
   ```

4. Dans Xcode : cible App, onglet Signing & Capabilities, cocher « Automatically manage signing », choisir son équipe.
   Si l'identifiant `io.github.maxencebrochard.chesslocal` est refusé, en choisir un autre et le reporter dans `capacitor.config.ts`.
5. Brancher l'iPhone, activer le mode développeur (Réglages, Confidentialité et sécurité, Mode développeur), le choisir comme destination, puis Run.
6. Faire la migration ci-dessus et la liste « Reste à vérifier sur iPhone ».
7. Pour TestFlight : Product, Archive, puis Distribute App, App Store Connect ; l'app est d'abord créée dans App Store Connect avec le même identifiant.
   Le build apparaît dans TestFlight après traitement, installable par l'app TestFlight de l'iPhone.

Après chaque changement web : `npm run ios:sync`, puis Run dans Xcode ou un nouvel archivage pour TestFlight.
Le déploiement GitHub Pages (`scripts/deploy.sh`) est indépendant et inchangé.
