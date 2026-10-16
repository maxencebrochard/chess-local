import { useMemo } from 'react'
import { Chess } from 'chess.js'
import { figurine } from '../lib/review'

// Coups en notation figurine : « 1.e4 e5 2.♘f3 ♘c6 3.d4 ».
export function MoveText({ moves, from = 0 }: { moves: string[]; from?: number }) {
  const text = useMemo(() => {
    const c = new Chess()
    const parts: string[] = []
    moves.forEach((m, i) => {
      const san = c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] }).san
      if (i < from) return
      const fig = figurine(san, i % 2 === 0 ? 'w' : 'b')
      parts.push(i % 2 === 0 ? `${i / 2 + 1}.${fig}` : i === from ? `${Math.ceil(i / 2)}…${fig}` : fig)
    })
    return parts.join(' ')
  }, [moves, from])
  return <>{text}</>
}
