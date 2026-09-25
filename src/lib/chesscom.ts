// Client de l'API publique chess.com (api.chess.com/pub, CORS ouvert, sans auth).
// Lecture seule : archives mensuelles de parties d'un joueur, plus les helpers purs
// (pseudo, lien de partie, libellés français) que la page d'import affiche.

export interface ChesscomGame {
  url: string
  pgn: string
  timeControl: string
  timeClass: string
  endTime: number // epoch secondes
  white: { username: string; rating: number; result: string }
  black: { username: string; rating: number; result: string }
  // Couleur du joueur dont on a lu l'archive.
  playerColor: 'w' | 'b'
}

type Side = ChesscomGame['white']

// Erreur de transport (réseau coupé, chess.com en panne, réponse illisible) : réessayable,
// contrairement à un pseudo inconnu ou un lien qui ne mène nulle part.
export class ChesscomNetworkError extends Error {}

async function fetchJson(url: string): Promise<unknown> {
  let res: Response
  try {
    res = await fetch(url)
  } catch (e) {
    // Erreur bas niveau (réseau, blocage, bug navigateur) : le détail part en console,
    // l'utilisateur reçoit une phrase courte sans URL technique.
    console.warn('[chess.com] requête impossible', url, e)
    throw new ChesscomNetworkError('chess.com est injoignable (réseau coupé ou bloqué). Réessaie dans un instant.')
  }
  if (res.status === 404) throw new Error('Joueur introuvable sur chess.com.')
  if (!res.ok) throw new ChesscomNetworkError(`chess.com a répondu ${res.status}. Réessaie dans un instant.`)
  try {
    return await res.json()
  } catch (e) {
    console.warn('[chess.com] réponse illisible', url, e)
    throw new ChesscomNetworkError('Réponse chess.com illisible. Réessaie dans un instant.')
  }
}

