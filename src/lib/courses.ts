// Cours détaillés d'« Apprendre » (src/data/courses.json), indexés par id d'item.
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
