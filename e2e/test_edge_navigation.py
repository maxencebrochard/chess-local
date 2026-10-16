"""Gestes de bord en PWA : annulation native et interactions tactiles conservées."""
from helpers import BASE, FINALES, Checker, drag_piece, mobile_context, piece_on, scroll_state, sq_center, tap_move, touch_drag

ck = Checker("edge_navigation")

# Garder l'événement en capture, lire son état APRÈS toute la propagation.
# Une microtask pourrait s'exécuter avant les écouteurs suivants.
PROBE = """
window.__touchStarts = [];
window.addEventListener('touchstart', e => {
  const sample = { event: e, x: e.touches[0].clientX,
    thinking: e.target.closest?.('[data-thinking]')?.dataset.thinking,
    square: e.target.closest?.('[data-square]')?.dataset.square,
    piece: e.target.closest?.('[data-piece]')?.dataset.piece };
  window.__touchStarts.push(sample);
}, {capture: true, passive: true});
"""


def last_start(page):
    return page.evaluate("""() => {
      const s = window.__touchStarts.at(-1);
      return s ? {x: s.x, piece: s.piece, thinking: s.thinking, square: s.square, prevented: s.event.defaultPrevented,
        trusted: s.event.isTrusted, cancelable: s.event.cancelable} : null;
    }""")



