"""E2E tactile : un geste qui commence sur l'échiquier ne fait jamais défiler la page.

Couvre TOUCH-1 (pièce saisie par son chiffre ou sa lettre de coordonnée), TOUCH-2 (glissé depuis
une case vide) et TOUCH-13 (teinte du dernier coup perdue après une désélection).
Tout se joue sur `/#/analyse` en 393x600 : `<main>` y est scrollable (sinon un geste volé par le
navigateur ne produit aucun défilement visible et les checks passeraient à vide), et la barre
d'actions collante ne recouvre pas encore la rangée du bas (à 560 elle masque les lettres).

Usage : npm run test:e2e -- --suite touch
"""
from helpers import BASE, SHOTS, Checker, drag_piece, mobile_context, piece_on, scroll_state, sq_center, tap_square, touch_drag

ck = Checker("touch")
check = ck.check

SWIPE_PX = 200
LAST_MOVE_TINT = "255, 255, 51"
TARGET_MARK = "rgba(0, 0, 0, 0.34)"


def open_page(p, browser, route, height):
    """Page fraîche + journal console (le Checker ne capte que les `pageerror`)."""
    ctx = mobile_context(p, browser, ck, viewport={"width": 393, "height": height})
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append(m.text))
    page.goto(f"{BASE}/#/{route}")
    return ctx, page, console


def open_analyse(p, browser, label):
    ctx, page, console = open_page(p, browser, "analyse", 600)
    ck.appears(f"[{label}] échiquier prêt", page, "[data-square='a2'] [data-piece]")
    page.wait_for_timeout(800)
    check(f"[{label}] précondition : <main> est scrollable", scroll_state(page)["mainScrollable"])
    return ctx, page, console


def eventually(page, cond, timeout_ms=4000):
    """Attente bornée d'un état : la machine de test est chargée, un délai fixe serait instable."""
    waited = 0
    while not cond() and waited < timeout_ms:
        page.wait_for_timeout(100)
        waited += 100
    return cond()


def coord_center(page, square, text):
    """Centre du `<span>` de coordonnée (`text` = « 2 », « g »...) dessiné par react-chessboard dans la case."""
    return page.evaluate(
        """([sq, text]) => {
          const span = [...document.querySelectorAll(`[data-square='${sq}'] > span > span`)]
            .find((s) => s.textContent === text)
          if (!span) return null
          const r = span.getBoundingClientRect()
          return [r.x + r.width / 2, r.y + r.height / 2]
        }""",
        [square, text],
    )


def hit(page, x, y):
    """Ce que le doigt touche réellement : code de la pièce, sinon balise et texte."""
    return page.evaluate(
        """([x, y]) => {
          const el = document.elementFromPoint(x, y)
          const piece = el?.closest('[data-piece]')
          return piece ? piece.getAttribute('data-piece') : `${el?.tagName}:${(el?.textContent ?? '').slice(0, 3)}`
        }""",
        [x, y],
    )


def same_place(label, before, after):
    check(f"{label} : <main> n'a pas défilé", after["mainScrollTop"] == before["mainScrollTop"], f"(scrollTop {before['mainScrollTop']} -> {after['mainScrollTop']})")
    check(f"{label} : la fenêtre n'a pas défilé", after["windowScrollY"] == before["windowScrollY"], f"({before['windowScrollY']} -> {after['windowScrollY']})")
    check(f"{label} : route et historique inchangés", (after["hash"], after["historyLength"]) == (before["hash"], before["historyLength"]), f"({before['hash']} {before['historyLength']} -> {after['hash']} {after['historyLength']})")


def grab_by_coord(label, page, frm, to, text, piece):
    """Saisit la pièce de `frm` en posant le doigt sur sa coordonnée `text`, et la tire vers `to`."""
    point = coord_center(page, frm, text)
    if not check(f"{label} : la case {frm} affiche la coordonnée « {text} »", point is not None):
        return
    x, y = point
    check(f"{label} : le doigt posé sur « {text} » touche la pièce", hit(page, x, y) == piece, f"(touché : {hit(page, x, y)})")
    before = scroll_state(page)
    touch_drag(page, x, y, *sq_center(page, to))
    played = eventually(page, lambda: piece_on(page, to) == piece and piece_on(page, frm) is None)
    check(f"{label} : coup joué {frm}-{to}", played, f"({frm}={piece_on(page, frm)} {to}={piece_on(page, to)})")
    same_place(label, before, scroll_state(page))


