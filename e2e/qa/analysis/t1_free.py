"""Passe 1 : analyse libre mobile standalone (393x852)."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *


def board_y(page):
    return page.locator(".boardbox").first.bounding_box()


def heval(page):
    return page.evaluate("""() => {
      const bar = document.querySelector('main .bg-neutral-800')
      if (!bar) return null
      const fill = bar.querySelector('div')
      return {label: bar.innerText.trim(), fillPct: fill ? fill.style.width : null}
    }""")


def lines_text(page):
    return page.evaluate("""() => [...document.querySelectorAll('main p.truncate')].map(p => p.innerText)""")


def strip(page):
    return page.evaluate("""() => [...document.querySelectorAll('main [data-current]')].filter(e => e.offsetParent).map(e => e.innerText + (e.dataset.current === 'true' ? '*' : ''))""")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2500)
    print("overflow_x", overflow_x(page), "scroll", scroll_state(page))
    print("board", board_y(page))
    print("heval start", heval(page), lines_text(page))
    shot(page, "t1_00_start")

    tap_move(page, "e2", "e4"); page.wait_for_timeout(300)
    print("after tap e4:", piece_on(page, "e4"), strip(page))
    drag_piece(page, "e7", "e5"); page.wait_for_timeout(300)
    print("after drag e5:", piece_on(page, "e5"), strip(page))
    tap_move(page, "g1", "f3")
    drag_piece(page, "b8", "c6")
    tap_move(page, "f1", "b5")
    page.wait_for_timeout(2500)
    print("strip", strip(page))
    print("opening banner:", page.locator("main .truncate.rounded.bg-surface-2").first.inner_text())
    print("heval", heval(page), lines_text(page))
    shot(page, "t1_01_ruy")

    # Trait aux noirs, blanc nettement mieux : la barre doit rester côté blanc.
    # Précédent x2 puis nouvelle variante
    page.locator("main button", has_text="Précédent").click(); page.wait_for_timeout(200)
    page.locator("main button", has_text="Précédent").click(); page.wait_for_timeout(1500)
    print("after 2x prev", strip(page))
    shot(page, "t1_02_prev2")
    # joue un autre coup (variante) : 3.Bc4 au lieu de ...Nc6/Bb5 ? On est après 2.Nf3 (trait noir). Jouons ...Nf6
    tap_move(page, "g8", "f6"); page.wait_for_timeout(800)
    print("after variation Nf6:", strip(page))
    shot(page, "t1_03_variation")

    # Moteur off : saut de layout ?
    b0 = board_y(page)
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(400)
    shot(page, "t1_04_options")
    print("options sheet scroll state", scroll_state(page))
    page.locator("button", has_text="Moteur").click(); page.wait_for_timeout(300)
    shot(page, "t1_05_options_engine_off")
    page.locator("button", has_text="Fermer").click(); page.wait_for_timeout(500)
    b1 = board_y(page)
    print("board y engine on:", b0["y"], "off:", b1["y"], "delta", b1["y"] - b0["y"])
    print("heval engine off", heval(page))
    shot(page, "t1_06_engine_off")
    # rallume
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Moteur").click(); page.wait_for_timeout(200)
    # tap extérieur pour fermer
    page.touchscreen.tap(196, 60); page.wait_for_timeout(400)
    print("options closed by outside tap:", page.locator("text=Copier le PGN").count() == 0)
    page.wait_for_timeout(1500)

    # Flip
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Retourner").click(); page.wait_for_timeout(1200)
    print("flipped heval", heval(page), lines_text(page))
    shot(page, "t1_07_flipped")

    # Explorer
    page.locator("main button", has_text="Explorer").click(); page.wait_for_timeout(500)
    shot(page, "t1_08_explorer")
    print("explorer text:", page.locator("text=Explorer d'ouvertures").first.locator("xpath=..").inner_text()[:600])
    print("scroll after explorer open", scroll_state(page))
    exp_btns = page.locator("main div:has(> p:text-is(\"Explorer d'ouvertures\")) button")
    n = exp_btns.count(); print("explorer buttons", n)
    if n:
        first = exp_btns.first.inner_text(); print("tap", first)
        before = strip(page)
        exp_btns.first.click(); page.wait_for_timeout(600)
        print("strip before", before, "after", strip(page))
    shot(page, "t1_09_explorer_played")
    print("LOGS", logs)
    browser.close()
