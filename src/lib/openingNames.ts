// Traduction française des noms d'ouvertures lichess (src/data/openings.json).
// Entrée : « Famille: Variante, Sous-variante » ; sortie : « Famille · variante, sous-variante ».
//
// Principes :
// 1. La famille est cherchée par égalité EXACTE (table FAMILIES) ; les précisions de famille
//    (« King's Indian Attack, with Bf5 ») sont traduites segment par segment.
// 2. Chaque segment de variante est analysé : [modificateurs] TÊTE [participes]. La tête
//    (Variation, Defense, Attack...) passe devant en français, les adjectifs s'accordent avec
//    elle, les noms propres restent tels quels.
// 3. Les coups SAN cités dans les noms (« with Bf5 ») passent en notation française (« avec Ff5 »).
// 4. Surnoms : traduits quand l'usage français est établi (Dragon, Hérisson, Foie frit) ou quand
//    c'est un nom commun sans double sens (Morse, Baleine, dame vagabonde) ; conservés tels quels
//    quand c'est un jeu de mots, de l'argot ou un patronyme possible (Wuss, Clam, Hillbilly, Edge).
// 5. Tout mot inconnu est un nom propre et reste tel quel (Najdorf, Winawer, Maróczy).

type Genre = 'm' | 'f'
type Adj = readonly [m: string, f: string]