// Pseudo tel que chess.com l'accepte : lettres, chiffres, - et _ (l'API ignore la casse).
const USERNAME_RE = /^[a-z0-9_-]{1,50}$/
const MEMBER_URL_RE = /chess\.com\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?member\/([^/?#]+)/

// Retire ce que le clavier iOS ou un copier-coller ajoutent (espaces autour, caractères
// invisibles, majuscules), accepte une URL de profil chess.com/member/<pseudo>, et REFUSE tout
// le reste : supprimer un caractère en silence (« Éric_59 » -> « ric_59 », « magnus carlsen »
// -> « magnuscarlsen ») ferait interroger le compte d'un autre joueur sans le dire.
export function normalizeUsername(input: string): string {
  let user = input.trim().replace(/[\u200B-\u200D\uFEFF]/g, '').toLowerCase()
  const member = user.match(MEMBER_URL_RE)
  if (member) user = member[1]
  if (!user) throw new Error('Pseudo vide.')
  if (!USERNAME_RE.test(user)) throw new Error('Pseudo invalide : lettres, chiffres, - et _ seulement.')
  return user
}

interface RawGame {
  url: string
  pgn?: string
  time_control: string
  time_class: string
  end_time: number
  rules?: string
  white: Side
  black: Side
}

// Couleur du joueur dans une partie de SON archive, sans dépendre de la casse renvoyée par l'API.
function colorOf(g: RawGame, user: string): 'w' | 'b' | null {
  if (g.white?.username?.toLowerCase() === user) return 'w'
  if (g.black?.username?.toLowerCase() === user) return 'b'
  return null
}

// Partie exploitable par l'analyse, ou null : sans PGN, variante (chess960, bughouse, crazyhouse :
// PGN qui ne se charge pas ou position de départ non standard), ou joueur absent de la partie.
function toGame(g: RawGame, user: string): ChesscomGame | null {
  if (!g.pgn || g.rules !== 'chess') return null
  const playerColor = colorOf(g, user)
  if (!playerColor) return null
  return {
    url: g.url,
    pgn: g.pgn,
    timeControl: g.time_control,
    timeClass: g.time_class,
    endTime: g.end_time,
    white: g.white,
    black: g.black,
    playerColor,
  }
}

// URLs des archives mensuelles, les plus récentes d'abord ; un joueur sans partie a une liste vide.
async function recentArchives(user: string, months: number): Promise<string[]> {
  const data = (await fetchJson(`https://api.chess.com/pub/player/${encodeURIComponent(user)}/games/archives`)) as {
    archives?: unknown
  }
  const archives = Array.isArray(data?.archives) ? data.archives.filter((a): a is string => typeof a === 'string') : []
  return archives.slice(-months).reverse()
}

async function fetchArchive(archiveUrl: string): Promise<RawGame[]> {
  const data = (await fetchJson(archiveUrl)) as { games?: unknown }
  return Array.isArray(data?.games) ? (data.games as RawGame[]) : []
}

// Parties récentes du joueur, les plus récentes d'abord.
export async function fetchRecentGames(username: string, months = 3, limit = 30): Promise<ChesscomGame[]> {
  const user = normalizeUsername(username)
  const games: ChesscomGame[] = []
  for (const archiveUrl of await recentArchives(user, months)) {
    for (const raw of await fetchArchive(archiveUrl)) {
      const game = toGame(raw, user)
      if (game) games.push(game)
    }
    if (games.length >= limit) break
  }
  return games.sort((a, b) => b.endTime - a.endTime).slice(0, limit)
}

// Lien de partie tel que l'app ou le site chess.com le partagent : /game/live/123, /game/daily/123,
// /live/game/123, /daily/game/123, /game/123, précédé ou non de /analysis/ et d'une langue (/fr/),
// quelle que soit la casse, suivi ou non de ?tab=review, d'une ancre ou d'une ponctuation collée.
// Ancré sur l'hôte chess.com : /events/2024/game/1/12 ou /member/game/42 ne sont pas des parties.
const GAME_URL_RE =
  /(?:^|\/\/)(?:[a-z0-9-]+\.)*chess\.com\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?(?:analysis\/)?(?:game\/(?:live|daily)|(?:live|daily)\/game|game)\/(\d+)(?=[/?#.,;)\s]|$)/i

export function extractGameId(gameUrl: string): string | null {
  const m = gameUrl.trim().match(GAME_URL_RE)
  return m ? m[1] : null
}

// Les parties contre l'ordinateur (/game/computer/…) n'existent pas dans l'API publique.
export function isComputerGameUrl(gameUrl: string): boolean {
  return /chess\.com\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?(?:analysis\/)?game\/computer\//i.test(gameUrl)
}

// Retrouve une partie partagée dans les archives du joueur, mois par mois du plus récent au plus
// ancien, sans plafond de parties (un joueur de bullet dépasse 200 parties en deux semaines) et en
// s'arrêtant dès qu'elle est trouvée : moins de réseau aussi.
export async function findGameByUrl(username: string, gameUrl: string): Promise<ChesscomGame | null> {
  const id = extractGameId(gameUrl)
  if (!id) return null
  const user = normalizeUsername(username)
  for (const archiveUrl of await recentArchives(user, 3)) {
    const raw = (await fetchArchive(archiveUrl)).find((g) => extractGameId(g.url) === id)
    if (!raw) continue
    const game = toGame(raw, user)
    if (game) return game
    throw new Error(
      raw.rules && raw.rules !== 'chess'
        ? `Cette partie est une variante (${raw.rules}) : non prise en charge.`
        : "Cette partie n'a pas de PGN exploitable.",
    )
  }
  return null
}

// Libellés français des codes de l'API.
const TIME_CLASS_FR: Record<string, string> = { bullet: 'bullet', blitz: 'blitz', rapid: 'rapide', daily: 'différé' }

export function timeClassLabel(timeClass: string): string {
  return TIME_CLASS_FR[timeClass] ?? timeClass
}

// Codes de résultat chess.com qui valent une nulle, quel que soit le camp qui les porte.
const DRAW_RESULTS = new Set(['agreed', 'repetition', 'stalemate', 'insufficient', '50move', 'timevsinsufficient'])

// Issue de la partie pour le joueur dont on a lu l'archive.
export function outcomeFor(g: Pick<ChesscomGame, 'white' | 'black' | 'playerColor'>): 'win' | 'draw' | 'loss' {
  const me = g.playerColor === 'w' ? g.white : g.black
  if (me.result === 'win') return 'win'
  return DRAW_RESULTS.has(me.result) ? 'draw' : 'loss'
}

// Motif de fin : chess.com le code sur le camp qui n'a pas gagné (« checkmated », « resigned »…).
const TERMINATION_FR: Record<string, string> = {
  checkmated: 'mat',
  resigned: 'abandon',
  timeout: 'au temps',
  abandoned: 'partie abandonnée',
  agreed: 'nulle par accord',
  repetition: 'répétition',
  stalemate: 'pat',
  insufficient: 'matériel insuffisant',
  '50move': 'règle des 50 coups',
  timevsinsufficient: 'temps contre matériel insuffisant',
}

export function terminationLabel(g: Pick<ChesscomGame, 'white' | 'black' | 'playerColor'>): string {
  const me = g.playerColor === 'w' ? g.white : g.black
  const opp = g.playerColor === 'w' ? g.black : g.white
  const code = me.result === 'win' ? opp.result : me.result
  return TERMINATION_FR[code] ?? code
}

// Nombre de coups complets d'un PGN : en-têtes et commentaires {…} ignorés, et « 1... » (reprise
// des Noirs après un commentaire, systématique dans les PGN chess.com) non compté.
export function moveCount(pgn: string): number {
  const movetext = pgn.replace(/^\[.*\]\s*$/gm, '').replace(/\{[^}]*\}/g, '')
  return (movetext.match(/\b\d+\.(?!\.)/g) ?? []).length
}
