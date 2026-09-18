"""Pourquoi le correctif touch-action laisse un scroll sur d1 en 393x560 ? Qui reçoit le doigt ? + taille des zones mortes."""
import sys, json
sys.path.insert(0, "e2e/qa/touch")
from tlib import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile_t(p, standalone=False, width=393, height=560)
    install(page)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    page.add_style_tag(content=".boardbox { touch-action: none; }")
    b = sq_rect(page, "d1"); x, y = b["x"] + b["width"] - 6, b["y"] + b["height"] - 6
    info = page.evaluate("""([x, y]) => {
      const chain = []; let e = document.elementFromPoint(x, y);
      while (e && e !== document.documentElement) { const s = getComputedStyle(e); chain.push(e.tagName.toLowerCase() + '.' + String(e.className.baseVal ?? e.className).slice(0, 50) + ' | pos=' + s.position + ' ta=' + s.touchAction); e = e.parentElement }
      const m = document.querySelector('main').getBoundingClientRect(); const nav = [...document.querySelectorAll('nav')].map(n => n.getBoundingClientRect()).filter(r => r.height > 0).map(r => ({top: r.top, bottom: r.bottom}));
      const spans = [...document.querySelectorAll('[data-square] > span > span')].map(s => { const r = s.getBoundingClientRect(); return {t: s.textContent, w: +r.width.toFixed(1), h: +r.height.toFixed(1)} });
      return { point: [x, y], inner: [innerWidth, innerHeight], mainRect: {top: m.top, bottom: m.bottom}, nav, chain, spans: spans.slice(0, 4).concat(spans.slice(-3)) }
    }""", [x, y])
    print(json.dumps(info, indent=1, ensure_ascii=False))
    shot(page, "t03_force560_point_d1")
    browser.close()