// ---------------------------------------------------------------------------
// 1. Familles : la partie avant « : », sans les précisions « , with ... »
// ---------------------------------------------------------------------------
const FAMILIES: Record<string, string> = {
  'Alekhine Defense': 'Défense Alekhine',
  'Amar Opening': 'Ouverture Amar',
  'Amazon Attack': "Attaque de l'Amazone",
  'Amsterdam Attack': "Attaque d'Amsterdam",
  "Anderssen's Opening": 'Ouverture Anderssen',
  'Australian Defense': 'Défense australienne',
  'Barnes Defense': 'Défense Barnes',
  'Barnes Opening': 'Ouverture Barnes',
  'Basque Opening': 'Ouverture basque',
  'Benko Gambit': 'Gambit Benko',
  'Benko Gambit Accepted': 'Gambit Benko accepté',
  'Benko Gambit Declined': 'Gambit Benko refusé',
  'Benoni Defense': 'Défense Benoni',
  'Bird Opening': 'Ouverture Bird',
  "Bishop's Opening": 'Début du fou',
  'Blackmar-Diemer Gambit': 'Gambit Blackmar-Diemer',
  'Blackmar-Diemer Gambit Accepted': 'Gambit Blackmar-Diemer accepté',
  'Blackmar-Diemer Gambit Declined': 'Gambit Blackmar-Diemer refusé',
  'Blumenfeld Countergambit': 'Contre-gambit Blumenfeld',
  'Blumenfeld Countergambit Accepted': 'Contre-gambit Blumenfeld accepté',
  'Bogo-Indian Defense': 'Défense bogo-indienne',
  'Bongcloud Attack': 'Attaque Bongcloud',
  'Borg Defense': 'Défense Borg',
  'Canard Opening': 'Ouverture Canard',
  'Caro-Kann Defense': 'Défense Caro-Kann',
  'Carr Defense': 'Défense Carr',
  'Catalan Opening': 'Ouverture catalane',
  'Center Game': 'Partie du centre',
  'Center Game Accepted': 'Partie du centre acceptée',
  'Clemenz Opening': 'Ouverture Clemenz',
  'Colle System': 'Système Colle',
  'Creepy Crawly Formation': 'Formation Creepy Crawly',
  'Czech Defense': 'Défense tchèque',
  'Danish Gambit': 'Gambit danois',
  'Danish Gambit Accepted': 'Gambit danois accepté',
  'Danish Gambit Declined': 'Gambit danois refusé',
  'Dresden Opening': 'Ouverture de Dresde',
  'Duras Gambit': 'Gambit Duras',
  'Dutch Defense': 'Défense hollandaise',
  'Döry Defense': 'Défense Döry',
  // 1.d4 Cf6 2.Cf3 g6 : la glose distingue de la King's Indian sans inventer un nom.
  'East Indian Defense': 'Défense est-indienne (sans c4)',
  'Elephant Gambit': "Gambit de l'Éléphant",
  'English Defense': 'Défense anglaise',
  // « Partie anglaise » et « Ouverture Réti » : titres Wikipédia FR, libellés déjà affichés par l'app.
  'English Opening': 'Partie anglaise',
  'English Orangutan': 'Orang-outan anglais',
  'Englund Gambit': 'Gambit Englund',
  'Englund Gambit Declined': 'Gambit Englund refusé',
  Formation: 'Formation',
  'Four Knights Game': 'Partie des quatre cavaliers',
  'French Defense': 'Défense française',
  'Fried Fox Defense': 'Défense Fried Fox',
  'Global Opening': 'Ouverture globale',
  'Goldsmith Defense': 'Défense Goldsmith',
  'Grob Opening': 'Ouverture Grob',
  'Grünfeld Defense': 'Défense Grünfeld',
  'Gunderam Defense': 'Défense Gunderam',
  'Hippopotamus Defense': 'Défense Hippopotame',
  'Horwitz Defense': 'Défense Horwitz',
  'Hungarian Opening': 'Ouverture hongroise',
  'Indian Defense': 'Défense indienne',
  'Irish Gambit': 'Gambit irlandais',
  'Italian Game': 'Partie italienne',
  'Kangaroo Defense': 'Défense Kangourou',
  "King's Gambit": 'Gambit du roi',
  "King's Gambit Accepted": 'Gambit du roi accepté',
  "King's Gambit Declined": 'Gambit du roi refusé',
  "King's Indian Attack": 'Attaque est-indienne',
  "King's Indian Defense": 'Défense est-indienne',
  "King's Knight Opening": 'Début du cavalier roi',
  "King's Pawn Game": 'Début du pion roi',
  "King's Pawn Opening": 'Ouverture du pion roi',
  'Kádas Opening': 'Ouverture Kádas',
  'Lasker Simul Special': 'Spéciale simultanée Lasker',
  'Latvian Gambit': 'Gambit letton',
  'Latvian Gambit Accepted': 'Gambit letton accepté',
  'Lemming Defense': 'Défense Lemming',
  'Lion Defense': 'Défense du Lion',
  'London System': 'Système de Londres',
  'Marienbad System': 'Système de Marienbad',
  'Mexican Defense': 'Défense mexicaine',
  'Mieses Opening': 'Ouverture Mieses',
  'Mikenas Defense': 'Défense Mikenas',
  'Modern Defense': 'Défense moderne',
  'Montevideo Defense': 'Défense de Montevideo',
  'Neo-Grünfeld Defense': 'Défense néo-Grünfeld',
  'Nimzo-Indian Defense': 'Défense nimzo-indienne',
  'Nimzo-Larsen Attack': 'Attaque Nimzo-Larsen',
  'Nimzowitsch Defense': 'Défense Nimzowitsch',
  'Old Indian Defense': 'Défense vieille-indienne',
  'Owen Defense': 'Défense Owen',
  'Paleface Attack': 'Attaque Paleface',
  // « Défense Petrov » plutôt que « Défense russe » : titre Wikipédia FR, usage des commentateurs.
  "Petrov's Defense": 'Défense Petrov',
  'Philidor Defense': 'Défense Philidor',
  'Pirc Defense': 'Défense Pirc',
  'Polish Defense': 'Défense polonaise',
  'Polish Opening': 'Ouverture polonaise',
  'Ponziani Opening': 'Ouverture Ponziani',
  'Portuguese Opening': 'Ouverture portugaise',
  "Pseudo Queen's Indian Defense": 'Défense pseudo-ouest-indienne',
  'Pterodactyl Defense': 'Défense Ptérodactyle',
  "Queen's Gambit": 'Gambit dame',
  "Queen's Gambit Accepted": 'Gambit dame accepté',
  "Queen's Gambit Declined": 'Gambit dame refusé',
  "Queen's Indian Accelerated": 'Défense ouest-indienne accélérée',
  "Queen's Indian Defense": 'Défense ouest-indienne',
  "Queen's Pawn": 'Début du pion dame',
  "Queen's Pawn Game": 'Début du pion dame',
  'Rapport-Jobava System': 'Système Rapport-Jobava',
  'Rat Defense': 'Défense du Rat',
  'Richter-Veresov Attack': 'Attaque Richter-Veresov',
  'Robatsch Defense': 'Défense Robatsch',
  'Rubinstein Opening': 'Ouverture Rubinstein',
  'Ruy Lopez': 'Partie espagnole',
  'Réti Opening': 'Ouverture Réti',
  'Saragossa Opening': 'Ouverture de Saragosse',
  'Scandinavian Defense': 'Défense scandinave',
  'Scotch Game': 'Partie écossaise',
  'Semi-Slav Defense': 'Défense semi-slave',
  'Semi-Slav Defense Accepted': 'Défense semi-slave acceptée',
  'Sicilian Defense': 'Défense sicilienne',
  'Slav Defense': 'Défense slave',
  'Slav Indian': 'Défense slavo-indienne',
  'Sodium Attack': 'Attaque Sodium',
  'St. George Defense': 'Défense Saint-Georges',
  'Tarrasch Defense': 'Défense Tarrasch',
  'Three Knights Opening': 'Partie des trois cavaliers',
  'Torre Attack': 'Attaque Torre',
  'Trompowsky Attack': 'Attaque Trompowsky',
  'Valencia Opening': 'Ouverture de Valence',
  "Van't Kruijs Opening": "Ouverture Van't Kruijs",
  'Van Geet Opening': 'Ouverture Van Geet',
  'Vienna Gambit': 'Gambit viennois',
  'Vienna Game': 'Partie viennoise',
  'Vulture Defense': 'Défense du Vautour',
  'Wade Defense': 'Défense Wade',
  'Ware Defense': 'Défense Ware',
  'Ware Opening': 'Ouverture Ware',
  'Yusupov-Rubinstein System': 'Système Youssoupov-Rubinstein',
  'Zaire Defense': 'Défense du Zaïre',
  'Zukertort Defense': 'Défense Zukertort',
  'Zukertort Opening': 'Ouverture Zukertort',
}

