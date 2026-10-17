"""Régression : panneau Oui/Non entièrement visible en navigateur mobile court."""
import json
import os

import test_visualisation as v
from helpers import BASE, SHOTS, mobile_context, shot


def suite(p):
    bank = v.read_bank()
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, v.ck, standalone=False, service_workers="block")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/visualisation")
    page.get_by_role("button", name="Commencer", exact=True).click()
    found = False
    for _ in range(40):
        page.locator('[data-phase="question"]').wait_for()
        it, kind, target, o = v.current(page, bank)
        if kind == "mate":
            found = True
            page.evaluate("() => document.fonts.ready")
            v.board_settled(page, page.evaluate(v.BOARD_JS))
            page.wait_for_timeout(1000)
            geo = page.evaluate("""() => {
              const q = document.querySelector('[data-question]').getBoundingClientRect();
              const main = document.querySelector('main').getBoundingClientRect();
              return {questionBottom: q.bottom, mainBottom: main.bottom,
                      viewport: {width: innerWidth, height: innerHeight}};
            }""")
            shot(page, "visualisation_mate_small_stable")
            with open(os.path.join(SHOTS, "visualisation-small-layout.json"), "w") as f:
                json.dump({"item": it["id"], **geo}, f, indent=2)
            v.check("[393x660] panneau mat visible après stabilisation",
                    geo["questionBottom"] <= geo["mainBottom"], str(geo))
            break
        v.give_answer(page, kind, target, o, True)
        page.locator('[data-phase="reveal"][data-verdict="ok"]').wait_for()
        page.get_by_role("button", name="Suivant", exact=True).click()
    v.check("[393x660] question mat exercée", found)
    ctx.close()
    browser.close()


if __name__ == "__main__":
    v.ck.run(suite)
