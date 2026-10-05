// Banque de phrases du coach (bilan, résumé, punchline, entraîneur en direct).
// Règles d'écriture : tutoiement, aucun adjectif accordé au joueur (son genre est inconnu),
// aucun tiret cadratin, 140 caractères au plus par phrase, et surtout rien que le code n'ait
// vérifié : une phrase n'est choisie que par la règle qui a constaté la situation sur l'échiquier.
// Les marqueurs {coup} {meilleur} {reponse} {piece} {Piece} {cible} {Cible} {cible2} {attaquant}
// {case} {n} {ouverture} {precision} {elo} {numero} {fautes} {v_ouverture} {v_milieu} {v_finale}
// sont remplis par l'appelant. Une variante {m, f} s'accorde avec le marqueur qui décide du genre.
export type Gender = 'm' | 'f'
export type Variant = string | { m: string; f: string }

export const PHRASES: Record<string, Variant[]> = {
  // ---------------------------------------------------------------- bilan : coup théorique
  'post.book.generique': [
    'Coup théorique. Tu suis un chemin connu et éprouvé.',
    'Toujours dans la théorie : rien à calculer ici, tout à mémoriser.',
    "C'est le coup des livres. Continue à développer tes pièces.",
    "Théorie pure. L'essentiel reste le même : centre, développement, roque.",
  ],
  'post.book.nommee': [
    'Tu es dans la théorie : {ouverture}.',
    '{ouverture} : ce coup fait partie des lignes principales.',
    'Coup de répertoire. Cette position porte un nom : {ouverture}.',
    "C'est la suite connue ({ouverture}). Retiens l'idée plus que l'ordre des coups.",
  ],
  'post.book.sortie': [
    "Dernier coup de théorie. À partir d'ici, c'est ta partie : place au calcul.",
    'Fin des sentiers battus : le prochain coup, tu le trouves sans aide.',
    "La théorie s'arrête ici. Garde les principes : sécurité du roi, pièces actives.",
    "Jusqu'ici, tout est connu. La vraie partie commence maintenant.",
  ],
  // ---------------------------------------------------------------- bilan : meilleur coup
  'post.best.generique': [
    "C'est le meilleur coup de la position. Bien joué.",
    'Tu as trouvé le coup le plus fort. Rien de mieux ici.',
    "Meilleur coup : tu gardes tout ce que la position t'offrait.",
    "Exactement le coup qu'il fallait. Ta position ne perd rien.",
    'Coup le plus précis. Tu avances sans rien concéder.',
    "Bien vu : parmi tous les coups possibles, c'était le plus fort.",
  ],
  'post.best.gain_materiel': [
    { m: '{Cible} était en prise : tu le captures sans contrepartie.', f: '{Cible} était en prise : tu la captures sans contrepartie.' },
    'Bonne prise : tu captures {cible} et ton avantage matériel grandit.',
    { m: "{Cible} adverse était laissé en prise, tu ne l'as pas raté.", f: "{Cible} adverse était laissée en prise, tu ne l'as pas ratée." },
    'Tu gagnes {cible} sans rien donner en échange. Encore fallait-il le voir !',
  ],
  // Prise qui gagne du matériel mais que l'adversaire peut reprendre : jamais « sans contrepartie ».
  'post.best.gain_echange': [
    "Tu prends {cible} : même après la reprise, l'échange tourne à ton avantage.",
    'Bonne prise. Les reprises comptées, tu sors de cet échange avec du matériel en plus.',
    "Tu captures {cible} et l'échange qui suit te laisse gagnant au compte du matériel.",
    "Échange gagnant : {cible} vaut plus que ce que tu rends ensuite.",
  ],
  'post.best.reprise': [
    "Tu reprends {cible} : l'échange est terminé.",
    'Reprise naturelle. Tu récupères {cible} tout de suite.',
    "Tu récupères {cible} tout de suite. C'est le bon réflexe.",
    'Échange terminé avec cette reprise. Ta position reste saine.',
  ],
  'post.best.mat': [
    "Échec et mat ! Le roi adverse n'a plus aucune case. Belle conclusion.",
    'Échec et mat ! Tu as conclu sans trembler.',
    "Mat ! Une attaque menée jusqu'au bout, bravo.",
    "Échec et mat. Il n'existe pas de coup plus précis : la partie est finie.",
  ],
  'post.best.mat_du_couloir': [
    'Mat du couloir ! Le roi adverse est enfermé derrière ses propres pièces.',
    "Échec et mat sur la dernière rangée. Le roi adverse n'avait aucune case de fuite.",
    'Le mat du couloir, un grand classique : un roi muré derrière ses propres pièces.',
    'Mat ! Ton adversaire a oublié de donner une case de fuite à son roi.',
  ],
  'post.best.mat_en_n': [
    'Tu restes sur le chemin du mat : mat en {n} au plus.',
    'Mat forcé en {n}. Continue à chercher les échecs en priorité.',
    'Le mat est forcé (en {n} au plus). Ne relâche pas ton calcul.',
    'La position est gagnée de force : mat en {n} si tu ne relâches rien.',
  ],
  'post.best.fourchette': [
    'Fourchette ! {coup} attaque {cible} et {cible2} en même temps.',
    { m: "Double attaque : {cible} et {cible2} sont visés d'un seul coup.", f: "Double attaque : {cible} et {cible2} sont visées d'un seul coup." },
    "Belle fourchette sur {cible} et {cible2}. À ton adversaire de choisir ce qu'il sauve.",
    "{coup} vise {cible} et {cible2} d'un seul coup. Le motif à retenir : la fourchette.",
  ],
  'post.best.clouage': [
    'Clouage : si {cible} bouge, {cible2} est à découvert juste derrière.',
    '{coup} cloue {cible} sur {cible2}. Une pièce clouée est une cible : attaque-la encore.',
    'Tu cloues {cible} devant {cible2}. Bouger la première coûterait la seconde.',
    'Bon clouage sur {cible} : {cible2} est juste derrière, sur la même ligne.',
  ],
  'post.best.clouage_absolu': [
    "Clouage : {cible} ne peut plus bouger, le roi adverse est juste derrière.",
    '{coup} cloue {cible} sur le roi adverse. Une pièce clouée devient une cible.',
    { m: "Tu cloues {cible} sur son roi : il n'a plus le droit de quitter la ligne.", f: "Tu cloues {cible} sur son roi : elle n'a plus le droit de quitter la ligne." },
    { m: 'Bon clouage : {cible} est immobilisé devant le roi adverse.', f: 'Bon clouage : {cible} est immobilisée devant le roi adverse.' },
  ],
  'post.best.enfilade': [
    { m: 'Enfilade : {cible} est attaqué, et {cible2} se trouve juste derrière, sur la même ligne.', f: 'Enfilade : {cible} est attaquée, et {cible2} se trouve juste derrière, sur la même ligne.' },
    "Tu attaques {cible} en ligne avec {cible2} derrière : c'est une enfilade.",
    "Belle enfilade. C'est un clouage inversé : la pièce la plus précieuse est devant.",
    '{coup} transperce la ligne : {cible} devant, {cible2} derrière.',
  ],
  'post.best.roque': [
    "Roi à l'abri et tour en jeu : le roque fait les deux en un seul coup.",
    "Bon réflexe : tu roques avant que le centre ne s'ouvre.",
    'Le roque au bon moment. Ton roi est en sécurité, tes tours vont pouvoir se relier.',
    "Tu mets ton roi à l'abri avant de lancer les opérations. C'est la bonne priorité.",
  ],
  'post.best.pion_passe': [
    "Pion passé en {case} : plus aucun pion adverse ne peut l'arrêter. Pousse-le dès que c'est sûr.",
    "Ton pion {case} est passé. En finale, c'est souvent lui qui décide de la partie.",
    'Tu crées un pion passé en {case}. Soutiens-le avec ton roi ou une tour placée derrière.',
    'Pion passé en {case} ! Ton adversaire va devoir mobiliser une pièce pour le bloquer.',
  ],
  // ---------------------------------------------------------------- bilan : très bon, brillant
  'post.great.seul_coup': [
    "C'était le seul coup qui tenait la position. Tout le reste perdait du terrain.",
    "Coup unique ! Un seul chemin était bon et tu l'as trouvé.",
    "Très bien vu : ici, il n'y avait qu'un bon coup, et c'est le tien.",
    'Seul coup. Dans ce genre de position critique, prendre son temps paie.',
  ],
  'post.great.retournement': [
    'Ce coup retourne la partie : tu étais en difficulté, te voilà de retour dans le jeu.',
    "Tu saisis ta chance au bon moment. L'évaluation bascule en ta faveur.",
    "Très bon coup : l'avantage change de camp.",
    'Le tournant de la partie. Tu as vu ce que la position offrait.',
  ],
  'post.great.reprise': [
    'Reprise obligée et bien vue : tu récupères {cible} sans rien lâcher.',
    "La reprise s'imposait : tu reprends {cible} et la position tient.",
    "Tu reprends {cible}. C'était de loin le meilleur coup ici.",
    'Bonne reprise en {case}. Le moteur ne voyait rien de mieux.',
  ],
  'post.brilliant.sacrifice': [
    'Tu sacrifies {piece}, et le calcul te donne raison. Superbe !',
    "Coup brillant : donner {piece} ici, il fallait l'oser et surtout le calculer.",
    'Sacrifice correct ! Si ton adversaire prend {piece}, ton attaque rapporte davantage.',
    'Magnifique. Tu offres {piece} pour un gain plus grand quelques coups plus loin.',
  ],
  // ---------------------------------------------------------------- bilan : excellent, bon
  'post.excellent.generique': [
    'Excellent coup, à un souffle du meilleur. Ta position reste intacte.',
    'Très proche du meilleur coup. La différence est minime.',
    'Coup très solide : tu ne concèdes pratiquement rien.',
    "Presque parfait. Le moteur préférait {meilleur}, mais l'écart est infime.",
    'Bon choix. {meilleur} faisait à peine mieux.',
  ],
  'post.excellent.mat_plus_rapide': [
    "Ça gagne aussi, mais {meilleur} matait en {n}. Quand le roi est exposé, cherche d'abord les échecs.",
    'Tu restes du bon côté, mais il y avait plus direct : {meilleur}, mat en {n}.',
    "Attention, un mat en {n} était là : {meilleur}. Prends l'habitude de vérifier chaque échec.",
    "Le gain n'est pas en danger, mais {meilleur} terminait la partie plus vite (mat en {n}).",
  ],
  'post.good.generique': [
    'Bon coup. {meilleur} était un peu plus précis, sans changer le cours de la partie.',
    "Coup correct. Le moteur préférait {meilleur}, l'écart reste faible.",
    'Ça se joue. {meilleur} te donnait une position un peu plus confortable.',
    'Rien de grave ici. Compare avec {meilleur} pour sentir la nuance.',
  ],
  // ---------------------------------------------------------------- bilan : fautes, générique par classe
  'post.inaccuracy.generique': [
    '{meilleur} était plus précis. Tu ne perds rien de concret, mais ta position se dégrade un peu.',
    'Petit relâchement. {meilleur} posait plus de problèmes à ton adversaire.',
    'Ce coup te coûte un peu de terrain. {meilleur} était plus exigeant pour ton adversaire.',
    'Pas une faute, mais {meilleur} était plus fort. Demande-toi ce que ce coup menaçait.',
  ],
  'post.mistake.generique': [
    'Ta position se dégrade nettement. {meilleur} gardait une bien meilleure position.',
    'Ce coup donne de vraies chances à ton adversaire. Il fallait jouer {meilleur}.',
    "Tu laisses passer le bon coup : {meilleur}. Regarde ce qu'il menaçait ou défendait.",
    "Avant de jouer, demande-toi ce que peut répondre ton adversaire. Ici, {meilleur} s'imposait.",
  ],
  'post.miss.generique': [
    "Ton adversaire venait de se tromper, et tu ne l'as pas puni. {meilleur} en profitait.",
    "Occasion manquée : {meilleur} exploitait tout de suite l'erreur adverse.",
    "Après une erreur adverse, cherche toujours le coup qui punit. Ici, c'était {meilleur}.",
    'Tu laisses passer une belle chance. Reviens sur la position et trouve {meilleur}.',
  ],
  'post.missedWin.generique': [
    "Tu avais une position gagnante, et ce coup laisse filer l'avantage. {meilleur} gardait le gain.",
    'Gain manqué : après ce coup, ton adversaire revient dans la partie. Il fallait {meilleur}.',
    'La position était gagnée. Dans ces moments-là, ralentis et cherche le coup le plus simple : {meilleur}.',
    "L'avantage s'envole d'un coup. {meilleur} maintenait une position gagnante.",
  ],
  'post.blunder.generique': [
    "L'évaluation s'effondre après ce coup. {meilleur} était indispensable.",
    'Ce coup change le cours de la partie. Il fallait trouver {meilleur}.',
    'Grosse faute. Rejoue la position avec « Réessayer » et cherche ce que {meilleur} empêchait.',
    "C'est le moment où la partie t'échappe. Prends le temps de comprendre pourquoi {meilleur} tenait.",
  ],
  // ---------------------------------------------------------------- bilan : motifs des fautes (toutes classes)
  'faute.pat': [
    "Pat ! Le roi adverse n'est pas en échec mais n'a plus aucun coup légal : partie nulle. Le moteur préférait {meilleur}.",
    'Attention au pat : en finale, laisse toujours un coup légal à ton adversaire. {meilleur} évitait le piège.',
    "Partie nulle par pat. Avant de resserrer l'étau, vérifie que le roi adverse garde un coup légal.",
    "C'est pat, donc nulle. Le moteur préférait {meilleur}. Le réflexe : laisser un coup légal au roi adverse.",
  ],
  'faute.mat_en_1': [
    'Ce coup autorise un mat en 1 : {reponse}. Avant de jouer, vérifie toujours les échecs adverses.',
    'Attention : après ce coup, {reponse} fait mat immédiatement. {meilleur} empêchait le mat.',
    'Tu oublies la menace de mat : {reponse} termine la partie au coup suivant.',
    'Mat en 1 pour ton adversaire avec {reponse}. Le premier contrôle avant chaque coup : la sécurité de ton roi.',
  ],
  'faute.mat_en_1_deja': [
    "La position était déjà perdue : {reponse} fait mat. Ton roi n'avait plus de défense durable.",
    'Mat en 1 avec {reponse}. Ici, le mat était déjà forcé : la faute est plus haut dans la partie.',
    '{reponse} fait mat au coup suivant. Le mal était fait avant ce coup, remonte de quelques coups.',
    'Ton adversaire mate avec {reponse}. La défense avait déjà cédé : cherche le vrai tournant plus tôt.',
  ],
  'faute.mat_en_n': [
    'Ce coup permet un mat forcé en {n}. Le moteur préférait {meilleur}.',
    'Ton roi ne tient plus : mat en {n} pour ton adversaire. Il fallait jouer {meilleur}.',
    "Après ce coup, l'attaque adverse est décisive (mat en {n}). Le moteur préférait {meilleur}.",
    'Tu ouvres la porte à un mat en {n}. Quand ton roi est visé, la défense passe avant tout.',
  ],
  'faute.mat_en_n_deja': [
    'Mat en {n} pour ton adversaire. Le mat était déjà forcé avant ce coup : le tournant est plus tôt.',
    "Ton adversaire a un mat en {n}. Ce coup n'y change rien : la partie s'est jouée avant.",
    'La position était déjà perdue de force (mat en {n}). Remonte quelques coups pour trouver la faute.',
    'Mat forcé en {n} contre toi. Ici, plus rien ne sauvait ton roi.',
  ],
  'faute.mat_du_couloir_subi': [
    'Mat du couloir ! Ton roi est enfermé derrière ses propres pièces : {reponse} fait mat.',
    "Ton roi n'a aucune case de fuite sur sa rangée : {reponse} fait mat. Pense à lui donner de l'air.",
    'Attention à la dernière rangée : sans case de fuite, {reponse} suffit à mater.',
    'Tu oublies la faiblesse du couloir : {reponse} mate sur la dernière rangée.',
  ],
  'faute.mat_manque': [
    "Tu avais un mat en {n} avec {meilleur}. Face à un roi exposé, regarde d'abord tous les échecs.",
    'Mat en {n} manqué : {meilleur} concluait la partie de force.',
    "{meilleur} donnait un mat en {n}. Prends l'habitude de vérifier échecs, prises et menaces.",
    'La partie pouvait se terminer ici : {meilleur}, mat en {n}.',
  ],
  'faute.mat_du_couloir_manque': [
    "Mat du couloir manqué : {meilleur} matait sur la dernière rangée, le roi adverse n'avait aucune case.",
    '{meilleur} faisait mat : le roi adverse était enfermé derrière ses propres pièces.',
    'Regarde la dernière rangée adverse : sans case de fuite, {meilleur} terminait la partie.',
    "Le motif à retenir : le mat du couloir. {meilleur} l'exécutait immédiatement.",
  ],
  'faute.piece_en_prise': [
    { m: "{Piece} n'est pas défendu en {case} : ton adversaire peut le prendre gratuitement.", f: "{Piece} n'est pas défendue en {case} : ton adversaire peut la prendre gratuitement." },
    'Après ce coup, {piece} est en prise en {case}. Le moteur préférait {meilleur}.',
    { m: 'Regarde {piece} en {case} : attaqué et sans défenseur. Le moteur préférait {meilleur}.', f: 'Regarde {piece} en {case} : attaquée et sans défenseur. Le moteur préférait {meilleur}.' },
    { m: '{Piece} est laissé sans protection en {case}. Avant chaque coup, vérifie ce que tu ne défends plus.', f: '{Piece} est laissée sans protection en {case}. Avant chaque coup, vérifie ce que tu ne défends plus.' },
  ],
  'faute.mal_defendue': [
    { m: "{Piece} est défendu en {case}, mais attaqué par {attaquant} qui vaut moins : l'échange te coûte du matériel.", f: "{Piece} est défendue en {case}, mais attaquée par {attaquant} qui vaut moins : l'échange te coûte du matériel." },
    "Une pièce défendue peut quand même être perdue : ici {attaquant} prend {piece}, et l'échange est perdant.",
    { m: 'En {case}, {piece} se retrouve attaqué par {attaquant}. Le défendre ne suffit pas.', f: 'En {case}, {piece} se retrouve attaquée par {attaquant}. La défendre ne suffit pas.' },
    "Compte la valeur des pièces : {attaquant} contre {piece}, c'est toi qui y perds. Le moteur préférait {meilleur}.",
  ],
  'faute.sous_defendue': [
    { m: "{Piece} en {case} n'est pas assez défendu : {attaquant} le prend et l'échange tourne mal pour toi.", f: "{Piece} en {case} n'est pas assez défendue : {attaquant} la prend et l'échange tourne mal pour toi." },
    "Compte les attaquants et les défenseurs de {case} : le compte n'y est pas, tu y perds du matériel.",
    { m: '{Piece} est trop peu défendu en {case}. Une reprise ne suffira pas.', f: '{Piece} est trop peu défendue en {case}. Une reprise ne suffira pas.' },
    'En {case}, {piece} manque de défenseurs. Il fallait en ajouter un, ou déplacer la pièce.',
  ],
  'faute.mauvais_echange': [
    'Tu donnes plus que tu ne prends dans cet échange. Compte la valeur des pièces avant de capturer.',
    'Échange perdant : tu captures {cible}, mais tu rends davantage ensuite.',
    'Cette prise te coûte du matériel une fois les reprises terminées. {meilleur} était plus sûr.',
    "Avant de prendre, compte les attaquants et les défenseurs de la case. Ici, le compte n'y est pas.",
  ],
  'faute.autorise_fourchette': [
    'Ce coup autorise une fourchette : {reponse} attaque {cible} et {cible2} en même temps.',
    { m: 'Après {reponse}, {cible} et {cible2} sont attaqués à la fois.', f: 'Après {reponse}, {cible} et {cible2} sont attaquées à la fois.' },
    'Attention aux doubles attaques : {reponse} vise {cible} et {cible2}.',
    '{reponse} prend {cible} et {cible2} en fourchette. Repère ces cases avant de jouer.',
  ],
  'faute.autorise_clouage': [
    { m: 'Ce coup permet un clouage : après {reponse}, {cible} est cloué sur {cible2}.', f: 'Ce coup permet un clouage : après {reponse}, {cible} est clouée sur {cible2}.' },
    '{reponse} va clouer {cible} sur {cible2}. Une pièce clouée devient une cible facile.',
    "Attention aux alignements : {reponse} cloue {cible} devant {cible2}.",
    { m: 'Après {reponse}, {cible} se retrouve cloué : {cible2} est juste derrière.', f: 'Après {reponse}, {cible} se retrouve clouée : {cible2} est juste derrière.' },
  ],
  'faute.prise_gratuite': [
    { m: "{Cible} était en prise et tu ne l'as pas pris. {meilleur} gagnait du matériel.", f: "{Cible} était en prise et tu ne l'as pas prise. {meilleur} gagnait du matériel." },
    '{meilleur} capturait {cible} sans contrepartie. Regarde toujours les pièces non défendues.',
    { m: 'Ton adversaire a laissé {cible} en prise : il fallait le prendre avec {meilleur}.', f: 'Ton adversaire a laissé {cible} en prise : il fallait la prendre avec {meilleur}.' },
    { m: 'Occasion manquée : {cible} pouvait être capturé par {meilleur}.', f: 'Occasion manquée : {cible} pouvait être capturée par {meilleur}.' },
  ],
  'faute.fourchette_manquee': [
    'Tu rates une fourchette : {meilleur} attaquait {cible} et {cible2} en même temps.',
    '{meilleur} créait une double attaque sur {cible} et {cible2}.',
    "Le motif à voir ici : la fourchette. {meilleur} visait {cible} et {cible2} d'un seul coup.",
    "Cherche les cases d'où une pièce attaque deux cibles : ici, {meilleur} visait {cible} et {cible2}.",
  ],
  'faute.clouage_manque': [
    'Tu rates un clouage : {meilleur} clouait {cible} sur {cible2}.',
    '{meilleur} clouait {cible} devant {cible2}. Une pièce clouée devient une cible facile.',
    'Le motif à voir ici : le clouage. {meilleur} alignait {cible} et {cible2}.',
    "Regarde l'alignement entre {cible} et {cible2} : {meilleur} l'exploitait tout de suite.",
  ],
  'faute.droit_au_roque_perdu': [
    "Avec ce coup, tu perds le droit de roquer. Ton roi ne pourra plus se mettre à l'abri ainsi.",
    'Ce coup te prive du roque pour toute la partie. Le moteur préférait {meilleur}.',
    'Tu ne pourras plus roquer. Sans roque, chaque ligne ouverte vers ton roi devient dangereuse.',
    'Attention au droit au roque : une fois perdu, il ne revient pas.',
  ],
  'faute.roque_tardif': [
    "Ton roi est encore au centre. {meilleur} le mettait à l'abri tout de suite.",
    "Pense à roquer : plus le centre s'ouvre, plus ton roi devient une cible. Ici, {meilleur}.",
    'Le roque attendait. Ne le repousse pas sans une bonne raison : {meilleur}.',
    "Sécurité d'abord : {meilleur} réglait la question du roi avant de passer à l'action.",
  ],
  'faute.simplification': [
    'Avec du matériel en plus, échange les pièces : {meilleur} simplifiait la position.',
    "{meilleur} échangeait {cible}. Quand tu as l'avantage matériel, chaque échange te rapproche du gain.",
    "Tu évites l'échange alors qu'il t'arrangeait : moins il reste de pièces, plus ton avantage pèse.",
    'Simplifie quand tu es devant. {meilleur} retirait des pièces à ton adversaire.',
  ],
  // ---------------------------------------------------------------- bilan : coups de l'adversaire
  'post.adverse.generique': [
    "Coup de ton adversaire. Demande-toi ce qu'il menace avant de regarder ta réponse.",
    "Ton adversaire a joué. Quelle est l'idée de ce coup ? Cherche-la avant d'avancer.",
    'Coup adverse. Passe au suivant pour retrouver mon commentaire sur ta réponse.',
    'Ton adversaire a joué. Vois-tu une menace ? Une pièce laissée en prise ?',
  ],
  'post.adverse.erreur': [
    "Ton adversaire se trompe ici. Avant d'avancer, cherche le coup qui punit.",
    'Erreur adverse ! Regarde bien la position : il y a quelque chose à gagner.',
    'Ce coup adverse est une faute. Vois-tu pourquoi ? La réponse est au coup suivant.',
    "Ton adversaire vient de t'offrir une occasion. À toi de la trouver.",
  ],
  'post.adverse.mat': [
    "Échec et mat. Ton roi n'a plus aucune case : la partie est finie.",
    "Mat. Remonte quelques coups : c'est là que ton roi a perdu ses défenseurs.",
    'Échec et mat contre toi. La leçon est plus haut dans la partie, allons la chercher.',
    "C'est mat. Regarde d'où venait l'attaque et à quel moment elle est devenue imparable.",
  ],
  'post.adverse.pat': [
    "Pat ! Ton roi n'a plus aucun coup légal et n'est pas en échec : partie nulle.",
    "Ton adversaire te fait pat : partie nulle, quoi qu'en dise le matériel.",
    "Pat. Aucun coup légal pour toi, pas d'échec : la partie est nulle.",
    "C'est pat : partie nulle. Ton adversaire a resserré l'étau sans laisser de coup légal.",
  ],
  'post.secours.generique': [
    'Pas de commentaire particulier sur ce coup. Passe au suivant.',
    'Coup sans histoire. La suite est plus intéressante.',
    'Rien à signaler ici. Continuons.',
    'Position calme, coup logique. On avance.',
  ],
  // ---------------------------------------------------------------- résumé narratif
  'resume.verdict.excellent': [
    "Très belle partie : {precision} % de précision, l'équivalent d'un niveau d'environ {elo} Elo.",
    'Partie remarquable. {precision} % de précision, soit un niveau de jeu proche de {elo} Elo.',
    'Du très beau jeu : {precision} % de précision (environ {elo} Elo sur cette partie).',
    '{precision} % de précision : tu as joué juste du début à la fin, autour de {elo} Elo.',
  ],
  'resume.verdict.solide': [
    'Partie solide : {precision} % de précision, soit environ {elo} Elo sur cette partie.',
    '{precision} % de précision. Du jeu sérieux, autour de {elo} Elo, avec quelques moments à revoir.',
    "Bonne partie dans l'ensemble : {precision} % de précision (environ {elo} Elo).",
    'Tu as bien tenu ta partie : {precision} % de précision, niveau estimé à {elo} Elo.',
  ],
  'resume.verdict.moyen': [
    '{precision} % de précision, soit environ {elo} Elo sur cette partie. Il y a du bon et du moins bon.',
    'Partie inégale : {precision} % de précision (environ {elo} Elo). Quelques coups ont coûté cher.',
    '{precision} % de précision. Des idées intéressantes, mais aussi des fautes à corriger.',
    'Une partie en dents de scie : {precision} % de précision, niveau estimé à {elo} Elo.',
  ],
  'resume.verdict.difficile': [
    "Partie difficile : {precision} % de précision. C'est dans ces parties qu'on apprend le plus.",
    '{precision} % de précision (environ {elo} Elo). Ne retiens que deux ou trois leçons, pas plus.',
    "Ça n'a pas tourné comme tu voulais : {precision} % de précision. Regardons pourquoi, calmement.",
    'Journée sans : {precision} % de précision. Les fautes sont nettes, donc faciles à corriger.',
  ],
  'resume.verdict.courte': [
    "Partie très courte : trop peu de coups pour un bilan chiffré. Regardons quand même ce qui s'est passé.",
    "Quelques coups seulement : pas de précision ni d'Elo estimé, mais chaque coup se relit.",
    'Une partie éclair. Trop courte pour des statistiques, assez pour une leçon.',
    'Trop court pour juger ton niveau. Relisons plutôt les coups un par un.',
  ],
  'resume.resultat.victoire_mat': [
    'Victoire par échec et mat, bravo !',
    'Tu conclus par un mat : la plus belle façon de gagner.',
    'Échec et mat au bout de la partie. Bien joué !',
    'Partie gagnée, et terminée par un mat en bonne et due forme.',
  ],
  'resume.resultat.defaite_mat': [
    'Partie perdue par mat, mais riche en enseignements. On regarde ça ensemble.',
    'Mat au bout de la partie. Voyons à quel moment ton roi a perdu sa protection.',
    "Ça s'est terminé par un mat. Les bonnes nouvelles : les fautes sont identifiables.",
    "Tu t'inclines sur un mat. Regardons le détail sans se presser.",
  ],
  'resume.resultat.pat': [
    "Partie nulle par pat. C'est un piège classique des finales, on va le décortiquer.",
    "Pat : le roi sans coup légal, et la nulle au bout. Voyons comment l'éviter, ou le provoquer.",
    'La partie se termine par un pat. Un thème à connaître par cœur en finale.',
    "Nulle par pat. Regardons le dernier coup de près, c'est lui qui décide de tout.",
  ],
  'resume.fautes.liste': [
    'À revoir : {fautes}. Le bouton « Moment clé » te les montre une par une.',
    'Les points à travailler : {fautes}. Parcours-les avec « Moment clé ».',
    'Dans le détail : {fautes}. On les reprend ensemble avec « Moment clé ».',
    'Bilan des fautes : {fautes}. Chacune est une leçon, va les voir avec « Moment clé ».',
  ],
  'resume.fautes.une': [
    "Une seule faute à revoir : {fautes}. Le bouton « Moment clé » t'y amène.",
    'Un point à travailler : {fautes}. Va le voir avec « Moment clé ».',
    "Dans le détail : {fautes}, et c'est tout. On y revient ensemble avec « Moment clé ».",
    'Une faute, une leçon : {fautes}. « Moment clé » te mène dessus.',
  ],
  'resume.fautes.aucune': [
    'Aucune faute sérieuse : une partie très propre.',
    "Pas une seule grosse faute. C'est rare, profites-en !",
    'Zéro gaffe, zéro erreur. Difficile de faire plus propre.',
    'Rien de grave à signaler : tu as joué juste de bout en bout.',
  ],
  'resume.brillant.un': [
    'Et un coup brillant en prime !',
    'Tu as aussi joué un coup brillant. Va le revoir, il en vaut la peine.',
    'Mention spéciale pour ton coup brillant.',
    "Tu as même trouvé un coup brillant : un vrai sacrifice, correct jusqu'au bout.",
  ],
  'resume.brillant.plusieurs': [
    'Et {n} coups brillants en prime !',
    'Avec {n} coups brillants, rien que ça. Va les revoir, ils en valent la peine.',
    'Mention spéciale pour tes {n} coups brillants.',
    "Tu as trouvé {n} coups brillants : de vrais sacrifices, corrects jusqu'au bout.",
  ],
  'resume.phases.trois': [
    'Phase par phase : ouverture {v_ouverture}, milieu de partie {v_milieu}, finale {v_finale}.',
    'Le fil de la partie : ouverture {v_ouverture}, milieu de partie {v_milieu}, finale {v_finale}.',
    'Ton ouverture a été {v_ouverture}, ton milieu de partie {v_milieu} et ta finale {v_finale}.',
    'En résumé : une ouverture {v_ouverture}, un milieu de partie {v_milieu}, une finale {v_finale}.',
  ],
  'resume.phases.deux': [
    'Phase par phase : ouverture {v_ouverture}, milieu de partie {v_milieu}.',
    'Le fil de la partie : ouverture {v_ouverture}, puis milieu de partie {v_milieu}.',
    'Ton ouverture a été {v_ouverture}, ton milieu de partie {v_milieu}.',
    'En résumé : une ouverture {v_ouverture}, un milieu de partie {v_milieu}.',
  ],
  'resume.pivot.coup': [
    'Le tournant de la partie : {numero}{coup}.',
    "Le moment clé : {numero}{coup}. C'est là que l'évaluation chute le plus.",
    "Si tu ne dois revoir qu'un seul coup, c'est {numero}{coup}.",
    "La partie s'est jouée sur {numero}{coup}.",
  ],
  // ---------------------------------------------------------------- punchline de l'écran de résumé
  'punchline.victoire.propre': [
    'Victoire nette et sans bavure. Continue comme ça !',
    'Gagnée proprement, du premier au dernier coup.',
    'Rien à redire : tu as dominé cette partie.',
    'Belle victoire, construite coup après coup.',
  ],
  'punchline.victoire.generique': [
    'Victoire ! Regardons les moments qui ont fait basculer la partie de ton côté.',
    'Partie gagnée. Voyons ce qui a fait la différence.',
    "Bien joué, la partie est pour toi. On regarde comment tu l'as gagnée ?",
    "Tu l'emportes. Il reste quand même des choses à apprendre de cette partie.",
  ],
  'punchline.victoire.brouillonne': [
    'Victoire ! Mais le chemin a été mouvementé : voyons où.',
    'Gagnée, mais pas sans frayeurs. On regarde les moments chauds ?',
    'Le point est pour toi. Le chemin, lui, aurait pu être plus simple.',
    'Tu gagnes, et il reste de quoi progresser : le meilleur des deux mondes.',
  ],
  'punchline.defaite.propre': [
    'Tu as bien joué, ton adversaire a simplement été un peu plus précis.',
    'Défaite honorable : peu de fautes, et pourtant le point est parti.',
    'Une bonne partie malgré le résultat. Le détail se joue sur un ou deux coups.',
    'Perdue malgré une bonne tenue. Trouve le coup qui a fait la différence.',
  ],
  'punchline.defaite.generique': [
    "Défaite cette fois-ci. Voyons à quel moment la partie t'a échappé.",
    "Ça n'est pas passé aujourd'hui. Les fautes sont identifiables, allons les voir.",
    'Partie perdue, mais riche en enseignements. On regarde ça ensemble.',
    "Tu t'inclines. Cherchons le moment où tout a basculé.",
  ],
  'punchline.defaite.difficile': [
    'Partie difficile. Deux ou trois leçons à retenir, et on repart.',
    'Ça arrive à tout le monde. Regardons les fautes une par une, sans se presser.',
    "Pas ta meilleure partie, mais sûrement l'une des plus instructives.",
    "On apprend plus d'une défaite que de dix victoires. Au travail, ensemble.",
  ],
  'punchline.nulle.pat': [
    'Partie nulle par pat. Un thème de finale à connaître par cœur.',
    'Pat : le demi-point est partagé. Regardons le dernier coup de près.',
    "Nulle par pat. Voyons si l'un des deux camps pouvait espérer mieux.",
    'Le pat a tranché : match nul. On décortique la finale ?',
  ],
  'punchline.gaffe_unique': [
    'Une partie propre, marquée par un seul coup. Allons le voir.',
    "Tout allait bien, jusqu'à un coup. C'est lui qu'il faut comprendre.",
    "Un seul vrai faux pas dans cette partie. Il mérite deux minutes d'attention.",
    'Presque parfait : une gaffe, une seule, mais elle mérite un vrai regard.',
  ],
  'punchline.ouverture_ratee': [
    "La partie s'est compliquée dès l'ouverture. Revoyons les premiers coups.",
    "Un départ difficile. Quelques principes d'ouverture vont t'aider.",
    "Tout s'est joué très tôt. Les dix premiers coups méritent un vrai coup d'œil.",
    "L'ouverture t'a coûté cher. Bonne nouvelle : c'est la phase la plus facile à corriger.",
  ],
  'punchline.milieu_rate': [
    "Bonne ouverture, puis le milieu de partie s'est compliqué. Voyons où.",
    "Tu sors bien de l'ouverture. C'est ensuite que les choses se gâtent.",
    'Le plan a manqué au milieu de partie. On cherche ensemble le moment où ça déraille ?',
    'Départ solide, suite plus hésitante. Les moments clés vont te montrer pourquoi.',
  ],
  'punchline.finale_ratee': [
    "Tout se jouait en finale, et elle t'a échappé. Ça se travaille très bien.",
    "La finale a fait la différence. Quelques positions types à connaître et c'est réglé.",
    "Bien jusqu'à la finale, moins bien ensuite. Un tour par « Apprendre » s'impose.",
    "C'est en finale que la partie a tourné. Roi actif, pions passés : revoyons les bases.",
  ],
  'punchline.remontee': [
    'Départ compliqué, mais tu as bien redressé la situation ensuite.',
    "L'ouverture a piqué, puis tu as redressé la barre. Bravo pour le sang-froid.",
    "Un début difficile, une suite bien meilleure. C'est une vraie qualité.",
    'Tu as su te battre après un début difficile. Reste à soigner les premiers coups.',
  ],
  'punchline.miniature.gagnee': [
    "Une miniature ! Ton adversaire n'a pas eu le temps de respirer.",
    'Vite fait, bien fait. Regardons comment tu as puni les fautes adverses.',
    'Partie éclair, et pour toi. Belle efficacité.',
    'Gagnée en quelques coups. Retiens le piège, il resservira.',
  ],
  'punchline.miniature.perdue': [
    "Partie très courte. Un piège d'ouverture à connaître, et tu ne retomberas plus dedans.",
    "C'est allé vite. Regardons le coup qui a tout déclenché.",
    "Une défaite éclair : ça pique, mais la leçon se retient d'autant mieux.",
    "Tout s'est joué en quelques coups. Bonne nouvelle : la leçon tient en un coup.",
  ],
  'punchline.generique.excellent': [
    'Une partie très propre. Continue comme ça !',
    "Du jeu précis d'un bout à l'autre. Bravo.",
    "Peu de choses à redire : c'est du beau travail.",
    'Une partie de haut niveau. Savoure, puis on affine.',
  ],
  'punchline.generique.solide': [
    'Une partie solide, avec quelques occasions à ne plus laisser filer.',
    "Du bon jeu dans l'ensemble. Deux ou trois moments méritent un regard.",
    'Solide. Les moments clés te diront où gratter encore.',
    'Bonne partie. Voyons ce qui séparait le bon du très bon.',
  ],
  'punchline.generique.moyen': [
    'Des hauts et des bas : on regarde les moments clés ensemble ?',
    "Une partie contrastée. Les moments clés vont parler d'eux-mêmes.",
    'Du bon et du moins bon. Cherchons ce qui a fait la différence.',
    'Partie en dents de scie. Voyons où la balance a penché.',
  ],
  'punchline.generique.difficile': [
    'Partie compliquée, mais chaque erreur est une leçon. Au travail.',
    'Journée difficile. Les fautes sont nettes, donc faciles à corriger.',
    "Ça n'a pas tourné comme prévu. Regardons pourquoi, calmement.",
    'Dur, mais instructif. On reprend les fautes une par une.',
  ],
  // ---------------------------------------------------------------- entraîneur en direct
  'live.salutation': [
    "C'est parti ! Je commente chaque coup, et on fera le bilan ensemble à la fin.",
    "Bonne partie ! Prends ton temps, il n'y a pas de pendule.",
    'Je suis là si tu veux une indication. À toi de jouer !',
    'On y va. Un seul objectif : comprendre chaque coup que tu joues.',
    'Installe-toi, respire, et joue ton premier coup. Je te suis.',
    'Nouvelle partie ! Avant chaque coup : échecs, prises, menaces.',
  ],
  'live.theorie.premier_coup_centre': [
    '{coup} : tu occupes le centre et tu ouvres des lignes à tes pièces.',
    "{coup}, un grand classique. Le centre d'abord !",
    "Bon départ avec {coup} : de l'espace au centre dès le premier coup.",
    '{coup}. Simple et fort : tu prends ta part du centre.',
  ],
  'live.theorie.premier_coup_souple': [
    '{coup} : un début plus souple. Le centre se disputera un peu plus tard.',
    '{coup}. Tu gardes tes options ouvertes pour le centre.',
    '{coup}. Un premier coup sans pion central : garde un œil sur les cases centrales.',
    "{coup}, pourquoi pas ! L'important sera de bien développer tes pièces.",
  ],
  'live.theorie.ouverture_nommee': [
    '{ouverture} : on entre en terrain connu.',
    '{ouverture}. Un terrain bien balisé.',
    'Cette position a un nom : {ouverture}.',
    '{ouverture}. Des milliers de parties ont commencé ainsi.',
  ],
  'live.theorie.generique': [
    '{coup}, toujours dans la théorie.',
    '{coup} : coup de livre.',
    'La théorie continue avec {coup}.',
    "{coup}. Rien à signaler, c'est connu.",
    '{coup}, comme dans les livres.',
  ],
  'live.joueur.excellent': [
    '{coup} : très bon coup.',
    '{coup}. Précis, rien à redire.',
    'Bien joué, {coup} garde toute ta position.',
    "{coup}, c'est dans le mille.",
    '{coup} : tu ne concèdes rien.',
    'Joli {coup}. Continue comme ça.',
  ],
  'live.joueur.good': [
    '{coup} : correct, ta position reste saine.',
    '{coup} se joue. Il y avait un soupçon mieux, rien de grave.',
    '{coup}. Coup solide.',
    '{coup} : ça tient. Garde un œil sur les menaces adverses.',
    'Pas mal, {coup}. La position reste jouable.',
    '{coup}, un coup raisonnable.',
  ],
  'live.joueur.inaccuracy': [
    '{coup} : il y avait un peu mieux. Rien de grave.',
    '{coup}. Tu lâches un peu de terrain, garde ta concentration.',
    '{coup}, légère imprécision. Regarde bien ce que ton adversaire menace.',
    "Hmm, {coup} n'était pas le plus précis. On en reparlera au bilan.",
    "{coup} : ta position glisse un peu. Rien d'irréparable.",
    '{coup}. Prends une seconde de plus au prochain coup.',
  ],
  'live.joueur.mistake': [
    '{coup} : attention, ça donne de vraies chances à ton adversaire.',
    '{coup} est une erreur. Tu peux annuler le coup si tu veux réessayer.',
    'Aïe, {coup} te coûte du terrain. Vérifie tes pièces non défendues.',
    '{coup}. Ton adversaire a maintenant une occasion : vois-tu laquelle ?',
    "{coup} : ce n'était pas le moment. La partie n'est pas finie, accroche-toi.",
    'Erreur avec {coup}. Respire, et cherche la menace adverse avant de rejouer.',
  ],
  'live.joueur.blunder': [
    '{coup} : ça fait mal. La position vient de basculer.',
    'Gaffe avec {coup}. Tu peux annuler le coup et chercher mieux.',
    '{coup} change tout. Regarde ce que ton adversaire peut jouer maintenant.',
    'Attention, {coup} est une grosse faute. Le bouton Annuler est là pour ça.',
    "{coup}. Aïe. On verra pourquoi au bilan, mais bats-toi jusqu'au bout.",
    '{coup} : ton adversaire a un coup très fort. Le vois-tu ?',
  ],
  'live.joueur.piece_en_prise': [
    { m: "Attention, {piece} n'est pas défendu en {case} !", f: "Attention, {piece} n'est pas défendue en {case} !" },
    '{coup} laisse {piece} en prise en {case}. Tu peux annuler le coup.',
    { m: 'Regarde {piece} en {case} : attaqué, et personne pour le défendre.', f: 'Regarde {piece} en {case} : attaquée, et personne pour la défendre.' },
    'Aïe, {piece} est en prise en {case}. Vérifie toujours tes pièces avant de lâcher le coup.',
  ],
  'live.joueur.mal_defendue': [
    { m: "{Piece} en {case} est attaqué par {attaquant} : l'échange est perdant pour toi.", f: "{Piece} en {case} est attaquée par {attaquant} : l'échange est perdant pour toi." },
    { m: '{coup} laisse {piece} mal défendu en {case}. Tu peux annuler le coup.', f: '{coup} laisse {piece} mal défendue en {case}. Tu peux annuler le coup.' },
    'Compte les attaquants sur {case} : {piece} y perd du matériel.',
    { m: '{Piece} est trop peu défendu en {case}. Une reprise ne suffira pas.', f: '{Piece} est trop peu défendue en {case}. Une reprise ne suffira pas.' },
  ],
  'live.joueur.gain_materiel': [
    '{coup} : tu gagnes {cible}. Bien vu !',
    'Bonne prise ! Tu remportes {cible}.',
    "{coup}, et {cible} disparaît de l'échiquier. Bien joué.",
    "Tu profites de l'occasion : {cible} est pour toi.",
  ],
  'live.joueur.mat': [
    '{coup} : échec et mat ! Bravo !',
    'Échec et mat ! Belle partie.',
    'Mat ! Tu as conclu comme il faut.',
    "{coup}, et c'est mat. Bien joué !",
  ],
  'live.joueur.autorise_mat': [
    'Attention : {reponse} fait mat ! Tu peux annuler le coup.',
    'Ce coup laisse un mat en 1 : {reponse}. Annule et protège ton roi.',
    'Danger : ton adversaire mate avec {reponse}.',
    'Mat en 1 pour ton adversaire ({reponse}). Le bouton Annuler est là pour ça.',
  ],
  'live.joueur.autorise_mat_n': [
    'Attention : ton adversaire a maintenant un mat forcé en {n}.',
    'Ce coup ouvre la porte à un mat en {n}. Tu peux annuler le coup.',
    'Danger pour ton roi : mat forcé en {n} pour ton adversaire.',
    'Ton roi est en grand danger : mat en {n} au plus. Annule si tu veux réessayer.',
  ],
  'live.joueur.autorise_fourchette': [
    'Attention : {reponse} ferait une fourchette sur {cible} et {cible2}.',
    'Ce coup permet {reponse}, qui attaque {cible} et {cible2} à la fois.',
    'Gare à la fourchette : {reponse} viserait {cible} et {cible2}. Tu peux annuler.',
    'Danger : {reponse} prendrait {cible} et {cible2} en fourchette.',
  ],
  'live.joueur.mat_manque': [
    'Il y avait mat en 1 avec {meilleur} !',
    '{meilleur} faisait mat. Cherche toujours les échecs en premier.',
    'Mat en 1 manqué : {meilleur}. Tu peux annuler et le jouer.',
    'Regarde mieux : {meilleur} terminait la partie (mat en 1).',
  ],
  'live.joueur.fourchette_manquee': [
    '{meilleur} faisait une fourchette sur {cible} et {cible2}.',
    'Fourchette manquée : {meilleur} attaquait {cible} et {cible2}.',
    'Il y avait une double attaque : {meilleur}, sur {cible} et {cible2}.',
    { m: 'Regarde {meilleur} : {cible} et {cible2} étaient pris en fourchette.', f: 'Regarde {meilleur} : {cible} et {cible2} étaient prises en fourchette.' },
  ],
  'live.joueur.fourchette': [
    'Fourchette ! Tu attaques {cible} et {cible2} en même temps.',
    'Double attaque sur {cible} et {cible2}. Bien vu !',
    { m: 'Belle fourchette : {cible} et {cible2} sont visés.', f: 'Belle fourchette : {cible} et {cible2} sont visées.' },
    "Fourchette sur {cible} et {cible2} : ton adversaire ne pourra pas tout sauver.",
  ],
  'live.joueur.clouage': [
    { m: 'Clouage : {cible} est cloué sur {cible2}.', f: 'Clouage : {cible} est clouée sur {cible2}.' },
    'Tu cloues {cible} devant {cible2}. Ajoute un attaquant dessus !',
    'Bon clouage : {cible2} est juste derrière {cible}.',
    { m: '{Cible} est cloué : s\'il bouge, {cible2} est à découvert.', f: '{Cible} est clouée : si elle bouge, {cible2} est à découvert.' },
  ],
  'live.joueur.roque': [
    "{coup} : roi à l'abri, tour en jeu. Parfait.",
    'Bon roque. Ton roi est en sécurité.',
    "{coup}. Tu peux maintenant penser à l'attaque.",
    'Roque effectué. Une chose de moins à surveiller.',
  ],
  'live.adversaire.best': [
    '{coup}. Ton adversaire joue juste, reste sur tes gardes.',
    '{coup} : bonne réponse en face. À toi de trouver un plan.',
    '{coup}. Pas de cadeau : améliore ta pièce la moins bien placée.',
    'Ton adversaire répond {coup}. Que menace ce coup ?',
    "{coup}. Coup sérieux. Prends le temps de regarder ce qu'il prépare.",
    "{coup} : c'est solide en face. Poursuis ton plan.",
  ],
  'live.adversaire.neutre': [
    '{coup}. À toi : échecs, prises, menaces ?',
    "Ton adversaire joue {coup}. Rien d'inquiétant, poursuis ton plan.",
    '{coup}. Regarde ce que ce coup change avant de répondre.',
    '{coup} en face. Une pièce adverse est-elle moins bien défendue maintenant ?',
    "{coup}. Pas le plus précis. Cherche ce qu'il te laisse.",
    'Réponse adverse : {coup}. À toi de jouer.',
  ],
  'live.adversaire.mistake': [
    '{coup} est une erreur. Cherche le coup qui en profite !',
    'Ton adversaire vient de se tromper avec {coup}. Prends ton temps.',
    '{coup} : ton adversaire te laisse une chance. Regarde bien.',
    'Occasion ! {coup} affaiblit la position adverse.',
  ],
  'live.adversaire.blunder': [
    '{coup} est une gaffe ! Il y a quelque chose de fort à jouer.',
    'Grosse faute en face avec {coup}. Échecs, prises, menaces : cherche bien.',
    "{coup} : ton adversaire t'offre une belle occasion. Ne joue pas trop vite !",
    'Cadeau avec {coup}. Trouve le coup qui punit.',
  ],
  'live.adversaire.piece_en_prise': [
    { m: "Regarde bien : {cible} adverse n'est pas défendu en {case}.", f: "Regarde bien : {cible} adverse n'est pas défendue en {case}." },
    "{coup} laisse {cible} en prise en {case}. À toi d'en profiter !",
    { m: '{Cible} adverse est attaqué en {case}, sans défenseur. Vois-tu le coup ?', f: '{Cible} adverse est attaquée en {case}, sans défenseur. Vois-tu le coup ?' },
    "Il y a du matériel à prendre en {case}. Vérifie juste que ce n'est pas un piège.",
  ],
  'live.adversaire.echec': [
    "Échec ! Trois parades possibles : bouger le roi, interposer une pièce ou capturer l'attaquant.",
    '{coup}, échec. Choisis la parade qui améliore aussi ta position.',
    'Ton roi est en échec. Pas de panique, regarde toutes les parades.',
    'Échec avec {coup}. La meilleure parade est souvent celle qui développe une pièce.',
  ],
  'live.adversaire.capture': [
    'Ton adversaire prend {cible}. Peux-tu reprendre ?',
    '{coup} : {cible} disparaît. Regarde si une reprise est possible.',
    "{coup}. Avant de reprendre, vérifie s'il n'y a pas encore mieux.",
    'Prise en face. Compte le matériel, puis choisis ta réponse.',
  ],
  'live.adversaire.fourchette': [
    { m: 'Fourchette adverse : {cible} et {cible2} sont attaqués en même temps.', f: 'Fourchette adverse : {cible} et {cible2} sont attaquées en même temps.' },
    'Attention, double attaque sur {cible} et {cible2}. Limite la casse.',
    'Ton adversaire fait une fourchette sur {cible} et {cible2}.',
    { m: 'Fourchette ! {cible} et {cible2} sont attaqués par la même pièce.', f: 'Fourchette ! {cible} et {cible2} sont attaquées par la même pièce.' },
  ],
  'live.adversaire.mat': [
    '{coup} : échec et mat. La partie est finie, on en tire les leçons au bilan.',
    "Mat. Ton roi n'avait plus de case. Le bilan te montrera où ça s'est joué.",
    'Échec et mat contre toi. Ça arrive : le bilan va nous dire pourquoi.',
    "{coup}, et c'est mat. Courage, on regarde ça ensemble tout de suite.",
  ],
  'live.pat': [
    "Pat ! Aucun coup légal, pas d'échec : partie nulle.",
    "C'est pat : la partie est nulle.",
    "Pat. Le roi n'a plus de coup légal sans être en échec : nulle.",
    'Partie nulle par pat.',
  ],
}

