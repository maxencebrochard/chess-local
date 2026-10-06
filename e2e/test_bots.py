"""E2E bots calibrés : fautes humaines crédibles pour les bots faibles, bots forts inchangés.

Usage : npm run test:e2e -- --suite bots

Deux volets :
- coups : `e2e/bots_moves.mjs` fait jouer la vraie logique de `src/lib/bots.ts` sur le vrai
  Stockfish WASM de l'app (Node) dans des positions fixes. Un coup qui s'impose (mat en 1, dame
  gratuite, parade d'un mat avec ou sans prise, reprise de dame sans la laisser) a une probabilité nulle d'être
  raté (loi exacte du tirage) ; en position calme, la perte espérée décroît strictement de Noa
  à Nina ; les bots bridés (Iris et au-delà) gardent options et movetime.
- page Jouer (Illimité) : avec `?debug-uci`, le trafic UCI réel d'une partie contre chaque bot
  faible (profondeur fixe, pleine force, MultiPV) et contre Iris (UCI_Elo 1600, movetime 350).
La calibration Elo elle-même (centaines de parties) est hors suite : `scripts/bench-bots.mjs`.
"""
import json
import os
import re
import subprocess

from helpers import BASE, Checker, mobile_context, shot, tap_move

ck = Checker("bots")
check = ck.check
E2E = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E)

WEAK = ["noa", "marty", "lea", "nina"]
# Bots bridés : réglages d'avant (eb0b22d), qui ne doivent pas bouger.
STRONG = {
    "iris": ({"UCI_LimitStrength": True, "UCI_Elo": 1600}, 350),
    "viktor": ({"UCI_LimitStrength": True, "UCI_Elo": 1900}, 400),
    "sofia": ({"UCI_LimitStrength": True, "UCI_Elo": 2200}, 500),
    "arun": ({"UCI_LimitStrength": True, "UCI_Elo": 2500}, 700),
    "maximus": ({"UCI_LimitStrength": False}, 1000),
}


def moves_part():
    r = subprocess.run(["node", os.path.join(E2E, "bots_moves.mjs")], cwd=ROOT, capture_output=True, text=True, timeout=600)
    if not check("[coups] harnais Node", r.returncode == 0, r.stderr[-400:]):
        return
    data = json.loads(r.stdout)

    for s in data["strong"]:
        options, movetime = STRONG[s["id"]]
        calls = s["calls"]
        check(f"[fort] {s['id']} : options UCI inchangées", calls[:1] == [["setOptions", options]], f"({calls[:1]})")
        check(f"[fort] {s['id']} : movetime {movetime}, MultiPV 1",
              calls[1:] == [["search", {"fen": calls[1][1]["fen"] if len(calls) > 1 else "", "movetimeMs": movetime, "multipv": 1}]],
              f"({calls[1:]})")
        check(f"[fort] {s['id']} : budget de pendule (movetimeMs) respecté", (s["budget"] or {}).get("movetimeMs") == 120,
              f"({s['budget']})")

    weak = {w["id"]: w for w in data["weak"]}
    for bot in WEAK:
        for pos, row in weak[bot]["forced"].items():
            check(f"[s'impose] {bot} / {pos} : probabilité de rater = 0", row["pBad"] < 1e-9, f"({row['bad'][:4]})")
            check(f"[s'impose] {bot} / {pos} : coups réels joués", not row["badSampled"], f"(raté : {row['badSampled'][:4]})")

    def mean(bot, key):
        q = weak[bot]["quiet"].values()
        return sum(x[key] for x in q) / len(q)

    losses = [round(mean(b, "expectedLoss")) for b in WEAK]
    print(f"  perte espérée en position calme (cp) : {dict(zip(WEAK, losses))}")
    check("[calme] perte espérée strictement décroissante Noa > Marty > Léa > Nina",
          all(a > b for a, b in zip(losses, losses[1:])), f"({losses})")
    cands = {b: round(mean(b, "candidates"), 1) for b in WEAK}
    print(f"  nombre effectif de candidats, exp(entropie), par position : {cands}")
    check("[calme] Noa hésite entre au moins 3 coups par position", cands["noa"] >= 3, f"({cands['noa']})")
    check("[calme] Noa hésite plus que Nina", cands["noa"] > cands["nina"], f"({cands})")
    p_best = {b: round(mean(b, "pBest"), 2) for b in WEAK}
    print(f"  probabilité du meilleur coup : {p_best}")
    check("[calme] Nina trouve le meilleur coup plus souvent que Noa", p_best["nina"] > p_best["noa"], f"({p_best})")
    worst = {b: round(max(x["pBlunder"] for x in weak[b]["quiet"].values()), 3) for b in WEAK}
    print(f"  pire probabilité de lâcher 3 pions en position calme : {worst}")
    check("[calme] Nina ne lâche pas de pièce en position calme (p < 5 %)", worst["nina"] < 0.05, f"({worst['nina']})")