// ---------------------------------------------------------------------------
// 2. Têtes de segment : le mot qui passe DEVANT en français, avec son genre
// ---------------------------------------------------------------------------
const HEADS: Record<string, readonly [string, Genre]> = {
  Variation: ['variante', 'f'],
  Variations: ['variantes', 'f'],
  Defense: ['défense', 'f'],
  Defenses: ['défenses', 'f'],
  Attack: ['attaque', 'f'],
  Gambit: ['gambit', 'm'],
  Countergambit: ['contre-gambit', 'm'],
  Counterattack: ['contre-attaque', 'f'],
  Counterthrust: ['contre-poussée', 'f'],
  System: ['système', 'm'],
  System3: ['système', 'm'], // coquille des données lichess (« Spassky System3 »)
  Line: ['ligne', 'f'],
  Opening: ['ouverture', 'f'],
  Game: ['partie', 'f'],
  Trap: ['piège', 'm'],
  Formation: ['formation', 'f'],
  Sacrifice: ['sacrifice', 'm'],
  Mate: ['mat', 'm'],
  Hybrid: ['hybride', 'm'],
  Refutation: ['réfutation', 'f'],
  Connection: ['connexion', 'f'],
  Transfer: ['transfert', 'm'],
  Extension: ['extension', 'f'],
  Symmetry: ['symétrie', 'f'],
  Plan: ['plan', 'm'],
  Push: ['poussée', 'f'],
  Break: ['rupture', 'f'], // « Central Break » -> « rupture centrale »
  Swap: ['échange', 'm'],
  Pterodactyl: ['Ptérodactyle', 'm'], // « Queen Pterodactyl » -> « Ptérodactyle de la dame »
}

// Têtes au pluriel : les adjectifs prennent la marque du pluriel (« variantes modernes »).
const HEADS_PLURIEL = new Set(['Variations', 'Deviations', 'Defenses'])

// Participes placés APRÈS la tête en anglais (« Evans Gambit Accepted »).
const POST: Record<string, Adj> = {
  Accepted: ['accepté', 'acceptée'],
  Declined: ['refusé', 'refusée'],
  Deferred: ['différé', 'différée'],
  Reversed: ['inversé', 'inversée'],
}

