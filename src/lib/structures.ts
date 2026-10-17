// Structures de pions typiques (plans par structure, `/apprendre/structures` et `/structures`) :
// détecteur pur, fondé sur les seuls pions (ni trait, ni pièces), et repérage dans une partie.
// N'importe que chess.js : bundlé sous Node par e2e/test_structures.py, qui le compare à un oracle
// python-chess écrit aux mêmes définitions. Changer une règle ici impose de changer l'oracle.
import { Chess } from 'chess.js'

export type Color = 'w' | 'b'

export type StructureId =
  | 'iqp' | 'pendants' | 'carlsbad' | 'maroczy' | 'herisson' | 'francaise' | 'est-indienne' | 'stonewall' | 'caro-slave' | 'majorite'

// Ordre d'affichage et de détection (le repli `majorite` en dernier).
export const STRUCTURE_IDS: StructureId[] = [
  'iqp', 'pendants', 'carlsbad', 'maroczy', 'herisson', 'francaise', 'est-indienne', 'stonewall', 'caro-slave', 'majorite',
]

// `side` : le camp « porteur » de la structure (celui qui a le pion isolé, l'étau, le hérisson…).
export interface StructureMatch {
  id: StructureId
  side: Color
}

type Cell = { type: string; color: Color } | null

// Rangs relatifs des pions de chaque camp, par colonne (0 = a) : 2 = rangée de départ du camp
// (2 pour les Blancs, 7 pour les Noirs), 4 = d4 pour les Blancs, d5 pour les Noirs.
type PawnFiles = number[][]

const A = 0, B = 1, C = 2, D = 3, E = 4, F = 5

function pawnFiles(board: Cell[][]): Record<Color, PawnFiles> {
  const out: Record<Color, PawnFiles> = { w: [[], [], [], [], [], [], [], []], b: [[], [], [], [], [], [], [], []] }
  board.forEach((row, ri) => {
    const rank = 8 - ri // chess.js : board()[0] est la 8e rangée
    row.forEach((cell, file) => {
      if (cell?.type === 'p') out[cell.color][file].push(cell.color === 'w' ? rank : 9 - rank)
    })
  })
  return out
}

// Règles de chaque structure pour un porteur `us` face à `them` (rangs relatifs de chacun).
type Rule = (us: PawnFiles, them: PawnFiles) => boolean

const at = (p: PawnFiles, file: number, rel: number) => p[file].includes(rel)
const none = (p: PawnFiles, ...files: number[]) => files.every((f) => p[f].length === 0)
const count = (p: PawnFiles, from: number, to: number) => p.slice(from, to + 1).reduce((n, f) => n + f.length, 0)

const RULES: Record<StructureId, Rule> = {
  // Pion dame isolé : un seul pion d, en d4 (d5 pour les Noirs), sans pion c ni e ; colonne d fermée
  // à l'adversaire (sinon c'est une autre structure, pion bloqué par un pion).
  iqp: (us, them) => us[D].length === 1 && at(us, D, 4) && none(us, C, E) && none(them, D),
  // Pions pendants : c4 et d4 côte à côte, sans voisins en b et e, adversaire sans pion c ni d.
  pendants: (us, them) => at(us, C, 4) && at(us, D, 4) && us[C].length === 1 && us[D].length === 1 && none(us, B, E) && none(them, C, D),
  // Carlsbad (gambit dame, variante d'échange) : porteur = camp de l'attaque de minorité, pion d4
  // sans pion c, avec un pion b et un pion e en e2/e3 ; adversaire d5, pion c en c7 ou c6, sans pion e.
  carlsbad: (us, them) =>
    at(us, D, 4) && none(us, C) && us[B].length > 0 && (at(us, E, 2) || at(us, E, 3)) &&
    at(them, D, 4) && (at(them, C, 2) || at(them, C, 3)) && none(them, E),
  // Étau de Maroczy : c4 et e4 sans pion d ; adversaire avec son pion d en d7/d6, sans pion c.
  maroczy: (us, them) => at(us, C, 4) && at(us, E, 4) && none(us, D) && (at(them, D, 2) || at(them, D, 3)) && none(them, C),
  // Hérisson : a6, b6, d6, e6 (rang relatif 3) sans pion c, face à l'étau c4-e4 sans pion d.
  herisson: (us, them) =>
    at(us, A, 3) && at(us, B, 3) && at(us, D, 3) && at(us, E, 3) && none(us, C) && at(them, C, 4) && at(them, E, 4) && none(them, D),
  // Chaîne bloquée française : porteur = chaîne avancée d4-e5, face à d5-e6.
  francaise: (us, them) => at(us, D, 4) && at(us, E, 5) && at(them, D, 4) && at(them, E, 3),
  // Chaîne bloquée est-indienne : porteur = chaîne d5-e4, face à d6-e5.
  'est-indienne': (us, them) => at(us, D, 5) && at(us, E, 4) && at(them, D, 3) && at(them, E, 4),
  // Stonewall : d4, e3, f4 (Noirs : d5, e6, f5, la hollandaise).
  stonewall: (us) => at(us, D, 4) && at(us, E, 3) && at(us, F, 4),
  // Caro-Kann / Slave : triangle c6-e6 sans pion d, face à d4 avec EXACTEMENT un des pions c et e
  // adverses (Caro-Kann : c2 sans e ; slave : e3 sans c). Sans aucun des deux, le d4 est isolé :
  // c'est `iqp`, et l'exclusivité tient par construction (ne pas « corriger » en « au moins un »).
  'caro-slave': (us, them) => at(us, C, 3) && at(us, E, 3) && none(us, D) && at(them, D, 4) && (them[C].length > 0) !== (them[E].length > 0),
  // Majorité à l'aile dame : plus de pions que l'adversaire sur a-c (deux au moins), moins sur d-h.
  // Repli : retenue seulement si aucune autre structure n'est reconnue.
  majorite: (us, them) => count(us, A, C) > count(them, A, C) && count(us, A, C) >= 2 && count(them, D, 7) > count(us, D, 7),
}

