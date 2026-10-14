"""E2E « Diagnostic d'attaque » : « Mes attaques manquées » (fautes des bilans dont le meilleur
coup attaquait le roi, rejouables contre Stockfish) et calque « Compte les attaquants » (zone de
chaque roi, attaquants contre défenseurs, dans l'Analyse et les parties contre le moteur).

Les fautes sont injectées directement dans la table Dexie `mistakes` (aucun bilan à calculer) :
`fenBefore` et `bestUci` suffisent, le type d'attaque est recalculé sur l'échiquier par l'app.
Les comptes du calque sont vérifiés sur des positions connues, à la fois contre des valeurs
attendues fixes (vérifiées à la main) et contre un oracle python-chess aux mêmes définitions.

Usage : npm run test:e2e -- --suite diagnostic_attaque
"""
import json

import chess

from helpers import BASE, SHOTS, Checker, desktop_context, mobile_context, overflow_x, tap_move

ck = Checker("diagnostic_attaque")
check = ck.check

T0 = 1758000000000
A = {"color": "w", "gameKey": "game:1", "gameLabel": "10 min · 0-1 mat", "attempts": 0, "solved": 0}
B = {"color": "w", "gameKey": "game:2", "gameLabel": "illimité · 1/2-1/2 pat", "attempts": 0, "solved": 0}
# Sept fautes : six du joueur (camp connu) sur deux parties, dont cinq où `bestUci` attaque le roi,
# plus deux témoins qui ne doivent apparaître nulle part : Cf3 d'ouverture (faute sans rapport avec
# le roi) et un Fxh7+ sans `color` (PGN collé : on ignore qui a fauté, ce n'est pas « tes » attaques).
MISTAKES = [
    {"id": 1, "date": T0, "cls": "miss", **A,
     "fenBefore": "r1bq1rk1/pp2bppp/2n1p3/3pP3/3P4/2NB1N2/PP3PPP/R2QK2R w KQ - 0 10", "playedSan": "a3", "bestUci": "d3h7"},  # Fxh7+ : sacrifice
    {"id": 2, "date": T0 + 1000, "cls": "mistake", **A,
     "fenBefore": "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6", "playedSan": "O-O", "bestUci": "g5f7"},  # Cxf7 : sacrifice
    {"id": 3, "date": T0 + 2000, "cls": "mistake", **A,
     "fenBefore": "r2q1rk1/pb1n1ppp/1p2pn2/2pp3P/3P4/2PBPN2/PP1N1PP1/R2QK2R w KQ - 0 12", "playedSan": "O-O", "bestUci": "h5h6"},  # h6 : pion contre le roque
    {"id": 4, "date": T0 + 3600_000, "cls": "blunder", **B,
     # Avec le fou c1 derrière, Cg5 ne se perd pas (Dxg5 Fxg5) : c'est une pièce amenée vers le roi, pas un sacrifice.
     "fenBefore": "r1bq1rk1/pp3ppp/2n1p3/3pP3/3P4/2NB1N2/PP3PPP/R1BQK2R w KQ - 0 10", "playedSan": "a3", "bestUci": "f3g5"},  # Cg5 : pièce
    {"id": 5, "date": T0 + 3601_000, "cls": "missedWin", **B,
     "fenBefore": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "playedSan": "Kf1", "bestUci": "a1a8"},  # Ta8# : mat
    {"id": 6, "date": T0 + 3602_000, "cls": "mistake", **B,
     "fenBefore": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "playedSan": "Qh5", "bestUci": "g1f3"},  # témoin : pas une attaque
    {"id": 7, "date": T0 + 7200_000, "cls": "miss", "gameLabel": "Partie analysée", "attempts": 0, "solved": 0,
     "fenBefore": "r1bq1rk1/pp2bppp/2n1p3/3pP3/3P4/2NB1N2/PP3PPP/R2QK2R w KQ - 0 10", "playedSan": "a3", "bestUci": "d3h7"},  # témoin : camp inconnu
    # Quatre témoins des filtres, un par filtre : chacun ressortirait comme attaque si son filtre sautait.
    {"id": 8, "date": T0 + 3603_000, "cls": "mistake", **B,
     "fenBefore": "6k1/5ppp/8/7P/8/8/5PPP/4R1K1 w - - 0 1", "playedSan": "Kf1", "bestUci": "h5h6"},  # finale : une seule pièce, pas une attaque
    {"id": 9, "date": T0 + 3604_000, "cls": "mistake", **B,
     "fenBefore": "r4rk1/pp3p2/8/7P/8/8/PPP2PPP/R2Q1RK1 w - - 0 1", "playedSan": "Kh1", "bestUci": "h5h6"},  # pion passé : promotion, pas tempête
    {"id": 10, "date": T0 + 3605_000, "cls": "blunder", **B,
     "fenBefore": "r3k3/pp3ppp/N7/8/2B5/8/PPPP1PPP/R1BQK2R w KQq - 0 1", "playedSan": "Nb4", "bestUci": "a6c7"},  # Cc7+ fourchette roi et tour : tactique
    {"id": 11, "date": T0 + 3606_000, "cls": "blunder", **B,
     "fenBefore": "3qk3/ppp3pp/8/4b3/2B5/5N2/PPPP1PPP/RNBQK2R w KQ - 0 1", "playedSan": "O-O", "bestUci": "f3e5"},  # Cxe5 gagne un fou : tactique
    # Ligne incomplète (sauvegarde ancienne ou retouchée, sans `playedSan`) : ignorée, la liste reste lisible.
    {"id": 12, "date": T0 + 3607_000, "cls": "blunder", **B,
     "fenBefore": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "bestUci": "a1a8"},
]
EXPECTED_KINDS = {1: "sacrifice", 2: "sacrifice", 3: "poussee", 4: "piece", 5: "mat"}
SUMMARY = "Dans tes fautes relevées sur 2 parties, 5 attaques manquées, surtout des sacrifices près du roi."
# Partie contre un bot passée au bilan par la suite (chemin « Voir » de l'Archive puis bouton Bilan) :
# 5. Cxf7 ?? perd sur Dxg2 ; le bilan doit relever les fautes des Blancs seulement, avec `color` et `gameKey`.
PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"