// ---------------------------------------------------------------------------
// 3. Adjectifs (accordés avec la tête). Les clés peuvent faire plusieurs mots.
// ---------------------------------------------------------------------------
const ADJ: Record<string, Adj> = {
  // qualificatifs
  Accelerated: ['accéléré', 'accélérée'],
  Hyperaccelerated: ['hyper-accéléré', 'hyper-accélérée'],
  Delayed: ['retardé', 'retardée'],
  'Ultra-Delayed': ['ultra-retardé', 'ultra-retardée'],
  Deferred: ['différé', 'différée'],
  Reversed: ['inversé', 'inversée'],
  Inverted: ['inversé', 'inversée'],
  Extended: ['étendu', 'étendue'],
  Classical: ['classique', 'classique'],
  'Anti-Classical': ['anti-classique', 'anti-classique'],
  Accepted: ['accepté', 'acceptée'],
  Declined: ['refusé', 'refusée'],
  'Semi-Classical': ['semi-classique', 'semi-classique'],
  'Neo-Classical': ['néo-classique', 'néo-classique'],
  Modern: ['moderne', 'moderne'],
  'Neo-Modern': ['néo-moderne', 'néo-moderne'],
  'Anti-Modern': ['anti-moderne', 'anti-moderne'],
  Closed: ['fermé', 'fermée'],
  Open: ['ouvert', 'ouverte'],
  Main: ['principal', 'principale'],
  Old: ['ancien', 'ancienne'],
  New: ['nouveau', 'nouvelle'],
  Normal: ['normal', 'normale'],
  Standard: ['standard', 'standard'],
  Original: ['original', 'originale'],
  Orthodox: ['orthodoxe', 'orthodoxe'],
  'Neo-Orthodox': ['néo-orthodoxe', 'néo-orthodoxe'],
  Traditional: ['traditionnel', 'traditionnelle'],
  Symmetrical: ['symétrique', 'symétrique'],
  'Ultra-Symmetrical': ['ultra-symétrique', 'ultra-symétrique'],
  Symmetric: ['symétrique', 'symétrique'],
  Quiet: ['tranquille', 'tranquille'],
  Slow: ['lent', 'lente'],
  Positional: ['positionnel', 'positionnelle'],
  Transpositional: ['transpositionnel', 'transpositionnelle'],
  Dynamic: ['dynamique', 'dynamique'],
  Fluid: ['fluide', 'fluide'],
  Flexible: ['flexible', 'flexible'],
  Forcing: ['forçant', 'forçante'],
  Defensive: ['défensif', 'défensive'],
  Primitive: ['primitif', 'primitive'],
  Provincial: ['provincial', 'provinciale'],
  Immediate: ['immédiat', 'immédiate'],
  Early: ['précoce', 'précoce'],
  Rare: ['rare', 'rare'],
  Forgotten: ['oublié', 'oubliée'],
  Wild: ['sauvage', 'sauvage'],
  Shy: ['timide', 'timide'],
  Lesser: ['petit', 'petite'],
  Great: ['grand', 'grande'],
  Big: ['grand', 'grande'],
  Small: ['petit', 'petite'],
  Full: ['complet', 'complète'],
  Improved: ['amélioré', 'améliorée'],
  Compromised: ['compromis', 'compromise'],
  Long: ['long', 'longue'],
  Sharp: ['aigu', 'aiguë'],
  Double: ['double', 'double'],
  Central: ['central', 'centrale'],
  Eastern: ['oriental', 'orientale'],
  Western: ['occidental', 'occidentale'],
  First: ['premier', 'première'],
  Second: ['second', 'seconde'],
  Martian: ['martien', 'martienne'],
  // nationalités, régions, villes adjectivées
  American: ['américain', 'américaine'],
  Arctic: ['arctique', 'arctique'],
  Argentine: ['argentin', 'argentine'],
  Argentinian: ['argentin', 'argentine'],
  Armenian: ['arménien', 'arménienne'],
  Australian: ['australien', 'australienne'],
  Austrian: ['autrichien', 'autrichienne'],
  Baltic: ['balte', 'balte'],
  Basque: ['basque', 'basque'],
  Bavarian: ['bavarois', 'bavaroise'],
  Berlin: ['berlinois', 'berlinoise'],
  Bulgarian: ['bulgare', 'bulgare'],
  Catalan: ['catalan', 'catalane'],
  Chinese: ['chinois', 'chinoise'],
  Czech: ['tchèque', 'tchèque'],
  Danish: ['danois', 'danoise'],
  Dutch: ['hollandais', 'hollandaise'],
  English: ['anglais', 'anglaise'],
  Finnish: ['finlandais', 'finlandaise'],
  Florentine: ['florentin', 'florentine'],
  French: ['français', 'française'],
  German: ['allemand', 'allemande'],
  Hungarian: ['hongrois', 'hongroise'],
  Icelandic: ['islandais', 'islandaise'],
  Indian: ['indien', 'indienne'],
  Italian: ['italien', 'italienne'],
  Kazakh: ['kazakh', 'kazakhe'],
  Lithuanian: ['lituanien', 'lituanienne'],
  Mediterranean: ['méditerranéen', 'méditerranéenne'],
  Mexican: ['mexicain', 'mexicaine'],
  Norwegian: ['norvégien', 'norvégienne'],
  Polish: ['polonais', 'polonaise'],
  Portuguese: ['portugais', 'portugaise'],
  Romanian: ['roumain', 'roumaine'],
  Russian: ['russe', 'russe'],
  Scandinavian: ['scandinave', 'scandinave'],
  Scotch: ['écossais', 'écossaise'],
  Siberian: ['sibérien', 'sibérienne'],
  Sicilian: ['sicilien', 'sicilienne'],
  Slav: ['slave', 'slave'],
  Spanish: ['espagnol', 'espagnole'],
  Swedish: ['suédois', 'suédoise'],
  Swiss: ['suisse', 'suisse'],
  Ukrainian: ['ukrainien', 'ukrainienne'],
  Valencian: ['valencien', 'valencienne'],
  Vienna: ['viennois', 'viennoise'],
  Viennese: ['viennois', 'viennoise'],
  Westphalian: ['westphalien', 'westphalienne'],
  Yugoslav: ['yougoslave', 'yougoslave'],
  // composés
  'Semi-Slav': ['semi-slave', 'semi-slave'],
  'Pseudo-Slav': ['pseudo-slave', 'pseudo-slave'],
  'Pseudo-Austrian': ['pseudo-autrichien', 'pseudo-autrichienne'],
  'Pseudo-Scandinavian': ['pseudo-scandinave', 'pseudo-scandinave'],
  'Pseudo-Spanish': ['pseudo-espagnol', 'pseudo-espagnole'],
  'Anglo-Indian': ['anglo-indien', 'anglo-indienne'],
  'Anglo-Slav': ['anglo-slave', 'anglo-slave'],
  'Anglo-Dutch': ['anglo-hollandais', 'anglo-hollandaise'],
  'Anglo-Scandinavian': ['anglo-scandinave', 'anglo-scandinave'],
  'Anglo-Lithuanian': ['anglo-lituanien', 'anglo-lituanienne'],
  'Double-Dutch': ['double-hollandais', 'double-hollandaise'],
  'Anti-English': ['anti-anglais', 'anti-anglaise'],
  'Batavo-Polish': ['batavo-polonais', 'batavo-polonaise'],
  'Icelandic-Palme': ['islandais-Palme', 'islandaise-Palme'],
  'Franco-Sicilian': ['franco-sicilien', 'franco-sicilienne'],
  'Anti-Nimzo-Indian': ['anti-nimzo-indien', 'anti-nimzo-indienne'],
  'Nimzo-Dutch': ['nimzo-hollandais', 'nimzo-hollandaise'],
  'Nimzo-English': ['nimzo-anglais', 'nimzo-anglaise'],
  'Nimzo-American': ['nimzo-américain', 'nimzo-américaine'],
  'Czech-Indian': ['tchéco-indien', 'tchéco-indienne'],
  'Benoni-Indian': ['Benoni-indien', 'Benoni-indienne'],
  'Spielmann-Indian': ['Spielmann-indien', 'Spielmann-indienne'],
  'Tartakower-Indian': ['Tartakower-indien', 'Tartakower-indienne'],
  'Dzindzi-Indian': ['Dzindzi-indien', 'Dzindzi-indienne'],
  'Neo-Catalan': ['néo-catalan', 'néo-catalane'],
  'Pseudo-Catalan': ['pseudo-catalan', 'pseudo-catalane'],
  'Old Indian': ['vieil-indien', 'vieille-indienne'],
  'West Indian': ['ouest-indien', 'ouest-indienne'],
  "King's Indian": ['est-indien', 'est-indienne'],
  "Queen's Indian": ['ouest-indien', 'ouest-indienne'],
  "Anti-Queen's Indian": ['anti-ouest-indien', 'anti-ouest-indienne'],
  "King's English": ['anglais du roi', 'anglaise du roi'],
}

// Adjectifs qui se placent AVANT le nom en français (« double gambit Muzio », « ancienne défense Steinitz »).
const ADJ_AVANT = new Set(['Old', 'New', 'Great', 'Big', 'Small', 'Lesser', 'Double'])
// Participes et états qui passent APRÈS la nationalité (« défense berlinoise ouverte », pas « ouverte berlinoise »).
const ADJ_FIN = new Set(['Open', 'Closed', 'Reversed', 'Inverted', 'Delayed', 'Deferred', 'Accepted', 'Declined', 'Accelerated'])