// Structures reconnues sur un échiquier (`chess.board()`), dans l'ordre de STRUCTURE_IDS, Blancs
// porteurs avant Noirs. Exclusions : un hérisson retire le Maroczy de l'autre camp (le hérisson en
// est un cas particulier) ; la majorité n'est qu'un repli.
export function detectBoard(board: Cell[][]): StructureMatch[] {
  const p = pawnFiles(board)
  const found: StructureMatch[] = []
  for (const id of STRUCTURE_IDS) {
    if (id === 'majorite') continue
    for (const side of ['w', 'b'] as Color[]) if (RULES[id](p[side], p[side === 'w' ? 'b' : 'w'])) found.push({ id, side })
  }
  const out = found.filter((m) => !(m.id === 'maroczy' && found.some((h) => h.id === 'herisson' && h.side !== m.side)))
  if (out.length === 0) {
    for (const side of ['w', 'b'] as Color[]) if (RULES.majorite(p[side], p[side === 'w' ? 'b' : 'w'])) out.push({ id: 'majorite', side })
  }
  return out
}

export function detectStructures(fen: string): StructureMatch[] {
  return detectBoard(new Chess(fen).board() as Cell[][])
}

// ---------- Repérage dans une partie ----------

// Milieu de partie : pas avant le 10e demi-coup, et au moins 3 pièces (C, F, T, D) par camp, sauf
// pour la majorité, structure de finale. Une structure « apparaît » quand elle tient STABLE
// positions de suite : un échange en deux temps crée souvent une structure d'un seul demi-coup.
export const MIN_PLY = 10
export const MIN_PIECES = 3
export const STABLE = 4

export interface Sighting {
  id: StructureId
  side: Color
  ply: number // demi-coups joués dans la position proposée (0 = départ)
  fen: string // position proposée : la première de la série où le joueur a le trait
}

function piecesOf(board: Cell[][], color: Color): number {
  let n = 0
  for (const row of board) for (const c of row) if (c && c.color === color && c.type !== 'p' && c.type !== 'k') n++
  return n
}

