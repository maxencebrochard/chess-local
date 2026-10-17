"""Épuise les positions avec mat via la vraie UI, aux quatre longueurs."""
import json
import os

import test_visualisation as v
from helpers import BASE, SHOTS, shot, mobile_context


def suite(p):
    bank = v.read_bank()
    browser = p.chromium.launch(headless=True)
    evidence = []
    for level, items in bank["levels"].items():
        oracles = {it["id"]: v.oracle(it) for it in items}
        yes_ids = {key for key, o in oracles.items() if o["mates"]}
        ctx = mobile_context(p, browser, v.ck, standalone=True, service_workers="block")
        page = ctx.new_page()
        page.goto(f"{BASE}/#/visualisation")
        page.locator(f'[data-level="{level}"]').click()
        page.get_by_role("button", name="Commencer", exact=True).click()
        page.locator('[data-phase="question"]').wait_for()
        used = set()
        seen_yes = set()
        # Première question libre, puis Oui jusque-delà de l'épuisement, enfin Non.
        # Seul l'aléa est contrôlé, pas la sélection ni les réponses du produit.
        for step in range(len(yes_ids) + 3):
            it, kind, target, o = v.current(page, bank)
            if step == 0 and o["mates"]:
                seen_yes.add(it["id"])
            if step:
                want_yes = step <= len(yes_ids) + 1
                v.check(f"[{level}] tirage {step} conserve {want_yes=}",
                        kind == "mate" and bool(o["mates"]) == want_yes)
                if want_yes:
                    if step == len(yes_ids) + 1:
                        v.check(f"[{level}] mat réutilisé après épuisement",
                                seen_yes == yes_ids and it["id"] in seen_yes)
                        shot(page, f"visualisation_exhausted_{level}")
                    seen_yes.add(it["id"])
            evidence.append({"level": level, "step": step, "id": it["id"], "kind": kind,
                             "mate": bool(o["mates"]), "used": len(used)})
            v.give_answer(page, kind, target, o, True)
            page.locator('[data-phase="reveal"][data-verdict="ok"]').wait_for()
            if step == len(yes_ids) + 2:
                break
            used.add(it["id"])
            size = len(items) - len(used) or len(items)
            want_yes = step < len(yes_ids) + 1
            page.evaluate("""({size, yes}) => {
              const next = [...document.querySelectorAll('button')].find(b => b.textContent === 'Suivant');
              next.addEventListener('click', () => {
              const native = Math.random;
              let call = 0;
              Math.random = () => {
                const n = call++;
                if (n === size + 2) { Math.random = native; return yes ? .25 : .75; }
                return n === size - 1 ? 0 : .999;
              };
              }, {capture: true, once: true});
            }""", {"size": size, "yes": want_yes})
            page.get_by_role("button", name="Suivant", exact=True).click()
            page.locator('[data-phase="question"]').wait_for()
        page.get_by_role("button", name="Arrêter la série").first.click()
        page.locator('[data-run-over]').wait_for()
        shot(page, f"visualisation_long_series_{level}")
        ctx.close()
    browser.close()
    with open(os.path.join(SHOTS, "visualisation-boundary-rounds.json"), "w") as f:
        json.dump(evidence, f, indent=2)


if __name__ == "__main__":
    v.ck.run(suite)
