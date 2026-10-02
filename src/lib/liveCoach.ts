// Coach live du mode entraîneur : phrases courtes en direct, façon chess.com.
// Classification rapide d'un coup à partir des évals avant/après (win%).
import { Chess, type PieceSymbol } from 'chess.js'
import { CLASS_META, figurine, winPct, type MoveClass } from './review'
import { openingForMoves } from './openings'
import { openingFamilyFr } from './openingNames'
import { Picker, type Vars } from './coachPhrases'
import { PIECE_FR, captureInfo, hangingAfter } from './motifs'

export interface LiveComment {
  text: string
  // Coup en figurine, affiché en gras avec la pastille de classe (PLAY-16).
  headline?: string
  cls: MoveClass | null
  mood: 'happy' | 'thinking' | 'worried'
}

// Une graine par partie : les variantes changent d'une partie à l'autre, sans se répéter
// d'un coup au suivant.
let picker = new Picker(Math.floor(Math.random() * 1e9))

export function greeting(): LiveComment {
  picker = new Picker(Math.floor(Math.random() * 1e9))
  return { text: picker.say('live.salutation', Math.floor(Math.random() * 1e6)), cls: null, mood: 'happy' }
}

// Classe rapide depuis les cp avant/après (point de vue du joueur qui a joué).
export function quickClass(cpBeforeMover: number, cpAfterMover: number, isBook: boolean): MoveClass {
  if (isBook) return 'book'
  const drop = Math.max(0, winPct(cpBeforeMover) - winPct(cpAfterMover))
  if (drop < 2) return 'best'
  if (drop < 5) return 'good'
  if (drop < 10) return 'inaccuracy'
  if (drop < 20) return 'mistake'
  return 'blunder'
}

const PLAYER_KEY: Partial<Record<MoveClass, string>> = {
  brilliant: 'live.joueur.excellent', great: 'live.joueur.excellent', best: 'live.joueur.excellent', excellent: 'live.joueur.excellent',
  good: 'live.joueur.good', inaccuracy: 'live.joueur.inaccuracy', mistake: 'live.joueur.mistake', miss: 'live.joueur.mistake',
  missedWin: 'live.joueur.blunder', blunder: 'live.joueur.blunder',
}
const FAULTS: MoveClass[] = ['inaccuracy', 'mistake', 'miss', 'missedWin', 'blunder']

// Rejoue la partie pour obtenir les positions avant/après le dernier coup.
function replay(uciMoves: string[]) {
  const c = new Chess()
  let fenBefore = c.fen()
  let lastCaptureSquare: string | null = null
  let captured: PieceSymbol | undefined
  let to = ''
  uciMoves.forEach((u, i) => {
    fenBefore = c.fen()
    const mv = c.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u[4] })
    if (i < uciMoves.length - 1) lastCaptureSquare = mv.captured ? mv.to : null
    captured = mv.captured
    to = mv.to
  })
  return { fenBefore, fenAfter: c.fen(), mated: c.isCheckmate(), pat: c.isStalemate(), lastCaptureSquare, captured, to }
}

// Commentaire d'un coup en direct. `byPlayer` : coup du joueur, sinon du bot.
export function liveComment(opts: {
  san: string
  moverColor: 'w' | 'b'
  byPlayer: boolean
  cls: MoveClass
  uciMoves: string[]
}): LiveComment {
  const { san, moverColor, byPlayer, cls, uciMoves } = opts
  const fig = figurine(san, moverColor)
  const i = uciMoves.length
  const vars: Vars = { coup: fig }
  let gender: 'm' | 'f' = 'm'
  let key: string
  let mood: LiveComment['mood'] = byPlayer
    ? (cls === 'blunder' || cls === 'mistake' || cls === 'missedWin' ? 'worried' : cls === 'best' || cls === 'excellent' || cls === 'great' || cls === 'brilliant' ? 'happy' : 'thinking')
    : (cls === 'mistake' || cls === 'blunder' || cls === 'miss' || cls === 'missedWin' ? 'happy' : 'thinking')

  let pos: ReturnType<typeof replay> | null = null
  try {
    pos = replay(uciMoves)
  } catch {
    pos = null
  }
  const cap = pos ? captureInfo(pos.fenBefore, uciMoves[i - 1], pos.lastCaptureSquare) : null

  if (pos?.mated) {
    key = byPlayer ? 'live.joueur.mat' : 'live.adversaire.mat'
    mood = byPlayer ? 'happy' : 'worried'
  } else if (pos?.pat) {
    key = 'live.pat'
  } else if (cls === 'book') {
    // Premier coup : « tu occupes le centre » ne vaut que pour le joueur, jamais pour le bot.
    if (i === 1 && byPlayer) key = san === 'e4' || san === 'd4' ? 'live.theorie.premier_coup_centre' : 'live.theorie.premier_coup_souple'
    else if (i === 1) key = 'live.theorie.generique'
    else {
      // L'ouverture est nommée une fois, quand sa famille change (jamais en anglais, PLAY-15).
      const now = openingForMoves(uciMoves)
      const before = openingForMoves(uciMoves.slice(0, -1))
      const fam = now ? openingFamilyFr(now.name) : null
      const famBefore = before ? openingFamilyFr(before.name) : null
      // Une famille sans traduction (openingNames.ts) reste en anglais : on ne la nomme pas.
      const translated = !!now && fam !== now.name.split(':')[0].trim()
      if (fam && translated && fam !== famBefore) {
        vars.ouverture = fam
        key = 'live.theorie.ouverture_nommee'
      } else key = 'live.theorie.generique'
    }
    mood = 'happy'
  } else if (byPlayer) {
    const hang = pos && FAULTS.includes(cls) ? hangingAfter(pos.fenBefore, pos.fenAfter, moverColor, { to: pos.to, captured: pos.captured }) : null
    if (hang) {
      gender = PIECE_FR[hang.piece].genre
      Object.assign(vars, { piece: PIECE_FR[hang.piece].defini, case: hang.square, attaquant: PIECE_FR[hang.attacker].defini })
      key = hang.defended ? 'live.joueur.mal_defendue' : 'live.joueur.piece_en_prise'
    } else if (cap?.kind === 'gain' && cap.clean && !FAULTS.includes(cls)) {
      vars.cible = PIECE_FR[cap.captured].defini
      key = 'live.joueur.gain_materiel'
    } else if (san.startsWith('O-O') && !FAULTS.includes(cls)) key = 'live.joueur.roque'
    else key = PLAYER_KEY[cls] ?? 'live.joueur.good'
  } else {
    if (san.includes('+')) key = 'live.adversaire.echec'
    else if (cls === 'blunder' || cls === 'missedWin') key = 'live.adversaire.blunder'
    else if (cls === 'mistake' || cls === 'miss') key = 'live.adversaire.mistake'
    else if (cap?.kind === 'gain') {
      vars.cible = PIECE_FR[cap.captured].defini
      key = 'live.adversaire.capture'
    } else if (cls === 'best' || cls === 'excellent' || cls === 'great' || cls === 'brilliant') key = 'live.adversaire.best'
    else key = 'live.adversaire.neutre'
  }

  return { text: picker.say(key, i, vars, gender), headline: fig, cls, mood }
}

export function classMeta(cls: MoveClass) {
  return CLASS_META[cls]
}
