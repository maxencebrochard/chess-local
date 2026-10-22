// Pilote haptique de l'app native, chargé par import dynamique depuis native.ts uniquement quand
// le runtime Capacitor est présent. Ne jamais l'importer statiquement : sur le web, le plugin
// retomberait sur `navigator.vibrate` (Android) et changerait le comportement de la PWA.
import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics'
import type { HapticKind } from './native'

export function playHaptic(kind: HapticKind): Promise<void> {
  switch (kind) {
    case 'lift':
      return Haptics.impact({ style: ImpactStyle.Light })
    case 'move':
      return Haptics.impact({ style: ImpactStyle.Medium })
    case 'capture':
      return Haptics.impact({ style: ImpactStyle.Heavy })
    case 'refuse':
      return Haptics.notification({ type: NotificationType.Error })
    case 'premove':
      // Le générateur de sélection d'iOS ne vibre qu'après selectionStart.
      return Haptics.selectionStart().then(() => Haptics.selectionChanged()).then(() => Haptics.selectionEnd())
  }
}
