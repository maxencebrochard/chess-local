import Dexie, { type EntityTable } from 'dexie'
import type { AttackOutcome } from './attack'
import type { DefenseOutcome } from './defense'
import type { GameReview } from './review'

export interface SavedGame {
  id?: number
  date: number
  mode: 'bot' | 'local'
  botId?: string
  playerColor: 'w' | 'b'
  timeControl: string // ex "5+0", "illimité"
  timeClass: 'bullet' | 'blitz' | 'rapid' | 'unlimited'
  pgn: string
  result: '1-0' | '0-1' | '1/2-1/2'
  termination: string
  playerRatingAfter?: number
}

export interface Rating {
  key: string // 'bullet' | 'blitz' | 'rapid' | 'unlimited' | 'puzzle'
  value: number
  games: number
}

export interface PuzzleAttempt {
  id?: number
  puzzleId: string
  date: number
  success: boolean
  puzzleRating: number
  ratingAfter: number
}

export interface RushScore {
  id?: number
  mode: '3min' | '5min' | 'survival'
  score: number
  date: number
}

// Faute détectée par un bilan de partie, rejouable dans « Apprendre ».
export interface Mistake {
  id?: number
  date: number
  gameLabel: string
  fenBefore: string
  playedSan: string
  bestUci: string
  cls: string // mistake | miss | missedWin | blunder
  attempts: number
  solved: 0 | 1
  // Champs non indexés, présents depuis « Mes attaques manquées » (absents des anciennes lignes).
  color?: 'w' | 'b' // camp du joueur, seulement quand le bilan le connaissait : la faute est la sienne
  gameKey?: string // partie d'origine : `game:<id>` (Archive) ou `pgn:<empreinte des coups>`
}

export interface LearnSession {
  id?: number
  date: number
  // endgame | tactic | opening | strategy | mistakes | endgame-play | course (leçon terminée d'un
  // cours d'Apprendre), opening-drill (entraîneur d'ouvertures), missed-attack (tentative sur une
  // attaque manquée), mats (une série de « Mats éclair »), revision (révision espacée), attack
  // (entraîneur d'attaque : itemId = id de la position, une ligne par tentative), defense
  // (entraîneur de défense : itemId = id de la position `def-<puzzle>`, une ligne par tentative) ou
  // missed-defense (tentative sur une défense ratée, même contrat que missed-attack), conversion
  // (entraîneur « Convertir l'avantage » : mêmes champs que attack, itemId = id de la position `conv-<puzzle>`),
  // structure-play (partie depuis une structure de pions de mes parties),
  // critical-moment (moments critiques du bilan, hors Elo), path (parcours d’apprentissage),
  // endgame-clock (une série des Finales au chrono, hors Elo) ou seance (séance du jour terminée).
  // course : itemId = `<slug>:<id>`, le slug désignant le cours (`finales:` pour le cours de finales,
  // `roque:` pour « Démolir le roque », `bases:` pour « Les bases », `structures:` pour « Structures de pions »,
  // `defense:` pour « Tenir sous l'attaque »), ex. `finales:mat-dame`, `roque:grec-schema`,
  // `defense:contre-le-grec`.
  // opening-drill : itemId = `<next|suite|full>:<w|b>:<UCI>`, l'UCI étant la ligne lichess de la
  // variante (suite, full) ou la position (next). L'état d'une variante s'y rattache par égalité
  // d'UCI : régénérer openings.json peut laisser des tentatives orphelines (jamais perdues).
  // Mon répertoire (/repertoire) écrit aussi des lignes `next:` : la position est alors celle d'une
  // sortie de théorie, avec les coups réels de la partie (un ordre de coups qui transpose compris).
  // missed-attack, missed-defense : itemId = id de la ligne `mistakes`, fen = sa `fenBefore` (le
  // couple identifie l'exercice : une sauvegarde restaurée peut réattribuer les ids), success =
  // premier coup sans aide, égal au coup du bilan ou accepté par `PositionGame.judgeKeyMove` après
  // vérification ; depuis la révision espacée, verdict de `MistakeExercise` (perte de win% < 5).
  // defense : fen = position de départ, success = défense réussie sans aide (outcome held, draw ou
  // win), outcome parmi held | draw | win | mated | collapsed | resign | abandon, attackerElo =
  // Elo de l'attaquant (null = pleine force), assisted comme pour attack ; defenderElo absent.
  // mats : itemId = `<exercice>:<cadence>`, ex. `chrono-kq:30s`, `mate-2:3min`.
  // critical-moment : fen = position du moment, itemId = `question:<attendu>:<choisi>` (réponse à
  // « Plan, menace ou coup forcé ? », success = bonne réponse) ou `coup:<attendu>` (tentative notée
  // par le keyMove de la position rejouée), attendu et choisi parmi `forced`, `threat`, `plan`.
  // endgame-clock : une série des Finales au chrono, itemId = `<famille|mix>:<base s>+<incrément s>`,
  // ex. `lucena:30+1`, `mix:15+0` ; score = finales réussies (même forme que `mats`).
  // revision : puzzles revus par la révision espacée, itemId = `puzzle:<id>` (sans Elo) ; les
  // fautes, variantes, attaques manquées et défenses ratées revues s'écrivent dans leurs domaines
  // d'origine (`mistakes`, `opening-drill`, `missed-attack`, `missed-defense`).
  // visualisation (« Calcul et visualisation », hors Elo) : itemId = `q:<N>:<type>:<id puzzle>` pour
  // une question répondue (fen = position montrée), ou `serie:<N>:<visible|flash>` pour une série
  // (score = bonnes réponses), N étant la longueur de la ligne en demi-coups.
  // path : parcours d'apprentissage (#/apprendre/parcours), sans Elo. itemId = id d'étape de
  // src/data/learningPath.json : une ligne par série notée jouée jusqu'au bout (score = réussites,
  // success = seuil atteint) ou par finale réussie depuis l'étape ; itemId = `placement` : un test
  // de placement (score = niveaux acquis, le meilleur test compte).
  // structure-play : partie contre Stockfish depuis une position de mes parties où une structure de
  // pions est apparue (/structures), une ligne par tentative, sans Elo ; itemId = `<partie>@<demi-coup>@<structure>`
  // (`local:<id>@14@iqp`, `chesscom:<id>@21@carlsbad`), fen = position de départ : le couple identifie la position
  // (une restauration peut réattribuer les ids `local:`) ; success = gain sans aide, outcome et
  // defenderElo comme l'entraîneur d'attaque.
  // threat-check : questions « Qu'est-ce qu'il menace ? » de Jouer (sans Elo), une ligne par
  // question répondue : itemId = `<type>:<UCI du coup menaçant>` (types de `THREAT_KINDS`,
  // lib/threat.ts), fen = position où la question est posée, success = menace trouvée.
  // seance : une séance du jour menée jusqu'au bilan (série de jours), itemId = types des blocs
  // joints par « + » (ex. `revision+puzzles+attack`), score = étapes réussies, sans Elo ; les
  // étapes elles-mêmes s'écrivent dans les domaines et tables de leurs écrans d'origine.
  domain: string
  itemId: string
  success: 0 | 1
  ratingAfter: number | null
  fen?: string // finales jouées jusqu'au bout, attaques manquées, défenses ratées, entraîneurs d'attaque, de défense et de conversion, moments critiques et structures : position de départ ; threat-check : position de la question (champ non indexé)
  score?: number // mats : mats réussis dans la série ; seance : étapes réussies (champ non indexé)
  // Entraîneurs d'attaque, de conversion et de défense (champs non indexés) : issue de la tentative (union des
  // issues des domaines, `draw` et `resign` et `abandon` communs), Elo du défenseur bridé
  // (attack, conversion) ou de l'attaquant bridé (defense, depuis l'entraîneur de défense), null = pleine
  // force, aide utilisée (indice ou coup repris).
  outcome?: AttackOutcome | DefenseOutcome
  defenderElo?: number | null
  attackerElo?: number | null
  assisted?: boolean
}