def swipe_from_empty(label, page, square):
    """Glissé vers le HAUT : à scrollTop = 0, c'est le seul sens qui peut faire défiler la page."""
    if not check(f"{label} : précondition, la case {square} est vide", piece_on(page, square) is None):
        return
    x, y = sq_center(page, square)
    before = scroll_state(page)
    touch_drag(page, x, y, x, y - SWIPE_PX)
    same_place(label, before, scroll_state(page))


def square_css(page, square, prop):
    return page.evaluate(
        "([sq, prop]) => getComputedStyle(document.querySelector(`[data-square='${sq}'] > div`))[prop]",
        [square, prop],
    )


def no_console(label, console, needle):
    found = [t for t in console if needle in t]
    check(f"{label} : aucun message console « {needle} »", not found, f"({len(found)} : {found[0][:120]})" if found else "")


def suite(p):
    browser = p.chromium.launch(headless=True)

    # ---------- TOUCH-1 : pièce saisie par sa coordonnée (blancs en bas) ----------
    # Une page fraîche par saisie : c'est toujours aux blancs de jouer.
    ctx, page, _ = open_analyse(p, browser, "chiffre")
    grab_by_coord("[chiffre] pion a2 saisi par son « 2 »", page, "a2", "a4", "2", "wP")
    page.screenshot(path=f"{SHOTS}/touch_chiffre_a2.png")
    ctx.close()

    ctx, page, _ = open_analyse(p, browser, "lettre")
    grab_by_coord("[lettre] cavalier g1 saisi par son « g »", page, "g1", "f3", "g", "wN")
    ctx.close()

    # ---------- TOUCH-2 : glissé depuis une case vide ----------
    ctx, page, console = open_analyse(p, browser, "case vide")
    swipe_from_empty("[case vide] glissé de 200 px depuis e3", page, "e3")
    # Quand le navigateur vole le geste, le preventDefault de la lib sur touchend est refusé.
    no_console("[case vide]", console, "Ignored attempt to cancel a touchend")
    ctx.close()

    # ---------- Noirs en bas : les coordonnées passent sur la colonne h et la rangée 8 ----------
    ctx, page, console = open_analyse(p, browser, "noirs en bas")
    page.click("button:has-text('Options')")
    page.click("button:has-text('Retourner')")
    flipped = eventually(page, lambda: coord_center(page, "h7", "7") is not None)
    check("[noirs en bas] échiquier retourné", flipped)
    swipe_from_empty("[noirs en bas] glissé de 200 px depuis e6", page, "e6")
    drag_piece(page, "e2", "e4")  # témoin : pièce saisie par son centre
    check("[noirs en bas] témoin 1.e4 par le centre", eventually(page, lambda: piece_on(page, "e4") == "wP"))
    grab_by_coord("[noirs en bas] pion h7 saisi par son « 7 »", page, "h7", "h5", "7", "bP")
    drag_piece(page, "d2", "d4")
    check("[noirs en bas] témoin 2.d4 par le centre", eventually(page, lambda: piece_on(page, "d4") == "wP"))
    grab_by_coord("[noirs en bas] cavalier g8 saisi par son « g »", page, "g8", "f6", "g", "bN")
    no_console("[noirs en bas]", console, "Ignored attempt to cancel a touchend")
    page.screenshot(path=f"{SHOTS}/touch_noirs_en_bas.png")
    ctx.close()

    # ---------- TOUCH-13 : la teinte du dernier coup survit à une sélection ----------
    ctx, page, console = open_analyse(p, browser, "dernier coup")
    tap_square(page, "e2")
    marked = eventually(page, lambda: TARGET_MARK in square_css(page, "e4", "background"))
    # `test_all_buttons` et `test_learn` repèrent une cible légale par ce même raccourci calculé.
    check("[dernier coup] cible légale : pastille lisible dans `background`", marked, f"({square_css(page, 'e4', 'background')[:90]})")
    tap_square(page, "e4")
    check("[dernier coup] 1.e4 joué", eventually(page, lambda: piece_on(page, "e4") == "wP"))
    tap_square(page, "d7")
    eventually(page, lambda: TARGET_MARK in square_css(page, "d5", "background"))
    tap_square(page, "d5")
    check("[dernier coup] 1...d5 joué", eventually(page, lambda: piece_on(page, "d5") == "bP"))
    check("[dernier coup] d7 et d5 teintées", eventually(page, lambda: all(LAST_MOVE_TINT in square_css(page, s, "backgroundColor") for s in ("d7", "d5"))))
    tap_square(page, "e4")  # sélection : d5 devient une cible de prise, anneau par-dessus la teinte
    ringed = eventually(page, lambda: TARGET_MARK in square_css(page, "d5", "backgroundImage"))
    check("[dernier coup] d5 cible de prise : anneau", ringed, f"({square_css(page, 'd5', 'backgroundImage')[:90]})")
    check("[dernier coup] d5 cible de prise : teinte conservée sous l'anneau", LAST_MOVE_TINT in square_css(page, "d5", "backgroundColor"), f"({square_css(page, 'd5', 'backgroundColor')})")
    page.screenshot(path=f"{SHOTS}/touch_dernier_coup_selection.png")
    tap_square(page, "e4")  # re-tap : désélection
    eventually(page, lambda: "gradient" not in square_css(page, "d5", "backgroundImage"))
    check("[dernier coup] désélection : l'anneau disparaît", "gradient" not in square_css(page, "d5", "backgroundImage"))
    for s in ("d7", "d5"):
        check(f"[dernier coup] désélection : {s} reste teintée", LAST_MOVE_TINT in square_css(page, s, "backgroundColor"), f"({square_css(page, s, 'backgroundColor')})")
    page.screenshot(path=f"{SHOTS}/touch_dernier_coup_deselection.png")
    # Avertissement de React, émis seulement par le serveur de dev (`npm run test:e2e:dev`).
    no_console("[dernier coup]", console, "Removing a style property")
    ctx.close()

    # ---------- Non-régression : le diagramme d'un cours laisse défiler la feuille ----------
    ctx, page, _ = open_page(p, browser, "apprendre", 660)
    ck.appears("[cours] accueil Apprendre", page, "main button:has-text('Finales')")
    page.locator("main button", has_text="Finales").click()
    ck.appears("[cours] leçon affichée", page, "text=Voir le cours complet")
    page.click("text=Voir le cours complet")
    ck.appears("[cours] diagramme affiché", page, "div.fixed [data-square='a1']")
    page.wait_for_timeout(500)
    sheet_top = "() => document.querySelector('div.fixed .overflow-y-auto').scrollTop"
    sheet_room = "() => { const s = document.querySelector('div.fixed .overflow-y-auto'); return s.scrollHeight - s.clientHeight }"
    check("[cours] précondition : la feuille est scrollable", page.evaluate(sheet_room) > 40, f"({page.evaluate(sheet_room)} px)")
    empty = page.evaluate(
        """() => [...document.querySelectorAll('div.fixed [data-square]')]
          .filter((s) => !s.querySelector('[data-piece]'))
          .map((s) => { const r = s.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2] })
          .filter(([, y]) => y < innerHeight - 40)
          .sort((a, b) => b[1] - a[1])[0] ?? null"""
    )
    if check("[cours] précondition : le diagramme a une case vide", empty is not None):
        x, y = empty
        touch_drag(page, x, y, x, y - 120)
        check("[cours] glissé depuis une case vide du diagramme : la feuille défile", page.evaluate(sheet_top) > 0, f"(scrollTop = {page.evaluate(sheet_top)})")
    page.screenshot(path=f"{SHOTS}/touch_cours.png")
    ctx.close()
    browser.close()


ck.run(suite)
