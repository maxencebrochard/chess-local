import { createRequire } from 'module'
import fs from 'fs'
const require = createRequire('package.json')
const { Chess } = require('chess.js')
const R = ''
const eg = JSON.parse(fs.readFileSync(R + 'src/data/endgames.json'))
const st = JSON.parse(fs.readFileSync(R + 'src/data/strategy.json'))
const co = JSON.parse(fs.readFileSync(R + 'src/data/courses.json'))
const themesSrc = fs.readFileSync(R + 'src/lib/themes.ts', 'utf8')
const themes = [...themesSrc.matchAll(/tag: '([^']+)', label: '([^']+)'/g)].map(m => ({ tag: m[1], label: m[2] }))
const reached = new Set()
console.log('=== FINALES -> cours')
for (const e of eg) { const c = co[e.id]; if (c) reached.add(e.id); console.log(`${e.id.padEnd(20)} ex="${e.title}" -> cours="${c ? c.title : 'AUCUN'}"`) }
console.log('=== THEMES TACTIQUES -> cours')
for (const t of themes) { const c = co[t.tag]; if (c) reached.add(t.tag); console.log(`${t.tag.padEnd(20)} label="${t.label}" -> cours="${c ? c.title : 'AUCUN'}"`) }
console.log('=== STRATEGIE -> cours')
for (const s of st) { const id = s.themes.find(t => co[t]) ?? s.id; const c = co[id]; if (c) reached.add(id); console.log(`${s.id.padEnd(16)} carte="${s.title}" themes=${JSON.stringify(s.themes)} -> id=${id} cours="${c ? c.title : 'AUCUN'}"`) }
reached.add('opening-principles')
console.log('=== OUVERTURES -> opening-principles :', co['opening-principles']?.title)
console.log('=== COURS JAMAIS ATTEIGNABLES :', Object.keys(co).filter(k => !reached.has(k)))
console.log('=== SCHEMA')
const SQ = /^[a-h][1-8]$/
for (const [id, c] of Object.entries(co)) {
  const p = []
  if (!c.title?.trim()) p.push('titre vide')
  if (!c.intro?.trim()) p.push('intro vide')
  if (!Array.isArray(c.sections) || !c.sections.length) p.push('0 section')
  else { c.sections.forEach((s, i) => { if (!s.heading?.trim()) p.push(`section ${i} heading vide`); if (!s.text?.trim()) p.push(`section ${i} texte vide`) })
    const hs = c.sections.map(s => s.heading); if (new Set(hs).size !== hs.length) p.push('headings dupliqués (clé React)') }
  if (!Array.isArray(c.keyPoints) || !c.keyPoints.length) p.push('0 keyPoint')
  else { if (c.keyPoints.some(k => !k?.trim())) p.push('keyPoint vide'); if (new Set(c.keyPoints).size !== c.keyPoints.length) p.push('keyPoints dupliqués') }
  if (!c.diagram) p.push('PAS DE DIAGRAMME')
  else {
    if (!c.diagram.caption?.trim()) p.push('caption vide')
    let ch = null
    try { ch = new Chess(c.diagram.fen) } catch (e) { p.push('FEN invalide: ' + e.message) }
    if (ch) {
      for (const a of c.diagram.arrows ?? []) {
        if (a.length !== 2 || !SQ.test(a[0]) || !SQ.test(a[1])) { p.push('flèche invalide ' + JSON.stringify(a)); continue }
        const pc = ch.get(a[0])
        if (!pc) p.push(`flèche ${a[0]}->${a[1]} part d'une case VIDE`)
        else {
          // coup légal pour le camp de la pièce ?
          const f = c.diagram.fen.split(' '); f[1] = pc.color; f[3] = '-'
          let legal = false
          try { const c2 = new Chess(f.join(' ')); legal = c2.moves({ square: a[0], verbose: true }).some(m => m.to === a[1]) } catch (e) { legal = 'n/a(' + e.message.slice(0, 30) + ')' }
          const tgt = ch.get(a[1])
          p.push(`  fleche ${a[0]}(${pc.color}${pc.type})->${a[1]}${tgt ? '(' + tgt.color + tgt.type + ')' : ''} legal=${legal} trait=${c.diagram.fen.split(' ')[1]}`)
        }
      }
      if (!(c.diagram.arrows ?? []).length) p.push('diagramme SANS flèche')
    }
  }
  console.log(`${id.padEnd(20)} "${c.title}" sections=${c.sections?.length} kp=${c.keyPoints?.length} fen=${c.diagram?.fen ?? '-'}`)
  p.forEach(x => console.log('     ' + x))
}
// FEN cours vs FEN exercice (finales)
console.log('=== FEN cours vs exercice (finales)')
for (const e of eg) { const c = co[e.id]; if (!c?.diagram) continue; console.log(`${e.id.padEnd(20)} same=${c.diagram.fen.split(' ')[0] === e.fen.split(' ')[0]} ex=${e.fen} | cours=${c.diagram.fen} side=${e.side}`) }
