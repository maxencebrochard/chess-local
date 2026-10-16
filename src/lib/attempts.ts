// Partie persistée d'une tentative écrasée par une autre partie (un seul emplacement de
// persistance, `POSITION_GAME_KEY`) : aiguillage par préfixe de clé vers l'entraîneur concerné.
// - `attaque:<id de la banque>` : tentative d'attaque notée abandonnée ;
// - `defense:<id>` : tentative de défense notée abandonnée ;
// - `attaque:<id de mistakes>` (attaques manquées), `defense-ratee:<id>` (défenses ratées),
//   `finale:<id>`, `position` : rien à noter (le premier coup est jugé dès qu'il est joué, les
//   finales et la partie libre ne notent qu'une fin).
// Module à part : defense.ts dépend d'attack.ts, l'aiguillage dépend des deux.
import { recordAttackReplaced } from './attack'
import { recordDefenseReplaced } from './defense'
import type { StoredGame } from './positionGame'

export function recordReplaced(stored: StoredGame) {
  if (stored.key.startsWith('attaque:')) recordAttackReplaced(stored)
  else if (stored.key.startsWith('defense:')) recordDefenseReplaced(stored)
}