// ---------------------------------------------------------------------------
// 4. Compléments invariables (« X Variation » -> « variante <complément> »).
//    Les clés peuvent faire plusieurs mots ; la plus longue gagne.
// ---------------------------------------------------------------------------
const COMPLEMENTS: Record<string, string> = {
  // pièces et cases
  'Two Knights': 'des deux cavaliers',
  'Three Knights': 'des trois cavaliers',
  'Four Knights': 'des quatre cavaliers',
  'Two Pawns': 'des deux pions',
  'Three Pawns': 'des trois pions',
  // Clés composées : l'adjectif qualifie le complément, pas la tête (« Big Center Variation »
  // -> « variante du grand centre », et non « grande variante du centre »).
  'Big Center': 'du grand centre',
  'Small Center': 'du petit centre',
  'New England': 'de Nouvelle-Angleterre',
  'Bishop Check': "de l'échec du fou",
  Check: "de l'échec",
  "Knight's Tour": 'du parcours du cavalier',
  'Four Pawns': 'des quatre pions',
  'Six Pawns': 'des six pions',
  'Poisoned Pawn': 'du pion empoisonné',
  'Double Fianchetto': 'du double fianchetto',
  "King's Knight": 'du cavalier roi',
  "King's Knight's": 'du cavalier roi',
  "Queen's Knight": 'du cavalier dame',
  "King's Bishop": 'du fou roi',
  "King's Pawn": 'du pion roi',
  "King's Head": 'de la Tête du roi',
  "King's": 'du roi',
  "Queen's": 'de la dame',
  "Bishop's": 'du fou',
  "Knight's": 'du cavalier',
  King: 'du roi',
  Queen: 'de la dame',
  Bishop: 'du fou',
  Knight: 'du cavalier',
  Knights: 'des cavaliers',
  Rook: 'de la tour',
  Pawn: 'du pion',
  Pawns: 'des pions',
  Center: 'du centre',
  Wing: "de l'aile",
  Flank: "de l'aile",
  Kingside: "de l'aile roi",
  Queenside: "de l'aile dame",
  // idées de jeu
  Exchange: "d'échange",
  Advance: "d'avance",
  Fianchetto: 'du fianchetto',
  Retreat: 'de retraite',
  Pin: 'du clouage',
  Unpin: 'du déclouage',
  Castling: 'du roque',
  Bayonet: 'à la baïonnette',
  Hedgehog: 'du Hérisson',
  Dragon: 'du Dragon',
  Halloween: "d'Halloween",
  Outflank: 'de débordement',
  Correspondence: 'par correspondance',
  Push: 'de la poussée',
  Battery: 'de la batterie',
  Development: 'du développement',
  Blockade: 'du blocus',
  Counterthrust: 'de la contre-poussée',
  Endgame: 'de la finale',
  "St. Patrick's": 'de la Saint-Patrick',
  'Bradley Beach': 'de Bradley Beach',
  Cambridge: 'de Cambridge',
  // bestiaire : noms communs sans double sens, traduits littéralement
  Pterodactyl: 'du Ptérodactyle',
  Hippopotamus: "de l'Hippopotame",
  Lion: 'du Lion',
  "Lion's Jaw": 'de la Gueule du lion',
  Snake: 'du Serpent',
  'Great Snake': 'du Grand Serpent',
  Lizard: 'du Lézard',
  Crab: 'du Crabe',
  Wolf: 'du Loup',
  Hawk: 'du Faucon',
  Snail: "de l'Escargot",
  Dodo: 'du Dodo',
  Tortoise: 'de la Tortue',
  Crocodile: 'du Crocodile',
  Giraffe: 'de la Girafe',
  Penguin: 'du Pingouin',
  Porcupine: 'du Porc-épic',
  Mongoose: 'de la Mangouste',
  Mosquito: 'du Moustique',
  Wasp: 'de la Guêpe',
  Horsefly: 'du Taon',
  Lobster: 'du Homard',
  Unicorn: 'de la Licorne',
  Monster: 'du Monstre',
  Nightingale: 'du Rossignol',
  Kingfisher: 'du Martin-pêcheur',
  Cormorant: 'du Cormoran',
  Woodchuck: 'de la Marmotte',
  Chameleon: 'du Caméléon',
  // lieux (usage français : « variante de Scheveningue », « variante de Méran »)
  Agincourt: "d'Azincourt",
  Aachen: "d'Aix-la-Chapelle",
  Amsterdam: "d'Amsterdam",
  Barmen: 'de Barmen',
  Belgrade: 'de Belgrade',
  Bled: 'de Bled',
  Brooklyn: 'de Brooklyn',
  Brussels: 'de Bruxelles',
  Budapest: 'de Budapest',
  'Buenos Aires': 'de Buenos Aires',
  Everglades: 'des Everglades',
  Pyrenees: 'des Pyrénées',
  Carlsbad: 'de Carlsbad',
  'Cambridge Springs': 'de Cambridge Springs',
  Chelyabinsk: 'de Tcheliabinsk',
  Colorado: 'du Colorado',
  Copenhagen: 'de Copenhague',
  Cracow: 'de Cracovie',
  Edinburgh: "d'Édimbourg",
  England: "d'Angleterre",
  Frankfurt: 'de Francfort',
  Goteborg: 'de Göteborg',
  Haiti: "d'Haïti",
  Hastings: "d'Hastings",
  Kiel: 'de Kiel',
  Leningrad: 'de Leningrad',
  Lisbon: 'de Lisbonne',
  London: 'de Londres',
  Manhattan: 'de Manhattan',
  'Mar del Plata': 'de Mar del Plata',
  Marienbad: 'de Marienbad',
  Meran: 'de Méran',
  'Monte Carlo': 'de Monte-Carlo',
  Moscow: 'de Moscou',
  Netherlands: 'des Pays-Bas',
  'New York': 'de New York',
  Novosibirsk: 'de Novossibirsk',
  Nürnberg: 'de Nuremberg',
  Paris: 'de Paris',
  Parma: 'de Parme',
  Prague: 'de Prague',
  Riga: 'de Riga',
  'Rio de Janeiro': 'de Rio de Janeiro',
  'San Francisco': 'de San Francisco',
  'San Remo': 'de San Remo',
  'San Sebastian': 'de Saint-Sébastien',
  Scheveningen: 'de Scheveningue',
  Seville: 'de Séville',
  'St. Petersburg': 'de Saint-Pétersbourg',
  Stockholm: 'de Stockholm',
  Tashkent: 'de Tachkent',
  Venice: 'de Venise',
  Voronezh: 'de Voronej',
  Warsaw: 'de Varsovie',
  Yerevan: "d'Erevan",
  Zurich: 'de Zurich',
}

