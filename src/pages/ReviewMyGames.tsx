// « Réviser mes parties » (`/apprendre/mes-parties`) : tout ce qui se rejoue à partir de tes
// propres parties. Révision espacée, Mes erreurs (séance d'Apprendre, domaine `mistakes`), attaques
// manquées, défenses ratées et moments critiques. Chaque entrée garde la page et la persistance de
// sa fonction ; cette page ne fait que les réunir, avec un compte réel par entrée.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ActivityCard } from '../components/ActivityCard'
import { PageHeader } from '../components/PageHeader'
import { SessionFailed } from '../components/SessionFailed'
import { useSessionFailed } from '../components/useSessionFailed'
import { db } from '../lib/db'
import { loadAttackDiagnostic, loadDefenseDiagnostic } from '../lib/kingAttack'
import { LEARN_BACK, MOMENTS_ROOT, REVIEW_ROOT } from '../lib/navigation'
import { describeKinds, dueLabel, loadReviewQueue, type ReviewQueue } from '../lib/revision'

interface Counts {
  mistakes: number
  attacks: number
  defenses: number
  analysed: number // parties du cache des bilans (table `reviews`), source des moments critiques
}

function CountBadge({ n, testId }: { n: number; testId?: string }) {
  return (
    <span data-testid={testId} className={`shrink-0 rounded-full px-2.5 py-0.5 text-sm font-bold tabular-nums ${n > 0 ? 'bg-accent/20 text-accent-light' : 'bg-surface-3 text-neutral-300'}`}>
      {n}
    </span>
  )
}

export default function ReviewMyGames() {
  const navigate = useNavigate()
  const failed = useSessionFailed()
  const [review, setReview] = useState<ReviewQueue | null>(null)
  const [counts, setCounts] = useState<Counts | null>(null)

  useEffect(() => {
    let alive = true
    void loadReviewQueue().then((q) => alive && setReview(q))
    void Promise.all([
      db.mistakes.where('solved').equals(0).count(),
      loadAttackDiagnostic().then((d) => d.items.length).catch(() => 0),
      loadDefenseDiagnostic().then((d) => d.items.length).catch(() => 0),
      db.reviews.count(),
    ]).then(([mistakes, attacks, defenses, analysed]) => alive && setCounts({ mistakes, attacks, defenses, analysed }))
    return () => {
      alive = false
    }
  }, [])

  const due = review?.due.length ?? 0
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader
        title="Réviser mes parties"
        description="Tes propres fautes et tournants, rejoués jusqu'à trouver le bon coup."
        back={{ label: LEARN_BACK.label, onClick: () => navigate(LEARN_BACK.to) }}
      />
      {failed && <SessionFailed>Aucune faute à rejouer pour l'instant.</SessionFailed>}
      <div className="grid gap-2">
        {/* Révision espacée : descente avec retour ici en fin de séance (Revision.tsx). */}
        <ActivityCard iconWidth
          to="/revision"
          state={{ returnTo: REVIEW_ROOT }}
          icon="📅"
          title="Révision espacée"
          description={review === null ? 'Lecture des échéances…'
            : review.due.length > 0 ? `À réviser aujourd'hui : ${describeKinds(review.due)}`
            : review.upcoming.length > 0 ? `Rien à réviser aujourd'hui · prochaine ${dueLabel(review.upcoming[0].due)}`
            : 'Puzzles, erreurs et variantes ratés reviennent à J+1, J+3, J+7 puis J+21'}
          aside={due > 0 ? <span data-review-count className="shrink-0 rounded-full bg-amber-400 px-2.5 py-0.5 text-sm font-bold text-neutral-900">{due}</span> : undefined}
        />
        <ActivityCard iconWidth
          onClick={() => navigate('/apprendre', { replace: true, state: { domain: 'mistakes', returnTo: REVIEW_ROOT, returnLabel: 'Retour à Réviser mes parties' } })}
          disabled={!counts?.mistakes}
          data-testid="mistakes-card"
          data-count={counts?.mistakes ?? ''}
          icon="🩹"
          title="Mes erreurs"
          description={counts === null ? 'Lecture de tes fautes…'
            : counts.mistakes > 0 ? 'Les fautes relevées par tes bilans : trouve plus fort'
            : "Se remplit quand tu fais le bilan d'une partie dans l'analyse"}
          aside={counts && <CountBadge n={counts.mistakes} />}
        />
        <ActivityCard iconWidth
          to="/attaques-manquees"
          data-testid="missed-attacks-card"
          data-count={counts?.attacks ?? ''}
          icon="🎯"
          title="Mes attaques manquées"
          description="Les moments de tes bilans où Stockfish attaquait le roi : à rejouer contre lui"
          aside={counts && <CountBadge n={counts.attacks} />}
        />
        <ActivityCard iconWidth
          to="/defenses-ratees"
          data-testid="missed-defenses-card"
          data-count={counts?.defenses ?? ''}
          icon="🧱"
          title="Mes défenses ratées"
          description="Les moments de tes bilans où ton roi était attaqué et où tu as craqué"
          aside={counts && <CountBadge n={counts.defenses} />}
        />
        <ActivityCard iconWidth
          to={MOMENTS_ROOT}
          data-testid="moments-card"
          data-count={counts?.analysed ?? ''}
          icon="⚖️"
          title="Moments critiques"
          description={counts && counts.analysed > 0
            ? `Les positions où tes parties ont basculé · ${counts.analysed} partie${counts.analysed > 1 ? 's' : ''} analysée${counts.analysed > 1 ? 's' : ''}`
            : 'Les positions où tes parties analysées ont basculé : retrouve le bon coup'}
        />
      </div>
    </div>
  )
}
