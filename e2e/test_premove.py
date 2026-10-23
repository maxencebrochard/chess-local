"""Prémouvements sur iPhone : vrais gestes, moteur retenu à la frontière UCI."""
import json
import os
import chess
from datetime import datetime, timedelta, timezone

from helpers import BASE, HOLD_BESTMOVE, WEBKIT_AUDIO, Checker, desktop_context, mobile_context, drag_piece, tap_move, tap_square, piece_on, sound_log, shot

ck = Checker("premove")


def red(page, square):
    return page.locator(f"[data-square={square}] > div").evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(220, 50, 50, 0.65)"


def wait(page, expression):
    try:
        page.wait_for_function(expression, timeout=15000)
        return True
    except Exception:
        return False


def start(p, browser, enabled=True):
    ctx = mobile_context(p, browser, ck, standalone=True, settings={"premoves": enabled, "playSounds": True, "playBotId": "maximus", "playTcLabel": "Illimité"})
    ctx.add_init_script(HOLD_BESTMOVE)
    ctx.add_init_script(WEBKIT_AUDIO)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/jouer")
    page.get_by_role("button", name="Jouer", exact=True).click()
    ck.appears("plateau iPhone", page, "[data-square=e2]")
    page.evaluate("window.__heldUci = []")
    tap_move(page, "e2", "e4")
    ck.check("réponse réelle du moteur retenue", wait(page, "window.__heldUci.length > 0"))
    return ctx, page


def release(page, uci="e7e5"):
    # Réponse légale imposée pour rendre le scénario indépendant du choix de Stockfish.
    page.evaluate("uci => { for (const h of window.__heldUci) h[1] = 'bestmove ' + uci; window.__releaseUci(); window.__heldUci = [] }", uci)
    wait(page, "document.querySelectorAll('main [data-current]').length >= 2 || !!document.querySelector('div.fixed')")
    page.wait_for_timeout(300)
    page.evaluate("window.__heldUci = []")


