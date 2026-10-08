// Famille d'ouverture d'un nom lichess, partagée par l'entraîneur d'ouvertures (/ouvertures) et
// Insights (ouvertures regroupées par famille). Sans Dexie ni React : utilisable sous Node.

// Les lignes « London System » sont rangées par lichess sous plusieurs familles
// (Queen's Pawn Game, Indian Defense...) : la famille Londres les regroupe par le nom.
export const BY_NAME: Record<string, (name: string) => boolean> = {
  'London System': (n) => n.includes('London System'),
}

// Famille d'un nom lichess : avant « : » et « , », suffixes Accepted/Declined retirés
// (« Queen's Gambit Declined » rejoint « Queen's Gambit »).
export function familyKey(name: string): string {
  return name.split(':')[0].split(',')[0].trim().replace(/ (Accepted|Declined)$/, '')
}

// Famille à laquelle l'entraîneur rattache une ligne : regroupement par le nom d'abord (Londres),
// sinon la clé de famille du nom.
export function familyOfLine(name: string): string {
  for (const [k, match] of Object.entries(BY_NAME)) if (match(name)) return k
  return familyKey(name)
}
