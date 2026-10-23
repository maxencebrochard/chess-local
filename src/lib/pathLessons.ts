// Leçons des étapes du parcours (`lesson: '<slug>:<id>'`), résolues dans les cours bundlés. Séparé
// de learningPath.ts pour que la progression (accueil) se calcule sans charger les cours.
import { BASES } from './basicsCourse'
import { ROQUE } from './attackCourse'
import { FINALES } from './endgameCourse'
import type { Course as LessonCourse, Lesson } from './lessonCourse'

const PATH_COURSES: Record<string, LessonCourse> = { [BASES.slug]: BASES, [FINALES.slug]: FINALES, [ROQUE.slug]: ROQUE }

// Leçon d'un cours désignée par `<slug>:<id>`, avec son chemin dans l'app.
export function lessonRef(ref: string | undefined): { course: LessonCourse; id: string; lesson: Lesson; path: string } | null {
  if (!ref) return null
  const [slug, id] = ref.split(':')
  const course = PATH_COURSES[slug]
  const lesson = course?.lessonById(id) ?? null
  return course && lesson ? { course, id, lesson, path: `${course.path}/${id}` } : null
}
