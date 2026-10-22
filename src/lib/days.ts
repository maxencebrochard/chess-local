// Jours civils locaux, partagés par la révision espacée et la séance du jour. Sans Dexie ni React :
// utilisable sous Node.
const DAY = 86_400_000

export function startOfDay(ms: number): number {
  const d = new Date(ms)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

// Jours civils locaux (setDate, pas des multiples de 86 400 000 ms : la nuit du passage à l'heure
// d'été compte 23 h, et un minuit calculé en millisecondes tomberait à 1 h du matin).
export function addDays(dayStart: number, days: number): number {
  const d = new Date(dayStart)
  d.setDate(d.getDate() + days)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

export function daysBetween(fromDayStart: number, toDayStart: number): number {
  return Math.round((toDayStart - fromDayStart) / DAY)
}
