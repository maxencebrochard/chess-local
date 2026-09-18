"""/#/jouer : jouer un coup PAR DRAG fait-il défiler <main> ? (MoveList.tsx:15 scrollIntoView)
Configs : safari660 (scroll remis à 0) et standalone852 + safe areas iPhone 14 Pro émulées (env() = 0 en émulation).
Usage : python3 t05_movelist_scroll.py [fixsiv]   (fixsiv : scrollIntoView restreint au conteneur de la liste)"""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

FIX = len(sys.argv) > 1 and sys.argv[1] == "fixsiv"
# Emule le correctif proposé : ne faire défiler QUE le conteneur scrollable le plus proche, jamais <main>.
FIX_JS = """
Element.prototype.scrollIntoView = function () {
  let box = this.parentElement;
  while (box && !/(auto|scroll)/.test(getComputedStyle(box).overflowY)) box = box.parentElement;
  if (!box || box.tagName === 'MAIN') return;
  const e = this.getBoundingClientRect(), b = box.getBoundingClientRect();
  if (e.top < b.top) box.scrollTop -= b.top - e.top; else if (e.bottom > b.bottom) box.scrollTop += e.bottom - b.bottom;
};
"""
# iPhone 14 Pro portrait : safe-area-inset-top 59px, bottom 34px. index.css : .pt-safe = inset-top + 12px.
INSETS_CSS = ".pt-safe { padding-top: 71px !important; } .pb-safe { padding-bottom: 34px !important; }"
CONFIGS = [("safari660", dict(standalone=False), ""), ("standalone852+insets-emules", dict(standalone=True), INSETS_CSS), ("standalone852-brut", dict(standalone=True), "")]
MOVES = [("h2", "h3"), ("a2", "a3"), ("g2", "g3"), ("b2", "b3"), ("h3", "h4"), ("a3", "a4"), ("g3", "g4"), ("b3", "b4")]

MAIN = "() => { const m = document.querySelector('main'); const b = document.querySelector('[id$=\"-board\"]'); return { top: Math.round(m.scrollTop), max: m.scrollHeight - m.clientHeight, boardTop: Math.round(b.getBoundingClientRect().top) } }"

with sync_playwright() as p:
    for name, kw, css in CONFIGS:
        browser, ctx, page, logs = open_mobile_t(p, **kw)
        install(page)
        if FIX:
            page.add_init_script(FIX_JS)
        page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(1200)
        if css:
            page.add_style_tag(content=css)
        page.locator("main button", has_text="Noa").first.click()
        page.locator("main button", has_text="Blancs").first.click()
        page.get_by_role("button", name="Jouer", exact=True).click()
        page.wait_for_timeout(1500)
        print(f"\n=== {name} | fix={FIX} | au démarrage: {page.evaluate(MAIN)}")
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        print(f"    après remise à 0 : {page.evaluate(MAIN)}")
        shot(page, f"t05_{name}_{'fix' if FIX else 'base'}_0_debut")
        first_scroll_shot = False
        for i, (frm, to) in enumerate(MOVES, 1):
            if piece_on(page, frm) != "wP" or piece_on(page, to):
                print(f"    coup {i} {frm}{to}: non jouable ici (pièce prise ou case occupée), ignoré"); continue
            m0 = page.evaluate(MAIN); pos0 = snap(page)["pos"]
            r = gesture(page, *sq_center(page, frm), *sq_center(page, to))
            m1 = page.evaluate(MAIN); v = verdict(r)
            # attend la réponse du bot (moteur partagé avec d'autres agents : marge large)
            for _ in range(40):
                page.wait_for_timeout(250)
                if len([k for k, val in snap(page)["pos"].items() if val.startswith("b")]) and snap(page)["pos"] != r["after"]["pos"]:
                    break
            page.wait_for_timeout(300)
            m2 = page.evaluate(MAIN)
            flag = "SCROLL" if (m1["top"] != m0["top"] or m2["top"] != m1["top"]) else "ok    "
            print(f"[{flag}] coup {i} {frm}->{to} hit={r['startHit']} joué={v['moved']} pcancel={v['pointercancel']} | main.scrollTop avant={m0['top']} après mon coup={m1['top']} après réponse bot={m2['top']} (max={m2['max']}) | boardTop {m0['boardTop']}->{m2['boardTop']}")
            if flag == "SCROLL" and not first_scroll_shot:
                shot(page, f"t05_{name}_{'fix' if FIX else 'base'}_1_apres_scroll_coup{i}"); first_scroll_shot = True
        shot(page, f"t05_{name}_{'fix' if FIX else 'base'}_2_fin")
        browser.close()
