// Progression du parcours d'apprentissage lue en base et calculée (src/lib/learningPath.ts),
// relue à chaque montage : retour d'une leçon, d'une séance de finale, d'une série.
import { useCallback, useEffect, useState } from 'react'
import type { PathState } from '../lib/learningPath'
import { loadPathState } from '../lib/learningPathStore'

export function usePathState(): { state: PathState | null; reload: () => Promise<void> } {
  const [state, setState] = useState<PathState | null>(null)
  const reload = useCallback(async () => {
    setState(await loadPathState())
  }, [])
  useEffect(() => {
    void reload()
  }, [reload])
  return { state, reload }
}