# Positions du calque : (nom, FEN, attendu {camp du roi: (attaquants, défenseurs)}), vérifiées à la main
# avec la zone de Stockfish (3x3 ramené dans b-g / 2-7) et les seules pièces (C, F, T, D).
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
OVERLAY_FENS = [
    # Chaque roi : dame, deux fous, deux cavaliers visent sa zone d1-f3 (ou d6-f8) ; les tours non.
    ("départ", START, {"w": (0, 5), "b": (0, 5)}),
    # Fd3 et Cg5 visent le roi g8, Dd8 et Tf8 le défendent : égalité 2 contre 2. Côté blanc, le Cg5
    # vise f3 dans la zone de son roi : il compte parmi ses 6 défenseurs.
    ("Cg5", "r1bq1rk1/pp3ppp/2n1p3/3pP1N1/3P4/2NB4/PP3PPP/R2QK2R b KQ - 1 10", {"w": (0, 6), "b": (2, 2)}),
    # Dh5, Cg5, Fd3 contre Dd8 et Tf8 : surnombre, le cadre du roi noir passe au rouge.
    ("surnombre", "r1bq1rk1/pp3pp1/2n1p2p/3pP1NQ/3P4/2NB4/PP3PPP/R3K2R b KQ - 0 1", {"w": (0, 6), "b": (3, 2)}),
    # Rois roqués en finale de tour : la zone remonte d'une rangée (f1-h3, f6-h8), la tour a1 vise f1.
    ("coin", "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", {"w": (0, 1), "b": (0, 0)}),
]


def oracle(fen, side):
    """Mêmes définitions que src/lib/kingAttack.ts : zone = 3x3 centré sur le roi ramené dans les
    colonnes b-g et les rangées 2-7 (anneau du roi de Stockfish) ; attaquants = pièces adverses
    (cavalier, fou, tour, dame) visant une case de la zone ; défenseurs = pièces du camp du roi."""
    b = chess.Board(fen)
    color = chess.WHITE if side == "w" else chess.BLACK
    k = b.king(color)
    f, r = min(6, max(1, chess.square_file(k))), min(6, max(1, chess.square_rank(k)))
    zone = [chess.square(ff, rr) for ff in (f - 1, f, f + 1) for rr in (r - 1, r, r + 1)]
    att, de = set(), set()
    for sq in zone:
        att |= {s for s in b.attackers(not color, sq) if b.piece_type_at(s) not in (chess.KING, chess.PAWN)}
        de |= {s for s in b.attackers(color, sq) if b.piece_type_at(s) not in (chess.KING, chess.PAWN)}
    return len(att), len(de)


def idb(page, script, arg=None):
    """Accès IndexedDB brut à la base Dexie `chess-local`, déjà créée par l'app."""
    return page.evaluate(
        """([body, arg]) => new Promise((resolve, reject) => {
          const req = indexedDB.open('chess-local')
          req.onerror = () => reject(req.error)
          req.onsuccess = () => {
            const db = req.result
            if (!db.objectStoreNames.contains('mistakes')) { db.close(); reject(new Error('base non initialisée')); return }
            new Function('db', 'arg', 'resolve', 'reject', body)(db, arg, (v) => { db.close(); resolve(v) }, reject)
          }
        })""",
        [script, arg],
    )