// Hachage mélangé : deux index consécutifs (ou espacés de 2, un coup sur deux étant au joueur)
// tombent sur des variantes différentes bien plus souvent qu'un simple modulo, qui alternerait
// entre deux phrases dès que le nombre de variantes est pair.
export function mix(a: number, b: number): number {
  let h = (Math.imul(a + 1, 0x9e3779b1) ^ Math.imul(b + 0x7f4a7c15, 0x85ebca6b)) >>> 0
  h ^= h >>> 15
  h = Math.imul(h, 0x2c1b3c6d) >>> 0
  h ^= h >>> 12
  h = Math.imul(h, 0x297a2d39) >>> 0
  h ^= h >>> 15
  return h >>> 0
}

// Typographie française : espace fine insécable avant ! ? ; et espace insécable avant : % »
// et après «. Les phrases de la banque sont écrites avec des espaces ordinaires, c'est ici
// qu'elles deviennent insécables (plus sûr que des caractères invisibles dans le source).
export function typo(text: string): string {
  return text
    .replace(/ ([!?;])/g, ' $1')
    .replace(/ ([:%»])/g, ' $1')
    .replace(/« /g, '« ')
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export type Vars = Record<string, string | number>

// Remplit les marqueurs ; {Piece} et {Cible} prennent la majuscule de leur minuscule si absents.
export function fill(template: string, vars: Vars): string {
  return template.replace(/\{([A-Za-z_0-9]+)\}/g, (_, key: string) => {
    if (key in vars) return String(vars[key])
    const lower = key.charAt(0).toLowerCase() + key.slice(1)
    if (lower in vars) return capitalize(String(vars[lower]))
    return `{${key}}`
  })
}

// Choix déterministe d'une variante : hachage de (index, graine), en sautant la dernière
// variante servie pour la même situation. Un Picker par bilan (ou par appel en direct).
export class Picker {
  private last = new Map<string, number>()
  private readonly seed: number

  constructor(seed = 0) {
    this.seed = seed
  }

  say(key: string, index: number, vars: Vars = {}, gender: Gender = 'm'): string {
    const variants = PHRASES[key]
    if (!variants) throw new Error(`situation inconnue : ${key}`)
    // Seules les variantes dont tous les marqueurs sont fournis sont candidates : jamais de
    // « {piece} » ni de « Le moteur préférait , mais » à l'écran.
    const texts = variants.map((v) => fill(typeof v === 'string' ? v : v[gender], vars))
    const ok = texts.map((t, i) => (/\{[A-Za-z_0-9]+\}/.test(t) ? -1 : i)).filter((i) => i >= 0)
    if (ok.length === 0) throw new Error(`marqueur manquant pour ${key}`)
    const n = ok.length
    let pos = mix(index, this.seed) % n
    if (n > 1 && this.last.get(key) === ok[pos]) pos = (pos + 1) % n
    this.last.set(key, ok[pos])
    return typo(texts[ok[pos]])
  }
}