// ---------------------------------------------------------------------------
// 5. Segments entiers à traduction figée (priment sur l'analyse générique)
// ---------------------------------------------------------------------------
const SEGMENTS: Record<string, string> = {
  'Main Line': 'ligne principale',
  'Modern Main Line': 'ligne principale moderne',
  'Long Whip': 'Long Whip',
  'Long Whip Defense': 'défense Long Whip',
  "Queen's Gambit Invitation": 'invitation au gambit dame',
  'Sicilian Invitation': 'invitation à la sicilienne',
  'Scotch Invitation Declined': "invitation à l'écossaise refusée",
  'Pirc Invitation': 'invitation à la Pirc',
  'Slav Invitation': 'invitation à la slave',
  'Bird Invitation': 'invitation à la Bird',
  'Rooks Swap Line': "ligne de l'échange des tours",
  'Full Symmetry Line': 'ligne de la symétrie complète',
  'Pawn Push Variation': 'variante de la poussée de pion',
  'Pawn Return Variation': 'variante du retour du pion',
  'Pawn Storm Variation': "variante de l'assaut de pions",
  'Pawn Center Variation': 'variante du centre de pions',
  'Central Storming Variation': "variante de l'assaut central",
  'Fully Accepted Variation': 'variante entièrement acceptée',
  'King Walk Variation': 'variante de la promenade du roi',
  'King March Line': 'ligne de la marche du roi',
  'Pawn Grab Line': 'ligne de la prise du pion',
  'Queenside Storm Line': "ligne de l'assaut à l'aile dame",
  'Center Holding Variation': 'variante du maintien du centre',
  'Endgame Offer': 'offre de finale',
  'Kingside Move Order': "ordre des coups à l'aile roi",
  'Anti-Qxd4 Move Order': 'ordre des coups anti-Dxd4',
  'Anti-Qxd4 Move Order Accepted': 'ordre des coups anti-Dxd4 accepté',
  'Accelerated Move Order': 'ordre des coups accéléré',
  "Lion's Cave": 'Caverne du Lion',
  "Lion's Claw": 'Griffe du Lion',
  'Lion Claw Gambit': 'gambit de la Griffe du Lion',
  'Three Pawn Attack': 'attaque des trois pions',
  'Anti-Fried Liver Defense': 'défense anti-Foie frit',
  'Fried Liver Attack': 'attaque du Foie frit',
  'Giuoco Piano': 'Giuoco Piano',
  'Giuoco Pianissimo': 'Giuoco Pianissimo',
  'Reversed Sicilian': 'sicilienne inversée',
  'Reversed Closed Sicilian': 'sicilienne fermée inversée',
  'Reversed Scandinavian': 'scandinave inversée',
  'Old Sicilian': 'ancienne sicilienne',
  'English Rat': 'Rat anglais',
  'Early Deviations': 'déviations précoces',
  'Double Spanish': 'double espagnole',
  'Maróczy Bind': 'étau de Maróczy',
  'Reversed Dragon': 'Dragon inversé',
  'Reversed Grünfeld': 'Grünfeld inversée',
  'Reversed Alekhine': 'Alekhine inversée',
  'Reversed Rat': 'Rat inversé',
  'Reversed Mokele Mbembe': 'Mokele Mbembe inversé',
  'Accelerated Dragon': 'Dragon accéléré',
  'Hyperaccelerated Dragon': 'Dragon hyper-accéléré',
  'Hyperaccelerated Pterodactyl': 'Ptérodactyle hyper-accéléré',
  'Double Fianchetto': 'double fianchetto',
  Fianchetto: 'fianchetto',
  Pterodactyl: 'Ptérodactyle',
  'Old Benoni': 'vieille Benoni',
  "Fool's Mate": 'mat du sot',
  "Beginner's Trap": 'piège du débutant',
  "Noah's Ark Trap": "piège de l'arche de Noé",
  'Fishing Pole Variation': 'variante de la canne à pêche',
  "Monkey's Bum": "Monkey's Bum", // jeu de mots, conservé tel quel
  'Big Clamp Formation': 'formation du grand étau',
  'Siesta Variation': 'variante Sieste',
  'Wayward Queen Attack': 'attaque de la dame vagabonde',
  'Bouncing Bishop Variation': 'variante du fou rebondissant',
  'Drunken Knight Variation': 'variante du cavalier ivre',
  'Drunken Cavalry Variation': 'variante de la cavalerie ivre',
  'Prickly Pawn Pass System': 'système du pion épineux',
  'Double Duck Formation': 'formation du double canard',
  'Aged Gibbon Gambit': 'gambit du vieux Gibbon',
  'Maltese Falcon': 'Faucon maltais',
  "Christiansen's Dream": 'rêve de Christiansen',
  "Santasiere's Folly": 'folie de Santasiere',
  'Kitchener Folly': 'folie de Kitchener',
  'Poisoned Pawn Accepted': 'pion empoisonné accepté',
  // surnoms conservés : la tête est traduite, le surnom reste tel quel
  'Mad Dog Attack': 'attaque Mad Dog',
  'Inner Doll Defense': 'défense Inner Doll',
  'Swiss Cheese Variation': 'variante Swiss Cheese',
  'Melbourne Shuffle Variation': 'variante Melbourne Shuffle',
}

