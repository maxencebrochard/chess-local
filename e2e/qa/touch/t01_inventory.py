"""Inventaire : géométrie du board + CSS calculés (touch-action, user-select, overscroll...) par page et viewport."""
import sys, json
sys.path.insert(0, "e2e/qa/touch")
from touch_env import *

PAGES = ["jouer", "analyse", "puzzles", "rush", "apprendre"]

JS = """() => {
  const cs = (el, props) => { if (!el) return null; const s = getComputedStyle(el); const o = {}; for (const p of props) o[p] = s.getPropertyValue(p); return o }
  const props = ['touch-action', 'user-select', '-webkit-user-select', '-webkit-touch-callout', 'overscroll-behavior-x', 'overscroll-behavior-y', 'overflow-x', 'overflow-y', '-webkit-tap-highlight-color']
  const board = document.querySelector('[id$="-board"]')
  const sq = document.querySelector('[data-square]')
  const pieceDiv = document.querySelector('[data-piece]')
  const dragWrap = pieceDiv ? pieceDiv.parentElement : null
  const svg = pieceDiv ? pieceDiv.querySelector('svg') : null
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return {x: +b.x.toFixed(1), y: +b.y.toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1)} }
  const m = document.querySelector('main')
  const pieceSq = pieceDiv ? pieceDiv.closest('[data-square]') : null
  return {
    html: cs(document.documentElement, props), body: cs(document.body, props), main: cs(m, props),
    boardbox: cs(document.querySelector('.boardbox'), props), boardEl: cs(board, props),
    square: cs(sq, props), dragWrap: cs(dragWrap, props), pieceDiv: cs(pieceDiv, props), svg: cs(svg, props),
    rects: { board: r(board), boardbox: r(document.querySelector('.boardbox')), pieceSq: r(pieceSq), dragWrap: r(dragWrap), pieceDiv: r(pieceDiv), svg: r(svg), main: r(m) },
    pieceSqName: pieceSq ? pieceSq.getAttribute('data-square') : null,
    nbBoards: document.querySelectorAll('[id$="-board"]').length,
    vw: innerWidth, vh: innerHeight,
    main_scroll: m ? {sh: m.scrollHeight, ch: m.clientHeight} : null,
    doc_scroll: {sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight},
  }
}"""


PROBE = """() => {
  const out = {}
  const desc = (el) => el ? (el.tagName.toLowerCase() + (el.getAttribute('data-piece') ? '[piece ' + el.getAttribute('data-piece') + ']' : '') + (el.getAttribute('data-square') ? '[sq ' + el.getAttribute('data-square') + ']' : '') + ' ta=' + getComputedStyle(el).touchAction + ' txt=' + (el.childElementCount ? '' : (el.textContent || '').slice(0, 3))) : null
  // touch-action EFFECTIF = intersection sur la chaîne d'ancêtres jusqu'au scroller
  const eff = (el) => { let e = el; const seen = []; while (e && e !== document.documentElement) { const ta = getComputedStyle(e).touchAction; if (ta !== 'auto') seen.push(ta); e = e.parentElement } return seen.length ? seen.join('&') : 'auto' }
  for (const sq of ['a1', 'a2', 'a8', 'h1', 'e1', 'e2', 'e4']) {
    const el = document.querySelector(`[data-square='${sq}']`); if (!el) continue
    const b = el.getBoundingClientRect(); const pts = { tl: [b.x + 5, b.y + 6], br: [b.right - 6, b.bottom - 6], c: [b.x + b.width / 2, b.y + b.height / 2], bl: [b.x + 3, b.bottom - 3] }
    out[sq] = {}
    for (const [k, [x, y]] of Object.entries(pts)) { const hit = document.elementFromPoint(x, y); out[sq][k] = desc(hit) + ' | effectif=' + eff(hit) }
  }
  const bb = document.querySelector('.boardbox'); const a = document.querySelector("[data-column='a']") || document.querySelector('[data-square]')
  const cols = [...document.querySelectorAll('[data-square]')].map(e => e.getBoundingClientRect())
  const minLeft = Math.min(...cols.map(r => r.x)), maxRight = Math.max(...cols.map(r => r.right)), w = cols[0] ? cols[0].width : 0
  out.edges = { boardLeft: +minLeft.toFixed(1), boardRightGap: +(innerWidth - maxRight).toFixed(1), squareW: +w.toFixed(1), leftColCenterX: +(minLeft + w / 2).toFixed(1), boardboxLeft: bb ? +bb.getBoundingClientRect().x.toFixed(1) : null }
  return out
}"""

out = {}
with sync_playwright() as p:
    for standalone in (True, False):
        browser, ctx, page, logs = open_mobile_t(p, standalone=standalone)
        for pg in PAGES:
            page.goto(f"{BASE}/#/{pg}")
            page.wait_for_timeout(1500)
            key = f"{pg}|{'standalone' if standalone else 'safari'}"
            out[key] = page.evaluate(JS)
            out[key]["scroll"] = scroll_state(page)
            out[key]["probe"] = page.evaluate(PROBE)
            shot(page, f"t01_{pg}_{'sa' if standalone else 'sf'}")
        browser.close()

json.dump(out, open(SHOTS + "/../t01_inventory.json", "w"), indent=1)
for k, v in out.items():
    print("==", k, "boards:", v["nbBoards"], "vw/vh", v["vw"], v["vh"])
    print("  rects", json.dumps(v["rects"]))
    print("  edges", json.dumps(v["probe"]["edges"]))
    for sq, d in v["probe"].items():
        if sq != "edges": print("   hit", sq, json.dumps(d, ensure_ascii=False))
    print("  main_scroll", v["main_scroll"], "doc", v["doc_scroll"])
    for el in ("html", "body", "main", "boardbox", "boardEl", "square", "dragWrap", "pieceDiv", "svg"):
        s = v[el]
        if s:
            print(f"  {el:9s} ta={s['touch-action']:12s} us={s['user-select']:6s} wus={s['-webkit-user-select']:6s} callout={s['-webkit-touch-callout'] or '-':6s} osb={s['overscroll-behavior-x']}/{s['overscroll-behavior-y']} ov={s['overflow-x']}/{s['overflow-y']}")
