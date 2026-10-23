// Hub Entraînement (`/apprendre/entrainement`) et ses cinq groupes de compétences
// (`/apprendre/entrainement/<groupe>`), décrits une fois dans `TRAINING_GROUPS` (lib/navigation.ts).
// Le hub ne montre que les groupes, leur objectif et au plus une information de progression ; les
// activités apparaissent dans le groupe choisi. Les séances s'ouvrent sur `/apprendre`
// (`state.domain`, Learn.tsx), qui y revient en fin de séance.
import { useEffect, useMemo, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { ActivityCard } from '../components/ActivityCard'
import { PageHeader } from '../components/PageHeader'
import { SessionFailed } from '../components/SessionFailed'
import { useSessionFailed } from '../components/useSessionFailed'
import { db } from '../lib/db'
import {
  groupPath, LEARN_BACK, REVIEW_ROOT, TRAINING_BACK, TRAINING_GROUPS, TRAINING_ROOT, trainingGroup,
  type SessionDomain, type TrainingGroup, type TrainingSlug,
} from '../lib/navigation'

// Mêmes clés que `DOMAIN_META` (lib/learn.ts), non importé pour garder ces pages légères.
const RATING_KEY: Record<SessionDomain, string> = {
  tactic: 'learn-tactic',
  endgame: 'learn-endgame',
  opening: 'learn-opening',
  strategy: 'learn-strategy',
}

// Information de progression d'un groupe, ou null tant qu'il n'y a rien de réel à montrer (pas de
// classement de départ présenté comme une performance).
async function groupProgress(g: TrainingGroup): Promise<string | null> {
  if (g.progress === 'positions') {
    const rows = await db.learnSessions.where('domain').anyOf(['attack', 'defense', 'conversion']).filter((r) => r.success === 1).toArray()
    const n = new Set(rows.map((r) => `${r.domain}|${r.itemId}|${r.fen ?? ''}`)).size
    return n ? `${n} position${n > 1 ? 's' : ''} réussie${n > 1 ? 's' : ''}` : null
  }
  const r = await db.ratings.get(RATING_KEY[g.progress])
  return r && r.games > 0 ? `Classement ${r.value}` : null
}

function useProgress(groups: TrainingGroup[]): Partial<Record<TrainingSlug, string | null>> {
  const [out, setOut] = useState<Partial<Record<TrainingSlug, string | null>>>({})
  useEffect(() => {
    let alive = true
    void Promise.all(groups.map(async (g) => [g.slug, await groupProgress(g).catch(() => null)] as const)).then(
      (entries) => alive && setOut(Object.fromEntries(entries)),
    )
    return () => {
      alive = false
    }
  }, [groups])
  return out
}

export default function Training() {
  const { groupe } = useParams()
  if (groupe === undefined) return <TrainingHub />
  const group = trainingGroup(groupe)
  if (!group) return <Navigate to={TRAINING_ROOT} replace />
  return <GroupPage key={group.slug} group={group} />
}

function TrainingHub() {
  const navigate = useNavigate()
  const progress = useProgress(TRAINING_GROUPS)
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title="Entraînement" description="Quelle compétence travailler ?" back={{ label: LEARN_BACK.label, onClick: () => navigate(LEARN_BACK.to) }} />
      <div className="grid gap-2">
        {TRAINING_GROUPS.map((g) => (
          <ActivityCard iconWidth key={g.slug} to={groupPath(g.slug)} data-group={g.slug} icon={g.icon} title={g.title} description={g.objective}>
            {progress[g.slug] && <span data-group-progress className="mt-1 block text-sm font-semibold text-neutral-200">{progress[g.slug]}</span>}
          </ActivityCard>
        ))}
      </div>
      <section aria-labelledby="training-games" className="mt-6">
        <h2 id="training-games" className="mb-2 text-lg font-semibold">À partir de mes parties</h2>
        <ActivityCard iconWidth
          to={REVIEW_ROOT}
          data-learn="mes-parties"
          icon="🔁"
          title="Réviser mes parties"
          description="Tes erreurs, attaques manquées, défenses ratées et moments critiques"
        />
      </section>
    </div>
  )
}

function GroupPage({ group }: { group: TrainingGroup }) {
  const navigate = useNavigate()
  const failed = useSessionFailed()
  const progress = useProgress(useMemo(() => [group], [group]))[group.slug]
  const here = groupPath(group.slug)

  // `replace` : la séance prend la place du groupe dans l'historique, et sa fermeture la lui rend
  // (Learn.tsx, `closeSession`) : pas d'entrée en double au retour arrière.
  function startSession(domain: SessionDomain) {
    navigate('/apprendre', { replace: true, state: { domain, returnTo: here, returnLabel: `Retour à ${group.title}` } })
  }

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title={group.title} description={group.objective} back={{ label: TRAINING_BACK.label, onClick: () => navigate(TRAINING_BACK.to) }} />
      {failed && <SessionFailed>Séance indisponible : les puzzles ne sont pas encore chargés. Réessaie une fois en ligne.</SessionFailed>}
      {progress && <p data-group-progress className="-mt-1 mb-4 text-sm font-semibold text-neutral-200">{progress}</p>}
      <section aria-labelledby="group-activities" className="mb-6 last:mb-0">
        <h2 id="group-activities" className="mb-2 text-lg font-semibold">S'entraîner</h2>
        <div className="grid gap-2">
          {group.items.map((it) =>
            it.session ? (
              <ActivityCard iconWidth key={it.label} onClick={() => startSession(it.session!)} data-session={it.session} icon={it.icon} title={it.label} description={it.description} />
            ) : (
              <ActivityCard iconWidth key={it.label} to={it.to!} state={it.state} data-testid={it.testId} icon={it.icon} title={it.label} description={it.description} />
            ),
          )}
        </div>
      </section>
      {group.lessons.length > 0 && (
        <section aria-labelledby="group-lessons">
          <h2 id="group-lessons" className="mb-2 text-lg font-semibold">Pour comprendre</h2>
          <div className="grid gap-2">
            {group.lessons.map((l) => (
              <ActivityCard iconWidth key={l.to} to={l.to} state={{ from: group.slug }} data-course-link={l.to} icon={l.icon} title={l.label} description="Le cours, leçon par leçon" />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
