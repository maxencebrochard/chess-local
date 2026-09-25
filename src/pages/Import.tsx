import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ChesscomNetworkError,
  extractGameId,
  fetchRecentGames,
  findGameByUrl,
  isComputerGameUrl,
  moveCount,
  normalizeUsername,
  outcomeFor,
  terminationLabel,
  timeClassLabel,
  type ChesscomGame,
} from '../lib/chesscom'
import { useSettings } from '../store/settings'

const APP_URL = 'https://maxencebrochard.github.io/chess-local/'

const OUTCOME_STYLE = {
  win: { label: 'G', color: 'text-accent' },
  draw: { label: '½', color: 'text-neutral-300' },
  loss: { label: 'P', color: 'text-red-400' },
}

const FIELD = 'min-w-0 flex-1 rounded bg-surface-2 px-3 py-2 outline-none placeholder:text-neutral-500 focus-visible:ring-2 focus-visible:ring-accent'

// Erreur affichable, avec l'action à rejouer telle qu'elle a échoué (pseudo ou lien capturés),
// seulement quand réessayer a un sens (transport), pas pour un pseudo inconnu ou une variante.
interface Failure {
  message: string
  retry?: () => void
}

function failure(e: unknown, retry: () => void): Failure {
  if (!navigator.onLine) return { message: "Pas de connexion : l'import chess.com nécessite internet.", retry }
  const message = e instanceof Error ? e.message : String(e)
  return e instanceof ChesscomNetworkError ? { message, retry } : { message }
}

// Ce qui empêche de chercher un lien, avant toute requête.
function linkProblem(link: string): string | null {
  if (isComputerGameUrl(link)) return "Les parties contre l'ordinateur ne sont pas disponibles via chess.com."
  if (!extractGameId(link)) return "Ce lien n'est pas une partie chess.com (attendu : https://www.chess.com/game/live/123456789)."
  return null
}

