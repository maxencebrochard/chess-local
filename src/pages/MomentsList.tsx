// Liste « Moments critiques » (`/apprendre/moments-critiques`, Réviser mes parties) : les moments
// critiques de tes parties déjà analysées, relus dans le cache des bilans (`loadMomentGames`,
// lib/criticalMoments.ts) sans moteur ni écriture. Chaque entrée ouvre l'exercice existant
// `/moment-critique` avec le même state que depuis le bilan, plus `from: 'liste'` : la sortie de
// l'exercice ramène ici. L'état affiché (retrouvé, manqué) vient du domaine `critical-moment`.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ClassIcon } from '../components/ClassIcon'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { loadMomentGames, momentHistory, momentState, type CriticalMoment, type MomentGame, type MomentHistory } from '../lib/criticalMoments'
import { REVIEW_BACK } from '../lib/navigation'
import { inProgressKey } from '../lib/positionGame'
import { figurine } from '../lib/review'

const RESULT_LABEL: Record<MomentGame['result'], string> = { win: 'Victoire', draw: 'Nulle', loss: 'Défaite' }
const DATE_FR = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })

export default function MomentsList() {
  const navigate = useNavigate()
  const [games, setGames] = useState<MomentGame[] | null>(null)
  const [history, setHistory] = useState<Map<string, MomentHistory>>(new Map())
  const [inProgress] = useState(inProgressKey)

  useEffect(() => {
    let alive = true
    void (async () => {
      const list = await loadMomentGames().catch(() => [] as MomentGame[])
      const h = await momentHistory(list.flatMap((g) => g.moments.map((m) => m.fen))).catch(() => new Map<string, MomentHistory>())
      if (!alive) return
      setHistory(h)
      setGames(list)
    })()
    return () => {
      alive = false
    }
  }, [])

  // `replace` comme depuis le bilan : l'exercice prend la place de la liste, et sa sortie la lui
  // rend (CriticalMoment.tsx) ; le retour arrière depuis l'exercice ramène à Réviser mes parties.
  function open(g: MomentGame, m: CriticalMoment) {
    navigate('/moment-critique', { replace: true, state: momentState(g.review, m, g.ctx, 'liste') })
  }

  const total = games?.reduce((n, g) => n + g.moments.length, 0) ?? 0
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader
        title="Moments critiques"
        description="Les positions où tes parties analysées ont basculé. Rejoue-les contre Stockfish pour retrouver le bon coup."
        back={{ label: REVIEW_BACK.label, onClick: () => navigate(REVIEW_BACK.to) }}
      />
      {games === null && <p role="status" data-testid="moments-loading" className="text-muted">Lecture de tes parties analysées…</p>}
      {games?.length === 0 && (
        <EmptyState testId="moments-empty" title="Analyse une partie pour voir ses moments critiques" to="/insights" action="Ouvrir Mon bilan">
          Mon bilan passe tes dernières parties au crible de Stockfish et garde leurs bilans : leurs moments critiques
          apparaîtront ici. Le bilan d'une seule partie, lancé dans l'analyse, les montre en bas de son résumé.
        </EmptyState>
      )}
      {games && games.length > 0 && (
        <>
          <p data-testid="moments-summary" className="mb-4 text-sm text-muted">
            {total} moment{total > 1 ? 's' : ''} dans {games.length} partie{games.length > 1 ? 's' : ''}, de la plus récente à la plus ancienne.
          </p>
          {games.map((g) => (
            <section key={g.key} data-testid="moments-game" data-key={g.key} aria-labelledby={`moments-${g.key}`} className="mb-6 last:mb-0">
              <h2 id={`moments-${g.key}`} className="text-lg font-semibold">
                Contre {g.opponent}{g.opponentRating !== null && <span className="font-normal text-muted"> ({g.opponentRating})</span>}
              </h2>
              <p className="mb-2 text-sm text-muted">
                {RESULT_LABEL[g.result]} · {g.source === 'chesscom' ? 'chess.com' : 'ChessLocal'} · {DATE_FR.format(g.date)}
              </p>
              <div className="grid gap-2">
                {g.moments.map((m) => (
                  <MomentRow
                    key={m.index}
                    moment={m}
                    history={history.get(m.fen) ?? null}
                    going={inProgress === `moment|${m.fen}`}
                    onOpen={() => open(g, m)}
                  />
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </div>
  )
}

function MomentRow({ moment: m, history, going, onOpen }: { moment: CriticalMoment; history: MomentHistory | null; going: boolean; onOpen: () => void }) {
  return (
    <button
      type="button"
      data-testid="moment-item"
      data-fen={m.fen}
      data-best={m.bestUci}
      data-status={going ? 'going' : history?.move ?? ''}
      onClick={onOpen}
      className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
    >
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
          <span className="font-semibold">Coup {m.moveNo}</span>
          {!m.found && (
            <>
              <span className="text-sm text-neutral-300">· tu as joué</span>
              <span className="text-sm font-semibold text-neutral-100">{figurine(m.playedSan, m.color)}</span>
              <ClassIcon cls={m.cls} size={18} />
            </>
          )}
        </span>
        <span className="mt-0.5 block text-sm text-muted">
          {m.found ? 'Tu avais trouvé le seul coup qui tenait : retrouve-le' : `Chances de gain : ${Math.round(m.winBefore)} % → ${Math.round(m.winBefore - m.drop)} %`}
        </span>
      </span>
      {going ? (
        <span className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs font-semibold text-amber-200">En cours</span>
      ) : history?.move === 'found' ? (
        <span className="shrink-0 text-sm font-bold text-accent">✓ Retrouvé</span>
      ) : history?.move === 'missed' ? (
        <span className="shrink-0 text-sm font-bold text-red-300">✗ Manqué</span>
      ) : (
        <span aria-hidden="true" className="shrink-0 text-xl text-neutral-500">›</span>
      )}
    </button>
  )
}
