"""Ressenti du plateau partagé : géométrie pendant un geste CDP et audio à la pose."""

from helpers import (
    BASE,
    WEBKIT_AUDIO,
    Checker,
    desktop_context,
    mobile_context,
    drag_piece,
    piece_on,
    shot,
    sound_log,
    tap_move,
)

ck = Checker("feeling")


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
            ctx.add_init_script(WEBKIT_AUDIO)
            ctx.add_init_script(
                "window.__release = 0; addEventListener('pointerup', () => window.__release = performance.now(), true)"
            )
            page = ctx.new_page()
            page.goto(f"{BASE}/#/analyse")
            if not ck.appears(
                f"{label} : plateau", page, "[data-square=e2] [data-piece]"
            ):
                ctx.close()
                continue
            page.locator("[data-square=a3]").click()
            page.wait_for_timeout(700)
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
            entries = [e for e in sound_log(page)[start:] if e["name"] != "(muet)"]
            release = page.evaluate("window.__release")
            ck.check(
                f"{label} : un seul bon son audible à moins de 80 ms",
                len(entries) == 1
                and entries[0]["name"] == "move-self"
                and entries[0]["audible"]
                and 0 <= entries[0]["at"] - release < 80,
                str(entries),
            )
            if not desktop:
                start = len(sound_log(page))

                def after_release():
                    active = page.locator("[data-square=e7] [data-piece]").evaluate(
                        '(e) => e.getAnimations({subtree: true}).some(a => a.playState === "running")'
                    )
                    ck.check("illégal : retour animé", active)

                drag_piece(page, "e7", "e4", after_release=after_release)
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
                entries = [e for e in sound_log(page)[start:] if e["name"] != "(muet)"]
                ck.check(
                    "clic-clic : son adverse unique à la pose",
                    len(entries) == 1
                    and entries[0]["name"] == "move-opponent"
                    and entries[0]["audible"]
                    and 0 <= entries[0]["at"] - page.evaluate("window.__release") < 80,
                )
                special_moves(page)
            ctx.close()
    finally:
        browser.close()


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
        entries = [e for e in sound_log(page)[start:] if e["name"] != "(muet)"]
        release = page.evaluate("window.__release")
        ck.check(
            f"{name} : bon son unique et immédiat",
            len(entries) == 1
            and entries[0]["name"] == name
            and entries[0]["audible"]
            and 0 <= entries[0]["at"] - release < 80,
            str(entries),
        )


ck.run(suite)
