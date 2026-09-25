"""(a) la parade touchstart.preventDefault prend-elle VRAIMENT effet sans casser tap/drag/promotion ? (journal écrit par l'écouteur lui-même)
(b) chess.com mobile : marge entre le bord de l'écran et le board ?"""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

CAND = """window.__ts = [];
document.addEventListener('touchstart', (e) => { if (e.target.closest && e.target.closest('[data-square]')) { e.preventDefault(); window.__ts.push({ cancelable: e.cancelable, prevented: e.defaultPrevented }) } }, { passive: false, capture: true });
for (const t of ['click', 'mousedown']) document.addEventListener(t, (e) => { if (e.target.closest && e.target.closest('[data-square]')) (window.__compat = window.__compat || []).push(t) }, true);"""

with sync_playwright() as p:
    print("=== (a) parade touchstart.preventDefault, standalone 852")
    browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page); page.add_init_script(CAND)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    page.add_style_tag(content=".boardbox { touch-action: none; } [data-square] > span, [data-square] > span > span { pointer-events: none; }")
    tap_square(page, "e2"); page.wait_for_timeout(250); s1 = snap(page)["selected"]
    tap_square(page, "e4"); page.wait_for_timeout(250)
    r = gesture(page, *sq_center(page, "e7"), *sq_center(page, "e5"))
    b = sq_rect(page, "a2"); r2 = gesture(page, b["x"] + 5, b["y"] + 7, *sq_center(page, "a4"))
    ts = page.evaluate("window.__ts"); compat = page.evaluate("window.__compat || []")
    print(f"   touchstart interceptés: {len(ts)} | tous cancelable+prevented: {all(t['cancelable'] and t['prevented'] for t in ts)} | événements souris/click de compatibilité émis sur les cases: {compat} (attendu [] si preventDefault effectif)")
    print(f"   tap e2 -> sélection {s1} | tap e4 -> e4={piece_on(page, 'e4')} | drag e7->e5 -> e5={piece_on(page, 'e5')} | a2 saisi par son chiffre -> a4={piece_on(page, 'a4')}")
    browser.close()

    print("=== (b) chess.com mobile (iPhone 14 Pro émulé, 393px) : marge latérale du board")
    browser, ctx, page, logs = open_mobile_t(p, standalone=False)
    try:
        page.goto("https://www.chess.com/play/computer", timeout=45000, wait_until="domcontentloaded"); page.wait_for_timeout(7000)
        info = page.evaluate("""() => { const b = document.querySelector('wc-chess-board, chess-board, .board'); if (!b) return { found: false, title: document.title };
          const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
          return { found: true, tag: b.tagName.toLowerCase(), left: +r.x.toFixed(1), rightGap: +(innerWidth - r.right).toFixed(1), width: +r.width.toFixed(1), vw: innerWidth, touchAction: cs.touchAction, userSelect: cs.userSelect,
                   coordsInsideBoard: !!b.querySelector('svg.coordinates, .coordinates'), coordsPointerEvents: (() => { const c = b.querySelector('svg.coordinates, .coordinates'); return c ? getComputedStyle(c).pointerEvents : null })() } }""")
        print("  ", info)
        shot(page, "t09_chesscom_mobile")
    except Exception as ex:
        print("   chess.com non mesurable depuis cet environnement:", type(ex).__name__, str(ex)[:160])
    browser.close()
