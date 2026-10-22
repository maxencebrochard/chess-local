"""Ressenti du plateau partagé : géométrie pendant un geste CDP et audio à la pose."""

import json
import os

from helpers import (
    BASE,
    WEBKIT_AUDIO,
    Checker,
    desktop_context,
    mobile_context,
    drag_piece,
    immediate_sound,
    piece_on,
    shot,
    sound_log,
    tap_move,
    wait_sounds_ready,
)

ck = Checker("feeling")

# Journal des animations Web Animations lancées sur une pièce de l'échiquier (case, keyframes).
ANIM_SPY = """(() => {
  window.__animations = []
  const native = Element.prototype.animate
  Element.prototype.animate = function (keyframes, options) {
    const sq = this.closest && this.closest('[data-square]')
    if (sq && Array.isArray(keyframes)) {
      window.__animations.push({ square: sq.getAttribute('data-square'), from: String(keyframes[0]?.transform ?? ''),
        to: String(keyframes[keyframes.length - 1]?.transform ?? ''), duration: typeof options === 'number' ? options : options?.duration ?? 0 })
    }
    return native.call(this, keyframes, options)
  }
})()"""


def suite(p):
    browser = p.chromium.launch()
    try:
        for desktop in (False, True):
            label = "souris" if desktop else "tactile"
            ctx = (
                desktop_context(browser, ck, settings={"playSounds": True})
                if desktop
                else mobile_context(
                    p, browser, ck, standalone=True, settings={"playSounds": True}
                )
            )
            mutation = os.environ.get("E2E_MUTATION", "")
            audio = WEBKIT_AUDIO
            if mutation in ("sound-task", "sound-scheduled"):
                # Mutation après l'espion : il observe le départ réellement demandé au navigateur.
                audio += """;(() => {
                  const start = AudioBufferSourceNode.prototype.start
                  AudioBufferSourceNode.prototype.start = function (...args) {
                """ + ("setTimeout(() => start.apply(this, args), 100)" if mutation == "sound-task"
                       else "start.call(this, this.context.currentTime + 0.2)") + "}})()"
            ctx.add_init_script(audio)
            animation = ANIM_SPY
            if mutation == "return-disabled":
                # Une animation supprimée doit rester détectée malgré la lecture différée du journal.
                animation += """;(() => {
                  const animate = Element.prototype.animate
                  Element.prototype.animate = function (frames, options) {
                    return animate.call(this, frames, typeof options === 'number' ? 0 : {...options, duration: 0})
                  }
                })()"""
            ctx.add_init_script(animation)
            page = ctx.new_page()
            page.goto(f"{BASE}/#/analyse")
            if not ck.appears(
                f"{label} : plateau", page, "[data-square=e2] [data-piece]"
            ):
                ctx.close()
                continue
            page.locator("[data-square=a3]").click()
            ck.check(f"{label} : sons préchargés au premier geste", wait_sounds_ready(page))
            start = len(sound_log(page))

            def during(x, y):
                geometry = page.evaluate("""() => {
                  const sq = document.querySelector('[data-square=e4]').getBoundingClientRect()
                  const el = [...document.querySelectorAll('[data-piece=wP]')].find(e => !e.closest('[data-square]'))
                  const r = el?.firstElementChild?.getBoundingClientRect()
                  const target = document.querySelector('[data-testid=drag-target]')
                  const t = target?.getBoundingClientRect()
                  return {size: sq.width, piece: r ? {w:r.width,y:r.y,h:r.height} : null,
                    target: t ? {x:t.x+t.width/2,y:t.y+t.height/2,w:t.width} : null,
                    legal: getComputedStyle(document.querySelector('[data-square=e4] > div')).backgroundImage}
                }""")
                ck.check(
                    f"{label} : pièce soulevée",
                    geometry["piece"] is not None
                    and (
                        1.5 < geometry["piece"]["w"] / geometry["size"] < 2
                        if not desktop
                        else 1.15 < geometry["piece"]["w"] / geometry["size"] < 1.25
                    ),
                    str(geometry),
                )
                if not desktop:
                    ck.check(
                        "tactile : pièce au-dessus du doigt",
                        geometry["piece"] is not None
                        and geometry["piece"]["y"] + geometry["piece"]["h"] / 2
                        < y - geometry["size"] * 0.5,
                    )
                    t = geometry["target"]
                    ck.check(
                        "tactile : disque centré sur la case visée",
                        t is not None
                        and abs(t["x"] - x) < 2
                        and abs(t["y"] - y) < 2
                        and 1.8 < t["w"] / geometry["size"] < 2.2,
                    )
                ck.check(
                    f"{label} : destinations légales pendant le geste",
                    "radial-gradient" in geometry["legal"],
                )
                ck.check(
                    f"{label} : pas de coup avant la pose",
                    piece_on(page, "e2") == "wP" and piece_on(page, "e4") is None,
                )
                ck.check(
                    f"{label} : silence pendant le geste",
                    not [e for e in sound_log(page)[start:] if e["name"] != "(muet)"],
                )
                shot(page, f"f14_drag_{label}")

            if desktop:
                a = page.locator("[data-square=e2]").bounding_box()
                b = page.locator("[data-square=e4]").bounding_box()
                page.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
                page.mouse.down()
                page.mouse.move(
                    b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=14
                )
                page.wait_for_timeout(100)
                during(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
                page.mouse.up()
                page.wait_for_timeout(250)
            else:

                def on_step(i, _x, _y):
                    if i == 7:
                        t = (
                            page.locator("[data-testid=drag-target]").bounding_box()
                            if page.locator("[data-testid=drag-target]").count()
                            else None
                        )
                        r = page.locator("[data-square=e3]").bounding_box()
                        x, y = r["x"] + r["width"] / 2, r["y"] + r["height"] / 2
                        ck.check(
                            "tactile : cible intermédiaire e3",
                            t is not None
                            and abs(t["x"] + t["width"] / 2 - x) < 2
                            and abs(t["y"] + t["height"] / 2 - y) < 2,
                        )

                drag_piece(page, "e2", "e4", during=during, on_step=on_step)
            ck.check(
                f"{label} : coup à la pose",
                piece_on(page, "e4") == "wP" and piece_on(page, "e2") is None,
            )
            ok, detail = immediate_sound(sound_log(page)[start:], "move-self")
            ck.check(f"{label} : un seul bon son audible, dans le geste de pose", ok, detail)
            if not desktop:
                start = len(sound_log(page))

                anims = page.evaluate("window.__animations.length")
                drag_piece(page, "e7", "e4")
                # Journal tenu dans la page : lire l'animation en cours après coup ratait ses 120 ms
                # sur une machine chargée (aller-retour CDP plus long que l'animation).
                back = [a for a in page.evaluate("window.__animations")[anims:] if a["square"] == "e7"]
                ck.check(
                    "illégal : retour animé",
                    len(back) == 1 and back[0]["from"].startswith("translate(") and back[0]["to"] == "none" and back[0]["duration"] > 0,
                    str(back),
                )
                ck.check(
                    "illégal : retour à la source et cible intacte",
                    piece_on(page, "e7") == "bP" and piece_on(page, "e4") == "wP",
                )
                returned = page.locator("[data-square=e7] .board-piece").evaluate("""(e) => {
                  const p=e.getBoundingClientRect(), s=e.closest('[data-square]').getBoundingClientRect()
                  return getComputedStyle(e).opacity === '1' && getComputedStyle(e).visibility === 'visible' && Math.abs(p.x-s.x)<1 && Math.abs(p.y-s.y)<1
                }""")
                ck.check("illégal : pièce visible et revenue au repos", returned)
                entries = [e for e in sound_log(page)[start:] if e["name"] != "(muet)"]
                ck.check(
                    "illégal : un seul son de refus",
                    [e["name"] for e in entries] == ["illegal"],
                )
                ck.check(
                    "fin de geste : disque retiré",
                    page.locator("[data-testid=drag-target]").count() == 0,
                )
                start = len(sound_log(page))
                tap_move(page, "e7", "e5")
                ck.check("clic-clic : coup adverse joué", piece_on(page, "e5") == "bP")
                ok, detail = immediate_sound(sound_log(page)[start:], "move-opponent")
                ck.check("clic-clic : son adverse unique, dans le toucher de pose", ok, detail)
                special_moves(page)
            ctx.close()
        puzzle_sound(p, browser)
    finally:
        browser.close()


# Amorce noire, coup calme du joueur, réponse, puis fin : le premier coup du joueur n'est ni
# le dernier (pas de success) ni un échec ou une prise.
QUIET_PUZZLE = ["F14Q", "6k1/5ppp/8/8/8/8/5PPP/R5K1 b - - 0 1", "h7h6 a1a7 g8h7 a7f7", 1000, "endgame"]


def puzzle_sound(p, browser):
    """Hors analyse aussi, le son d'un coup accepté part dans le geste de pose, une seule fois."""
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block", settings={"playSounds": True})
    ctx.add_init_script(WEBKIT_AUDIO)
    body = json.dumps([QUIET_PUZZLE])
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    page.goto(f"{BASE}/#/")
    nav = "nav[aria-label='Navigation principale'] a:visible"
    if not ck.appears("puzzle : navigation", page, nav, timeout=30000):
        ctx.close()
        return
    page.locator(nav, has_text="Puzzles").first.tap()
    ck.check("puzzle : sons préchargés au geste d'arrivée", wait_sounds_ready(page))
    try:
        page.wait_for_function("() => document.querySelector('[data-square=h6] [data-piece=bP]')", timeout=20000)
    except Exception:
        ck.check("puzzle : amorce jouée", False)
        ctx.close()
        return
    page.wait_for_timeout(300)
    start = len(sound_log(page))
    drag_piece(page, "a1", "a7")
    ck.check("puzzle : coup accepté", piece_on(page, "a7") == "wR")
    ok, detail = immediate_sound(sound_log(page)[start:], "move-self")
    ck.check("puzzle : son du coup dans le geste de pose", ok, detail)
    page.wait_for_timeout(800)
    heard = [e["name"] for e in sound_log(page)[start:] if e["name"] != "(muet)"]
    ck.check("puzzle : coup du joueur sonné une fois, puis la réponse", heard == ["move-self", "move-opponent"], str(heard))
    ctx.close()


def special_moves(page):
    for fen, frm, to, name in [
        ("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1", "e4", "d5", "capture"),
        ("4k3/8/8/8/8/8/8/4K2R w K - 0 1", "e1", "g1", "castle"),
        ("4k3/8/8/8/8/8/R7/4K3 w - - 0 1", "a2", "e2", "move-check"),
        ("8/P7/7k/8/8/8/8/4K3 w - - 0 1", "a7", "a8", "promote"),
    ]:
        page.locator("main button:visible", has_text="Options").click()
        page.locator("button:visible", has_text="Importer PGN ou FEN").click()
        page.locator("textarea").fill(fen)
        page.locator("button:visible", has_text="Charger").click()
        page.wait_for_timeout(500)
        start = len(sound_log(page))
        drag_piece(page, frm, to)
        if name == "promote":
            ck.check(
                "promotion : attend le choix sans son",
                not [e for e in sound_log(page)[start:] if e["name"] != "(muet)"],
            )
            if ck.appears(
                "promotion : choix proposé",
                page,
                'button[aria-label="Dame"]',
                timeout=2000,
            ):
                page.get_by_role("button", name="Dame", exact=True).tap()
                page.wait_for_timeout(200)
        ok, detail = immediate_sound(sound_log(page)[start:], name)
        ck.check(f"{name} : bon son unique et immédiat", ok, detail)


ck.run(suite)
