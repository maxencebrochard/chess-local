// Adversaires façon chess.com : personnalités avec force cible.
// Stockfish limite à 1320 Elo minimum via UCI_Elo ; en dessous on injecte
// des coups aléatoires avec une probabilité croissante.

export interface Bot {
  id: string
  name: string
  elo: number
  emoji: string
  description: string
  // Probabilité de jouer un coup aléatoire au lieu du coup moteur (bots faibles).
  randomness: number
  movetimeMs: number
}

export const BOTS: Bot[] = [
  { id: 'noa', name: 'Noa', elo: 400, emoji: '🐣', description: 'Débute à peine, laisse des pièces en prise.', randomness: 0.45, movetimeMs: 150 },
  { id: 'marty', name: 'Marty', elo: 700, emoji: '🤓', description: 'Connaît les règles, pas encore les plans.', randomness: 0.3, movetimeMs: 200 },
  { id: 'lea', name: 'Léa', elo: 1000, emoji: '🎒', description: 'Joueuse de club junior, tactique irrégulière.', randomness: 0.18, movetimeMs: 250 },
  { id: 'nina', name: 'Nina', elo: 1300, emoji: '☕', description: 'Habituée du club, solide en ouverture.', randomness: 0.08, movetimeMs: 300 },
  { id: 'iris', name: 'Iris', elo: 1600, emoji: '📚', description: 'Compétitrice sérieuse, punit les erreurs simples.', randomness: 0, movetimeMs: 350 },
  { id: 'viktor', name: 'Viktor', elo: 1900, emoji: '🧊', description: 'Positionnel et froid, rarement pressé.', randomness: 0, movetimeMs: 400 },
  { id: 'sofia', name: 'Sofia', elo: 2200, emoji: '🔥', description: 'Attaquante candidate maître.', randomness: 0, movetimeMs: 500 },
  { id: 'arun', name: 'Arun', elo: 2500, emoji: '🎯', description: 'Grand-maître, précision chirurgicale.', randomness: 0, movetimeMs: 700 },
  { id: 'maximus', name: 'Maximus', elo: 3200, emoji: '🤖', description: 'Stockfish pleine puissance. Bonne chance.', randomness: 0, movetimeMs: 1000 },
]

export function botById(id: string): Bot | undefined {
  return BOTS.find((b) => b.id === id)
}

// Options UCI pour un bot donné.
export function botEngineOptions(bot: Bot): Record<string, string | number | boolean> {
  if (bot.elo >= 3190) return { UCI_LimitStrength: false }
  return {
    UCI_LimitStrength: true,
    UCI_Elo: Math.max(1320, Math.min(3190, bot.elo)),
  }
}