export default function Import() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { chesscomUsername, setChesscomUsername } = useSettings()
  // ?user= : le Raccourci iOS ouvre Safari, dont le stockage est séparé de l'app installée ;
  // le pseudo voyage donc dans le lien et prime sur celui mémorisé ici.
  const [usernameInput, setUsernameInput] = useState(() => params.get('user') || chesscomUsername)
  const [games, setGames] = useState<ChesscomGame[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Failure | null>(null)
  const [link, setLink] = useState('')
  const sharedUrl = params.get('url') ?? ''
  const sharedProblem = sharedUrl ? linkProblem(sharedUrl) : null

  function openReview(game: ChesscomGame) {
    navigate('/analyse', {
      state: {
        pgn: game.pgn,
        color: game.playerColor,
        label: `chess.com · ${game.white.username} contre ${game.black.username}`,
        review: true,
      },
    })
  }

  // Pseudo du champ, validé sans requête ; null (et message) s'il est vide ou invalide.
  function currentUser(): string | null {
    if (!usernameInput.trim()) {
      setError({ message: "Entre d'abord ton pseudo chess.com." })
      return null
    }
    try {
      return normalizeUsername(usernameInput)
    } catch (e) {
      setError({ message: (e as Error).message })
      return null
    }
  }

  // Rien ne part vers chess.com sans une action explicite : pas de chargement au montage.
  // Le pseudo n'est mémorisé qu'après un chargement réussi (une liste vide en est un) :
  // un pseudo inconnu ne remplace jamais le bon.
  async function loadGames(user: string) {
    setLoading(true)
    setError(null)
    try {
      setGames(await fetchRecentGames(user))
      setChesscomUsername(user)
      setUsernameInput(user)
    } catch (e) {
      setGames(null)
      setError(failure(e, () => void loadGames(user)))
    } finally {
      setLoading(false)
    }
  }

  async function searchLink(rawLink: string, user: string) {
    setLoading(true)
    setError(null)
    try {
      const game = await findGameByUrl(user, rawLink)
      if (!game) {
        setError({ message: 'Partie introuvable : vérifie le lien, et que la partie est à toi (3 derniers mois).' })
        return
      }
      setChesscomUsername(user)
      openReview(game)
    } catch (e) {
      setError(failure(e, () => void searchLink(rawLink, user)))
    } finally {
      setLoading(false)
    }
  }

  function submitUsername() {
    const user = currentUser()
    if (user) void loadGames(user)
  }

  function submitLink(rawLink: string) {
    const trimmed = rawLink.trim()
    if (!trimmed) return
    const problem = linkProblem(trimmed)
    if (problem) {
      setError({ message: problem })
      return
    }
    const user = currentUser()
    if (user) void searchLink(trimmed, user)
  }

  const hasUser = usernameInput.trim() !== ''

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <h1 className="mb-1 text-2xl font-bold">♟ Importer depuis chess.com</h1>
      <p className="mb-5 text-sm text-neutral-400">
        Tes parties chess.com, analysées par le coach local. Rien ne part vers chess.com avant que tu ne le
        demandes ; le bilan tourne ensuite 100 % sur l'appareil.
      </p>

      <form
        className="mb-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          submitUsername()
        }}
      >
        <input
          value={usernameInput}
          onChange={(e) => setUsernameInput(e.target.value)}
          placeholder="Ton pseudo chess.com"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="go"
          className={FIELD}
        />
        <button
          type="submit"
          disabled={loading || !hasUser}
          className="shrink-0 cursor-pointer whitespace-nowrap rounded bg-accent px-4 py-2 font-bold text-white hover:bg-accent-hover disabled:opacity-40"
        >
          {games ? 'Actualiser' : 'Voir mes parties'}
        </button>
      </form>

      {sharedUrl && (
        <div className="mb-4 rounded bg-surface-2 p-3 text-sm text-neutral-300">
          <p className="font-semibold">Partie partagée depuis chess.com</p>
          <p className="break-all text-xs text-neutral-500">{sharedUrl}</p>
          {sharedProblem ? (
            <p className="mt-2">{sharedProblem}</p>
          ) : (
            <>
              {!hasUser && <p className="mt-2">Entre d'abord ton pseudo chess.com ci-dessus.</p>}
              <button
                type="button"
                onClick={() => submitLink(sharedUrl)}
                disabled={loading || !hasUser}
                className="mt-2 cursor-pointer rounded bg-accent px-4 py-2 font-bold text-white hover:bg-accent-hover disabled:opacity-40"
              >
                Chercher cette partie sur chess.com
              </button>
            </>
          )}
        </div>
      )}

      {(chesscomUsername || hasUser) && (
        <form
          className="mb-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            submitLink(link)
          }}
        >
          <input
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="…ou colle un lien de partie"
            inputMode="url"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="go"
            className={`${FIELD} text-base`}
          />
          <button
            type="submit"
            disabled={!link.trim() || loading}
            className="shrink-0 cursor-pointer rounded bg-surface-3 px-4 py-2 text-sm font-semibold hover:bg-surface-3/70 disabled:opacity-40"
          >
            Bilan
          </button>
        </form>
      )}

      {error && (
        <div role="alert" className="mb-4 flex flex-wrap items-center gap-2 rounded bg-red-900/40 p-3 text-sm text-red-300">
          <span className="min-w-0 flex-1 break-words">{error.message}</span>
          {error.retry && (
            <button
              type="button"
              onClick={error.retry}
              disabled={loading}
              className="shrink-0 cursor-pointer rounded bg-red-900/60 px-3 py-1.5 font-semibold hover:bg-red-900/80 disabled:opacity-40"
            >
              Réessayer
            </button>
          )}
        </div>
      )}
      {loading && <p className="mb-4 text-sm text-neutral-400">Chargement…</p>}

      {games && !loading && (
        <div className="mb-6 space-y-1">
          {games.length === 0 && <p className="text-sm text-neutral-500">Aucune partie récente trouvée.</p>}
          {games.map((g) => {
            const res = OUTCOME_STYLE[outcomeFor(g)]
            const white = g.playerColor === 'w'
            const opponent = white ? g.black : g.white
            return (
              <button
                key={g.url}
                onClick={() => openReview(g)}
                className="flex w-full cursor-pointer items-center gap-3 rounded bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
              >
                <span className={`w-5 shrink-0 text-center text-lg font-black ${res.color}`}>{res.label}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      role="img"
                      aria-label={white ? 'Blancs' : 'Noirs'}
                      title={white ? 'Blancs' : 'Noirs'}
                      className={`h-3 w-3 shrink-0 rounded-full border ${white ? 'border-neutral-500 bg-white' : 'border-neutral-300 bg-neutral-900'}`}
                    />
                    <span className="truncate font-semibold">contre {opponent.username}</span>
                    <span className="shrink-0 text-sm text-neutral-400">({opponent.rating})</span>
                  </div>
                  <div className="truncate text-xs text-neutral-400">
                    {new Date(g.endTime * 1000).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })} ·{' '}
                    {timeClassLabel(g.timeClass)} · {moveCount(g.pgn)} coups · {terminationLabel(g)}
                  </div>
                </div>
                <span className="shrink-0 rounded bg-accent/20 px-2.5 py-1 text-xs font-semibold text-accent">
                  🔍 Bilan
                </span>
              </button>
            )
          })}
        </div>
      )}

      <details className="rounded bg-surface-2 p-4">
        <summary className="cursor-pointer font-semibold">📲 Partager directement depuis l'app chess.com</summary>
        <div className="mt-3 space-y-2 text-sm text-neutral-300">
          <p>iOS ne laisse pas une web-app apparaître dans le menu Partager. Un Raccourci Apple le fait (2 min, une fois) :</p>
          <ol className="list-decimal space-y-1 pl-5">
            <li>Ouvre l'app <b>Raccourcis</b> → « + » → nomme-le <b>Bilan ChessLocal</b>.</li>
            <li>Touche « i » en bas → active <b>Afficher dans la feuille de partage</b> → type d'entrée : <b>URL</b>.</li>
            <li>
              Ajoute l'action <b>Ouvrir les URL</b> avec :
              <code className="mt-1 block break-all rounded bg-surface p-2 text-xs">
                {`${APP_URL}#/import?user=${chesscomUsername || 'TON_PSEUDO'}&url=[Entrée du raccourci]`}
              </code>
              (insère la variable « Entrée du raccourci » à la fin)
            </li>
            <li>
              Dans l'app chess.com : partie → <b>Partager</b> → <b>Bilan ChessLocal</b>, puis « Chercher cette partie ».
            </li>
          </ol>
          <p>
            Le Raccourci ouvre ChessLocal dans Safari, pas dans l'app installée sur l'écran d'accueil, et les deux ne
            partagent pas leurs données. Pour garder le bilan et ses fautes dans l'app, copie plutôt le lien de la
            partie et colle-le ci-dessus.
          </p>
        </div>
      </details>
      <p className="mt-4 text-center text-[10px] text-neutral-600">build {__BUILD__}</p>
    </div>
  )
}
