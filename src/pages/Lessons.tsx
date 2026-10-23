// « Toutes les leçons » (`/apprendre/lecons`) : les cinq cours écrits, rangés par sujet, sans
// exiger de parcours. Les cours sont aussi des raccourcis des groupes d'Entraînement (« Pour
// comprendre ») ; leur propriétaire reste cette page, où ramène le retour de leur sommaire.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ActivityCard } from '../components/ActivityCard'
import { PageHeader } from '../components/PageHeader'
import { ProgressBar } from '../components/ProgressBar'
import { ROQUE } from '../lib/attackCourse'
import { BASES } from '../lib/basicsCourse'
import { DEFENSE } from '../lib/defenseCourse'
import { FINALES } from '../lib/endgameCourse'
import type { Course } from '../lib/lessonCourse'
import { LEARN_BACK } from '../lib/navigation'
import { STRUCTURES_COURSE } from '../lib/structuresCourse'

// `testId` : témoins de progression lus par les suites des cours (même nom qu'avant le lot 5).
const SUBJECTS: { title: string; courses: { course: Course; testId: string }[] }[] = [
  { title: 'Débuter', courses: [{ course: BASES, testId: 'basics-card-progress' }] },
  { title: 'Finales', courses: [{ course: FINALES, testId: 'course-card-progress' }] },
  {
    title: 'Attaque et défense',
    courses: [
      { course: ROQUE, testId: 'attack-card-progress' },
      { course: DEFENSE, testId: 'defense-card-progress' },
    ],
  },
  { title: 'Stratégie', courses: [{ course: STRUCTURES_COURSE, testId: 'structures-card-progress' }] },
]

export default function Lessons() {
  const navigate = useNavigate()
  const [done, setDone] = useState<Record<string, number> | null>(null)

  useEffect(() => {
    let alive = true
    void Promise.all(
      SUBJECTS.flatMap((s) => s.courses).map(async ({ course }) => {
        const ids = await course.completedLessons()
        return [course.slug, course.lessonIds.filter((id) => ids.has(id)).length] as const
      }),
    ).then((entries) => alive && setDone(Object.fromEntries(entries)))
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader
        title="Toutes les leçons"
        description="Des cours courts, une idée par leçon, avec des positions à jouer. Dans l'ordre que tu veux."
        back={{ label: LEARN_BACK.label, onClick: () => navigate(LEARN_BACK.to) }}
      />
      {SUBJECTS.map((s) => (
        <section key={s.title} className="mb-6 last:mb-0">
          <h2 className="mb-2 text-lg font-semibold">{s.title}</h2>
          <div className="grid gap-2">
            {s.courses.map(({ course, testId }) => (
              <ActivityCard key={course.slug} onClick={() => navigate(course.path)} data-course={course.slug} className="w-full" icon={course.emoji} title={course.title}>
                {done === null
                  ? <span className="mt-2 block text-sm text-muted">Lecture de ta progression…</span>
                  : <ProgressBar value={done[course.slug] ?? 0} total={course.lessonIds.length} label={`Leçons terminées : ${course.title}`} testId={testId} unit="leçons" />}
              </ActivityCard>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
