# Archive de la campagne QA du 2026-09-18

Ce dossier n'est PAS une suite de tests et le gate ne l'exécute pas.
C'est l'archive d'une campagne QA mobile : 154 constats, leurs scripts de reproduction et leurs sorties brutes.
Les scripts sont conservés tels qu'ils ont tourné, sans maintenance.
Chaque lot de correctifs en extrait son test de régression, réécrit proprement sur `e2e/helpers.py`, dans une vraie suite `e2e/test_*.py`.

## Contenu

- `findings/<zone>.md` : les constats, au format fixe (repro, attendu, observé, cause `fichier:ligne`, correctif proposé).
- `findings/PLAN-correctifs.md` : le découpage en lots de correctifs.
- `<zone>/` : 82 scripts de repro et leurs sorties brutes (`out_*.txt`, `*.log`, `*.json`) citées comme preuves dans les constats.
- `qa_helpers.py` : le helper de la campagne, gardé pour que ces scripts restent lisibles. Le socle maintenu est `e2e/helpers.py`.
- `verify_touch1.py` : contre-vérification du constat TOUCH-1 (pièce saisie par sa coordonnée), avant et après correctif.
- Les captures d'écran (environ 90 Mo) ne sont pas versionnées.

## Rejouer un script

Depuis la racine du repo, avec un serveur déjà lancé :

```bash
npm run dev -- --port 5199 --strictPort    # dans un autre terminal
BASE=http://localhost:5199 python3 e2e/qa/touch/t11_proof_shots.py
```

Limites connues :

- La plupart des scripts supposent le serveur de DEV (React StrictMode actif) : certains constats, comme les écritures en double, n'existent que là.
- Les scripts marqués « API chess.com réelle » ont besoin d'internet et de comptes publics qui peuvent changer.
- Les scripts marqués « sert le build sur le port 5198 » attendent `npx vite preview --port 5198` lancé à la main.
- Les scripts écrivent leurs captures dans `e2e/qa/<zone>/shots/` (ignoré par git).
- Plusieurs constats portent sur des insets iPhone (`env(safe-area-inset-*)`) que l'émulation met à 0 : les scripts les injectent par CSS, ce n'est pas une mesure sur appareil.

## Scripts par zone

### touch - Gestes tactiles sur l'échiquier

Constats : `findings/touch.md`.

