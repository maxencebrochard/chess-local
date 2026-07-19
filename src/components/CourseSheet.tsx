// Feuille de cours détaillé (bouton « ? » d'Apprendre) : texte structuré,
// diagramme interactif en lecture seule, points clés. Fermeture instantanée.
import { Board, type BoardArrow } from './Board'
import coursesData from '../data/courses.json'

export interface Course {
  title: string
  intro: string
  sections: { heading: string; text: string }[]
  diagram?: { fen: string; caption: string; arrows?: string[][] }
  keyPoints: string[]
}

const COURSES = coursesData as Record<string, Course>

export function courseFor(id: string): Course | null {
  return COURSES[id] ?? null
}

interface CourseSheetProps {
  course: Course
  onClose: () => void
}

export function CourseSheet({ course, onClose }: CourseSheetProps) {
  const arrows: BoardArrow[] =
    course.diagram?.arrows?.map(([from, to]) => ({ startSquare: from, endSquare: to, color: '#69c3f2' })) ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 md:items-center" onClick={onClose}>
      <div
        className="pb-safe flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl bg-surface-2 md:max-h-[85vh] md:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center border-b border-black/30 px-4 py-2">
          <h2 className="flex-1 text-lg font-black">📚 {course.title}</h2>
          <button onClick={onClose} className="cursor-pointer p-2 text-2xl leading-none text-neutral-400 hover:text-white">
            ✕
          </button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          <p className="text-[15px] leading-snug text-neutral-200">{course.intro}</p>
          {course.diagram && (
            <div>
              <div className="mx-auto w-full max-w-[320px]">
                <Board fen={course.diagram.fen} orientation="w" interactive={false} arrows={arrows} />
              </div>
              <p className="mt-1.5 text-center text-xs text-neutral-400">{course.diagram.caption}</p>
            </div>
          )}
          {course.sections.map((s) => (
            <div key={s.heading}>
              <h3 className="mb-1 font-bold text-accent">{s.heading}</h3>
              <p className="text-[15px] leading-snug text-neutral-300">{s.text}</p>
            </div>
          ))}
          <div className="rounded-lg bg-surface p-3">
            <h3 className="mb-1.5 font-bold">À retenir</h3>
            <ul className="space-y-1">
              {course.keyPoints.map((k) => (
                <li key={k} className="flex gap-2 text-sm text-neutral-300">
                  <span className="text-accent">✓</span>
                  {k}
                </li>
              ))}
            </ul>
          </div>
          <button
            onClick={onClose}
            className="w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 font-semibold text-neutral-200 hover:bg-surface-3/70"
          >
            Retour à l'exercice
          </button>
        </div>
      </div>
    </div>
  )
}
