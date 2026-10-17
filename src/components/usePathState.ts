// Progression du parcours d'apprentissage lue en base et calculée (src/lib/learningPath.ts),
// relue à chaque montage : retour d'une leçon, d'une séance de finale, d'une série.
import { useCallback, useEffect, useState } from 'react'
import { computePath, EMPTY_FACTS, type PathState } from '../lib/learningPath'
import { loadPathFacts } from '../lib/learningPathStore'

export function usePathState(): { state: PathState | null; reload: () => Promise<void> } {
  const [state, setState] = useState<PathState | null>(null)
  const reload = useCallback(async () => {
    try {
      setState(computePath(await loadPathFacts()))
    } catch {
      setState(computePath(EMPTY_FACTS))
    }
  }, [])
  useEffect(() => {
    void reload()
  }, [reload])
  return { state, reload }
}
