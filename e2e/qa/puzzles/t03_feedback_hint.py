"""T03 : surlignage du dernier coup (tap vs drag), durée du message « Trouvé ! », indice (progressif ? pénalité ?)."""
import time
from pz import *

SQ_BG_JS = """(sq) => {
  const el = document.querySelector(`[data-square='${sq}']`);
  return [...el.querySelectorAll('*')].filter(n => n.style && (n.style.background || n.style.backgroundColor || n.style.backgroundImage)).map(n => ({ inline: n.style.cssText.slice(0, 160), bg: getComputedStyle(n).backgroundColor, img: getComputedStyle(n).backgroundImage.slice(0, 50) }));
}"""


def yellow_squares(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-square]')].filter(e =>
            [e, ...e.querySelectorAll('*')].some(n => getComputedStyle(n).backgroundColor.includes('255, 255, 51'))
        ).map(e => e.getAttribute('data-square'))"""
    )


def skip_until(page, cond, max_skips=60):
    pz = wait_puzzle(page)
    n = 0
    while not cond(pz) and n < max_skips:
        page.locator("main button", has_text="Passer").tap()
        pz = wait_puzzle(page, not_id=pz["id"])
        n += 1
    return pz


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)

    # ---- 1. Surlignage dernier coup : tap-tap ----
    pz = skip_until(page, lambda z: len(z["moves"]) >= 4)
    wait_placement(page, pz, 1)
    print("puzzle", pz["id"], pz["moves"])
    print("jaunes après amorce:", yellow_squares(page), "attendu:", [pz["moves"][0][:2], pz["moves"][0][2:4]])
    m = pz["moves"][1]
    tap_square(page, m[:2]); page.wait_for_timeout(250)
    print("TAP sélection -> style case destination:", page.evaluate(SQ_BG_JS, m[2:4]))
    tap_square(page, m[2:4])
    # Sonde « Trouvé ! » et position des boutons toutes les 25 ms pendant 900 ms
    t0 = time.time(); seen = []
    ys = set()
    while time.time() - t0 < 0.9:
        r = page.evaluate("""() => ({ t: document.querySelector('main').innerText.includes('Trouvé'),
             y: Math.round([...document.querySelectorAll('main button')].find(b => b.innerText.includes('Indice'))?.getBoundingClientRect().y ?? -1) })""")
        seen.append((round(time.time() - t0, 3), r["t"], r["y"]))
        ys.add(r["y"])
        if r["t"] and not any(n == "shot" for n in ys if isinstance(n, str)):
            shot(page, "t03_trouve_flash"); ys.add("shot")
    vis = [s for s in seen if s[1]]
    print("« Trouvé ! » visible de", vis[0][0] if vis else None, "à", vis[-1][0] if vis else None, "s ; y du bouton Indice:", sorted(y for y in ys if isinstance(y, int)))
    assert wait_placement(page, pz, 3)
    # après la réponse adverse, on rejoue au tap et on regarde le surlignage AVANT la fin
    m3 = pz["moves"][3]
    tap_move(page, m3[:2], m3[2:4])
    page.wait_for_timeout(500)
    print("TAP fin -> jaunes:", yellow_squares(page), "attendu:", [m3[:2], m3[2:4]])
    print("TAP style destination:", page.evaluate(SQ_BG_JS, m3[2:4]))
    shot(page, "t03_tap_lastmove")

    # ---- 2. même chose au drag ----
    page.locator("main button", has_text="Suivant").tap()
    pz2 = wait_puzzle(page, not_id=pz["id"])
    pz2 = skip_until(page, lambda z: len(z["moves"]) == 2 and "mateIn1" not in z["themes"])
    wait_placement(page, pz2, 1)
    m = pz2["moves"][1]
    drag_piece(page, m[:2], m[2:4])
    page.wait_for_timeout(500)
    print("DRAG fin -> jaunes:", yellow_squares(page), "attendu:", [m[:2], m[2:4]])
    shot(page, "t03_drag_lastmove")

    # ---- 3. Indice ----
    page.locator("main button", has_text="Suivant").tap()
    pz3 = wait_puzzle(page, not_id=pz2["id"])
    pz3 = skip_until(page, lambda z: len(z["moves"]) >= 4)
    wait_placement(page, pz3, 1)
    r0 = rating_shown(page)
    print("HINT puzzle", pz3["id"], pz3["moves"], "rating", r0)
    page.locator("main button", has_text="Indice").tap(); page.wait_for_timeout(300)
    print("HINT 1er tap -> jaunes:", yellow_squares(page), "(case de départ attendue:", pz3["moves"][1][:2], ")")
    shot(page, "t03_hint1")
    page.locator("main button", has_text="Indice").tap(); page.wait_for_timeout(300)
    print("HINT 2e tap -> jaunes:", yellow_squares(page), "(destination:", pz3["moves"][1][2:4], ")")
    page.locator("main button", has_text="Indice").tap(); page.wait_for_timeout(300)
    print("HINT 3e tap -> jaunes:", yellow_squares(page))
    shot(page, "t03_hint3")
    # résout avec indice à chaque coup
    play_uci(page, pz3["moves"][1])
    assert wait_placement(page, pz3, 3)
    page.locator("main button", has_text="Indice").tap(); page.wait_for_timeout(300)
    print("HINT coup 2 -> jaunes:", yellow_squares(page), "(attendu:", pz3["moves"][3][:2], ")")
    solve_rest = pz3["moves"][3:]
    i = 3
    while i < len(pz3["moves"]):
        play_uci(page, pz3["moves"][i])
        if i + 1 < len(pz3["moves"]):
            assert wait_placement(page, pz3, i + 2)
            page.locator("main button", has_text="Indice").tap(); page.wait_for_timeout(200)
        i += 2
    page.wait_for_timeout(500)
    print("HINT résolu avec indices -> rating:", r0, "->", rating_shown(page))
    shot(page, "t03_hint_solved")

    # ---- 4. Indice pendant les 500 ms avant le coup d'amorce ----
    page.locator("main button", has_text="Suivant").tap()
    pz4 = wait_puzzle(page, not_id=pz3["id"])
    page.locator("main button", has_text="Indice").tap()
    page.wait_for_timeout(80)
    print("HINT avant amorce -> jaunes:", yellow_squares(page), "amorce:", pz4["moves"][0], "solution:", pz4["moves"][1],
          "placement == fen initiale ?", board_placement(page) == expected_placement(pz4, 0))
    shot(page, "t03_hint_before_setup")
    print("LOGS:", logs)
    browser.close()