def exercise_drags(p, browser):
    # Chaque geste repart d'une position fraîche : aucun coup précédent ne masque un refus.
    for mode in ("analyse", "cours", "jouer", "puzzle"):
        for side, distance in (("gauche", 13), ("droit", 13), ("gauche", 20), ("droit", 20), ("centre", None)):
            label = f"[{mode} {side} {distance}]"
            ctx = mobile_context(p, browser, ck, standalone=True)
            ctx.add_init_script(PROBE)
            page = ctx.new_page()
            square, target, piece = {"gauche": ("a4", "c4", "wR"), "droit": ("h4", "f4", "wR"), "centre": ("d4", "d6", "wR")}[side]
            if mode == "cours":
                lesson, square, target, piece = {
                    "gauche": ("mat-deux-tours?etape=2", "a1", "a4", "wR"),
                    "droit": ("mat-tour?etape=3", "h7", "a7", "wR"),
                    "centre": ("mat-dame?etape=2", "d1", "d7", "wQ"),
                }[side]
                page.goto(f"{BASE}/#/apprendre/finales/{lesson}")
            elif mode == "jouer":
                page.goto(f"{BASE}/#/jouer")
                page.get_by_role("button", name="2 joueurs (local)").tap()
                page.get_by_role("button", name="Jouer", exact=True).tap()
                square, target, piece = {"gauche": ("a2", "a4", "wP"), "droit": ("h2", "h4", "wP"), "centre": ("e2", "e4", "wP")}[side]
            elif mode == "puzzle":
                # Une solution déterministe par geste, distribuée par le vrai chargeur de puzzles.
                puzzle = [["bord", "4k3/8/8/8/R2R3R/8/8/4K3 b - - 0 1", f"e8e7 {square}{target}", 800, "rookEndgame"]]
                page.route("**/puzzles.json", lambda route: route.fulfill(json=puzzle))
                page.goto(f"{BASE}/#/puzzles")
                ck.appears(f"{label} amorce jouée", page, "[data-square='e7'] [data-piece='bK']")
            else:
                page.goto(f"{BASE}/#/analyse")
                page.get_by_role("button", name="Options").tap()
                page.get_by_role("button", name="Importer PGN ou FEN", exact=True).tap()
                page.locator("textarea").fill("4k3/8/8/8/R2R3R/8/8/4K3 w - - 0 1")
                page.get_by_role("button", name="Charger", exact=True).tap()
            if not ck.appears(f"{label} pièce prête", page, f"[data-square='{square}'] [data-piece='{piece}']"):
                ctx.close()
                continue
            x, y = sq_center(page, square)
            width = page.evaluate("innerWidth")
            if distance is not None:
                x = distance if side == "gauche" else width - distance
            ck.check(f"{label} départ sur la pièce attendue", page.evaluate("([x,y]) => document.elementFromPoint(x,y)?.closest('[data-piece]')?.dataset.piece", [x, y]) == piece)
            before = scroll_state(page)
            drag_piece(page, square, target, start=(x, y))
            event = last_start(page)
            ck.check(f"{label} contact natif annulable", event and event["trusted"] and event["cancelable"] and event["piece"] == piece, str(event))
            ck.check(f"{label} annulation conforme", event and event["prevented"] == (distance is not None), str(event))
            ck.appears(f"{label} pièce arrivée", page, f"[data-square='{target}'] [data-piece='{piece}']")
            ck.check(f"{label} coup joué", piece_on(page, target) == piece and piece_on(page, square) is None)
            after = scroll_state(page)
            # Le résultat du puzzle peut allonger le contenu sans le faire défiler.
            stable = ("windowScrollY", "mainScrollTop", "hash", "historyLength")
            ck.check(f"{label} route et défilement stables", all(after[k] == before[k] for k in stable), f"{before} -> {after}")
            ctx.close()

    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(PROBE)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre/finales/mat-deux-tours")
    if ck.appears("[diagramme] cours affiché", page, "[data-square='a4']"):
        for side in ("gauche", "droit"):
            x = 20 if side == "gauche" else page.evaluate("innerWidth") - 20
            _, y = sq_center(page, "a4")
            ck.check(f"[diagramme {side}] contact sur une case", page.evaluate("([x,y]) => !!document.elementFromPoint(x,y)?.closest('[data-square]')", [x, y]))
            touch_drag(page, x, y, x, y - 80)
            event = last_start(page)
            ck.check(f"[diagramme {side}] contact annulé au bord", event and event["trusted"] and event["cancelable"] and event["prevented"], str(event))
        # Le cours complet fournit un diagramme dans une feuille réellement défilable.
        page.set_viewport_size({"width": 393, "height": 660})
        page.goto(f"{BASE}/#/apprendre")
        page.locator("main button", has_text=FINALES).tap()
        page.get_by_text("Voir le cours complet", exact=True).tap()
        if ck.appears("[diagramme centre] cours complet", page, "div.fixed [data-board] [data-piece]"):
            panel = page.locator("div.fixed .overflow-y-auto")
            ck.check("[diagramme centre] panneau défilable", panel.evaluate("el => el.scrollHeight - el.clientHeight >= 120"))
            # Une case vide et une pièce, colonnes c à f du premier diagramme : loin des bords.
            # react-chessboard pose touch-action: none sur ses pièces, le contact sur une pièce
            # est le cas qui a déjà bloqué le défilement.
            for kind, with_piece in (("case vide", False), ("pièce", True)):
                square = page.evaluate("""withPiece => {
                  const board = document.querySelector('div.fixed [data-board]');
                  return [...board.querySelectorAll('[data-square]')].find(s => 'cdef'.includes(s.dataset.square[0])
                    && !!s.querySelector('[data-piece]') === withPiece)?.dataset.square ?? null;
                }""", with_piece)
                if not ck.check(f"[diagramme centre {kind}] case trouvée", square is not None, str(square)):
                    continue
                panel.evaluate("el => { el.scrollTop = 0 }")
                target = page.locator(f"div.fixed [data-board] [data-square='{square}']").first
                target.tap(trial=True)
                box = target.bounding_box()
                x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                before = panel.evaluate("el => el.scrollTop")
                page.evaluate("window.__touchStarts = []")
                touch_drag(page, x, y, x, y - 120)
                event = last_start(page)
                ck.check(f"[diagramme centre {kind}] contact non annulé", event and event["trusted"] and event["cancelable"]
                         and not event["prevented"] and event["square"] == square and bool(event["piece"]) == with_piece, str(event))
                # Le geste de 120 px défile d'environ 105 px (seuil de démarrage du défilement).
                moved = panel.evaluate("el => el.scrollTop") - before
                ck.check(f"[diagramme centre {kind}] défilement vertical", moved >= 80, f"{moved} px")
    ctx.close()


