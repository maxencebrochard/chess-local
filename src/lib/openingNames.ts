// Traduction française des familles d'ouvertures (noms lichess en anglais).
const FR: [string, string][] = [
  ['Italian Game', 'Partie italienne'],
  ['Ruy Lopez', 'Partie espagnole'],
  ['Sicilian Defense', 'Défense sicilienne'],
  ['French Defense', 'Défense française'],
  ['Caro-Kann Defense', 'Défense Caro-Kann'],
  ["Queen's Gambit Declined", 'Gambit dame refusé'],
  ["Queen's Gambit Accepted", 'Gambit dame accepté'],
  ["Queen's Gambit", 'Gambit dame'],
  ['London System', 'Système de Londres'],
  ['Scandinavian Defense', 'Défense scandinave'],
  ["King's Indian Defense", 'Est-indienne'],
  ["King's Indian Attack", 'Attaque est-indienne'],
  ['Nimzo-Indian Defense', 'Défense nimzo-indienne'],
  ["Queen's Indian Defense", 'Ouest-indienne'],
  ['Grünfeld Defense', 'Défense Grünfeld'],
  ['Slav Defense', 'Défense slave'],
  ['Semi-Slav Defense', 'Défense semi-slave'],
  ['Dutch Defense', 'Défense hollandaise'],
  ['English Opening', 'Partie anglaise'],
  ['Réti Opening', 'Ouverture Réti'],
  ['Zukertort Opening', 'Ouverture Zukertort'],
  ['Scotch Game', 'Partie écossaise'],
  ['Vienna Game', 'Partie viennoise'],
  ["King's Gambit", 'Gambit roi'],
  ['Petrov', 'Défense Petrov'],
  ["Philidor Defense", 'Défense Philidor'],
  ['Pirc Defense', 'Défense Pirc'],
  ['Modern Defense', 'Défense moderne'],
  ['Alekhine Defense', 'Défense Alekhine'],
  ['Four Knights Game', 'Partie des quatre cavaliers'],
  ['Three Knights', 'Partie des trois cavaliers'],
  ['Bishop', "Partie du fou"],
  ['Center Game', 'Partie du centre'],
  ['Catalan Opening', 'Ouverture catalane'],
  ['Trompowsky Attack', 'Attaque Trompowsky'],
  ['Benoni Defense', 'Défense Benoni'],
  ["King's Pawn Game", 'Début du pion roi'],
  ["Queen's Pawn Game", 'Début du pion dame'],
]

// Nom FR d'une ouverture lichess ("Italian Game: Two Knights Defense" ->
// "Partie italienne · Two Knights Defense" ; famille seule -> nom FR seul).
export function openingFr(name: string): string {
  const [family, ...rest] = name.split(':')
  const hit = FR.find(([en]) => family.trim().startsWith(en))
  const fam = hit ? hit[1] : family.trim()
  const variation = rest.join(':').trim()
  return variation ? `${fam} · ${variation}` : fam
}

// Famille seule, en FR.
export function openingFamilyFr(name: string): string {
  return openingFr(name.split(':')[0])
}
