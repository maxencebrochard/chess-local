// Sons du jeu (public/sounds, provenance dans LICENSES.md), joués via Web Audio pour une latence minimale.
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

// Téléchargement et décodage n'exigent aucun geste : seule la reprise du contexte en demande un.
// Mémoïsé : coût nul après le premier appel.
function preload() {
  for (const name of FILES) void load(name)
}

// Appelé pendant un geste : seul moment où iOS laisse démarrer ou reprendre l'audio.
function unlock() {
  if (!useSettings.getState().playSounds) return
  const c = context()
  if (!c) return
  // Sons activés en cours de session, ou préchargement du démarrage échoué.
  preload()
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
  // Dès le démarrage : le premier coup ne doit pas attendre un téléchargement lancé par son geste.
  if (useSettings.getState().playSounds) preload()
}

async function ready(c: AudioContext): Promise<boolean> {
  if (stateOf(c) === 'running') return true
  if (stateOf(c) !== 'suspended') return false
  // resume() hors geste peut ne jamais aboutir : borné, et le son est abandonné.
  await Promise.race([c.resume().catch(() => {}), new Promise((r) => setTimeout(r, 300))])
  return stateOf(c) === 'running'
}

export function play(name: SoundName, outdated: () => boolean = () => false) {
  const { playSounds, soundVolume } = useSettings.getState()
  if (!playSounds || soundVolume <= 0) return
  const c = context()
  if (!c) return
  const start = (buf: AudioBuffer | null, ok: boolean) => {
    if (!buf || !ok || c !== ctx || !gain || outdated()) return
    const { playSounds, soundVolume } = useSettings.getState()
    if (!playSounds || soundVolume <= 0) return
    gain.gain.setValueAtTime(soundVolume, c.currentTime)
    const src = c.createBufferSource()
    src.buffer = buf
    src.connect(gain)
    src.start()
  }
  // Un son déjà décodé sur un contexte actif part sans attendre les microtâches du rendu.
  const buf = buffers.get(name)
  if (buf && stateOf(c) === 'running') start(buf, true)
  else void Promise.all([load(name), ready(c)]).then(([loaded, ok]) => start(loaded, ok))
}

// Son d'un coup, priorités de chess.com : échec, promotion, roque, prise, puis coup simple
// (le mien ou celui de l'adversaire).
// Au-delà, un son de coup arriverait trop tard après la pose : mieux vaut aucun son.
const MOVE_SOUND_MAX_DELAY_MS = 1000
let moveSoundId = 0
export function playMoveSound(move: Pick<Move, 'san' | 'flags'>, opponent: boolean) {
  // Un son de coup qui attend encore son fichier ou le contexte se tait dès qu'un coup plus récent
  // est demandé (pas de rafale de sons anciens), ou s'il dépasse le plafond depuis la pose.
  const id = ++moveSoundId
  const requestedAt = performance.now()
  play(moveSoundName(move, opponent), () => id !== moveSoundId || performance.now() - requestedAt > MOVE_SOUND_MAX_DELAY_MS)
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
