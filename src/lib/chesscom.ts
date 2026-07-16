// Client de l'API publique chess.com (api.chess.com/pub, CORS ouvert, sans auth).
// Lecture seule : archives mensuelles de parties d'un joueur.

export interface ChesscomGame {
  url: string
  pgn: string
  timeControl: string
  timeClass: string
  endTime: number // epoch secondes
  white: { username: string; rating: number; result: string }
  black: { username: string; rating: number; result: string }
  // Couleur du joueur `username` passé à fetchRecentGames.
  playerColor: 'w' | 'b'
}

async function fetchJson(url: string): Promise<unknown> {
  const res = await fetch(url)
  if (res.status === 404) throw new Error('Joueur introuvable sur chess.com.')
  if (!res.ok) throw new Error(`chess.com a répondu ${res.status}.`)
  return res.json()
}

interface RawGame {
  url: string
  pgn?: string
  time_control: string
  time_class: string
  end_time: number
  white: { username: string; rating: number; result: string }
  black: { username: string; rating: number; result: string }
}

// Parties récentes du joueur, les plus récentes d'abord.
export async function fetchRecentGames(username: string, months = 3, limit = 30): Promise<ChesscomGame[]> {
  const user = username.trim().toLowerCase()
  const archives = (await fetchJson(`https://api.chess.com/pub/player/${user}/games/archives`)) as {
    archives: string[]
  }
  const recent = archives.archives.slice(-months).reverse()
  const games: ChesscomGame[] = []
  for (const archiveUrl of recent) {
    const data = (await fetchJson(archiveUrl)) as { games: RawGame[] }
    for (const g of data.games) {
      if (!g.pgn) continue
      games.push({
        url: g.url,
        pgn: g.pgn,
        timeControl: g.time_control,
        timeClass: g.time_class,
        endTime: g.end_time,
        white: g.white,
        black: g.black,
        playerColor: g.white.username.toLowerCase() === user ? 'w' : 'b',
      })
    }
    if (games.length >= limit) break
  }
  return games.sort((a, b) => b.endTime - a.endTime).slice(0, limit)
}

// Retrouve une partie depuis un lien partagé par l'app chess.com
// (https://www.chess.com/game/live/123… ou /game/daily/123… ou /live/game/123…).
export function extractGameId(gameUrl: string): string | null {
  const m = gameUrl.match(/(?:game\/(?:live|daily)|live\/game|game)\/(\d+)/)
  return m ? m[1] : null
}

export async function findGameByUrl(username: string, gameUrl: string): Promise<ChesscomGame | null> {
  const id = extractGameId(gameUrl)
  if (!id) return null
  const games = await fetchRecentGames(username, 3, 200)
  return games.find((g) => extractGameId(g.url) === id) ?? null
}
