// Sons du set standard lichess (public/sounds), préchargés et joués via WebAudio
// pour une latence minimale. L'échec (check) réutilise Move, comme lichess.

const FILES = {
  move: 'Move',
  capture: 'Capture',
  check: 'Move',
  gameEnd: 'GenericNotify',
  success: 'Confirmation',
  fail: 'Error',
  lowTime: 'LowTime',
} as const

type SoundName = keyof typeof FILES

let ctx: AudioContext | null = null
const buffers = new Map<string, AudioBuffer>()

async function load(file: string): Promise<AudioBuffer | null> {
  if (buffers.has(file)) return buffers.get(file)!
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}sounds/${file}.mp3`)
    const buf = await (ctx as AudioContext).decodeAudioData(await res.arrayBuffer())
    buffers.set(file, buf)
    return buf
  } catch {
    return null
  }
}

function play(name: SoundName) {
  ctx ??= new AudioContext()
  if (ctx.state === 'suspended') void ctx.resume()
  void load(FILES[name]).then((buf) => {
    if (!buf || !ctx) return
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    src.start()
  })
}

export const sounds = {
  move: () => play('move'),
  capture: () => play('capture'),
  check: () => play('check'),
  gameEnd: () => play('gameEnd'),
  success: () => play('success'),
  fail: () => play('fail'),
  lowTime: () => play('lowTime'),
}