def seed_mistakes(page):
    idb(page, "const tx = db.transaction('mistakes', 'readwrite'); for (const r of arg) tx.objectStore('mistakes').put(r);"
              "tx.oncomplete = () => resolve(true); tx.onerror = () => reject(tx.error)", MISTAKES)


def learn_sessions(page):
    return idb(page, "const r = db.transaction('learnSessions').objectStore('learnSessions').getAll(); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error)")


def pills(page):
    """Pastilles du calque : {camp: (attaquants, défenseurs, surnombre)}."""
    return {
        p["side"]: (int(p["a"]), int(p["d"]), p["over"] == "1")
        for p in page.evaluate("""() => [...document.querySelectorAll('[data-testid=attack-count]')].map((e) => ({
          side: e.dataset.side, a: e.dataset.attackers, d: e.dataset.defenders, over: e.dataset.over }))""")
    }


def settings_state(page):
    return page.evaluate("() => { try { return JSON.parse(localStorage.getItem('chess-local-settings')).state } catch { return null } }")


def open_analysis(ctx):
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    ck.appears("[calque] analyse ouverte", page, "[data-square='e4']", timeout=30000)
    page.wait_for_timeout(800)
    return page


def load_fen(page, fen):
    page.locator("main button:visible", has_text="Options").click()
    page.locator("button:visible", has_text="Importer PGN ou FEN").click()
    if not ck.appears("[calque] zone d'import ouverte", page, "textarea", timeout=5000):
        return
    page.fill("textarea", fen)
    page.locator("button:visible", has_text="Charger").click()
    page.wait_for_timeout(600)


def attackers_option(page):
    """Bouton de la feuille Options qui porte l'état du calque (feuille laissée ouverte)."""
    page.locator("main button:visible", has_text="Options").click()
    return page.locator("button:visible", has_text="Compter les attaquants")


def wait_idle(page, timeout=20000):
    """Stockfish a répondu et le joueur a le trait."""
    try:
        page.wait_for_selector("[data-testid=position-game][data-thinking='0']", timeout=timeout)
        return True
    except Exception:
        return False


# ---------- Mes attaques manquées ----------