def uci_traffic(p, browser, bot_name, label):
    """Partie réelle contre `bot_name` avec ?debug-uci : renvoie les commandes UCI envoyées."""
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    sent = []
    page.on("console", lambda m: sent.append(m.text[len("[uci>] "):]) if m.text.startswith("[uci>] ") else None)
    page.goto(f"{BASE}/?debug-uci#/jouer")
    ck.appears(f"[{label}] page Jouer", page, "main button:has-text('Noa')")
    page.locator("main button", has_text=bot_name).first.click()
    page.locator("main button", has_text="Blancs").first.click()
    page.locator("main button", has_text="Illimité").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(800)
    tap_move(page, "e2", "e4")
    replied = True
    try:
        page.wait_for_function("() => document.querySelectorAll('main [data-current]').length >= 2", timeout=20000)
    except Exception:
        replied = False
    check(f"[{label}] {bot_name} répond à 1.e4", replied, f"({page.locator('main [data-current]').count()} demi-coups)")
    shot(page, f"bots_{label}")
    ctx.close()
    return sent


def page_part(p):
    browser = p.chromium.launch(headless=True)
    try:
        for name in ["Noa", "Marty", "Léa", "Nina"]:
            label = name.lower().replace("é", "e")
            sent = uci_traffic(p, browser, name, label)
            cmds = [c for c in sent if c.startswith(("setoption", "go"))]
            check(f"[{label}] moteur pleine force (UCI_LimitStrength false)", "setoption name UCI_LimitStrength value false" in sent, f"({cmds[:6]})")
            check(f"[{label}] jamais de UCI_Elo", not any("UCI_Elo" in c for c in sent), f"({cmds[:6]})")
            check(f"[{label}] recherche à profondeur fixe (go depth)", any(re.fullmatch(r"go depth \d+", c) for c in sent), f"({cmds[:6]})")
            check(f"[{label}] plusieurs candidats (MultiPV > 1)",
                  any(re.fullmatch(r"setoption name MultiPV value \d+", c) and int(c.split()[-1]) > 1 for c in sent), f"({cmds[:6]})")
            check(f"[{label}] aucun go movetime", not any(c.startswith("go movetime") for c in sent), f"({cmds[:6]})")

        sent = uci_traffic(p, browser, "Iris", "iris")
        cmds = [c for c in sent if c.startswith(("setoption", "go"))]
        check("[iris] UCI_LimitStrength true + UCI_Elo 1600",
              "setoption name UCI_LimitStrength value true" in sent and "setoption name UCI_Elo value 1600" in sent, f"({cmds[:6]})")
        check("[iris] go movetime 350, MultiPV 1, jamais go depth",
              "go movetime 350" in sent and "setoption name MultiPV value 1" in sent and not any(c.startswith("go depth") for c in sent),
              f"({cmds[:6]})")
    finally:
        browser.close()


def suite(p):
    moves_part()
    page_part(p)


ck.run(suite)