def engine_edge(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(PROBE)
    # Retenir les `go` du moteur tant que window.__holdGo est vrai : la réflexion dure alors
    # jusqu'au contact au bord, quelle que soit la vitesse de la machine.
    ctx.add_init_script("""
const send = Worker.prototype.postMessage;
Worker.prototype.postMessage = function (msg, ...rest) {
  if (typeof msg === 'string' && msg.startsWith('go') && window.__holdGo) {
    const wait = () => window.__holdGo ? setTimeout(wait, 20) : send.call(this, msg, ...rest);
    return wait();
  }
  return send.call(this, msg, ...rest);
};
""")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    page.get_by_role("button", name="Options").tap()
    page.get_by_role("button", name="♟ Jouer contre le moteur depuis ici", exact=True).tap()
    if ck.appears("[moteur] partie prête", page, "[data-testid='position-game'][data-thinking='0']"):
        # Coordonnées avant le coup pour toucher le bord dès le début de la réflexion.
        _, y = sq_center(page, "a4")
        page.evaluate("window.__holdGo = true")
        tap_move(page, "e2", "e4", pause=0)
        ck.appears("[moteur] réflexion en cours", page, "[data-testid='position-game'][data-thinking='1']")
        page.touchscreen.tap(20, y)
        event = last_start(page)
        page.evaluate("window.__holdGo = false")
        ck.check("[moteur] contact pendant la réflexion", event and event["thinking"] == "1" and event["square"] == "a4", str(event))
        ck.check("[moteur] contact au bord annulé", event and event["trusted"] and event["cancelable"] and event["prevented"], str(event))
        ck.appears("[moteur] coup du joueur joué", page, "[data-square='e4'] [data-piece='wP']")
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    for square, target, side in [("a4", "c4", "gauche"), ("h4", "f4", "droit")]:
        ctx = mobile_context(p, browser, ck, standalone=True)
        ctx.add_init_script(PROBE)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/analyse")
        if not ck.appears(f"[{side}] échiquier", page, "[data-square='a2'] [data-piece]"):
            ctx.close()
            continue
        page.get_by_role("button", name="Options").tap()
        page.get_by_role("button", name="Importer PGN ou FEN", exact=True).tap()
        page.locator("textarea").fill("4k3/8/8/8/R6R/8/8/4K3 w - - 0 1")
        page.get_by_role("button", name="Charger", exact=True).tap()
        ck.appears(f"[{side}] position chargée", page, f"[data-square='{square}'] [data-piece='wR']")
        _, y = sq_center(page, square)
        box = page.locator(f"[data-square='{square}']").first.bounding_box()
        x = box["x"] + 3 if side == "gauche" else box["x"] + box["width"] - 3
        ck.check(f"[{side}] départ à moins de 15 px du bord", min(x, page.evaluate("innerWidth")-x) < 15, str(x))
        before = scroll_state(page)
        drag_piece(page, square, target, start=(x, y))
        event = last_start(page)
        ck.check(f"[{side}] vrai touchstart sur la tour", event and event["trusted"] and event["cancelable"] and event["piece"] == "wR", str(event))
        ck.check(f"[{side}] touchstart defaultPrevented", event and event["prevented"], str(event))
        ck.check(f"[{side}] glissé horizontal joué", piece_on(page, target) == "wR" and piece_on(page, square) is None)
        ck.check(f"[{side}] route, historique et défilement stables", scroll_state(page) == before)

        # Clic-clic depuis le même bord, avec le roi noir puis la tour blanche.
        tap_move(page, "e8", "e7")
        ck.appears(f"[{side}] coup noir joué", page, "[data-square='e7'] [data-piece='bK']")
        # La tour a quitté sa case : vérifier le clic-clic sur l'autre tour de bord.
        other, dest = ("h4", "g4") if square == "a4" else ("a4", "b4")
        other_box = page.locator(f"[data-square='{other}']").first.bounding_box()
        edge_x = other_box["x"] + (other_box["width"] - 3 if other == "h4" else 3)
        page.touchscreen.tap(edge_x, y)
        page.wait_for_timeout(250)
        page.locator(f"[data-square='{dest}']").first.tap()
        ck.appears(f"[{side}] tour arrivée par clic-clic", page, f"[data-square='{dest}'] [data-piece='wR']")
        ck.check(f"[{side}] clic-clic depuis le bord joue le coup", piece_on(page, dest) == "wR" and piece_on(page, other) is None)

        page.touchscreen.tap(*sq_center(page, "e4"))
        event = last_start(page)
        ck.check(f"[{side}] touchstart central non empêché", event and event["trusted"] and not event["prevented"], str(event))
        page.get_by_role("button", name="Options").tap()
        ck.appears(f"[{side}] bouton Options tactile", page, "button:has-text('Importer PGN ou FEN')")
        ctx.close()
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(PROBE)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    ck.appears("[contenu] échiquier", page, "[data-square='a2'] [data-piece]")
    page.get_by_role("button", name="Options").tap()
    ck.appears("[contenu] options", page, "button:has-text('Importer PGN ou FEN')")
    # Le bouton pleine largeur doit rester utilisable jusque dans sa marge gauche.
    button = page.get_by_role("button", name="Importer PGN ou FEN", exact=True)
    box = button.bounding_box()
    page.touchscreen.tap(box["x"] + 2, box["y"] + box["height"]/2)
    ck.appears("[contenu] bouton près du bord utilisable", page, "textarea", timeout=3000)
    ctx.close()

    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[contenu] accueil Apprendre", page, "main button:has-text('Finales')")
    ck.check("[contenu] page assez longue", scroll_state(page)["mainScrollable"])
    touch_drag(page, 10, 700, 10, 400)
    ck.check("[contenu] défilement vertical depuis le bord", scroll_state(page)["mainScrollTop"] > 0)
    ctx.close()
    engine_edge(p, browser)
    exercise_drags(p, browser)
    browser.close()


ck.run(suite)
