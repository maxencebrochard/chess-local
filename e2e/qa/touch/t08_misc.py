"""Divers : (1) diagramme lecture seule de CourseSheet vs scroll de la feuille, (2) annulation de promotion,
(3) scroll de <main> conservé entre routes, (4) croissance de history.length (analyse swipe-back),
(5) parade candidate 'touchstart preventDefault' : casse-t-elle taps, drags, boutons de promotion ?"""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

with sync_playwright() as p:
    # ---------- 1. CourseSheet : board non interactif dans une feuille scrollable ----------
    print("=== 1. CourseSheet (diagramme lecture seule dans une feuille overflow-y-auto), safari660")
    browser, ctx, page, logs = open_mobile_t(p, standalone=False); install(page)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1000)
    page.locator("main button", has_text="Finales").last.click(); page.wait_for_timeout(1200)
    page.get_by_role("button", name="Voir le cours complet").first.click(); page.wait_for_timeout(800)
    sheet = """() => { const s = [...document.querySelectorAll('.fixed.z-50 .overflow-y-auto')][0]; if (!s) return null; const b = s.querySelector('[id$="-board"]');
      return { top: Math.round(s.scrollTop), max: s.scrollHeight - s.clientHeight, board: b ? (() => { const r = b.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width)] })() : null,
               pieces: [...s.querySelectorAll('[data-piece]')].map(e => { const r = e.getBoundingClientRect(); return [e.getAttribute('data-piece'), Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2), getComputedStyle(e).touchAction] }),
               empties: [...s.querySelectorAll('[data-square]')].filter(q => !q.querySelector('[data-piece]')).slice(0, 40).map(e => { const r = e.getBoundingClientRect(); return [e.getAttribute('data-square'), Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)] }) } }"""
    st = page.evaluate(sheet); print("   feuille:", {k: v for k, v in st.items() if k in ('top', 'max', 'board')}, "| nb pièces:", len(st["pieces"]))
    shot(page, "t08_1_coursesheet")
    if st["max"] > 0 and st["pieces"]:
        vis_p = [q for q in st["pieces"] if 120 < q[2] < 560]; vis_e = [q for q in st["empties"] if 120 < q[2] < 560]
        pc = vis_p[0]; r = gesture(page, pc[1], pc[2], pc[1], pc[2] - 160); a = page.evaluate(sheet)
        print(f"   doigt posé sur une PIECE du diagramme ({pc[0]}, touch-action={pc[3]}), glissé haut 160px -> feuille scrollTop {st['top']} -> {a['top']} | pcancel={verdict(r)['pointercancel']} hit={r['startHit']}")
        page.evaluate("() => { document.querySelector('.fixed.z-50 .overflow-y-auto').scrollTop = 0 }"); page.wait_for_timeout(200)
        em = vis_e[len(vis_e) // 2]; r = gesture(page, em[1], em[2], em[1], em[2] - 160); a2 = page.evaluate(sheet)
        print(f"   doigt posé sur une CASE VIDE du diagramme ({em[0]}), glissé haut 160px -> feuille scrollTop 0 -> {a2['top']} | hit={r['startHit']}")
    else:
        print("   (feuille non scrollable ou sans diagramme pour ce cours : cas non testable ici)")
    browser.close()

    # ---------- 2. annulation d'une promotion ----------
    print("=== 2. promotion : peut-on annuler ? (tap sur le voile hors boutons)")
    browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    for m in ["h2h4", "g7g5", "h4g5", "h7h6", "g5h6", "f8g7", "h6g7", "g8f6"]:
        tap_move(page, m[:2], m[2:], pause=180)
    tap_move(page, "g7", "h8"); page.wait_for_timeout(300)
    PROMO_ON = "() => !!document.querySelector('.z-20.bg-black\\\\/60, .absolute.inset-0.z-20')"
    print("   voile de promotion affiché:", page.evaluate(PROMO_ON))
    x, y = sq_center(page, "a1"); page.touchscreen.tap(x, y); page.wait_for_timeout(400)
    print("   après tap sur le voile (coin a1, hors boutons) -> voile toujours affiché:", page.evaluate(PROMO_ON), "| g7 =", piece_on(page, "g7"))
    page.locator("main button", has_text="Précédent").click(); page.wait_for_timeout(400)
    print("   après bouton 'Précédent' -> voile toujours affiché:", page.evaluate(PROMO_ON))
    shot(page, "t08_2_promotion_annulation"); browser.close()

    # ---------- 3 + 4. scroll conservé entre routes, croissance de l'historique ----------
    print("=== 3/4. navigation par la barre du bas : history.length et scroll de <main> (safari660)")
    browser, ctx, page, logs = open_mobile_t(p, standalone=False); install(page)
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(1000)
    h0 = page.evaluate("history.length")
    for label in ["Jouer", "Puzzles", "Analyse", "Stats", "Jouer", "Puzzles"]:
        page.locator("nav a", has_text=label).last.click(); page.wait_for_timeout(500)
    print(f"   history.length : {h0} -> {page.evaluate('history.length')} après 6 taps d'onglets (chaque tap empile une entrée = autant de cibles pour le swipe-back iOS)")
    page.locator("nav a", has_text="Jouer").last.click(); page.wait_for_timeout(500)
    page.evaluate("() => { const m = document.querySelector('main'); m.scrollTop = m.scrollHeight }"); page.wait_for_timeout(200)
    a = scroll_state(page); page.locator("nav a", has_text="Puzzles").last.click(); page.wait_for_timeout(900); b = scroll_state(page)
    print(f"   <main> scrollé à {a['mainScrollTop']} sur Jouer, puis onglet Puzzles -> mainScrollTop={b['mainScrollTop']} (attendu 0) boardTop={snap(page)['boardTop']}")
    shot(page, "t08_3_scroll_conserve_entre_routes"); browser.close()

    # ---------- 5. parade candidate : touchstart non passif + preventDefault sur les cases ----------
    print("=== 5. parade candidate touchstart.preventDefault (cases uniquement, pas le voile de promotion)")
    CAND = """document.addEventListener('touchstart', (e) => { if (e.target.closest && e.target.closest('[data-square]')) e.preventDefault() }, { passive: false, capture: true });"""
    browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page); page.add_init_script(CAND)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    page.add_style_tag(content=".boardbox { touch-action: none; } [data-square] > span, [data-square] > span > span { pointer-events: none; }")
    tap_square(page, "e2"); page.wait_for_timeout(250); print("   tap e2 -> sélection:", snap(page)["selected"], "(attendu ['e2'])")
    tap_square(page, "e4"); page.wait_for_timeout(250); print("   tap e4 -> e4 =", piece_on(page, "e4"), "(attendu wP)")
    r = gesture(page, *sq_center(page, "e7"), *sq_center(page, "e5")); v = line("drag e7->e5", r, "piece:b")
    print("   touchstart marqué prevented:", any("touchstart" in e and "prevented" in e for e in r["events"]), "| events:", [e for e in r["events"] if e.startswith("touch")][:3])
    for m in ["h2h4", "g7g5", "h4g5", "h7h6", "g5h6", "f8g7", "h6g7", "g8f6"]:
        tap_move(page, m[:2], m[2:], pause=180)
    tap_move(page, "g7", "h8"); page.wait_for_timeout(300)
    btn = page.evaluate("() => { const b = [...document.querySelectorAll('.absolute.inset-0.z-20 button')][0]; if (!b) return null; const r = b.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2] }")
    if btn:
        page.touchscreen.tap(*btn); page.wait_for_timeout(500)
    print("   promotion par tap sur la dame avec la parade active -> h8 =", piece_on(page, "h8"), "(attendu wQ)")
    print("   logs:", [l for l in logs if "cancel a touchend" not in l][:3])
    browser.close()