// Première apparition de chaque structure dans la partie (une par id, porteur compris), dans
// l'ordre des apparitions. PGN illisible : aucune.
export function structuresInGame(pgn: string, player: Color): Sighting[] {
  const game = new Chess()
  try {
    game.loadPgn(pgn)
  } catch {
    return []
  }
  const moves = game.history({ verbose: true })
  if (moves.length === 0) return []
  const replay = new Chess(moves[0].before)
  const fens = [replay.fen()]
  const runs = new Map<string, number>() // `${id}:${side}` -> positions consécutives
  const out: Sighting[] = []
  const seen = new Set<StructureId>()
  const check = (ply: number) => {
    const board = replay.board() as Cell[][]
    const middlegame = ply >= MIN_PLY && piecesOf(board, 'w') >= MIN_PIECES && piecesOf(board, 'b') >= MIN_PIECES
    const keys = new Set<string>()
    for (const m of ply >= MIN_PLY ? detectBoard(board) : []) {
      if (m.id !== 'majorite' && !middlegame) continue
      const k = `${m.id}:${m.side}`
      keys.add(k)
      const n = (runs.get(k) ?? 0) + 1
      runs.set(k, n)
      if (n === STABLE && !seen.has(m.id)) {
        // Première position de la série où le joueur a le trait (la série en compte au moins deux).
        const start = ply - STABLE + 1
        for (let j = start; j <= ply; j++) {
          if (fens[j].split(' ')[1] === player && !new Chess(fens[j]).isGameOver()) {
            seen.add(m.id)
            out.push({ id: m.id, side: m.side, ply: j, fen: fens[j] })
            break
          }
        }
      }
    }
    for (const k of [...runs.keys()]) if (!keys.has(k)) runs.delete(k)
  }
  check(0)
  moves.forEach((mv, i) => {
    replay.move(mv.san)
    fens.push(replay.fen())
    check(i + 1)
  })
  return out
}

// ---------- Bilan par structure ----------

export interface StructureGame {
  key: string // `local:<id Dexie>` ou `chesscom:<id de partie>`
  playerColor: Color
  result: 'win' | 'draw' | 'loss' // pour le joueur
}

export interface StructureStat<G extends StructureGame = StructureGame> {
  id: StructureId
  games: number
  wins: number
  draws: number
  losses: number
  score: number // points du joueur / parties, 0..1
  owner: number // parties où le joueur était le porteur
  sightings: { game: G; sighting: Sighting; owner: boolean }[]
}

// Structures des parties, les plus fréquentes d'abord (puis ordre de STRUCTURE_IDS). Les apparitions
// de chaque structure sont rangées dans l'ordre des parties reçues.
export function structureStats<G extends StructureGame>(games: { game: G; sightings: Sighting[] }[]): StructureStat<G>[] {
  const by = new Map<StructureId, StructureStat<G>>()
  for (const { game, sightings } of games) {
    for (const s of sightings) {
      let st = by.get(s.id)
      if (!st) by.set(s.id, (st = { id: s.id, games: 0, wins: 0, draws: 0, losses: 0, score: 0, owner: 0, sightings: [] }))
      const owner = s.side === game.playerColor
      st.games++
      if (game.result === 'win') st.wins++
      else if (game.result === 'draw') st.draws++
      else st.losses++
      if (owner) st.owner++
      st.sightings.push({ game, sighting: s, owner })
    }
  }
  const stats = [...by.values()]
  for (const st of stats) st.score = (st.wins + st.draws / 2) / st.games
  return stats.sort((a, b) => b.games - a.games || STRUCTURE_IDS.indexOf(a.id) - STRUCTURE_IDS.indexOf(b.id))
}

// ---------- Fiches ----------

// Textes écrits pour un porteur blanc ; `squaresFor` les retourne quand le porteur est noir.
export interface StructureMeta {
  name: string
  emoji: string
  owner: string // ce que le porteur possède : « avec le pion isolé », « contre le pion isolé »
  lesson: string // leçon du cours (src/data/structuresCourse.json)
  planOwner: string // plan du porteur
  planOpponent: string // plan de l'adversaire
}

