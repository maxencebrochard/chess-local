"""/#/jouer contre un bot, cibles VALIDEES (toute ligne dont le doigt n'a pas touché la cible prévue sort en INVALI).
Configs : standalone852 brut, standalone852 + safe areas iPhone 14 Pro émulées, safari660 (scroll remis à 0).
Usage : python3 t04_play.py [fix2]"""
import os, sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

FIX = sys.argv[1] if len(sys.argv) > 1 else ""
FIX_CSS = {"fix2": ".boardbox { touch-action: none; } [data-square] > span, [data-square] > span > span { pointer-events: none; }"}.get(FIX, "")
INSETS_CSS = ".pt-safe { padding-top: 71px !important; } .pb-safe { padding-bottom: 34px !important; }"
CONFIGS = [("standalone852-brut", dict(standalone=True), ""), ("standalone852+insets-emules", dict(standalone=True), INSETS_CSS), ("safari660", dict(standalone=False), "")]
ONLY = os.environ.get("ONLY")
STATE = """(sq) => { const p = document.querySelector(`[data-square='${sq}'] [data-piece]`); if (!p) return null;
  return p.getAttribute('data-piece') + ' ta=' + getComputedStyle(p).touchAction + ' aria-disabled=' + p.parentElement.getAttribute('aria-disabled') }"""
VISIBLE = """(sqs) => { const m = document.querySelector('main').getBoundingClientRect(); return sqs.filter(s => { const r = document.querySelector(`[data-square='${s}']`).getBoundingClientRect(); return r.top >= m.top + 80 && r.bottom <= m.bottom - 4 }) }"""

def wait_bot(page, ref_pos, ms=9000):
    for _ in range(ms // 250):
        page.wait_for_timeout(250)
        if snap(page)["pos"] != ref_pos:
            break
    page.wait_for_timeout(400)

with sync_playwright() as p:
    for name, kw, css in [c for c in CONFIGS if not ONLY or c[0] == ONLY]:
        browser, ctx, page, logs = open_mobile_t(p, **kw)
        install(page)
        page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(1200)
        if css:
            page.add_style_tag(content=css)
        page.locator("main button", has_text="Noa").first.click()
        page.locator("main button", has_text="Blancs").first.click()
        page.get_by_role("button", name="Jouer", exact=True).click()
        page.wait_for_timeout(1500)
        if FIX_CSS:
            page.add_style_tag(content=FIX_CSS)
        s0 = snap(page)
        print(f"\n=== jouer | {name} | fix={FIX or '-'} | AU DEMARRAGE scrollers={s0['scrollers']} boardTop={s0['boardTop']}")
        shot(page, f"t04_{name}_{FIX or 'base'}_debut")
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        c = lambda sq: sq_center(page, sq)
        vis = lambda sqs: page.evaluate(VISIBLE, sqs)
        # 1. coup jouable puis, SANS attendre, drag d'une de mes pièces pendant que le bot réfléchit
        r = gesture(page, *c("e2"), *c("e4"), steps=6, step_ms=8, hold_ms=20); line("jouable e2->e4 (haut)", r, "piece:w")
        pre = page.evaluate(STATE, "d2"); x, y = c("d2")
        r = gesture(page, x, y, x, y - 200, steps=6, step_ms=8, hold_ms=20)
        v = line(f"BOT REFLECHIT, d2 [{pre}] drag haut 200px", r, "piece:w")
        print("      (fenêtre 'bot réfléchit' " + ("ATTRAPEE" if pre and "aria-disabled=true" in pre else "MANQUEE : le bot avait déjà répondu, ligne non probante") + ")")
        wait_bot(page, r["after"]["pos"])
        # 2. pièce adverse visible, long drag vertical
        opp = vis(squares_with(page, "b"))
        x, y = c(opp[0]); r = gesture(page, x, y, x, y + 260); line(f"pièce ADVERSE {opp[0]} drag bas 260px", r, "piece:b")
        x, y = c(opp[-1]); r = gesture(page, x, y, x, y - 120); line(f"pièce ADVERSE {opp[-1]} drag haut 120px", r, "piece:b")
        # 3. cases vides visibles (rangées du milieu), dans les deux sens
        emp = [s for s in vis(empty_squares(page)) if s[1] in "3456"]
        x, y = c(emp[0]); r = gesture(page, x, y, x, y - 200); line(f"case VIDE {emp[0]} drag haut 200px", r, "case-vide")
        x, y = c(emp[-1]); r = gesture(page, x, y, x, y + 200); line(f"case VIDE {emp[-1]} drag bas 200px", r, "case-vide")
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        # 4. colonne a : pièce saisie par son chiffre (coin haut-gauche), à quelques px du bord d'écran
        b = sq_rect(page, "a2"); r = gesture(page, b["x"] + 5, b["y"] + 7, *c("a4"))
        v = line(f"colonne a : pion a2 saisi sur son chiffre (x={b['x'] + 5:.0f}px) -> a4", r, "piece:w" if FIX else "coordonnee")
        if v["moved"]:
            wait_bot(page, r["after"]["pos"])
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        # 5. rangée 1 : pièce saisie par sa lettre (coin bas-droit) ; cavalier g1 -> f3
        b = sq_rect(page, "g1"); r = gesture(page, b["x"] + b["width"] - 6, b["y"] + b["height"] - 6, *c("f3"))
        v = line("rangée 1 : cavalier g1 saisi sur sa lettre -> f3", r, "piece:w" if FIX else "coordonnee")
        if v["moved"]:
            wait_bot(page, r["after"]["pos"])
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        # 6. colonne h par le centre
        r = gesture(page, *c("h2"), *c("h4")); v = line("colonne h : h2 -> h4 (centre)", r, "piece:w")
        if v["moved"]:
            wait_bot(page, r["after"]["pos"])
        # 7. relecture : board non interactif
        page.locator("main button", has_text="◀").first.click(); page.wait_for_timeout(400)
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        mine = [s for s in vis(squares_with(page, "w")) if s[1] == "2"][0]
        x, y = c(mine); r = gesture(page, x, y, x, y - 220); line(f"RELECTURE pièce {mine} [{page.evaluate(STATE, mine)}] drag haut", r, "piece:w")
        emp = [s for s in vis(empty_squares(page)) if s[1] in "3456"]
        x, y = c(emp[0]); r = gesture(page, x, y, x, y - 200); line(f"RELECTURE case vide {emp[0]} drag haut 200px", r, "case-vide")
        shot(page, f"t04_{name}_{FIX or 'base'}_fin")
        print("   nb erreurs console 'Ignored attempt to cancel a touchend':", sum(1 for l in logs if "cancel a touchend" in l), "| autres:", [l for l in logs if "cancel a touchend" not in l][:3])
        browser.close()
