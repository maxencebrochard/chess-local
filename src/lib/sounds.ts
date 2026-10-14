// Sons du jeu (public/sounds, CC0, voir LICENSES.md), joués via Web Audio pour une latence minimale.
//
// iOS impose deux contraintes, cause du « pas de son » de la PWA :
// - un AudioContext ne démarre (ou ne reprend) que pendant un geste de l'utilisateur (fin de
//   toucher, click, keydown ; pas pointerdown ni touchstart) ;
// - quand l'app passe en arrière-plan (verrouillage, appel, retour à l'écran d'accueil), le
//   contexte passe en `interrupted`, ou reste `running` mais muet : il faut alors le recréer.
// D'où `installAudioUnlock()` : un contexte qui a connu l'arrière-plan est jeté, et à chaque geste,
// si le contexte ne tourne pas, on le crée, le recrée ou le reprend, dans le geste. Un son demandé
// alors que le contexte ne tourne pas est abandonné, jamais rejoué en retard.
// Note : sur iPhone, Web Audio obéit aussi au bouton silencieux (comportement voulu par iOS, pour ne
// pas couper la musique de l'utilisateur) ; l'écran Réglages le signale.

import type { Move } from 'chess.js'
import { useSettings } from '../store/settings'

const FILES = [
  'move-self',
  'move-opponent',
  'capture',
  'castle',
  'move-check',
  'promote',
  'game-start',
  'game-end',
  'low-time',
  'illegal',
  'success',
  'fail',
] as const

export type SoundName = (typeof FILES)[number]

let ctx: AudioContext | null = null
let gain: GainNode | null = null
// Fichiers décodés, indépendants du contexte (un AudioBuffer se rejoue dans un contexte recréé).
const buffers = new Map<SoundName, AudioBuffer>()
const loading = new Map<SoundName, Promise<AudioBuffer | null>>()
// Le contexte a connu l'arrière-plan : on ne s'y fie plus, il sera recréé.
let stale = false

type State = AudioContextState | 'interrupted'
const stateOf = (c: AudioContext) => c.state as State

function newContext(): AudioContext | null {
  const Ctor = window.AudioContext ?? (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Ctor) return null
  const c = new Ctor({ latencyHint: 'interactive' })
  gain = c.createGain()
  gain.connect(c.destination)
  return c
}

// Contexte utilisable : recréé s'il est fermé ou interrompu (iOS), créé s'il n'existe pas.
function context(): AudioContext | null {
  if (ctx && (stale || stateOf(ctx) === 'closed' || stateOf(ctx) === 'interrupted')) {
    if (stateOf(ctx) !== 'closed') void ctx.close().catch(() => {})
    ctx = null
  }
  stale = false
  ctx ??= newContext()
  return ctx
}

function load(name: SoundName): Promise<AudioBuffer | null> {
  const done = buffers.get(name)
  if (done) return Promise.resolve(done)
  let p = loading.get(name)
  if (!p) {
    const c = context()
    if (!c) return Promise.resolve(null)
    p = fetch(`${import.meta.env.BASE_URL}sounds/${name}.mp3`)
      .then((res) => {
        if (!res.ok) throw new Error(`${name}.mp3 : HTTP ${res.status}`)
        return res.arrayBuffer()
      })
      // Décodé sur le contexte du moment : celui du départ a pu être jeté pendant le fetch
      // (passage en arrière-plan en plein préchargement).
      .then((data) => (context() ?? c).decodeAudioData(data))
      .then((buf) => {
        buffers.set(name, buf)
        return buf
      })
      .catch((err) => {
        console.warn('Son non chargé :', err)
        loading.delete(name) // nouvel essai au prochain appel
        return null
      })
    loading.set(name, p)
  }
  return p
}

// Appelé pendant un geste : seul moment où iOS laisse démarrer ou reprendre l'audio.
function unlock() {
  if (!useSettings.getState().playSounds) return
  const c = context()
  if (!c) return
  // Préchargement dès le premier geste, que le contexte tourne déjà ou non (mémoïsé : coût nul ensuite).
  for (const name of FILES) void load(name)
  if (stateOf(c) === 'running') return
  void c.resume().catch(() => {})
  // Un tampon muet joué dans le geste achève le déverrouillage sur les anciens iOS.
  const src = c.createBufferSource()
  src.buffer = c.createBuffer(1, 1, 22050)
  src.connect(c.destination)
  src.start(0)
}

let installed = false
export function installAudioUnlock() {
  if (installed) return
  installed = true
  // Capture : passe avant tout gestionnaire de l'app, même si l'un d'eux arrête la propagation.
  // pointerup : le coup d'un drag est joué à la fin du toucher, avant touchend ; pointerdown n'est
  // pas un geste pour iOS mais l'est pour les navigateurs de bureau.
  for (const type of ['pointerup', 'touchend', 'click', 'keydown', 'pointerdown'] as const) {
    window.addEventListener(type, unlock, { capture: true, passive: true })
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && ctx) stale = true
  })
}

async function ready(c: AudioContext): Promise<boolean> {
  if (stateOf(c) === 'running') return true
  if (stateOf(c) !== 'suspended') return false
  // resume() hors geste peut ne jamais aboutir : borné, et le son est abandonné.
  await Promise.race([c.resume().catch(() => {}), new Promise((r) => setTimeout(r, 300))])
  return stateOf(c) === 'running'
}

export function play(name: SoundName) {
  const { playSounds, soundVolume } = useSettings.getState()
  if (!playSounds || soundVolume <= 0) return
  const c = context()
  if (!c) return
  void Promise.all([load(name), ready(c)]).then(([buf, ok]) => {
    if (!buf || !ok || c !== ctx || !gain) return
    const { playSounds, soundVolume } = useSettings.getState()
    if (!playSounds || soundVolume <= 0) return
    gain.gain.setValueAtTime(soundVolume, c.currentTime)
    const src = c.createBufferSource()
    src.buffer = buf
    src.connect(gain)
    src.start()
  })
}

// Son d'un coup, priorités de chess.com : échec, promotion, roque, prise, puis coup simple
// (le mien ou celui de l'adversaire).
export function playMoveSound(move: Pick<Move, 'san' | 'flags'>, opponent: boolean) {
  play(moveSoundName(move, opponent))
}

export function moveSoundName(move: Pick<Move, 'san' | 'flags'>, opponent: boolean): SoundName {
  if (move.san.includes('+') || move.san.includes('#')) return 'move-check'
  if (move.flags.includes('p')) return 'promote'
  if (move.flags.includes('k') || move.flags.includes('q')) return 'castle'
  if (move.flags.includes('c') || move.flags.includes('e')) return 'capture'
  return opponent ? 'move-opponent' : 'move-self'
}

export const sounds = {
  gameStart: () => play('game-start'),
  gameEnd: () => play('game-end'),
  lowTime: () => play('low-time'),
  illegal: () => play('illegal'),
  success: () => play('success'),
  fail: () => play('fail'),
}