| Script | Objet | Particularités |
|---|---|---|
| `t01_inventory.py` | Inventaire : géométrie du board + CSS calculés (touch-action, user-select, overscroll...) par page et viewport |  |
| `t02_analyse.py` | /#/analyse : drags 4 directions, pièce non jouable, case vide, coordonnées, bordure. 3 viewports. |  |
| `t03_probe560.py` | Pourquoi le correctif touch-action laisse un scroll sur d1 en 393x560 ? Qui reçoit le doigt ? + taille des zon |  |
| `t04_play.py` | /#/jouer contre un bot, cibles VALIDEES (toute ligne dont le doigt n'a pas touché la cible prévue sort en INVA |  |
| `t05_movelist_scroll.py` | /#/jouer : jouer un coup PAR DRAG fait-il défiler <main> ? (MoveList.tsx:15 scrollIntoView) |  |
| `t06_puzzles_rush_learn.py` | Puzzles, Puzzle Rush, Apprendre (4 domaines) : pièce à moi (centre, coup légal), pièce à moi saisie par sa coo |  |
| `t07_interactions.py` | /#/analyse (standalone 852) : tap tremblant vs dragActivationDistance:1, tap-tap, changement de sélection, |  |
| `t08_misc.py` | Divers : (1) diagramme lecture seule de CourseSheet vs scroll de la feuille, (2) annulation de promotion, |  |
| `t09_touchstart_and_chesscom.py` | (a) la parade touchstart.preventDefault prend-elle VRAIMENT effet sans casser tap/drag/promotion ? (journal éc |  |
| `t10_back_nav.py` | (a) effet d'un retour arrière (= ce que fait le swipe-back iOS) pendant une partie : la partie survit-elle ? |  |
| `t11_proof_shots.py` | Captures avant/après du constat principal : pion a2 saisi par son chiffre, standalone 852 + safe areas émulées |  |
| `t12_promo_glyphs.py` | TOUCH-8 : après 'Précédent', quels glyphes le voile de promotion propose-t-il ? (lecture DOM, pas interprétati |  |
| `tlib.py` | Gestes tactiles instrumentés : état avant / pendant / après + journal d'événements navigateur. |  |
| `touch_env.py` | Enveloppe locale de qa_helpers (que je ne modifie pas : module partagé). |  |

### play - Jouer

Constats : `findings/play.md`.

| Script | Objet | Particularités |
|---|---|---|
| `common.py` | Socle commun des scripts QA de la page Jouer. |  |
| `t01_setup.py` | Écran de configuration : mesures CTA, zones tactiles, troncatures, 852 et 660. |  |
| `t02_rules.py` | Règles en mode 2 joueurs local (déterministe) : roques, e.p., promotion, illégal, clouage, échec, pat, répétit |  |
| `t03_noa.py` | Partie complète contre Noa (400) jusqu'au mat, 10 min, puis Archive et Stats dans le même contexte. |  |
| `t04_clock.py` | Pendules : bullet 1+0, échantillonnage fin, drapeau, dérive, gel de page (arrière-plan). |  |
| `t05_races.py` | Courses : abandon pendant la réflexion du bot, nouvelle partie immédiate, navigation en pleine partie, abandon |  |
| `t06_coach.py` | Mode Entraîneur : bulle, latence, saut de layout, cohérence des commentaires, indication, annuler. |  |
| `t07_maximus_robust.py` | Maximus 4 coups, seuil humain de la course R2, Nouvelle partie x5, paysage, desktop. |  |
| `t08_prod_doublesave.py` | Vérifie si la double sauvegarde de fin de partie existe aussi sur le build de prod (sans StrictMode dev). | vise la prod déployée |
| `t09_misc.py` | Divers : perte de surbrillance après désélection, a11y, modale en 375 px, dérive pendule sous charge CPU. |  |
| `t10_660.py` | Écran de partie en 393x660 (onglet Safari) : ce qui tient à l'écran, modale. |  |
| `t11_autoscroll.py` | Auto-scroll de <main> provoqué par la liste de coups (scrollIntoView) quand l'écran de partie dépasse la haute |  |
| `t12_coach660.py` | (sans description) |  |

### puzzles - Puzzles et Puzzle Rush

Constats : `findings/puzzles.md`.

| Script | Objet | Particularités |
|---|---|---|
| `find_special.py` | promotion joueur |  |
| `find_special2.py` | mat alternatif à un coup INTERMÉDIAIRE (la solution continue, mais un mat en 1 existe ?) -> rare, on ignore |  |
| `pz.py` | Aides spécifiques puzzles : lecture du puzzle courant (props React), jeu de la solution. |  |
| `t01_load.py` | T01 : chargement initial /#/puzzles (standalone 393x852), état de chargement, 1er puzzle. |  |
| `t02_solve.py` | T02 : solution correcte (tap puis drag), coup faux (1er coup, puis 2e coup joueur), réessayer, analyser + reto |  |
| `t03_feedback_hint.py` | T03 : surlignage du dernier coup (tap vs drag), durée du message « Trouvé ! », indice (progressif ? pénalité ? |  |
| `t04_special.py` | T04 : puzzles choisis servis un par un (route sur puzzles.json) : reprise (surlignage), promotion, |  |
| `t05_chain.py` | T05 : enchaîne 10 puzzles (7 réussis, 3 ratés), dérive Elo, répétitions, latence « Suivant », heap, |  |
| `t05b_leak.py` | T05b : fuite ? 60 x « Passer », mesure heap / noeuds DOM / listeners tous les 15. |  |
| `t05c_leak_solve.py` | T05c : fuite quand on RÉSOUT (tap vs drag) ? noeuds DOM / listeners après GC. |  |
| `t05d_leak_bisect.py` | T05d : quel geste fait fuir un board détaché ? 8 itérations par scénario. |  |
| `t05e_leak_nohandle.py` | T05e : même scénario select_only, mais coordonnées via evaluate (aucun ElementHandle Playwright sur les cases) |  |
| `t06_rush_survival.py` | T06 : Puzzle Rush, mode Survie : difficulté croissante, 3 erreurs, double erreur < 400 ms, record, égalité de  |  |
| `t07_rush_timed.py` | T07 : Puzzle Rush 3 min (horloge pilotée par page.clock) et 5 min. |  |
| `t08_visual.py` | T08 : passe visuelle. 393x852 avec safe-areas réelles simulées, 393x660, paysage 852x393, desktop 1440x900. |  |
| `t09_sounds.py` | T09 : sons (playSounds=true) : quels fichiers sont demandés à chaque étape ? |  |
| `t10_double_score.py` | T10 : puzzles classés, 3 coups faux très rapides : l'Elo n'est-il débité qu'une fois ? |  |

### learn - Apprendre

Constats : `findings/learn.md`.

| Script | Objet | Particularités |
|---|---|---|
| `egdrv.py` | Pilote de finale : joue de vrais coups (tap / drag tactile) et suit la partie avec python-chess. |  |
| `lh.py` | Helpers spécifiques à la QA Apprendre. |  |
| `s10_content_shots.py` | Captures de preuve pour les défauts de contenu des cours. |  |
| `s1_course_sheet.py` | B. Feuille de cours depuis chaque domaine : bon cours, contenu, diagramme, scroll, fermeture. |  |
| `s2_endgames_a.py` | (sans description) |  |
| `s2_endgames_b.py` | reste sur les rangées 1-2 / colonnes a-b pour ne rien « couper » |  |
| `s3_tactics.py` | Tactiques : 3 puzzles (tap, drag, raté exprès), Elo Dexie, Réessayer (double comptage ? delta périmé ?), board |  |
| `s3_tactics_lib.py` | (sans description) |  |
| `s4_openings.py` | Ouvertures, archive VIDE : lignes de repli, textes, mauvais coup, 1 faute vs 2 fautes, Elo. |  |
| `s5_repertoire.py` | Archive NON vide : 2 vraies parties courtes contre Noa (Blancs puis Noirs), puis drill d'ouvertures. |  |
| `s6_mistakes.py` | Mes erreurs (via bilan /analyse), aller-retour Analyser (simple + double), rechargement en séance. |  |
| `s7_auto.py` | Séance auto : ordre des domaines, abandon, écran de fin, aller-retour Analyser sur une finale (état du board). |  |
| `s8_viewports.py` | Passe visuelle : 393x660 (onglet Safari), paysage 852x393, desktop 1440x900. Géométrie + chaînage de scroll de |  |
| `s9_misc.py` | Divers : finale à objectif nulle RATÉE, saut de layout « Je vérifie… », taille du board par domaine, cibles ta |  |
| `static_audit.mjs` | coup légal pour le camp de la pièce ? |  |
| `static_endgames.py` | Vérifie avec Stockfish natif que chaque finale a bien l'issue théorique annoncée (win/draw pour `side`). |  |

### analysis - Analyse, Archive, Import chess.com

Constats : `findings/analysis.md`.

| Script | Objet | Particularités |
|---|---|---|
| `t1_free.py` | Passe 1 : analyse libre mobile standalone (393x852). |  |
| `t1b_engine_mate.py` | Passe 1b : moteur OFF stoppe-t-il vraiment Stockfish ? Mat annoncé, signe de l'éval trait noir. |  |
| `t1c_uci_proof.py` | (sans description) |  |
| `t2_import.py` | Passe 2 : import PGN / FEN collé + export. |  |
| `t3_review.py` | Passe 3 : bilan complet sur la partie à fautes (mobile standalone). |  |
| `t3b_guided.py` | Passe 3b : graphe cliquable, vue non guidée après bilan, flèches, Réessayer. |  |
| `t4_concurrency.py` | Passe 4 : interactions pendant un bilan en cours (longue partie 230 demi-coups). |  |
| `t5_archive.py` | Passe 5 : archive (état vide, création de parties, liste, Analyser/Bilan, export, suppression). |  |
| `t5b_archive_black.py` | Passe 5b : partie jouée avec les noirs -> Analyser / Bilan depuis l'archive ; doublons en dev vs prod. |  |
| `t6_chesscom.py` | Passe 6 : import chess.com (réseau réel). | API chess.com réelle |
| `t6b_chesscom_errors.py` | Passe 6b : pseudo inexistant, hors-ligne, reprise après erreur, popeye232. | API chess.com réelle |
| `t7_visual.py` | Passe 7 : visuel multi-viewports (393x660 Safari, paysage 852x393, desktop 1440x900). |  |
| `t7b_landscape.py` | Passe 7b : paysage 852x393 (layout md) + nom d'ouverture long en standalone 393x852. |  |
| `t8_coach.py` | Passe 8 : texte du coach (résumé, accords), brillant (mat de Legal), ?game inexistant, promotion. |  |
| `t9_variation_after_review.py` | Passe 9 : un coup exploratoire après bilan détruit-il le bilan et la suite ? Feedback de copie PGN ? |  |

### global - Accueil, Stats, navigation, PWA

Constats : `findings/global.md`.

| Script | Objet | Particularités |
|---|---|---|
| `backup.py` | Sauvegarde / restauration : export complet, aller-retour dans un contexte neuf, fichiers invalides, écrasement |  |
| `envelope.py` | Enveloppe : chaque route x chaque viewport. Titre, overflow_x, onglet actif, erreurs, capture pleine page. |  |
| `home_stats.py` | Accueil + Stats : état peuplé, justesse des chiffres, CTA, réglages, persistance, thème partout. |  |
| `misc.py` | Captures de preuve + mesures de cohérence visuelle (h1, paddings, rayons) + responsive en partie. |  |
| `nav_a11y.py` | Navigation, cibles tactiles, contrastes, focus clavier, aria, bouton retour, rechargement. |  |
| `pwa.py` | PWA sur le build servi (BASE=http://localhost:5198) : SW, précache, puis HORS LIGNE sur chaque route. | sert le build sur le port 5198, API chess.com réelle |
| `seed.py` | Jeu de données réaliste injecté dans IndexedDB `chess-local` (schéma src/lib/db.ts, version(2)). |  |
