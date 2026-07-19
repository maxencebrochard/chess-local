// Coach live du mode entraîneur : phrases courtes en direct, façon chess.com.
// Classification rapide d'un coup à partir des évals avant/après (win%).
import { CLASS_META, figurine, winPct, type MoveClass } from './review'
import { openingForMoves } from './openings'

export interface LiveComment {
  text: string
  cls: MoveClass | null
  mood: 'happy' | 'thinking' | 'worried'
}

export const GREETINGS = [
  'Allez, on lance la partie. On la passera en revue après — bonne chance.',
  'Une partie par jour éloigne les gaffes pour toujours. Enfin presque.',
  'Concentré. Chaque coup a une idée derrière lui.',
]

export function greeting(): LiveComment {
  return { text: GREETINGS[Math.floor(Math.random() * GREETINGS.length)], cls: null, mood: 'happy' }
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

const BY_CLASS: Record<string, string[]> = {
  best: ['Exactement ça.', 'Propre. Le moteur approuve.', 'Rien à redire sur ce coup.'],
  good: ['Ça tient la route.', 'Solide, la position reste saine.', 'Correct.'],
  inaccuracy: ['Hmm, il y avait un peu mieux.', 'La position glisse légèrement.', 'Pas terrible, sans être grave.'],
  mistake: ['Aïe, ça donne une vraie chance à l\'adversaire.', 'Ça, ça va coûter quelque chose.', 'Le moteur grimace.'],
  blunder: ['Ouille. On en reparlera au bilan…', 'Ça fait mal. La position vient de basculer.', 'Grosse occasion pour le camp adverse.'],
}

const BOT_GOOD = ['Ton adversaire joue juste, reste attentif.', 'Bonne réponse en face. À toi de trouver le plan.']
const BOT_BAD = ['Ton adversaire vient de se tromper — punis-le !', 'Cadeau en face. Cherche le coup qui punit.']

// Commentaire d'un coup en direct. `mover` : 'player' ou 'bot'.
export function liveComment(opts: {
  san: string
  moverColor: 'w' | 'b'
  byPlayer: boolean
  cls: MoveClass
  uciMoves: string[]
}): LiveComment {
  const { san, moverColor, byPlayer, cls, uciMoves } = opts
  const fig = figurine(san, moverColor)

  if (cls === 'book') {
    const opening = openingForMoves(uciMoves)
    if (opening && uciMoves.length <= 8) {
      return {
        text: uciMoves.length === 1
          ? `${fig} — le grand classique. On prend le centre.`
          : `Ah, ${opening.name.split(':')[0]}. Terrain connu.`,
        cls,
        mood: 'happy',
      }
    }
    return { text: `${fig} suit la théorie.`, cls, mood: 'thinking' }
  }

  const pool = byPlayer
    ? BY_CLASS[cls] ?? BY_CLASS.good
    : cls === 'mistake' || cls === 'blunder'
      ? BOT_BAD
      : cls === 'best'
        ? BOT_GOOD
        : null
  if (!pool) return { text: `${fig}.`, cls, mood: 'thinking' }
  const text = `${fig} — ${pool[Math.floor(Math.random() * pool.length)]}`
  const mood = cls === 'blunder' || cls === 'mistake' ? (byPlayer ? 'worried' : 'happy') : cls === 'best' ? 'happy' : 'thinking'
  return { text, cls, mood }
}

export function classMeta(cls: MoveClass) {
  return CLASS_META[cls]
}