def suite(p):
    browser = p.chromium.launch()
    if os.environ.get("PREMOVE_CASE", "selection") == "selection":
        ctx, page = start(p, browser)
        tap_move(page, "a1", "b1")
        tap_square(page, "c3")
        ck.check("pièce alliée : sélection du cavalier puis prémouvement", red(page, "b1") and red(page, "c3") and not red(page, "a1"))
        release(page)
        ck.check("pièce alliée : seul le cavalier joue", piece_on(page, "c3") == "wN" and piece_on(page, "a1") == "wR")
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "refus") == "refus":
        ctx, page = start(p, browser)
        page.evaluate("""() => {
          window.__returns = []
          const native = Element.prototype.animate
          Element.prototype.animate = function(frames, options) {
            if (this.classList.contains('board-piece')) window.__returns.push({frames, options})
            return native.call(this, frames, options)
          }
        }""")
        before = len(sound_log(page))
        drag_piece(page, "g1", "g3")
        ck.check("refus prémouvement : son illégal unique", [s["name"] for s in sound_log(page)[before:]] == ["illegal"])
        ck.check("refus prémouvement : retour animé 120 ms", page.evaluate("window.__returns.some(a => a.options.duration === 120 && a.frames[1].transform === 'none')"))
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "remplacement") == "remplacement":
        ctx, page = start(p, browser)
        tap_move(page, "g1", "f3")
        drag_piece(page, "b1", "c3")
        ck.check("remplacement : seule la nouvelle file est rouge", red(page, "b1") and red(page, "c3") and not red(page, "g1") and not red(page, "f3"))
        release(page)
        ck.check("remplacement : seul le nouveau coup exécuté", piece_on(page, "c3") == "wN" and piece_on(page, "g1") == "wN" and page.locator("main [data-current]").count() == 3)
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "escape") == "escape":
        ctx = desktop_context(browser, ck, settings={"playBotId": "maximus", "playTcLabel": "Illimité"})
        ctx.add_init_script(HOLD_BESTMOVE)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/jouer")
        page.get_by_role("button", name="Jouer", exact=True).click()
        page.evaluate("window.__heldUci = []")
        for sq in ("e2", "e4"):
            page.locator(f"[data-square={sq}]").click()
        ck.check("desktop : moteur retenu", wait(page, "window.__heldUci.length > 0"))
        for sq in ("g1", "f3"):
            page.locator(f"[data-square={sq}]").click()
        ck.check("desktop : file prête à annuler", red(page, "f3"))
        page.keyboard.press("Escape")
        ck.check("Échap souris : rouge effacé", not red(page, "g1") and not red(page, "f3"))
        release(page)
        ck.check("Échap souris : aucun coup automatique", piece_on(page, "g1") == "wN" and page.locator("main [data-current]").count() == 2)
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "chrono") == "chrono":
        for flag in (False, True):
            ctx = mobile_context(p, browser, ck, standalone=True)
            ctx.add_init_script(HOLD_BESTMOVE)
            page = ctx.new_page()
            page.goto(f"{BASE}/#/mats?d=chrono-krr")
            page.get_by_role("radio", name="15 s", exact=True).click()
            now = datetime.now(timezone.utc)
            page.clock.install(time=now)
            page.clock.pause_at(now + timedelta(seconds=1))
            page.get_by_role("button", name="Commencer").click()
            run = page.locator("[data-run=chrono]")
            board = chess.Board(run.get_attribute("data-fen"))
            # Oracle indépendant : trois demi-coups légaux, sans mat ni nulle intermédiaire.
            def sequence(b, depth):
                if depth == 0:
                    return []
                for m in b.legal_moves:
                    after = b.copy()
                    after.push(m)
                    if not after.is_game_over():
                        rest = sequence(after, depth - 1)
                        if rest is not None:
                            return [m] + rest
                return None
            first, reply, planned = sequence(board, 3)
            if flag:
                page.clock.run_for(14900)
            page.evaluate("window.__heldUci = []")
            tap_move(page, first.uci()[:2], first.uci()[2:4], pause=0)
            page.clock.run_for(150)
            held = wait(page, "window.__heldUci.length > 0")
            before_ms = int(page.locator("[role=timer]").get_attribute("data-ms"))
            tap_move(page, planned.uci()[:2], planned.uci()[2:4], pause=0)
            queued = red(page, planned.uci()[2:4])
            page.evaluate("uci => { for (const h of window.__heldUci) h[1] = 'bestmove ' + uci; window.__releaseUci() }", reply.uci())
            page.wait_for_timeout(300)
            board.push(first)
            board.push(reply)
            if not flag:
                board.push(planned)
            actual = chess.Board(run.get_attribute("data-fen"))
            after_ms = int(page.locator("[role=timer]").get_attribute("data-ms"))
            if flag:
                ck.check("ChronoRun : 100 ms restants, drapeau à zéro sans jouer", held and queued and before_ms == 100 and after_ms == 0 and run.get_attribute("data-phase") == "over" and actual.board_fen() == board.board_fen() and actual.turn == board.turn)
            else:
                ck.check("ChronoRun : prémouvement exécuté et débité de 100 ms", held and queued and before_ms - after_ms == 100 and actual.board_fen() == board.board_fen() and actual.turn == board.turn)
            ctx.close()

    if os.environ.get("PREMOVE_CASE", "continuation") == "continuation":
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
        ctx.add_init_script(HOLD_BESTMOVE)
        puzzle = [["PRECONT", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8", 800, "mateIn1 fork"]]
        ctx.route("**/puzzles.json", lambda route: route.fulfill(content_type="application/json", body=json.dumps(puzzle)))
        page = ctx.new_page()
        page.goto(f"{BASE}/#/apprendre")
        page.locator("main button", has_text="Tactiques").click()
        page.get_by_role("button", name="C'est parti").click()
        wait(page, "!!document.querySelector('[data-square=c3] [data-piece]')")
        tap_move(page, "h2", "h3")
        page.get_by_role("button", name="Jouer contre le moteur").click()
        dialog = page.locator("[data-continuation]")
        page.wait_for_timeout(800)
        page.evaluate("window.__heldUci = []")
        for sq in ("h2", "h3"):
            dialog.locator(f"[data-square={sq}]").tap()
        held = wait(page, "window.__heldUci.length > 0")
        for sq in ("a1", "a8"):
            dialog.locator(f"[data-square={sq}]").tap()
        queued = dialog.locator("[data-square=a8] > div").evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(220, 50, 50, 0.65)"
        page.evaluate("() => { for (const h of window.__heldUci) h[1] = 'bestmove c3e4'; window.__releaseUci() }")
        executed = wait(page, "!!document.querySelector('[data-continuation] [data-square=a8] [data-piece=wR]')")
        ck.check("EngineContinuation : prémouvement joué une seule fois", held and queued and executed and dialog.locator("[data-current]").count() == 3 and dialog.locator("[data-square=a1] [data-piece]").count() == 0)
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "gestes") == "gestes":
        ctx, page = start(p, browser)
        tap_move(page, "g1", "g3")
        ck.check("géométrie : cavalier refusé en ligne droite", not red(page, "g3"))
        tap_move(page, "b8", "c6")
        ck.check("camp adverse non jouable", not red(page, "c6"))
        before = len(sound_log(page))
        drag_piece(page, "g1", "f3")
        ck.check("glissé : deux cases rouges", red(page, "g1") and red(page, "f3"))
        ck.check("glissé : pièce restée au départ", piece_on(page, "g1") == "wN" and piece_on(page, "f3") is None)
        ck.check("saisie silencieuse", len(sound_log(page)) == before)
        shot(page, "premove_attente")
        release(page)
        ck.check("exécution automatique", piece_on(page, "g1") is None and piece_on(page, "f3") == "wN")
        ck.check("historique exact", page.locator("main [data-current]").count() == 3
                 and page.evaluate("JSON.parse(localStorage.getItem('chess-local-play-game')).sans") == ["e4", "e5", "Nf3"])
        expected = chess.Board()
        for uci in ("e2e4", "e7e5", "g1f3"):
            expected.push_uci(uci)
        expected_pieces = {chess.square_name(sq): ("w" if pc.color else "b") + pc.symbol().upper() for sq, pc in expected.piece_map().items()}
        actual_pieces = page.locator("[data-square]").evaluate_all("els => Object.fromEntries(els.filter(e => e.querySelector('[data-piece]')).map(e => [e.dataset.square, e.querySelector('[data-piece]').dataset.piece]))")
        ck.check("position complète conforme à python-chess", actual_pieces == expected_pieces)
        ck.check("son à l'exécution", any(s["name"] == "move-self" for s in sound_log(page)[before:]))
        ck.check("jaune après exécution", page.locator("[data-square=f3] > div").evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(255, 255, 51, 0.4)")
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "annulations") == "annulations":
        for scenario in ("illégal", "annulation", "désactivé"):
            ctx, page = start(p, browser, scenario != "désactivé")
            frm, to = ("e4", "e5") if scenario == "illégal" else ("g1", "f3")
            tap_move(page, frm, to)
            ck.check(f"{scenario} : saisie clic-clic", red(page, to) == (scenario != "désactivé"))
            if scenario == "annulation":
                tap_square(page, "a3")
                ck.check("toucher vide : rouge effacé", not red(page, to))
            before = len(sound_log(page))
            release(page)
            ck.check(f"{scenario} : aucun coup automatique", page.locator("main [data-current]").count() == 2 and piece_on(page, frm) == ("wP" if scenario == "illégal" else "wN"))
            ck.check(f"{scenario} : file effacée", not red(page, to))
            ck.check(f"{scenario} : aucun son joueur ou refus", not any(s["name"] in ("move-self", "illegal") for s in sound_log(page)[before:]))
            ctx.close()
    if os.environ.get("PREMOVE_CASE", "reglages") == "reglages":
        # Ancien stockage : absence de clé, défaut actif ; modification par le vrai interrupteur.
        ctx = mobile_context(p, browser, ck, standalone=True)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/reglages")
        page.evaluate("() => { const s=JSON.parse(localStorage.getItem('chess-local-settings')); delete s.state.premoves; s.state.themeId='blue'; localStorage.setItem('chess-local-settings', JSON.stringify(s)) }")
        page.reload()
        toggle = page.get_by_role("switch", name="Prémouvements", exact=True)
        ck.check("ancien stockage : prémouvements actifs", toggle.get_attribute("aria-checked") == "true")
        ck.check("ancien stockage : autres réglages conservés", page.evaluate("JSON.parse(localStorage.getItem('chess-local-settings')).state.themeId") == "blue")
        toggle.click()
        page.reload()
        ck.check("interrupteur désactivé persistant", toggle.get_attribute("aria-checked") == "false")
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "cycle") == "cycle":
        # Historique au trait adverse : il serait possible de préparer un coup sans la garde.
        ctx, page = start(p, browser)
        release(page)
        tap_move(page, "g1", "f3")
        ck.check("historique : seconde réponse retenue", wait(page, "window.__heldUci.length > 0"))
        tap_move(page, "b1", "c3")
        ck.check("historique : file initiale visible", red(page, "c3"))
        page.locator("main [data-current]").first.click()
        ck.check("historique : file annulée", not red(page, "c3"))
        tap_move(page, "b1", "c3")
        ck.check("historique : saisie interdite", not red(page, "c3"))
        release(page, "b8c6")
        page.wait_for_timeout(900)
        ck.check("historique : pas de coup retardé", piece_on(page, "b1") == "wN" and page.locator("main [data-current]").count() == 4)
        ctx.close()

        ctx, page = start(p, browser)
        tap_move(page, "g1", "f3")
        page.locator("main button", has_text="🏳").first.click()
        page.get_by_role("button", name="Oui, annuler", exact=True).click()
        ck.check("fin : file annulée", not red(page, "f3"))
        release(page)
        ck.check("fin : pas de coup retardé", piece_on(page, "g1") == "wN")
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "promotion") == "promotion":
        # Promotion prévue depuis une position importée, via le composant PositionGame.
        ctx = mobile_context(p, browser, ck, standalone=True, settings={"playSounds": True})
        ctx.add_init_script(WEBKIT_AUDIO)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/analyse")
        page.locator("main button", has_text="Options").tap()
        page.locator("button", has_text="Importer PGN ou FEN").tap()
        page.fill("textarea", "7k/P7/8/8/8/8/8/4K3 w - - 0 1")
        page.click("button:has-text('Charger')")
        page.locator("main button", has_text="Options").tap()
        page.locator("button", has_text="Jouer contre le moteur").locator("visible=true").tap()
        ck.appears("PositionGame chargé", page, "[data-testid=position-game]")
        # Armer uniquement les workers créés dans la partie (au premier coup).
        # Sinon un bestmove tardif de l'analyse quittée satisfait l'attente avant la
        # réponse de PositionGame : release libère le mauvais moteur, puis perd la vraie réponse.
        page.evaluate(HOLD_BESTMOVE)
        page.evaluate("window.__heldUci = []")
        tap_move(page, "e1", "d1")
        ck.check("PositionGame : moteur retenu", wait(page, "window.__heldUci.length > 0"))
        tap_move(page, "a7", "a8")
        ck.check("promotion : prévue sans sélecteur", red(page, "a8") and page.get_by_role("button", name="Dame", exact=True).count() == 0)
        release(page, "h8g8")
        ck.check("promotion automatique en dame", piece_on(page, "a8") == "wQ" and piece_on(page, "a7") is None)
        ck.check("promotion : historique persisté", page.evaluate("JSON.parse(localStorage.getItem('chess-local-position-game-v1')).uci") == ["e1d1", "h8g8", "a7a8q"])
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "pendule") == "pendule":
        # Pendule gelée pendant la réponse : coût fixe mesuré dans l'instantané réel de Play.
        ctx = mobile_context(p, browser, ck, standalone=True, settings={"playBotId": "maximus", "playTcLabel": "1 min"})
        ctx.add_init_script(HOLD_BESTMOVE)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/jouer")
        now = datetime.now(timezone.utc)
        page.clock.install(time=now)
        page.clock.pause_at(now + timedelta(seconds=1))
        # Geler les ticks de pendule, mais laisser passer la latence du bot.
        # Avancer l'horloge de 900 ms peut sinon facturer un tick entre réponse et effet React.
        page.evaluate("""() => {
          const native = window.setInterval
          window.setInterval = (fn, ms, ...args) => native(ms === 100 ? () => {} : fn, ms, ...args)
        }""")
        page.get_by_role("button", name="Jouer", exact=True).click()
        page.evaluate("window.__heldUci = []")
        tap_move(page, "e2", "e4", pause=0)
        ck.check("pendule : moteur retenu", wait(page, "window.__heldUci.length > 0"))
        tap_move(page, "g1", "f3", pause=0)
        before_ms = page.evaluate("JSON.parse(localStorage.getItem('chess-local-play-game')).clocks.w")
        page.evaluate("() => { for (const h of window.__heldUci) h[1] = 'bestmove e7e5'; window.__releaseUci(); window.__heldUci = [] }")
        page.clock.run_for(900)
        page.evaluate("window.__heldUci = []")
        after = page.evaluate("JSON.parse(localStorage.getItem('chess-local-play-game'))")
        ck.check("pendule : prémouvement exécuté", after["sans"] == ["e4", "e5", "Nf3"])
        ck.check("pendule : débit de 0,1 seconde", before_ms - after["clocks"]["w"] == 100, str(after["clocks"]))
        ctx.close()

    if os.environ.get("PREMOVE_CASE", "puzzle") == "puzzle":
        # Puzzle : temps figé pendant la réponse scriptée, même geste que contre le bot.
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
        puzzle = [["PRE", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "e7e5 g1f3 b8c6 f1c4", 800, "opening"]]
        ctx.route("**/puzzles.json", lambda route: route.fulfill(content_type="application/json", body=json.dumps(puzzle)))
        page = ctx.new_page()
        now = datetime.now(timezone.utc)
        page.clock.install(time=now)
        page.clock.pause_at(now + timedelta(seconds=1))
        page.goto(f"{BASE}/#/puzzles")
        # Puzzles est une page paresseuse : React dévoile le contenu suspendu sur une minuterie,
        # que l'horloge figée retient. Avancer par petits pas jusqu'à l'échiquier, sans déborder
        # sur le délai de l'amorce (1 s, mesuré ensuite).
        for _ in range(100):
            if page.locator("[data-square=g1]").count():
                break
            page.clock.run_for(50)
            page.wait_for_timeout(50)
        ck.appears("puzzle chargé", page, "[data-square=g1]")
        page.clock.run_for(1000)
        page.wait_for_timeout(50)
        page.clock.run_for(200)
        ck.check("puzzle : amorce effectuée", piece_on(page, "e5") == "bP")
        tap_square(page, "g1")
        page.clock.run_for(1)
        tap_square(page, "f3")
        page.clock.run_for(150)
        ck.check("puzzle : premier coup joueur effectué", piece_on(page, "f3") == "wN")
        tap_move(page, "f1", "c4", pause=0)
        ck.check("puzzle : aucun prémouvement rouge", not red(page, "f1") and not red(page, "c4"))
        page.clock.run_for(600)
        page.wait_for_timeout(50)
        page.clock.run_for(200)
        ck.check("puzzle : réponse adverse effectuée", piece_on(page, "c6") == "bN")
        ck.check("puzzle : aucun coup automatique", piece_on(page, "f1") == "wB" and piece_on(page, "c4") is None)
        ctx.close()
    browser.close()


ck.run(suite)
