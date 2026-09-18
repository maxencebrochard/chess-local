"""Passe 1b : moteur OFF stoppe-t-il vraiment Stockfish ? Mat annoncé, signe de l'éval trait noir."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *


def heval(page):
    return page.evaluate("""() => {
      const bar = document.querySelector('main .bg-neutral-800')
      if (!bar) return null
      const fill = bar.querySelector('div')
      return {label: bar.innerText.trim(), fillPct: fill ? fill.style.width : null}
    }""")


def lines_text(page):
    return page.evaluate("""() => [...document.querySelectorAll('main p.truncate')].map(p => p.innerText)""")


def load_text(page, text):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(400)


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    uci = []
    page.on("console", lambda m: uci.append(m.text) if m.text.startswith("[uci") else None)
    page.goto(f"{BASE}/?debug-uci#/analyse"); page.wait_for_timeout(2500)
    tap_move(page, "e2", "e4"); page.wait_for_timeout(1500)
    n_before = len(uci)
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Moteur").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Fermer").click(); page.wait_for_timeout(300)
    h = []
    for _ in range(6):
        h.append(heval(page)["label"]); page.wait_for_timeout(700)
    print("UCI après OFF:", uci[n_before:])
    print("heval labels engine OFF sur 4 s:", h)
    # le moteur tourne-t-il encore ? on compte les messages info via un hook worker impossible ; on regarde la profondeur desktop non dispo.
    shot(page, "t1b_engine_off_bar")
    # on rallume
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Moteur").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Fermer").click(); page.wait_for_timeout(300)

    # Mat du lion : 1.f3 e5 2.g4 -> trait noir, M1 pour les noirs
    load_text(page, "1. f3 e5 2. g4")
    page.wait_for_timeout(2500)
    print("noirs matent en 1:", heval(page), lines_text(page))
    shot(page, "t1b_black_m1")
    tap_move(page, "d8", "h4"); page.wait_for_timeout(1200)
    print("après Qh4#:", heval(page), lines_text(page))
    shot(page, "t1b_mated")

    load_text(page, "1. e4 e5 2. Qh5 Ke7")
    page.wait_for_timeout(2500)
    print("blancs matent en 1:", heval(page), lines_text(page))
    shot(page, "t1b_white_m1")

    # FEN trait noir, blanc écrasant
    load_text(page, "4k3/8/8/8/8/8/8/QQ2K3 b - - 0 1")
    page.wait_for_timeout(3000)
    print("FEN trait noir blanc gagnant:", heval(page), lines_text(page))
    shot(page, "t1b_fen_black_to_move")
    # FEN trait noir, noir +dame
    load_text(page, "3qk3/8/8/8/8/8/8/4K3 b - - 0 1")
    page.wait_for_timeout(3000)
    print("FEN trait noir noir gagnant:", heval(page), lines_text(page))
    shot(page, "t1b_fen_black_winning")
    print("LOGS", logs)
    browser.close()
