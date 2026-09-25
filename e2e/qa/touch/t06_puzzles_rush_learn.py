"""Puzzles, Puzzle Rush, Apprendre (4 domaines) : pièce à moi (centre, coup légal), pièce à moi saisie par sa coordonnée,
pièce adverse, case vide. Position aléatoire -> cibles choisies dynamiquement et VALIDEES (INVALI sinon).
Usage : python3 t06_puzzles_rush_learn.py [fix2]"""
import os, sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

FIX = sys.argv[1] if len(sys.argv) > 1 else ""
FIX_CSS = {"fix2": ".boardbox { touch-action: none; } [data-square] > span, [data-square] > span > span { pointer-events: none; }"}.get(FIX, "")
INSETS_CSS = ".pt-safe { padding-top: 71px !important; } .pb-safe { padding-bottom: 34px !important; }"
CONFIGS = [("standalone852+insets-emules", dict(standalone=True), INSETS_CSS), ("safari660", dict(standalone=False), "")]
ONLY = os.environ.get("ONLY"); PAGE_ONLY = os.environ.get("PAGE")

def enter(page, target):
    if target == "puzzles":
        page.goto(f"{BASE}/#/puzzles")
    elif target == "rush":
        page.goto(f"{BASE}/#/rush"); page.wait_for_timeout(1000); page.locator("main button", has_text="Survie").first.click()
    else:
        page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1000); page.locator("main button", has_text=target.split(":")[1]).last.click()
        page.wait_for_timeout(1200)
        go = page.get_by_role("button", name="C'est parti")   # carte d'introduction avant le board
        if go.count():
            go.first.click()
    try:
        page.wait_for_selector("[data-square]", timeout=12000)
    except Exception:
        pass  # écran sans échiquier (carte de stratégie) : géré par l'appelant
    page.wait_for_timeout(1800)

INFO = """() => {
  const sqs = [...document.querySelectorAll('[data-square]')]; const first = sqs[0].getAttribute('data-square');
  const me = first === 'a8' ? 'w' : 'b';   // orientation = couleur du joueur sur ces pages
  const box = (() => { let e = document.querySelector('[id$="-board"]'); while (e && !/(auto|scroll)/.test(getComputedStyle(e).overflowY)) e = e.parentElement; return e })();
  const vb = box ? box.getBoundingClientRect() : { top: 0, bottom: innerHeight };
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.top >= Math.max(0, vb.top) + 2 && r.bottom <= Math.min(innerHeight, vb.bottom) - 2 };
  const name = (el) => el.getAttribute('data-square');
  const mine = sqs.filter(s => vis(s) && s.querySelector(`[data-piece^='${me}']`)).map(name);
  const opp = sqs.filter(s => vis(s) && s.querySelector(`[data-piece^='${me === 'w' ? 'b' : 'w'}']`)).map(name);
  const empty = sqs.filter(s => vis(s) && !s.querySelector('[data-piece]')).map(name);
  // cases portant une coordonnée (colonne de gauche / rangée du bas) ET une pièce à moi
  const labelled = sqs.filter(s => vis(s) && s.querySelector(':scope > span span') && s.querySelector(`[data-piece^='${me}']`)).map(s => ({ sq: name(s), spans: [...s.querySelectorAll(':scope > span span')].map(x => { const r = x.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, x.textContent] }) }));
  return { me, mine, opp, empty, labelled, scroller: box ? box.tagName.toLowerCase() + '.' + String(box.className).slice(0, 30) : null };
}"""
LEGAL = """() => [...document.querySelectorAll('[data-square]')].filter(s => { const i = s.lastElementChild; return i && /radial-gradient/.test(i.style.background) && !/255, 0, 0/.test(i.style.background) }).map(s => s.getAttribute('data-square'))"""

def legal_move(page, mine):
    """Trouve (from, to) légal en tapant mes pièces pour révéler les pastilles de coups légaux."""
    for sq in mine:
        tap_square(page, sq); page.wait_for_timeout(200)
        t = page.evaluate(LEGAL)
        tap_square(page, sq); page.wait_for_timeout(150)  # re-tap : désélection
        if t:
            return sq, t[0]
    return None, None

