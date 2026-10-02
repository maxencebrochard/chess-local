// Finales jouées jusqu'au bout, façon Drills de chess.com : liste des positions par thème
// (`/finales`), puis partie contre Stockfish à pleine force sans plafond de coups
// (`/finales/:id`). Résultat noté à part, sans incidence sur l'Elo d'Apprendre.
import { useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Cta } from '../components/Cta'
import { PositionGame } from '../components/PositionGame'
import { courseFor } from '../lib/courses'
import { ENDGAMES, type EndgameItem } from '../lib/learn'
import {
  endgameTheme, GOAL_HINT, inProgressKey, recordEndgamePlay, solvedEndgames, THEME_LABEL,
  validFen, type EndgameTheme,
} from '../lib/positionGame'

const THEME_ORDER: EndgameTheme[] = ['mates', 'pawns', 'rooks', 'queen', 'other']

const solvedKey = (eg: EndgameItem) => `${eg.id}|${eg.fen}`

// Tirage d'une finale : d'abord parmi celles pas encore réussies, jamais la finale courante.
function pickEndgame(solved: Set<string>, exclude?: string): EndgameItem {
  const others = ENDGAMES.filter((e) => e.id !== exclude && validFen(e.fen))
  const fresh = others.filter((e) => !solved.has(solvedKey(e)))
  const pool = fresh.length ? fresh : others.length ? others : ENDGAMES
  return pool[Math.floor(Math.random() * pool.length)]
}

function useSolved(): Set<string> {
  const [solved, setSolved] = useState<Set<string>>(new Set())
  useEffect(() => {
    void solvedEndgames().then(setSolved)
  }, [])
  return solved
}

export default function Endgames() {
  const { id } = useParams()
  return id ? <EndgamePlay key={id} id={id} /> : <EndgameList />
}

function EndgameList() {
  const navigate = useNavigate()
  const solved = useSolved()
  const [inProgress] = useState(inProgressKey)

  const sections = useMemo(
    () =>
      THEME_ORDER.map((theme) => ({
        theme,
        items: ENDGAMES.filter((e) => endgameTheme(e.fen) === theme).sort((a, b) => a.difficulty - b.difficulty),
      })).filter((s) => s.items.length > 0),
    [],
  )

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <div className="mb-1 flex items-center gap-1">
        <button
          onClick={() => navigate('/apprendre')}
          aria-label="Retour à Apprendre"
          className="-ml-2 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-2xl text-neutral-400 hover:text-white"
        >
          ←
        </button>
        <h1 className="text-2xl font-black">🏁 Finales jusqu'au bout</h1>
      </div>
      <p className="mb-4 text-sm text-neutral-400">
        Une position de finale, Stockfish à pleine force en face, aucune limite de coups : tu joues jusqu'au mat ou jusqu'à la nulle.
      </p>

      <Cta className="mb-5 w-full" onClick={() => navigate(`/finales/${pickEndgame(solved).id}`)}>
        🎲 Au hasard
      </Cta>

      {sections.map(({ theme, items }) => (
        <section key={theme} data-testid="endgame-section" className="mb-4">
          <h2 className="mb-2 text-sm font-semibold text-neutral-400">{THEME_LABEL[theme]}</h2>
          <div className="flex flex-col gap-2">
            {items.map((eg) => {
              const done = solved.has(solvedKey(eg))
              const going = inProgress === `finale:${eg.id}|${eg.fen}`
              return (
                <button
                  key={eg.id}
                  data-testid="endgame-item"
                  data-id={eg.id}
                  onClick={() => navigate(`/finales/${eg.id}`)}
                  className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-bold">{eg.title}</span>
                    <span className="mt-0.5 flex items-center gap-2 text-xs">
                      <span
                        className={`rounded px-1.5 py-0.5 font-semibold ${
                          eg.objective === 'win' ? 'bg-accent/15 text-accent' : 'bg-sky-900/40 text-sky-300'
                        }`}
                      >
                        {eg.objective === 'win' ? 'Gagner' : 'Tenir la nulle'}
                      </span>
                      <span className="text-neutral-500">{eg.difficulty}</span>
                    </span>
                  </span>
                  {/* Une partie en cours prime : c'est elle qu'un tap reprend. */}
                  {going ? (
                    <span className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs font-semibold text-amber-200">En cours</span>
                  ) : done ? (
                    <span className="shrink-0 text-sm font-bold text-accent">✓ Réussie</span>
                  ) : (
                    <span aria-hidden="true" className="shrink-0 text-xl text-neutral-500">›</span>
                  )}
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

function EndgamePlay({ id }: { id: string }) {
  const navigate = useNavigate()
  const location = useLocation()
  const solved = useSolved()
  const eg = ENDGAMES.find((e) => e.id === id)
  if (!eg) return <Navigate to="/finales" replace />
  // Position illégale, ou camp du joueur qui n'a pas le trait : le joueur commence toujours.
  if (!validFen(eg.fen) || eg.fen.split(' ')[1] !== eg.side) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p className="text-neutral-300">La position de « {eg.title} » est invalide : impossible de la jouer.</p>
        <button onClick={() => navigate('/finales', { replace: true })} className="cursor-pointer rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Toutes les finales
        </button>
      </div>
    )
  }
  const restore = !!(location.state as { restore?: boolean } | null)?.restore

  return (
    <PositionGame
      gameKey={`finale:${eg.id}`}
      startFen={eg.fen}
      title={eg.title}
      objective={eg.objective}
      goalHint={GOAL_HINT[eg.goal]}
      lesson={eg.lesson}
      courseId={courseFor(eg.id) ? eg.id : null}
      restoreFinished={restore}
      returnTo={`/finales/${eg.id}`}
      returnLabel="Retour à la finale"
      // La liste est l'entrée d'en dessous quand on vient d'elle ; sinon (lien direct) on la pose.
      onExit={() => (((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0 ? navigate(-1) : navigate('/finales', { replace: true }))}
      onOther={() => navigate(`/finales/${pickEndgame(solved, eg.id).id}`, { replace: true })}
      onFinished={(success) => void recordEndgamePlay(eg.id, eg.fen, success)}
    />
  )
}
