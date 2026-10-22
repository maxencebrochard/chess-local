// Partie persistée d'une tentative écrasée par une autre partie (un seul emplacement de
// persistance, `POSITION_GAME_KEY`) : aiguillage par préfixe de clé vers l'entraîneur concerné.
// - `attaque:<id de la banque>` : tentative d'attaque notée abandonnée ;
// - `structure:<partie>@<demi-coup>@<structure>` : partie de structure notée abandonnée ;
// - `defense:<id>` : tentative de défense notée abandonnée ;
// - `convertir:<id>` : tentative de conversion notée abandonnée ;
// - `attaque:<id de mistakes>` (attaques manquées), `defense-ratee:<id>` (défenses ratées),
//   `finale:<id>`, `position` : rien à noter (le premier coup est jugé dès qu'il est joué, les
//   finales et la partie libre ne notent qu'une fin).
// Module à part : defense.ts et conversion.ts dépendent d'attack.ts, l'aiguillage dépend de tous.
import { recordAttackReplaced } from './attack'
import { recordConversionReplaced } from './conversion'
import { recordDefenseReplaced } from './defense'
import { recordStructurePlay } from './myStructures'
import type { StoredGame } from './positionGame'

export function recordReplaced(stored: StoredGame) {
  if (stored.key.startsWith('attaque:')) recordAttackReplaced(stored)
  else if (stored.key.startsWith('defense:')) recordDefenseReplaced(stored)
  else if (stored.key.startsWith('convertir:')) recordConversionReplaced(stored)
  else if (stored.key.startsWith('structure:')) {
    void recordStructurePlay(stored.key.slice('structure:'.length), stored.startFen, 'abandon', stored.level ?? null, stored.assisted)
  }
}