export const STRUCTURES: Record<StructureId, StructureMeta> = {
  iqp: {
    name: 'Pion dame isolé',
    emoji: '🗼',
    owner: 'le pion isolé',
    lesson: 'iqp-avec',
    planOwner: "Avec le pion isolé, joue pour l'initiative : cavalier en e5, fou vers le roi, tours au centre, et la poussée d5 quand elle ouvre le jeu. Évite les échanges.",
    planOpponent: "Contre le pion isolé, bloque-le en d5 avec une pièce, de préférence un cavalier, échange les pièces mineures, puis attaque le pion en finale.",
  },
  pendants: {
    name: 'Pions pendants',
    emoji: '⚖️',
    owner: 'les pions pendants',
    lesson: 'pendants',
    planOwner: "Garde les pions côte à côte en c4 et d4 : ils tiennent le centre. Pousse d5 ou c5 au bon moment, quand tes pièces sont prêtes à profiter des lignes ouvertes.",
    planOpponent: "Force l'un des pions à avancer : il laisse une case faible devant l'autre. Vise-les avec tes tours et ta dame sur les colonnes c et d.",
  },
  carlsbad: {
    name: 'Carlsbad',
    emoji: '🏰',
    owner: "l'attaque de minorité",
    lesson: 'carlsbad',
    planOwner: "Attaque de minorité : b4 puis b5 pour créer un pion faible en c6, tours sur la colonne c, cavalier vers c5 ou e5.",
    planOpponent: "Face à l'attaque de minorité, installe un cavalier en e4 et joue sur l'aile roi ; prépare a6 pour freiner b5.",
  },
  maroczy: {
    name: 'Étau de Maroczy',
    emoji: '🗜️',
    owner: "l'étau",
    lesson: 'maroczy',
    planOwner: "L'étau c4-e4 empêche la rupture d5 : garde-le, occupe d5 avec un cavalier quand c'est utile, et joue sur ton avance d'espace.",
    planOpponent: "Contre l'étau, échange des pièces pour respirer, puis prépare b5, d5 ou f5 : les seules ruptures qui libèrent ton jeu.",
  },
  herisson: {
    name: 'Hérisson',
    emoji: '🦔',
    owner: 'le hérisson',
    lesson: 'herisson',
    planOwner: "Le hérisson attend : pions en a3, b3, d3, e3, pièces derrière, puis la rupture b4 ou d4 quand l'adversaire s'avance trop.",
    planOpponent: "Contre le hérisson, garde l'étau et empêche b4 et d4 ; prépare une poussée à l'aile roi ou e4 au bon moment.",
  },
  francaise: {
    name: 'Chaîne française',
    emoji: '⛓️',
    owner: 'la chaîne avancée',
    lesson: 'francaise',
    planOwner: "La chaîne d4-e5 te donne de l'espace à l'aile roi : attaque là où elle pointe (f4-f5, Fd3, Dg4) et défends sa base d4.",
    planOpponent: "Attaque la base de la chaîne : c5 contre d4, puis f6 contre e5. Ton fou de cases blanches est souvent ton mauvais fou.",
  },
  'est-indienne': {
    name: 'Chaîne est-indienne',
    emoji: '🔗',
    owner: 'la chaîne d5-e4',
    lesson: 'est-indienne',
    planOwner: "La chaîne d5-e4 pointe vers l'aile dame : attaque là (c5, b4, cavalier vers c4), pendant que l'adversaire attaque ton roi.",
    planOpponent: "Ta chaîne pointe vers l'aile roi : f5, f4, g5, et lance tes pièces vers le roi. Chaque temps compte.",
  },
  stonewall: {
    name: 'Stonewall',
    emoji: '🧱',
    owner: 'le Stonewall',
    lesson: 'stonewall',
    planOwner: "Le Stonewall fait de e5 un avant-poste : un cavalier y règne. Attaque ensuite à l'aile roi avec la dame et une tour.",
    planOpponent: "Contre le Stonewall, la case e4 est un trou : installe-y un cavalier, échange le bon fou adverse et ouvre l'aile dame avec c5.",
  },
  'caro-slave': {
    name: 'Caro-Kann / slave',
    emoji: '🛡️',
    owner: 'le triangle c3-e3',
    lesson: 'caro-slave',
    planOwner: "Le triangle c3-e3 est solide : développe le fou de cases blanches avant e3, puis libère le jeu par c4 ou e4.",
    planOpponent: "Contre ce bloc solide, prends de l'espace : avance à l'aile roi ou installe un cavalier en e4, et empêche la libération c4 ou e4.",
  },
  majorite: {
    name: "Majorité à l'aile dame",
    emoji: '➕',
    owner: 'la majorité',
    lesson: 'majorite',
    planOwner: "Ta majorité à l'aile dame fera un pion passé : simplifie, active ton roi en finale et pousse les pions, le candidat d'abord.",
    planOpponent: "Contre la majorité adverse, joue au centre et à l'aile roi avant la finale, ou bloque les pions sur des cases de ta couleur.",
  },
}

// Texte d'une fiche pour un porteur `side` : cases retournées (rang r -> 9 - r) pour un porteur noir.
export function squaresFor(text: string, side: Color): string {
  return side === 'w' ? text : text.replace(/([a-h])([1-8])/g, (_, f: string, r: string) => f + String(9 - Number(r)))
}