// Bilan Stockfish d'une partie, mis en cache par Insights (/insights). Ligne autosuffisante : le
// rapport se recalcule hors ligne depuis cette table seule, sans réseau ni moteur.
export interface ReviewRow {
  key: string // 'chesscom:<id de partie>' ou 'local:<id Dexie de games>'
  source: 'chesscom' | 'local'
  username: string | null // pseudo chess.com normalisé (null pour l'app) : deux comptes ne se mélangent pas
  date: number // fin de partie, ms
  timeClass: 'bullet' | 'blitz' | 'rapid' | 'unlimited'
  timeControl: string // '180+2', '600', '5+0', 'illimité'
  playerColor: 'w' | 'b'
  playerRating: number | null
  opponent: string
  opponentRating: number | null
  result: 'win' | 'draw' | 'loss' // pour le joueur
  termination: string // libellé français
  lostOnTime: boolean
  pgn: string
  depth: number // profondeur du bilan : un rapport ne mélange pas deux profondeurs
  review: GameReview
}

export const db = new Dexie('chess-local') as Dexie & {
  games: EntityTable<SavedGame, 'id'>
  ratings: EntityTable<Rating, 'key'>
  puzzleAttempts: EntityTable<PuzzleAttempt, 'id'>
  rushScores: EntityTable<RushScore, 'id'>
  mistakes: EntityTable<Mistake, 'id'>
  learnSessions: EntityTable<LearnSession, 'id'>
  reviews: EntityTable<ReviewRow, 'key'>
}

db.version(1).stores({
  games: '++id, date, mode, timeClass',
  ratings: 'key',
  puzzleAttempts: '++id, date, puzzleId',
  rushScores: '++id, mode, score, date',
})

db.version(2).stores({
  games: '++id, date, mode, timeClass',
  ratings: 'key',
  puzzleAttempts: '++id, date, puzzleId',
  rushScores: '++id, mode, score, date',
  mistakes: '++id, date, solved, fenBefore',
  learnSessions: '++id, date, domain',
})

// Version 3 : cache des bilans d'Insights. Tous les stores sont redéclarés, aucune donnée ne bouge.
db.version(3).stores({
  games: '++id, date, mode, timeClass',
  ratings: 'key',
  puzzleAttempts: '++id, date, puzzleId',
  rushScores: '++id, mode, score, date',
  mistakes: '++id, date, solved, fenBefore',
  learnSessions: '++id, date, domain',
  reviews: 'key, date',
})

export const DEFAULT_RATING = 800

export async function getRating(key: string): Promise<Rating> {
  return (await db.ratings.get(key)) ?? { key, value: DEFAULT_RATING, games: 0 }
}

// Elo classique, K décroissant avec l'expérience.
export function eloUpdate(rating: number, opponent: number, score: 0 | 0.5 | 1, games: number): number {
  const k = games < 20 ? 40 : 20
  const expected = 1 / (1 + 10 ** ((opponent - rating) / 400))
  return Math.round(rating + k * (score - expected))
}

export async function applyRating(key: string, opponent: number, score: 0 | 0.5 | 1): Promise<number> {
  const r = await getRating(key)
  const value = eloUpdate(r.value, opponent, score, r.games)
  await db.ratings.put({ key, value, games: r.games + 1 })
  return value
}
