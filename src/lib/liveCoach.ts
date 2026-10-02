// Coach live du mode entraîneur : phrases courtes en direct, façon chess.com.
// Classification rapide d'un coup à partir des évals avant/après (win%).
import { Chess, type PieceSymbol } from 'chess.js'
import { CLASS_META, figurine, winPct, type MoveClass } from './review'
import { openingForMoves } from './openings'
import { openingFamilyFr } from './openingNames'
import { Picker, type Vars } from './coachPhrases'
import { PIECE_FR, captureInfo, fork, isCheckmateFen, pinOrSkewer, sanOf } from './motifs'

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

// Classe rapide depuis les cp avant/après (point de vue du joueur qui a joué), seuils de
// review.ts. « Meilleur » est réservé au coup que le moteur jouait lui-même (pv[0]) : sans
// ce repère, un coup qui ne perd rien est « excellent ».
export function quickClass(cpBeforeMover: number, cpAfterMover: number, isBook: boolean, playedBest = false): MoveClass {
  if (isBook) return 'book'
  const drop = Math.max(0, winPct(cpBeforeMover) - winPct(cpAfterMover))
  if (drop < 3.5) return playedBest ? 'best' : 'excellent'
  if (drop < 7) return 'good'
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
function replay(uciMoves: string[], startFen?: string) {
  const c = new Chess(startFen)
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

const pairGender = (a: PieceSymbol, b: PieceSymbol): 'm' | 'f' => (PIECE_FR[a].genre === 'f' && PIECE_FR[b].genre === 'f' ? 'f' : 'm')

// Commentaire d'un coup en direct. `byPlayer` : coup du joueur, sinon du bot.
// `bestUci` : meilleur coup du moteur dans la position avant le coup (inconnu au 1er coup) ;
// `replyUci` : meilleure réponse du moteur après le coup ; `mateFor` : mat annoncé après le
// coup, en coups, positif s'il est pour le camp qui vient de jouer, négatif s'il est contre lui.
export function liveComment(opts: {
  san: string
  moverColor: 'w' | 'b'
  byPlayer: boolean
  cls: MoveClass
  uciMoves: string[]
  bestUci?: string | null
  replyUci?: string | null
  mateFor?: number | null
  startFen?: string
}): LiveComment {
  const { san, moverColor, byPlayer, cls, uciMoves } = opts
  const fig = figurine(san, moverColor)
  const opp = moverColor === 'w' ? 'b' : 'w'
  const i = uciMoves.length
  const vars: Vars = { coup: fig }
  let gender: 'm' | 'f' = 'm'
  let key: string
  let mood: LiveComment['mood'] = byPlayer
    ? (cls === 'blunder' || cls === 'mistake' || cls === 'missedWin' ? 'worried' : cls === 'best' || cls === 'excellent' || cls === 'great' || cls === 'brilliant' ? 'happy' : 'thinking')
    : (cls === 'mistake' || cls === 'blunder' || cls === 'miss' || cls === 'missedWin' ? 'happy' : 'thinking')

  let pos: ReturnType<typeof replay> | null = null
  try {
    pos = replay(uciMoves, opts.startFen)
  } catch {
    pos = null
  }
  const played = uciMoves[i - 1]
  const cap = pos ? captureInfo(pos.fenBefore, played, pos.lastCaptureSquare) : null
  const reply = pos && opts.replyUci && sanOf(pos.fenAfter, opts.replyUci) ? opts.replyUci : null
  const best = pos && opts.bestUci && opts.bestUci !== played && sanOf(pos.fenBefore, opts.bestUci) ? opts.bestUci : null
  const fault = FAULTS.includes(cls)
  const replyFig = () => figurine(sanOf(pos!.fenAfter, reply!)!, opp)
  const forkVars = (targets: PieceSymbol[], own: boolean) => {
    const name = (p: PieceSymbol) => (own ? PIECE_FR[p].ton : PIECE_FR[p].defini)
    Object.assign(vars, { cible: name(targets[0]), cible2: name(targets[1]) })
    gender = pairGender(targets[0], targets[1])
  }

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
  } else if (byPlayer && pos) {
    key = playerKey(pos)
  } else if (pos) {
    key = botKey(pos)
  } else key = byPlayer ? PLAYER_KEY[cls] ?? 'live.joueur.good' : 'live.adversaire.neutre'

  return { text: picker.say(key, i, vars, gender), headline: fig, cls, mood }

  // Joueur : ce qui menace d'abord (mat, fourchette, pièce perdue), puis ce qui a été manqué,
  // puis ce qui a été bien joué. « Manqué » et « autorisé » ne parlent que sur un coup fautif.
  function playerKey(p: NonNullable<typeof pos>): string {
    const mateAgainst = opts.mateFor && opts.mateFor < 0 ? -opts.mateFor : 0
    if (fault && mateAgainst === 1 && reply && isCheckmateFen(afterUci(p.fenAfter, reply))) {
      vars.reponse = replyFig()
      return 'live.joueur.autorise_mat'
    }
    if (fault && mateAgainst > 1) {
      vars.n = mateAgainst
      return 'live.joueur.autorise_mat_n'
    }
    if (fault && reply) {
      const f = fork(p.fenAfter, reply)
      // « Ce coup permet » n'est vérifié que si le meilleur coup empêchait la fourchette.
      if (f && best && !fork(afterUci(p.fenBefore, best), reply)) {
        vars.reponse = replyFig()
        forkVars(f.targets, true)
        return 'live.joueur.autorise_fourchette'
      }
      const cap2 = captureInfo(p.fenAfter, reply, null)
      const capturer = !!cap2 && cap2.square === p.to && !!p.captured
      if (cap2 && cap2.net >= 2 && !capturer) {
        const c = new Chess(p.fenAfter)
        gender = PIECE_FR[cap2.captured].genre
        Object.assign(vars, { piece: PIECE_FR[cap2.captured].ton, case: cap2.square, attaquant: PIECE_FR[cap2.by].defini })
        return c.attackers(cap2.square, moverColor).length > 0 ? 'live.joueur.mal_defendue' : 'live.joueur.piece_en_prise'
      }
    }
    if (fault && best) {
      vars.meilleur = figurine(sanOf(p.fenBefore, best)!, moverColor)
      if (isCheckmateFen(afterUci(p.fenBefore, best))) return 'live.joueur.mat_manque'
      const f = fork(p.fenBefore, best)
      if (f) {
        forkVars(f.targets, false)
        return 'live.joueur.fourchette_manquee'
      }
    }
    if (!fault) {
      const f = fork(p.fenBefore, played)
      if (f) {
        forkVars(f.targets, false)
        return 'live.joueur.fourchette'
      }
      const l = pinOrSkewer(p.fenBefore, played)
      if (l?.kind === 'clouage') {
        Object.assign(vars, { cible: PIECE_FR[l.front].defini, cible2: PIECE_FR[l.rear].defini })
        gender = PIECE_FR[l.front].genre
        return 'live.joueur.clouage'
      }
      if (cap?.kind === 'gain' && cap.clean) {
        vars.cible = PIECE_FR[cap.captured].defini
        return 'live.joueur.gain_materiel'
      }
      if (san.startsWith('O-O')) return 'live.joueur.roque'
    }
    return PLAYER_KEY[cls] ?? 'live.joueur.good'
  }

  // Bot : échec, fourchette contre le joueur, pièce du bot laissée en prise (seulement si la
  // meilleure réponse du joueur la prend), faute, capture, sinon neutre.
  function botKey(p: NonNullable<typeof pos>): string {
    // La fourchette avant l'échec : ♞c7+ sur le roi et la tour, c'est la fourchette qui compte.
    const f = fork(p.fenBefore, played)
    if (f) {
      forkVars(f.targets, true)
      return 'live.adversaire.fourchette'
    }
    if (san.includes('+')) return 'live.adversaire.echec'

    if (reply) {
      const cap2 = captureInfo(p.fenAfter, reply, null)
      const c = new Chess(p.fenAfter)
      if (cap2 && cap2.clean && cap2.net >= 2 && c.attackers(cap2.square, moverColor).length === 0) {
        gender = PIECE_FR[cap2.captured].genre
        Object.assign(vars, { cible: PIECE_FR[cap2.captured].defini, case: cap2.square })
        return 'live.adversaire.piece_en_prise'
      }
    }
    if (cls === 'blunder' || cls === 'missedWin') return 'live.adversaire.blunder'
    if (cls === 'mistake' || cls === 'miss') return 'live.adversaire.mistake'
    if (cap?.kind === 'gain') {
      vars.cible = PIECE_FR[cap.captured].defini
      return 'live.adversaire.capture'
    }
    if (cls === 'best' || cls === 'excellent' || cls === 'great' || cls === 'brilliant') return 'live.adversaire.best'
    return 'live.adversaire.neutre'
  }
}

// Position après un coup UCI, ou la même position si le coup est illégal.
function afterUci(fen: string, uci: string): string {
  const c = new Chess(fen)
  try {
    c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  } catch {
    return fen
  }
  return c.fen()
}

export function classMeta(cls: MoveClass) {
  return CLASS_META[cls]
}