with sync_playwright() as p:
    for name, kw, css in [c for c in CONFIGS if not ONLY or c[0] == ONLY]:
        for target in [t for t in ["puzzles", "rush", "apprendre:Finales", "apprendre:Tactiques", "apprendre:Ouvertures", "apprendre:Stratégie"] if not PAGE_ONLY or t.startswith(PAGE_ONLY)]:
            browser, ctx, page, logs = open_mobile_t(p, **kw)
            install(page)
            try:
                page.goto(f"{BASE}/#/"); page.wait_for_timeout(500)
                if css:
                    page.add_init_script(f"document.addEventListener('DOMContentLoaded', () => {{ const s = document.createElement('style'); s.textContent = {css!r}; document.head.appendChild(s) }})")
                enter(page, target)
                if css:
                    page.add_style_tag(content=css)
                if FIX_CSS:
                    page.add_style_tag(content=FIX_CSS)
                page.wait_for_timeout(300)
                tag = target.replace(":", "_")
                if not page.locator("[data-square]").count():
                    shot(page, f"t06_{tag}_{name[:6]}_{FIX or 'base'}_sans_board")
                    print(f"\n=== {target} | {name} : pas d'échiquier sur cet écran (capture _sans_board)"); browser.close(); continue
                info = page.evaluate(INFO); s0 = snap(page)
                print(f"\n=== {target} | {name} | fix={FIX or '-'} | joueur={info['me']} scroller_du_board={info['scroller']} scrollers={s0['scrollers']} boardTop={s0['boardTop']}")
                shot(page, f"t06_{tag}_{name[:6]}_{FIX or 'base'}_debut")
                if not page.locator("[data-square]").count():
                    print("   (pas de board sur cet écran : carte sans échiquier)"); browser.close(); continue
                c = lambda sq: sq_center(page, sq)
                def reset():
                    page.evaluate("() => { for (const e of document.querySelectorAll('*')) if (e.scrollTop) e.scrollTop = 0 }"); page.wait_for_timeout(150)
                # a. pièce adverse, long drag vertical
                if info["opp"]:
                    x, y = c(info["opp"][0]); r = gesture(page, x, y, x, y + 220); line(f"pièce ADVERSE {info['opp'][0]} drag bas 220px", r, "piece:" + ("b" if info["me"] == "w" else "w")); reset()
                # b. case vide, deux sens
                if info["empty"]:
                    e = info["empty"][len(info["empty"]) // 2]; x, y = c(e)
                    r = gesture(page, x, y, x, y - 200); line(f"case VIDE {e} drag haut 200px", r, "case-vide"); reset()
                    r = gesture(page, x, y, x, y + 200); line(f"case VIDE {e} drag bas 200px", r, "case-vide"); reset()
                # c. pièce à moi saisie par sa coordonnée (si une de mes pièces est sur la colonne de gauche / rangée du bas)
                if info["labelled"]:
                    L = info["labelled"][0]; sx, sy, txt = L["spans"][0]
                    r = gesture(page, sx, sy, sx + 30, sy - 120); line(f"pièce à moi {L['sq']} saisie sur sa coordonnée '{txt}'", r, "piece:" + info["me"] if FIX else "coordonnee"); reset()
                else:
                    print("   (aucune pièce à moi sur une case à coordonnée dans cette position)")
                # d. pièce à moi par le centre : long drag vertical (lâché hors coup légal) puis VRAI coup légal par drag
                if info["mine"]:
                    m = info["mine"][0]; x, y = c(m); r = gesture(page, x, y, x, y - 180 if y > 300 else y + 180); line(f"pièce à moi {m} long drag vertical", r, "piece:" + info["me"]); reset()
                    frm, to = legal_move(page, info["mine"])
                    if frm:
                        r = gesture(page, *c(frm), *c(to)); v = line(f"coup légal par drag {frm}->{to}", r, "piece:" + info["me"])
                    else:
                        print("   (aucun coup légal trouvé par tap : board non interactif à cet instant ?)")
                page.wait_for_timeout(600)
                shot(page, f"t06_{tag}_{name[:6]}_{FIX or 'base'}_fin")
                other = [l for l in logs if "cancel a touchend" not in l]
                print("   erreurs console touchend:", sum(1 for l in logs if "cancel a touchend" in l), "| autres:", other[:3])
            except Exception as ex:
                print(f"\n=== {target} | {name} : ERREUR DE SCRIPT {type(ex).__name__}: {str(ex)[:200]}")
                shot(page, f"t06_{target.replace(':', '_')}_{name[:6]}_ERREUR")
            browser.close()
