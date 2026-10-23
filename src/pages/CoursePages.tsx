// Routes des cours écrits (finales, « Démolir le roque », défense, bases, structures), chargées à
// la demande comme les autres pages (App.tsx) : la page partagée `LessonCourse` et les données
// JSON de chaque cours arrivent avec la route, chaque cours dans sa propre chunk, jamais au
// démarrage de l'app. Ce module ne contient que des imports dynamiques : il reste minuscule dans
// le bundle initial.
import type { ReactNode } from 'react'
import type { Course } from '../lib/lessonCourse'
import { lazyPage } from '../lib/lazyPage'

/**
 * Sommaire et leçon d'un cours, paresseux. `loadExtra` charge le bloc propre au cours affiché
 * sous la progression du sommaire (structures : « Dans mes parties »).
 */
export function lazyCourse(loadCourse: () => Promise<Course>, loadExtra?: () => Promise<ReactNode>) {
  const Index = lazyPage(() =>
    Promise.all([import('./LessonCourse'), loadCourse(), loadExtra?.()]).then(([page, course, extra]) => {
      const CourseIndex = page.default
      return { default: () => <CourseIndex course={course} extra={extra} /> }
    }),
  )
  const Lesson = lazyPage(() =>
    Promise.all([import('./LessonCourse'), loadCourse()]).then(([page, course]) => {
      const CourseLesson = page.CourseLesson
      return { default: () => <CourseLesson course={course} /> }
    }),
  )
  return { Index, Lesson }
}