// Segments « The X » (surnoms lichess) : article et nom commun traduits.
const THE: Record<string, string> = {
  Walrus: 'le Morse',
  Potato: 'la Patate',
  Squirrel: "l'Écureuil",
  Whale: 'la Baleine',
  Goblin: 'le Gobelin',
}

// Noms propres dont la graphie française diffère (appliqués mot à mot).
const PROPRES_FR: Record<string, string> = {
  Napoleon: 'Napoléon',
  'Anti-Moscow': 'anti-Moscou',
  'Semi-Meran': 'semi-Méran',
}

// ---------------------------------------------------------------------------
// 6. Notation : SAN anglais -> français (K Q R B N -> R D T F C)
// ---------------------------------------------------------------------------
const PIECE_FR: Record<string, string> = { K: 'R', Q: 'D', R: 'T', B: 'F', N: 'C' }
const SAN_RE = /^(?:[KQRBN][a-h]?[1-8]?x?[a-h][1-8]|[a-h](?:x[a-h])?[1-8](?:=[QRBN])?|O-O(?:-O)?)[+#]?$/

function isSan(token: string): boolean {
  return SAN_RE.test(token)
}

/** SAN anglais -> SAN français (« Nf3 » -> « Cf3 »). Sert aussi aux lignes moteur et à l'explorer. */
export function sanFr(san: string): string {
  return san.replace(/[KQRBN]/g, (c) => PIECE_FR[c])
}

function tokenFr(token: string): string {
  if (token === '..' || token === '...') return '...'
  if (token === 'and') return 'et'
  if (isSan(token)) return sanFr(token)
  if (Object.hasOwn(PROPRES_FR, token)) return PROPRES_FR[token]
  const anti = /^Anti-(.+)$/.exec(token)
  if (anti && isSan(anti[1])) return `anti-${sanFr(anti[1])}`
  // Possessif anglais retiré (« Bird's », « Reynolds' »), préfixes savants en minuscule et
  // accentués (« anti-Noteboom », « néo-Grünfeld »).
  return token
    .replace(/'s?$/, '')
    .replace(/^(Anti|Pseudo|Semi)-/, (_, pre: string) => `${pre.toLowerCase()}-`)
    .replace(/^Neo-/, 'néo-')
}

// ---------------------------------------------------------------------------
// 7. Analyse d'un segment
// ---------------------------------------------------------------------------
interface Parts {
  propers: string[]
  complements: string[]
  avant: Adj[] // adjectifs antéposés
  apres: Adj[] // adjectifs postposés
  fin: Adj[] // participes et états (ouverte, inversée, accélérée) : en dernier, après la nationalité
}

function emptyParts(): Parts {
  return { propers: [], complements: [], avant: [], apres: [], fin: [] }
}

// Plus longue correspondance d'abord (3 mots, puis 2, puis 1).
function parseModifiers(tokens: string[]): Parts {
  const parts = emptyParts()
  let i = 0
  while (i < tokens.length) {
    let matched = false
    for (let len = Math.min(3, tokens.length - i); len >= 1 && !matched; len--) {
      const key = tokens.slice(i, i + len).join(' ')
      if (Object.hasOwn(ADJ, key)) {
        ;(ADJ_AVANT.has(key) ? parts.avant : ADJ_FIN.has(key) ? parts.fin : parts.apres).push(ADJ[key])
        matched = true
      } else if (Object.hasOwn(COMPLEMENTS, key)) {
        parts.complements.push(COMPLEMENTS[key])
        matched = true
      }
      if (matched) i += len
    }
    if (!matched) {
      parts.propers.push(tokenFr(tokens[i]))
      i++
    }
  }
  return parts
}

function assemble(head: string, g: Genre, parts: Parts, posts: Adj[], pluriel = false): string {
  const idx = g === 'm' ? 0 : 1
  const accord = (a: Adj) => (pluriel && !a[idx].endsWith('s') ? `${a[idx]}s` : a[idx])
  return [
    ...parts.avant.map(accord),
    head,
    ...parts.propers,
    ...parts.complements,
    ...parts.apres.map(accord),
    ...parts.fin.map(accord),
    ...posts.map(accord),
  ]
    .filter(Boolean)
    .join(' ')
}

function article(noun: string, g: Genre): string {
  return /^[aeéèêiouy]/i.test(noun) ? `l'${noun}` : `${g === 'm' ? 'le' : 'la'} ${noun}`
}

function de(noun: string, g: Genre): string {
  if (/^[aeéèêiouy]/i.test(noun)) return `de l'${noun}`
  return g === 'm' ? `du ${noun}` : `de la ${noun}`
}

// Genre d'un groupe déjà traduit, d'après son premier mot (« attaque Bradford » -> f).
function genreDe(fr: string): Genre | undefined {
  const first = fr.split(' ')[0]
  return Object.values(HEADS).find(([head]) => head === first)?.[1]
}

function segmentFr(raw: string): string {
  const seg = raw.trim()
  if (!seg) return ''
  if (Object.hasOwn(SEGMENTS, seg)) return SEGMENTS[seg]
  if (Object.hasOwn(FAMILIES, seg)) return decapitalize(FAMILIES[seg])

  // « with e3 », « with Bc4 and h6 », « with .. d6 », « with Max Lange Defense »
  if (seg.startsWith('with ')) {
    const rest = seg.slice(5).trim()
    const restTokens = rest.split(/\s+/)
    if (restTokens.every((t) => t === '..' || t === 'and' || isSan(t))) return `avec ${restTokens.map(tokenFr).join(' ')}`
    const inner = segmentFr(rest)
    const g = genreDe(inner)
    return g ? `avec ${article(inner, g)}` : `avec ${inner}`
  }

  const tokens = seg.split(/\s+/)
  if (tokens[0] === 'The' && tokens.length === 2 && Object.hasOwn(THE, tokens[1])) return THE[tokens[1]]

  // Participes finaux, puis tête.
  let end = tokens.length
  const posts: Adj[] = []
  while (end > 1 && Object.hasOwn(POST, tokens[end - 1])) {
    posts.unshift(POST[tokens[end - 1]])
    end--
  }
  const last = tokens[end - 1]
  if (Object.hasOwn(HEADS, last)) {
    const [headFr, g] = HEADS[last]
    const inner = tokens[end - 2]
    // Tête dans tête (« Bradford Attack Variation », « Gambit Line ») : « variante de l'attaque Bradford ».
    if (end >= 2 && Object.hasOwn(HEADS, inner) && !Object.hasOwn(COMPLEMENTS, inner)) {
      const innerFr = segmentFr(tokens.slice(0, end - 1).join(' '))
      return assemble(`${headFr} ${de(innerFr, genreDe(innerFr) ?? HEADS[inner][1])}`, g, emptyParts(), posts)
    }
    return assemble(headFr, g, parseModifiers(tokens.slice(0, end - 1)), posts, HEADS_PLURIEL.has(last))
  }

  // Segment sans tête : « Closed », « Dragon », « Two Knights », « Nf3 », « Delayed .. Nc6 ».
  const parts = parseModifiers(tokens.slice(0, end))
  const hasMove = tokens.some(isSan)
  if (parts.propers.length === 0) return assemble('variante', 'f', parts, posts)
  // Un coup est masculin (« ... Cc6 retardé »), une variante nommée est féminine.
  return assemble('', hasMove ? 'm' : 'f', parts, posts)
}

function capitalize(s: string): string {
  return s ? s[0].toLocaleUpperCase('fr-FR') + s.slice(1) : s
}

function decapitalize(s: string): string {
  return s ? s[0].toLocaleLowerCase('fr-FR') + s.slice(1) : s
}

// « Queen's Indian Defense, with e3, Bb4+ Line » -> base + précisions de famille.
function splitFamily(name: string): { base: string; extras: string[] } {
  const [base, ...extras] = name.split(':')[0].split(',').map((s) => s.trim())
  return { base, extras: extras.filter(Boolean) }
}

function familyBaseFr(base: string): string {
  return Object.hasOwn(FAMILIES, base) ? FAMILIES[base] : capitalize(segmentFr(base))
}

// ---------------------------------------------------------------------------
// 8. API publique
// ---------------------------------------------------------------------------
const cache = new Map<string, string>()

/** Nom complet en français : « Défense sicilienne · variante du Dragon, attaque yougoslave ». */
export function openingFr(name: string): string {
  const hit = cache.get(name)
  if (hit !== undefined) return hit
  const { base, extras } = splitFamily(name)
  const family = [familyBaseFr(base), ...extras.map(segmentFr)].join(', ')
  const colon = name.indexOf(':')
  const variation = colon < 0 ? '' : name.slice(colon + 1).split(',').map(segmentFr).filter(Boolean).join(', ')
  const out = variation ? `${family} · ${variation}` : family
  cache.set(name, out)
  return out
}

/** Famille seule, sans variante ni précision de coup : « Attaque est-indienne ». */
export function openingFamilyFr(name: string): string {
  return familyBaseFr(splitFamily(name).base)
}

const MASCULIN_PREMIER_MOT = new Set(['Gambit', 'Contre-gambit', 'Début', 'Système', 'Orang-outan'])

/** Genre grammatical du nom de famille français (« Gambit dame » -> 'm', « Défense slave » -> 'f'). */
export function openingGender(name: string): Genre {
  return MASCULIN_PREMIER_MOT.has(openingFamilyFr(name).split(' ')[0]) ? 'm' : 'f'
}

/**
 * Groupe « de + article + famille » pour une phrase :
 * « de la défense sicilienne », « du gambit dame refusé », « de l'ouverture anglaise ».
 * Le nom commun initial perd sa majuscule en milieu de phrase.
 */
export function openingDe(name: string): string {
  return de(decapitalize(openingFamilyFr(name)), openingGender(name))
}
