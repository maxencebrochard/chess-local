"""T07 : Puzzle Rush 3 min (horloge pilotée par page.clock) et 5 min."""
import re
import time
from pz import *


def clock_text(page):
    loc = page.locator("main .font-mono")
    return loc.first.inner_text() if loc.count() else None


def clock_classes(page):
    return page.locator("main .font-mono").first.get_attribute("class")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.clock.install()
    page.goto(f"{BASE}/#/rush")
    page.wait_for_function("() => document.querySelectorAll('main button').length >= 3 && ![...document.querySelectorAll('main button')].some(b => b.disabled)", timeout=30000)
    page.locator("main button", has_text="3 minutes").tap()
    t0 = time.time()
    samples = []
    while time.time() - t0 < 2.3:
        samples.append((round(time.time() - t0, 2), clock_text(page)))
        page.wait_for_timeout(100)
    chg = [s for i, s in enumerate(samples) if i == 0 or s[1] != samples[i - 1][1]]
    print("horloge au démarrage (changements):", chg)
    pz = wait_puzzle(page)
    print("1er puzzle:", pz["id"], pz["rating"])
    solve(page, pz); prev = pz["id"]
    pz = wait_puzzle(page, not_id=prev); solve(page, pz); prev = pz["id"]
    pz = wait_puzzle(page, not_id=prev); assert wait_placement(page, pz, 1)
    w = wrong_move(pz, 1); tap_move(page, w[:2], w[2:4]); page.wait_for_timeout(600)
    print("après 2 réussis + 1 raté : horloge", clock_text(page), "| texte:", page.locator("main").inner_text().replace("\n", " ")[-40:])
    shot(page, "t07_3min_running")
    boxes = page.evaluate("""() => [...document.querySelectorAll('main .boardbox ~ div > *')].map(e => { const r = e.getBoundingClientRect(); return [e.innerText.replace(/\\n/g,' '), Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] })""")
    print("bandeau infos (texte, x, y, w, h):", boxes)

    # Simulation d'une suspension de l'app (iOS en arrière-plan) : 60 s d'un coup.
    before = clock_text(page)
    page.clock.fast_forward(60_000)
    page.wait_for_timeout(300)
    print(f"suspension simulée de 60 s (fast_forward) : horloge {before} -> {clock_text(page)}")

    # Avance jusqu'à ~0:31 puis ~0:29
    def secs():
        m = re.match(r"(\d+):(\d+)", clock_text(page)); return int(m.group(1)) * 60 + int(m.group(2))
    page.clock.run_for((secs() - 31) * 1000); page.wait_for_timeout(200)
    print("à", clock_text(page), "classes rouges ?", "bg-red" in clock_classes(page))
    page.clock.run_for(2000); page.wait_for_timeout(200)
    print("à", clock_text(page), "classes rouges ?", "bg-red" in clock_classes(page))
    shot(page, "t07_3min_red")
    page.clock.run_for((secs() - 3) * 1000); page.wait_for_timeout(200)
    print("proche de la fin:", clock_text(page))
    # Laisse le temps réel finir, en échantillonnant l'affichage
    t0 = time.time(); seen = []
    while time.time() - t0 < 6:
        txt = clock_text(page)
        state = "done" if page.locator("main button", has_text="Rejouer").count() else "running"
        if not seen or seen[-1][1:] != (txt, state):
            seen.append((round(time.time() - t0, 1), txt, state))
        page.wait_for_timeout(100)
    print("fin du temps (t, horloge, état):", seen)
    print("écran fin:", page.locator("main").inner_text().replace("\n", " | "))
    shot(page, "t07_3min_done")
    print("DB:", [(s["mode"], s["score"]) for s in db_dump(page)["rushScores"]])
    page.locator("main button", has_text="Menu").tap(); page.wait_for_timeout(300)
    print("menu:", page.locator("main").inner_text().replace("\n", " | ")[-110:])

    # 5 minutes
    page.locator("main button", has_text="5 minutes").tap(); page.wait_for_timeout(600)
    print("5 min : horloge", clock_text(page))
    x = page.locator("main button", has_text="✕").bounding_box()
    print("bouton ✕ :", x)
    page.locator("main button", has_text="✕").tap(); page.wait_for_timeout(500)
    print("après ✕ (aucune confirmation ?) :", page.locator("main").inner_text().replace("\n", " | ")[:90])
    print("LOGS:", set(l[:140] for l in logs))
    browser.close()
