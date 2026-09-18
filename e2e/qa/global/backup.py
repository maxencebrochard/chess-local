"""Sauvegarde / restauration : export complet, aller-retour dans un contexte neuf, fichiers invalides, écrasement."""
import json
import os
import sys

QA = "e2e/qa"
os.environ.setdefault("SHOTS", f"{QA}/global/shots")
sys.path.insert(0, QA)
sys.path.insert(0, f"{QA}/global")
from qa_helpers import *  # noqa
from seed import seed, dump_counts, DATA

FILES = f"{QA}/global/backup_files"
os.makedirs(FILES, exist_ok=True)
fails = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        fails.append(name)


def write(name, content):
    path = os.path.join(FILES, name)
    with open(path, "w") as f:
        f.write(content if isinstance(content, str) else json.dumps(content))
    return path


def restore(page, path, wait=900):
    page.locator("input[type=file]").set_input_files(path)
    page.wait_for_timeout(wait)
    msg = page.locator("main p.text-xs.text-accent, main p.text-xs.text-red-400, main p.text-xs.text-red-300")
    return msg.first.inner_text() if msg.count() else "(aucun message)"


with sync_playwright() as p:
    # ---------- A. EXPORT ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True, settings={"themeId": "purple", "reviewDepth": "deep", "showLegalMoves": False})
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1200)
    seed(page)
    page.reload(); page.wait_for_timeout(1200)
    with page.expect_download() as dl:
        page.locator("button", has_text="Exporter tout").tap()
    export_path = os.path.join(FILES, "export.json")
    dl.value.save_as(export_path)
    print("nom de fichier:", dl.value.suggested_filename)
    exp = json.load(open(export_path))
    print("clés:", list(exp.keys()))
    print("compteurs:", {k: len(v) for k, v in exp.items() if isinstance(v, list)})
    db_tables = ["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions"]
    check("export: toutes les tables de db.ts", all(t in exp for t in db_tables))
    check("export: compteurs = données injectées", all(len(exp[t]) == len(DATA[t]) for t in db_tables))
    check("export: réglages inclus", isinstance(exp.get("settings"), str) and '"purple"' in exp["settings"])
    check("export: nom chesslocal-sauvegarde-AAAA-MM-JJ.json", dl.value.suggested_filename.startswith("chesslocal-sauvegarde-") and dl.value.suggested_filename.endswith(".json"))
    check("export: retour visuel après export (message/toast)", page.locator("main", has_text="export").count() > 0 and "Exporté" in page.locator("main").inner_text())
    browser.close()

    # ---------- B. RESTAURATION DANS UN CONTEXTE NEUF ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1200)
    before = page.locator("main").inner_text()
    msg = restore(page, export_path, 1200)
    print("message:", msg)
    after = page.locator("main").inner_text()
    counts = dump_counts(page)
    print("IDB après restauration:", counts)
    check("restore: données en base", counts.get("games") == 10 and counts.get("mistakes") == 3 and counts.get("learnSessions") == 3 and counts.get("ratings") == 7)
    check("restore: l'UI Stats se rafraîchit sans reload", "3 gagnées" in after, "(toujours '0 gagnées')" if "0 gagnées" in after else "")
    theme_ui = page.evaluate("[...document.querySelectorAll('main button[title]')].filter(b => b.className.includes('border-accent')).map(b => b.title)")
    check("restore: réglages appliqués sans reload", theme_ui == ["Améthyste"], str(theme_ui))
    shot(page, "restore_success_stale_ui")
    # piège : l'utilisateur touche un réglage AVANT de recharger -> le store Zustand (ancien état) réécrit localStorage
    page.locator("main button.h-6.w-11").nth(1).tap(); page.wait_for_timeout(300)
    ls = json.loads(page.evaluate("localStorage.getItem('chess-local-settings')"))
    check("restore: un réglage touché avant reload ne détruit pas les réglages restaurés", ls["state"]["themeId"] == "purple", f"themeId={ls['state']['themeId']} reviewDepth={ls['state']['reviewDepth']}")
    page.reload(); page.wait_for_timeout(1200)
    after_reload = page.locator("main").inner_text()
    check("restore: après reload les stats reviennent", "3 gagnées" in after_reload and "1034" in after_reload)
    browser.close()

    # ---------- C. ÉCRASEMENT SANS CONFIRMATION ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1200)
    seed(page); page.reload(); page.wait_for_timeout(1000)
    empty = write("valide_vide.json", {"_app": "chess-local", "_version": 2, "games": [], "ratings": [], "puzzleAttempts": [], "rushScores": [], "mistakes": [], "learnSessions": []})
    msg = restore(page, empty)
    counts = dump_counts(page)
    print("C. message:", msg, "| dialogs:", dialogs, "| IDB:", counts)
    check("écrasement: confirmation demandée avant d'effacer 10 parties", len(dialogs) > 0 or page.locator("div.fixed").count() > 0)
    check("écrasement: données conservées tant que non confirmé", counts.get("games") == 10, f"games={counts.get('games')}")
    browser.close()

    # ---------- D. FICHIERS INVALIDES ----------
    cases = [
        ("texte brut", write("texte.json", "bonjour, je ne suis pas du JSON")),
        ("JSON tronqué", write("tronque.json", '{"_app":"chess-local","games":[{"date":1')),
        ("JSON null", write("null.json", "null")),
        ("JSON tableau", write("tableau.json", "[1,2,3]")),
        ("autre app", write("autre_app.json", {"_app": "lichess-backup", "games": []})),
        ("tables non-tableaux", write("non_tableaux.json", {"_app": "chess-local", "_version": 2, "games": "oops", "ratings": {"a": 1}})),
        ("lignes en conflit de clé", write("conflit.json", {"_app": "chess-local", "_version": 2, "games": [{"id": 1, "date": 1}, {"id": 1, "date": 2}], "ratings": [{"key": "blitz", "value": 1, "games": 1}]})),
        ("version future", write("futur.json", {"_app": "chess-local", "_version": 99, "games": [], "nouvelleTable": [1]})),
    ]
    for label, path in cases:
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1100)
        seed(page); page.reload(); page.wait_for_timeout(900)
        msg = restore(page, path)
        counts = dump_counts(page)
        color = page.evaluate("(() => { const e = [...document.querySelectorAll('main p.text-xs')].find(p => p.className.includes('text-accent') || p.className.includes('text-red')); return e ? e.className : null })()")
        preserved = counts.get("games") == 10 and counts.get("ratings") == 7
        print(f"D. [{label}] message: {msg!r} | classes: {color} | données préservées: {preserved} {counts} | pageerrors: {[l for l in logs if 'PAGEERROR' in l]}")
        if label in ("texte brut", "lignes en conflit de clé", "tables non-tableaux"):
            shot(page, f"restore_invalid_{label.split()[0]}")
        browser.close()

    # ---------- E. ANCIENNE VERSION (sans mistakes / learnSessions) ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1100)
    seed(page); page.reload(); page.wait_for_timeout(900)
    old = write("v1_ancienne.json", {"_app": "chess-local", "_version": 1, "_date": "2026-01-01T00:00:00.000Z",
                                      "games": DATA["games"][:2], "ratings": DATA["ratings"][:2], "puzzleAttempts": [], "rushScores": [],
                                      "settings": json.dumps({"state": {"themeId": "brown", "showLegalMoves": True, "playSounds": True, "chesscomUsername": "vieuxpseudo"}, "version": 0})})
    msg = restore(page, old)
    counts = dump_counts(page)
    print("E. message:", msg, "| IDB:", counts)
    check("v1: parties/classements remplacés", counts.get("games") == 2 and counts.get("ratings") == 2)
    check("v1: mistakes/learnSessions de l'ancien appareil NE survivent PAS (état cohérent)", counts.get("mistakes") == 0 and counts.get("learnSessions") == 0, f"mistakes={counts.get('mistakes')} learnSessions={counts.get('learnSessions')}")
    page.reload(); page.wait_for_timeout(1200)
    ls = json.loads(page.evaluate("localStorage.getItem('chess-local-settings')"))
    print("   réglages après reload (v1 sans reviewDepth):", ls["state"])
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(800)
    depth_ui = page.evaluate("[...document.querySelectorAll('main button')].filter(b => b.className.includes('bg-accent/10')).map(b => b.innerText)")
    check("v1: réglage manquant (reviewDepth) retombe sur le défaut", depth_ui == ["Équilibré"], str(depth_ui))
    browser.close()

    # ---------- F. RÉGLAGES CORROMPUS DANS LA SAUVEGARDE ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1100)
    bad = write("settings_corrompus.json", {"_app": "chess-local", "_version": 2, "games": [], "settings": "{pas du json"})
    msg = restore(page, bad)
    page.reload(); page.wait_for_timeout(1500)
    txt = page.locator("main").inner_text()
    print("F. message:", msg, "| app rend après reload:", len(txt) > 50, "| logs:", logs)
    check("réglages corrompus: l'app démarre encore", len(txt) > 50)
    browser.close()

print("\nFAILS:", fails)