def part_diagnostic(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    if not ck.appears("[apprendre] page chargée", page, "main :text('Apprendre')", timeout=20000):
        ctx.close()
        return
    page.wait_for_timeout(800)
    seed_mistakes(page)
    page.reload()
    page.wait_for_timeout(1500)

    card = page.locator("[data-testid=missed-attacks-card]")
    if ck.appears("[apprendre] carte « Mes attaques manquées »", page, "[data-testid=missed-attacks-card]", timeout=10000):
        check("[apprendre] la carte compte 5 attaques (ni le Cf3, ni la faute sans camp)", card.get_attribute("data-count") == "5", f"({card.get_attribute('data-count')})")
        card.click()
    else:
        page.goto(f"{BASE}/#/attaques-manquees")
    page.wait_for_timeout(1000)
    check("[liste] route /attaques-manquees", page.url.endswith("#/attaques-manquees"), f"({page.url})")
    actives = page.locator("nav a[aria-current]").locator("visible=true").all_inner_texts()
    check("[liste] onglet Apprendre allumé", len(actives) == 1 and "Apprendre" in actives[0], f"({actives})")

    if ck.appears("[liste] synthèse affichée", page, "[data-testid=attack-summary]", timeout=10000):
        text = page.locator("[data-testid=attack-summary]").inner_text().strip()
        check("[liste] synthèse exacte (2 parties, 5 attaques, surtout des sacrifices)", text == SUMMARY, f"({text!r})")
    check("[liste] principe affiché", page.locator("main :text('Attaque quand tes attaquants dépassent les défenseurs')").count() >= 1)
    items = page.locator("[data-testid=attack-item]")
    check("[liste] 5 attaques listées", items.count() == 5, f"({items.count()})")
    kinds = {int(i.get_attribute("data-id")): i.get_attribute("data-kind") for i in items.all()}
    check("[liste] types par position (sacrifice, sacrifice, poussée, pièce, mat), témoins absents (Cf3, camp inconnu, finale, pion passé, fourchette, gain)",
          kinds == EXPECTED_KINDS, f"({kinds})")
    counts = {e.get_attribute("data-kind"): e.get_attribute("data-count") for e in page.locator("[data-testid=attack-kind-count]").all()}
    check("[liste] compteurs par type", counts == {"mat": "1", "sacrifice": "2", "poussee": "1", "piece": "1"}, f"({counts})")
    if items.count() > 0:
        first = items.first
        check("[liste] la plus récente d'abord (mat, bilan B)", first.get_attribute("data-id") == "5", f"({first.get_attribute('data-id')})")
        check("[liste] l'item dit le coup joué, pas le bon coup", "♔f1" in first.inner_text() and "a8" not in first.inner_text(), f"({first.inner_text()!r})")
    else:
        ck.fail("[liste] la plus récente d'abord (mat, bilan B)", "(aucun item)")
    check("[liste] aucun débordement horizontal (393x852)", overflow_x(page) == 0, f"({overflow_x(page)})")
    page.screenshot(path=f"{SHOTS}/attaque_liste_852.png")

    # --- Stats : même synthèse, lien vers la liste ---
    page.goto(f"{BASE}/#/stats")
    if ck.appears("[stats] carte « Attaques manquées »", page, "[data-testid=attack-stats]", timeout=15000):
        text = page.locator("[data-testid=attack-stats]").inner_text()
        check("[stats] même synthèse que la liste", SUMMARY in text, f"({text!r})")
        page.locator("[data-testid=attack-stats] a").first.click()
        page.wait_for_timeout(800)
        check("[stats] le lien ouvre la liste", page.url.endswith("#/attaques-manquees"), f"({page.url})")

    # --- Exercice : mat manqué, le coup du bilan mate ---
    page.goto(f"{BASE}/#/attaques-manquees/5")
    if ck.appears("[mat] exercice monté", page, "[data-testid=position-game]", timeout=20000):
        page.wait_for_timeout(600)
        check("[mat] titre = type de l'attaque", page.locator("h1", has_text="Mat manqué").count() == 1)
        check("[mat] objectif : retrouver l'attaque", page.locator("[data-testid=objective]").inner_text().startswith("Objectif : retrouve l'attaque"))
        check("[mat] consigne prudente (« au bilan »)", "Au bilan" in page.locator("[data-testid=objective-subline]").inner_text())
        check("[mat] calque forcé : deux puces de compte", len(pills(page)) == 2, f"({pills(page)})")
        check("[mat] principe sous l'échiquier", page.locator("[data-testid=attack-legend]").count() == 1)
        check("[mat] cadres sur l'échiquier", page.locator("[data-testid=king-zone]").count() == 2)
        check("[mat] aucun débordement horizontal", overflow_x(page) == 0)
        page.screenshot(path=f"{SHOTS}/attaque_exercice_852.png")
        tap_move(page, "a1", "a8")
        ok = ck.appears("[mat] Ta8# : partie terminée", page, "[data-testid=position-game][data-status='over']", timeout=8000)
        if ok:
            objective = page.locator("[data-testid=objective]").inner_text()
            check("[mat] victoire par mat", "Victoire" in objective and "Mat en 1 coup" in objective, f"({objective!r})")
            page.wait_for_timeout(500)
            rows = [r for r in learn_sessions(page) if r.get("domain") == "missed-attack"]
            check("[mat] une ligne learnSessions missed-attack réussie", len(rows) == 1 and rows[0].get("itemId") == "5" and rows[0].get("success") == 1 and rows[0].get("fen") == MISTAKES[4]["fenBefore"], f"({rows})")
            check("[mat] CTA « Attaque suivante »", page.get_by_role("button", name="Attaque suivante").is_visible())
        page.get_by_role("button", name="Retour").click()
        page.wait_for_timeout(800)
        check("[mat] retour à la liste", page.url.endswith("#/attaques-manquees"), f"({page.url})")
        done = page.locator("[data-testid=attack-item][data-id='5']")
        check("[mat] item marqué « Retrouvée »", done.count() == 1 and "Retrouvée" in done.inner_text(), f"({done.inner_text() if done.count() else 'absent'!r})")

    # --- Exercice : sacrifice, verdict sur le premier coup ---
    page.goto(f"{BASE}/#/attaques-manquees/1")
    if ck.appears("[sacrifice] exercice monté", page, "[data-testid=position-game]", timeout=20000):
        page.wait_for_timeout(600)
        check("[sacrifice] titre", page.locator("h1", has_text="Sacrifice près du roi").count() == 1)
        sub = page.locator("[data-testid=objective-subline]")
        # Cxd5 ?? (exd5 gagne le cavalier) est vérifié par Stockfish (profondeur 12) : il perd bien plus
        # de 5 points de win% par rapport au meilleur coup, la tentative est ratée.
        tap_move(page, "c3", "d5")
        ck.appears("[sacrifice] un autre coup : le coup du bilan est rappelé", page, "[data-testid=objective-subline]:has-text('Au bilan : ♗xh7+')", timeout=30000)
        check("[sacrifice] Stockfish a répondu", wait_idle(page))
        rows = [r for r in learn_sessions(page) if r.get("domain") == "missed-attack" and r.get("itemId") == "1"]
        check("[sacrifice] tentative notée ratée", len(rows) == 1 and rows[0].get("success") == 0, f"({rows})")
        page.get_by_role("button", name="Annuler").click()
        page.wait_for_timeout(500)
        check("[sacrifice] Annuler efface le verdict", "♗xh7+" not in sub.inner_text(), f"({sub.inner_text()!r})")
        check("[sacrifice] position revenue (fou en d3)", page.locator("[data-square='d3'] [data-piece='wB']").count() == 1)
        tap_move(page, "d3", "h7")
        ck.appears("[sacrifice] le bon coup est reconnu", page, "[data-testid=objective-subline]:has-text(\"C'est le coup du bilan\")", timeout=5000)
        check("[sacrifice] Stockfish a répondu au sacrifice", wait_idle(page))
        rows = [r for r in learn_sessions(page) if r.get("domain") == "missed-attack" and r.get("itemId") == "1"]
        check("[sacrifice] une seule ligne par tentative (le réessai après Annuler ne recompte pas)", len(rows) == 1, f"({rows})")
        check("[sacrifice] tentative marquée avec aide", page.locator("main :text('avec aide')").count() >= 1)
        page.screenshot(path=f"{SHOTS}/attaque_sacrifice_852.png")

    # --- Exercice : Recommencer pendant la vérification Stockfish ---
    # La tentative interrompue est notée ratée, la suivante a sa propre ligne (réussie ici).
    page.goto(f"{BASE}/#/attaques-manquees/2")
    if ck.appears("[recommencer] exercice monté", page, "[data-testid=position-game]", timeout=20000):
        page.wait_for_timeout(600)
        tap_move(page, "d2", "d3")
        checking = "Je vérifie" in page.locator("[data-testid=objective-subline]").inner_text()
        page.get_by_role("button", name="Recommencer").click()
        check("[recommencer] cliqué pendant la vérification", checking)
        page.wait_for_timeout(500)
        tap_move(page, "g5", "f7")
        ck.appears("[recommencer] le bon coup est reconnu", page, "[data-testid=objective-subline]:has-text(\"C'est le coup du bilan\")", timeout=5000)
        check("[recommencer] Stockfish a répondu", wait_idle(page))
        page.wait_for_timeout(1500)  # le verdict périmé de la première tentative a eu le temps d'arriver
        rows = [r for r in learn_sessions(page) if r.get("domain") == "missed-attack" and r.get("itemId") == "2"]
        check("[recommencer] tentative interrompue ratée, la suivante réussie", [r.get("success") for r in rows] == [0, 1], f"({rows})")

    # --- Id inconnu ou ligne hors liste : message propre, jamais d'exercice ni d'exception ---
    page.goto(f"{BASE}/#/attaques-manquees/12")
    if ck.appears("[liste] ligne incomplète (id 12, sans playedSan) : message propre", page, "[data-testid=attack-missing]", timeout=10000):
        check("[liste] ligne incomplète : pas d'exercice ouvert", page.locator("[data-testid=position-game]").count() == 0)
    page.goto(f"{BASE}/#/attaques-manquees/999")
    if ck.appears("[liste] id inconnu : message propre", page, "[data-testid=attack-missing]", timeout=10000):
        page.get_by_role("link", name="Retour à la liste").click()
        page.wait_for_timeout(800)
        check("[liste] id inconnu : le lien ramène à la liste", page.url.endswith("#/attaques-manquees"), f"({page.url})")
    ctx.close()

    # --- 393x660 : liste et exercice sans débordement ---
    ctx = mobile_context(p, browser, ck, standalone=False)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    if ck.appears("[660] Apprendre", page, "main :text('Apprendre')", timeout=20000):
        page.wait_for_timeout(600)
        seed_mistakes(page)
        page.goto(f"{BASE}/#/attaques-manquees")
        if ck.appears("[660] liste", page, "[data-testid=attack-item]", timeout=10000):
            check("[660] liste sans débordement", overflow_x(page) == 0)
            page.screenshot(path=f"{SHOTS}/attaque_liste_660.png")
        page.goto(f"{BASE}/#/attaques-manquees/4")
        if ck.appears("[660] exercice", page, "[data-testid=position-game]", timeout=20000):
            page.wait_for_timeout(600)
            check("[660] exercice sans débordement", overflow_x(page) == 0)
            check("[660] échiquier et barre d'actions visibles", page.locator("[data-square='e4']").is_visible() and page.get_by_role("button", name="Indice").is_visible())
            page.screenshot(path=f"{SHOTS}/attaque_exercice_660.png")
    ctx.close()

    # --- Sans faute : états vides honnêtes ---
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/attaques-manquees")
    if ck.appears("[vide] page", page, "[data-testid=attack-summary]", timeout=15000):
        text = page.locator("[data-testid=attack-summary]").inner_text()
        check("[vide] synthèse sans chiffre inventé", "Aucune faute à ton nom" in text and "undefined" not in text and "NaN" not in text, f"({text!r})")
        check("[vide] aucun item, explication affichée", page.locator("[data-testid=attack-item]").count() == 0 and page.locator("[data-testid=attack-empty]").is_visible())
    ctx.close()


# ---------- Calque « Compte les attaquants » ----------

def part_overlay(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = open_analysis(ctx)
    check("[calque] désactivé par défaut : ni puce ni cadre", page.locator("[data-testid=attack-count]").count() == 0 and page.locator("[data-testid=king-zone]").count() == 0)
    btn = attackers_option(page)
    if ck.appears("[calque] option dans la feuille Options", page, "button:visible:has-text('Compter les attaquants')", timeout=5000):
        check("[calque] libellé initial « désactivé »", "désactivé" in btn.inner_text(), f"({btn.inner_text()!r})")
        btn.click()
        page.wait_for_timeout(300)
        check("[calque] libellé « activé » après le tap", "activé" in btn.inner_text() and "désactivé" not in btn.inner_text(), f"({btn.inner_text()!r})")
        page.locator("button:visible", has_text="Fermer").click()
        page.wait_for_timeout(300)
    st = settings_state(page)
    check("[calque] réglage persisté (showAttackers: true)", bool(st) and st.get("showAttackers") is True, f"({st})")
    check("[calque] légende avec le principe", page.locator("[data-testid=attack-legend]:visible").count() == 1
          and "dépassent les défenseurs" in page.locator("[data-testid=attack-legend]:visible").inner_text())

    for name, fen, expected in OVERLAY_FENS:
        if fen != START:
            load_fen(page, fen)
        got = pills(page)
        check(f"[calque] {name} : deux pastilles", set(got) == {"w", "b"}, f"({got})")
        for side in ("w", "b"):
            if side not in got:
                continue
            a, d, over = got[side]
            check(f"[calque] {name} roi {'blanc' if side == 'w' else 'noir'} : {expected[side][0]} attaquants / {expected[side][1]} défenseurs", (a, d) == expected[side], f"(lu {a}/{d})")
            check(f"[calque] {name} roi {'blanc' if side == 'w' else 'noir'} : oracle python-chess d'accord", (a, d) == oracle(fen, side), f"(oracle {oracle(fen, side)})")
            check(f"[calque] {name} roi {'blanc' if side == 'w' else 'noir'} : surnombre {'signalé' if a > d else 'non signalé'}", over == (a > d))
        zones = page.locator("[data-testid=king-zone]")
        check(f"[calque] {name} : un cadre par roi", zones.count() == 2, f"({zones.count()})")
        if name == "surnombre":
            check("[calque] surnombre : cadre du roi noir en rouge", page.locator("[data-testid=king-zone][data-side='b'][data-over='1']").count() == 1)
            check("[calque] surnombre : légende ▲ sur le roi noir", "▲" in page.locator("[data-testid=attack-legend]:visible").inner_text())
            page.screenshot(path=f"{SHOTS}/attaque_calque_852.png")
        if name == "coin":
            box = page.locator("[data-testid=king-zone][data-side='w']").bounding_box()
            board = page.locator("[id^='chessboard-']").first.bounding_box()
            check("[calque] coin : le cadre (3x3 remonté) reste dans l'échiquier", box is not None and board is not None
                  and box["x"] >= board["x"] - 1 and box["x"] + box["width"] <= board["x"] + board["width"] + 1
                  and box["y"] + box["height"] <= board["y"] + board["height"] + 1)
    # Les pastilles ne gênent pas la saisie : un tap sur une case de la zone sélectionne bien la pièce.
    load_fen(page, START)
    page.locator("[data-square='e2']").click()
    page.wait_for_timeout(200)
    page.locator("[data-square='e4']").click()
    page.wait_for_timeout(400)
    check("[calque] un coup se joue à travers le cadre (e2-e4)", page.locator("[data-square='e4'] [data-piece='wP']").count() == 1)
    # Après e4 le roi blanc garde ses 5 défenseurs (le pion e4 ne vise plus rien près de lui), le
    # roi noir en voit toujours 5 : la pastille se recalcule avec la position.
    got = pills(page)
    check("[calque] après e4 les comptes suivent la position", got.get("w", ())[:2] == (0, 5) and got.get("b", ())[:2] == (0, 5), f"({got})")
    check("[calque] aucun débordement horizontal", overflow_x(page) == 0)

    # Option désactivée : plus rien.
    btn = attackers_option(page)
    btn.click()
    page.wait_for_timeout(300)
    page.locator("button:visible", has_text="Fermer").click()
    page.wait_for_timeout(300)
    check("[calque] désactivé : pastilles et cadres disparus", page.locator("[data-testid=attack-count]").count() == 0 and page.locator("[data-testid=king-zone]").count() == 0)
    check("[calque] désactivé : légende retirée", page.locator("[data-testid=attack-legend]:visible").count() == 0)
    ctx.close()

    # Desktop : même calque, interrupteur dans la colonne de droite (la feuille Options est mobile), capture.
    ctx = desktop_context(browser, ck, settings={"showAttackers": True})
    page = open_analysis(ctx)
    check("[desktop] pastilles présentes avec le réglage activé", len(pills(page)) == 2, f"({pills(page)})")
    page.screenshot(path=f"{SHOTS}/attaque_calque_1440.png")
    toggle = page.locator("[data-testid=toggle-attackers]:visible")
    if check("[desktop] interrupteur du calque visible et allumé", toggle.count() == 1 and toggle.get_attribute("aria-checked") == "true"):
        toggle.click()
        page.wait_for_timeout(300)
        check("[desktop] interrupteur éteint : pastilles, cadres et légende retirés", len(pills(page)) == 0
              and page.locator("[data-testid=king-zone]").count() == 0 and page.locator("[data-testid=attack-legend]:visible").count() == 0)
        st = settings_state(page)
        check("[desktop] interrupteur éteint : réglage persisté (showAttackers: false)", bool(st) and st.get("showAttackers") is False, f"({st})")
        toggle.click()
        page.wait_for_timeout(300)
        check("[desktop] interrupteur rallumé : calque de retour", len(pills(page)) == 2 and page.locator("[data-testid=king-zone]").count() == 2)
    ctx.close()

    # Jouer : interrupteur sur l'écran de configuration, calque pendant la partie contre un bot.
    ctx = mobile_context(p, browser, ck, settings={"showAttackers": True}, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/jouer")
    if ck.appears("[jouer] écran de configuration", page, "text=Adversaire", timeout=20000):
        toggle = page.locator("[data-testid=toggle-attackers]")
        check("[jouer] interrupteur « Compter les attaquants » présent", toggle.count() == 1)
        check("[jouer] interrupteur allumé (réglage pré-rempli)", toggle.get_attribute("aria-checked") == "true", f"({toggle.get_attribute('aria-checked')})")
        page.locator("main button", has_text="Contre un bot").first.click()
        page.locator("main button", has_text="Noa").first.click()
        page.locator("main button", has_text="Blancs").first.click()
        page.get_by_role("button", name="Illimité", exact=True).click()
        page.get_by_role("button", name="Jouer", exact=True).click()
        if ck.appears("[jouer] partie lancée", page, "[data-square='e2']", timeout=15000):
            page.wait_for_timeout(500)
            got = pills(page)
            check("[jouer] deux pastilles sur la position de départ (0 / 5)", got.get("w", ())[:2] == (0, 5) and got.get("b", ())[:2] == (0, 5), f"({got})")
            check("[jouer] légende visible", page.locator("[data-testid=attack-legend]:visible").count() == 1)
            check("[jouer] aucun débordement horizontal", overflow_x(page) == 0)
            page.screenshot(path=f"{SHOTS}/attaque_jouer_852.png")
    ctx.close()

    # Stats : le même interrupteur dans Réglages.
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    if ck.appears("[stats] page", page, "main :text('Réglages')", timeout=15000):
        toggle = page.locator("[data-testid=toggle-attackers]")
        if check("[stats] interrupteur présent dans Réglages", toggle.count() == 1):
            toggle.click()
            page.wait_for_timeout(300)
            st = settings_state(page)
            check("[stats] l'interrupteur écrit le réglage", bool(st) and st.get("showAttackers") is True, f"({st})")
    ctx.close()


# ---------- Chaîne réelle : bilan d'une partie de l'Archive -> `color` et `gameKey` ----------

def part_review_chain(p, browser):
    """Le bilan écrit `color` (camp du joueur) et `gameKey` (`game:<id>`) sur chaque faute, même lancé
    par le bouton Bilan après « Voir » (sans `review=1`), et complète une faute déjà en base (même
    position, même coup joué) qui n'avait pas de camp."""
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/archive")
    if not ck.appears("[bilan] archive chargée", page, "main", timeout=20000):
        ctx.close()
        return
    page.wait_for_timeout(1000)
    game_id = idb(page, "const tx = db.transaction('games', 'readwrite'); const r = tx.objectStore('games').add(arg);"
                        "tx.oncomplete = () => resolve(r.result); tx.onerror = () => reject(tx.error)",
                  {"date": T0, "mode": "bot", "botId": "noa", "playerColor": "w", "timeControl": "illimité", "timeClass": "unlimited",
                   "pgn": PGN, "result": "0-1", "termination": "mat"})
    board = chess.Board()
    for san in PGN.replace("1. ", "").split():
        if san[0].isdigit():
            continue
        if board.fullmove_number == 5 and board.turn == chess.WHITE:
            break
        board.push_san(san)
    before_nxf7 = board.fen()
    idb(page, "const tx = db.transaction('mistakes', 'readwrite'); tx.objectStore('mistakes').put(arg);"
              "tx.oncomplete = () => resolve(true); tx.onerror = () => reject(tx.error)",
        {"id": 50, "date": T0, "gameLabel": "Partie analysée", "fenBefore": before_nxf7, "playedSan": "Nxf7", "bestUci": "c4f7", "cls": "blunder", "attempts": 0, "solved": 0})

    page.goto(f"{BASE}/#/analyse?game={game_id}")
    if ck.appears("[bilan] partie ouverte depuis l'Archive", page, "[data-square='e4']", timeout=30000):
        page.wait_for_timeout(1500)
        page.locator("main button:visible", has_text="Bilan").first.click()
        if ck.appears("[bilan] bilan terminé (résumé affiché)", page, "text=Démarrer le bilan", timeout=240000):
            page.wait_for_timeout(800)
            rows = idb(page, "const r = db.transaction('mistakes').objectStore('mistakes').getAll(); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error)")
            fresh = [r for r in rows if r.get("id") != 50]
            check("[bilan] des fautes écrites", len(fresh) >= 1, f"({len(fresh)})")
            check("[bilan] toutes les fautes sont celles des Blancs (couleur du joueur connue)",
                  all(chess.Board(r["fenBefore"]).turn == chess.WHITE for r in rows), f"({[r['playedSan'] for r in rows]})")
            check("[bilan] color 'w' et gameKey game:<id> sur chaque faute, même via le bouton Bilan après « Voir »",
                  all(r.get("color") == "w" and r.get("gameKey") == f"game:{game_id}" for r in fresh), f"({[(r.get('color'), r.get('gameKey')) for r in fresh]})")
            old = next((r for r in rows if r.get("id") == 50), None)
            check("[bilan] la faute déjà en base (5. Cxf7) est complétée : camp et partie, coup joué inchangé",
                  old is not None and old.get("color") == "w" and old.get("gameKey") == f"game:{game_id}" and old.get("playedSan") == "Nxf7" and old.get("bestUci") == "c4f7", f"({old})")
            check("[bilan] pas de doublon de la faute complétée", sum(1 for r in rows if r["fenBefore"] == before_nxf7) == 1)
    ctx.close()


def part_engine_failure(p, browser):
    """Une commande UCI rejetée ne note pas un échec ; Recommencer permet de rejouer."""
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script("""(() => {
      const Native = window.Worker
      window.Worker = class extends Native {
        postMessage(...args) {
          if (window.__failAttackSearch && args[0] === 'go depth 12') {
            window.__failAttackSearch = false
            throw new Error('Commande UCI rejetée pour le test')
          }
          return super.postMessage(...args)
        }
      }
    })()""")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_selector("[data-testid=missed-attacks-card]")
    seed_mistakes(page)
    page.goto(f"{BASE}/#/attaques-manquees/1")
    page.wait_for_selector("[data-testid=position-game]")
    page.wait_for_timeout(600)
    page.evaluate("window.__failAttackSearch = true")
    tap_move(page, "c3", "d5")
    ck.appears("[panne] invitation à réessayer sans faux verdict", page,
               '[data-testid=objective-subline]:has-text("Stockfish n\'a pas pu vérifier")', timeout=15000)
    check("[panne] la réponse réelle du moteur arrive", wait_idle(page))
    check("[panne] aucune tentative notée", not learn_sessions(page))
    page.screenshot(path=f"{SHOTS}/attaque_panne_moteur.png")
    page.get_by_role("button", name="Recommencer").click()
    tap_move(page, "d3", "h7")
    ck.appears("[panne] nouvelle tentative reconnue", page,
               "[data-testid=objective-subline]:has-text(\"C'est le coup du bilan\")")
    check("[panne] réponse réelle après reprise", wait_idle(page))
    rows = learn_sessions(page)
    check("[panne] seule la nouvelle réussite est enregistrée", len(rows) == 1
          and rows[0].get("domain") == "missed-attack" and rows[0].get("success") == 1, f"({rows})")
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    part_diagnostic(p, browser)
    part_overlay(p, browser)
    part_review_chain(p, browser)
    part_engine_failure(p, browser)
    browser.close()


ck.run(suite)
