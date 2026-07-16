import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchRecentGames, findGameByUrl, type ChesscomGame } from '../lib/chesscom'
import { useSettings } from '../store/settings'

const APP_URL = 'https://maxencebrochard.github.io/chess-local/'

export default function Import() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { chesscomUsername, setChesscomUsername } = useSettings()
  const [usernameInput, setUsernameInput] = useState(chesscomUsername)
  const [games, setGames] = useState<ChesscomGame[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [link, setLink] = useState('')
  const [deepLinkStatus, setDeepLinkStatus] = useState('')

  const openReview = useCallback(
    (game: ChesscomGame) => {
      navigate('/analyse', {
        state: {
          pgn: game.pgn,
          color: game.playerColor,
          label: `chess.com · ${game.white.username} vs ${game.black.username}`,
          review: true,
        },
      })
    },
    [navigate],
  )

  const loadGames = useCallback(async (user: string) => {
    if (!user.trim()) return
    setLoading(true)
    setError('')
    try {
      setGames(await fetchRecentGames(user))
    } catch (e) {
      setGames(null)
      setError(navigator.onLine ? (e as Error).message : "Pas de connexion — l'import chess.com nécessite internet.")
    } finally {
      setLoading(false)
    }
  }, [])

  // Deep-link du Raccourci iOS : /#/import?url=…
  useEffect(() => {
    const sharedUrl = params.get('url')
    if (!sharedUrl || !chesscomUsername) return
    setDeepLinkStatus('Recherche de la partie partagée…')
    void findGameByUrl(chesscomUsername, sharedUrl)
      .then((game) => {
        if (game) openReview(game)
        else setDeepLinkStatus('Partie introuvable dans tes 3 derniers mois chess.com.')
      })
      .catch((e) => setDeepLinkStatus((e as Error).message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (chesscomUsername) void loadGames(chesscomUsername)
  }, [chesscomUsername, loadGames])

  async function handleLink() {
    if (!link.trim() || !chesscomUsername) return
    setLoading(true)
    setError('')
    try {
      const game = await findGameByUrl(chesscomUsername, link)
      if (game) openReview(game)
      else setError('Partie introuvable — vérifie le lien et que la partie est à toi (3 derniers mois).')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function resultFor(g: ChesscomGame): { label: string; color: string } {
    const me = g.playerColor === 'w' ? g.white : g.black
    if (me.result === 'win') return { label: 'G', color: 'text-accent' }
    if (['agreed', 'repetition', 'stalemate', 'insufficient', '50move', 'timevsinsufficient'].includes(me.result))
      return { label: '½', color: 'text-neutral-300' }
    return { label: 'P', color: 'text-red-400' }
  }

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <h1 className="mb-1 text-2xl font-bold">♟ Importer depuis chess.com</h1>
      <p className="mb-5 text-sm text-neutral-400">
        Tes parties chess.com, analysées par le coach local. Nécessite internet pour récupérer la partie ; le bilan
        tourne ensuite 100 % sur l'appareil.
      </p>

      {deepLinkStatus && <p className="mb-4 rounded bg-surface-2 p-3 text-sm text-neutral-300">{deepLinkStatus}</p>}

      <div className="mb-4 flex gap-2">
        <input
          value={usernameInput}
          onChange={(e) => setUsernameInput(e.target.value)}
          placeholder="Ton pseudo chess.com"
          className="flex-1 rounded bg-surface-2 px-3 py-2 outline-none placeholder:text-neutral-500"
        />
        <button
          onClick={() => setChesscomUsername(usernameInput.trim())}
          disabled={!usernameInput.trim()}
          className="cursor-pointer rounded bg-accent px-4 py-2 font-bold text-white hover:bg-accent-hover disabled:opacity-40"
        >
          {chesscomUsername ? 'Actualiser' : 'Connecter'}
        </button>
      </div>

      {chesscomUsername && (
        <div className="mb-4 flex gap-2">
          <input
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="…ou colle un lien de partie (Partager → Copier le lien)"
            className="flex-1 rounded bg-surface-2 px-3 py-2 text-sm outline-none placeholder:text-neutral-500"
          />
          <button
            onClick={() => void handleLink()}
            disabled={!link.trim() || loading}
            className="cursor-pointer rounded bg-surface-3 px-4 py-2 text-sm font-semibold hover:bg-surface-3/70 disabled:opacity-40"
          >
            Bilan
          </button>
        </div>
      )}

      {error && <p className="mb-4 rounded bg-red-900/40 p-3 text-sm text-red-300">{error}</p>}
      {loading && <p className="mb-4 text-sm text-neutral-400">Chargement…</p>}

      {games && !loading && (
        <div className="mb-6 space-y-1">
          {games.length === 0 && <p className="text-sm text-neutral-500">Aucune partie récente trouvée.</p>}
          {games.map((g) => {
            const res = resultFor(g)
            const opponent = g.playerColor === 'w' ? g.black : g.white
            return (
              <button
                key={g.url}
                onClick={() => openReview(g)}
                className="flex w-full cursor-pointer items-center gap-3 rounded bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
              >
                <span className={`w-5 text-center text-lg font-black ${res.color}`}>{res.label}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">
                    vs {opponent.username} ({opponent.rating})
                    <span className="ml-2 text-xs font-normal text-neutral-500">
                      {g.playerColor === 'w' ? 'Blancs' : 'Noirs'}
                    </span>
                  </div>
                  <div className="text-xs text-neutral-400">
                    {new Date(g.endTime * 1000).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })} ·{' '}
                    {g.timeClass}
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
                {APP_URL}#/import?url=[Entrée du raccourci]
              </code>
              (insère la variable « Entrée du raccourci » à la fin)
            </li>
            <li>Dans l'app chess.com : partie → <b>Partager</b> → <b>Bilan ChessLocal</b>. Le coach s'ouvre direct.</li>
          </ol>
        </div>
      </details>
    </div>
  )
}
