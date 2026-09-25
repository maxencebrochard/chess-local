"""E2E sauvegarde : la seule opération destructive de l'app doit être tout ou rien.

Les données de l'utilisateur ne vivent que dans l'IndexedDB de son iPhone : supprimer l'icône
de la PWA efface tout, la sauvegarde est son seul filet. Cette suite prouve :
- aller-retour export -> profil vierge -> restauration STRICTEMENT identique (ids compris) ;
- tout fichier refusé laisse la base INCHANGÉE (instantané avant = après), avec un message
  français, et n'ouvre aucune confirmation ;
- une confirmation annulée ne change rien ;
- une ancienne sauvegarde sans `mistakes` ni `learnSessions` a un comportement défini et annoncé ;
- après restauration, l'interface et les réglages sont à jour SANS rechargement, et un réglage
  touché ensuite n'écrase pas les réglages restaurés (piège du store Zustand en mémoire) ;
- export par la feuille de partage quand elle existe, sinon téléchargement, nom en date LOCALE,
  date du dernier export mémorisée seulement après succès ;
- état du stockage visible ; réinitialisation derrière une double confirmation.

Instantanés et seeds passent par l'IndexedDB NATIVE (pas Dexie, pas l'UI de restauration :
le test serait circulaire). Usage : npm run test:e2e -- --suite backup
"""
import json
import os
import re
import tempfile

from helpers import BASE, SHOTS, Checker, mobile_context

ck = Checker("backup")
check = ck.check

TABLES = ["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions"]
SETTINGS_KEY = "chess-local-settings"
LAST_EXPORT_KEY = "chess-local-last-export"
FILE_INPUT = "input[type=file]"
MSG = "[data-testid=backup-msg]"

# Chromium de bureau expose parfois navigator.share : sans activation utilisateur « réelle », il
# rejette ou ouvre une feuille native qui bloque. Les contextes « téléchargement » le retirent.
NO_SHARE = """
Object.defineProperty(navigator, 'canShare', { value: undefined, configurable: true })
Object.defineProperty(navigator, 'share', { value: undefined, configurable: true })
"""


def share_stub(mode="ok"):
    """Feuille de partage simulée. ok : enregistre le fichier reçu dans window.__shared ;
    abort : l'utilisateur ferme la feuille ; fail_then_ok : premier appel refusé
    (NotAllowedError, activation utilisateur expirée), les suivants réussissent."""
    record = "const f = d.files[0]; window.__shared = { name: f.name, type: f.type, size: f.size, head: (await f.text()).slice(0, 40) }"
    if mode == "abort":
        body = "throw new DOMException('annulé', 'AbortError')"
    elif mode == "fail_then_ok":
        body = f"window.__shareCalls = (window.__shareCalls || 0) + 1; if (window.__shareCalls === 1) throw new DOMException('refusé', 'NotAllowedError'); {record}"
    else:
        body = record
    return f"""
Object.defineProperty(navigator, 'canShare', {{ value: (d) => !!(d && d.files && d.files.length), configurable: true }})
Object.defineProperty(navigator, 'share', {{ value: async (d) => {{ {body} }}, configurable: true }})
"""


def persisted_stub(value):
    # try/catch : le script tourne aussi sur about:blank, où navigator.storage n'existe pas.
    return f"try {{ Object.defineProperty(navigator.storage, 'persisted', {{ value: async () => {json.dumps(value)}, configurable: true }}) }} catch {{}}"


PGN = "[Event \"Partie vs Noa\"]\n[Site \"chess-local\"]\n[Result \"1-0\"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0"


def game(i, result, color="w", mode="bot"):
    g = {
        "id": i,
        "date": 1758000000000 + i * 3600_000,
        "mode": mode,
        "playerColor": color,
        "timeControl": "10+0",
        "timeClass": "rapid",
        "pgn": PGN.replace("1-0", result),
        "result": result,
        "termination": "mat",
        "playerRatingAfter": 800 + i,
    }
    if mode == "bot":
        g["botId"] = "noa"
    return g


# Seed à l'image de ce que l'app écrit (mêmes champs, ids Dexie explicites). 3 parties contre
# un bot dont 2 gagnées, 1 locale : Stats doit afficher « 2 gagnées ».
SEED = {
    "games": [game(1, "1-0"), game(2, "0-1"), game(3, "1-0"), game(4, "1/2-1/2", mode="local")],
    "ratings": [
        {"key": "blitz", "value": 812, "games": 3},
        {"key": "bullet", "value": 790, "games": 1},
        {"key": "learn-tactic", "value": 845, "games": 4},
        {"key": "puzzle", "value": 901, "games": 4},
        {"key": "rapid", "value": 803, "games": 4},
    ],
    "puzzleAttempts": [
        {"id": 1, "puzzleId": "00sHx", "date": 1758000100000, "success": True, "puzzleRating": 850, "ratingAfter": 830},
        {"id": 2, "puzzleId": "00sJ5", "date": 1758000200000, "success": False, "puzzleRating": 900, "ratingAfter": 815},
        {"id": 3, "puzzleId": "00sJb", "date": 1758000300000, "success": True, "puzzleRating": 880, "ratingAfter": 860},
        {"id": 4, "puzzleId": "00sO1", "date": 1758000400000, "success": True, "puzzleRating": 950, "ratingAfter": 901},
    ],
    "rushScores": [
        {"id": 1, "mode": "3min", "score": 7, "date": 1758000500000},
        {"id": 2, "mode": "survival", "score": 12, "date": 1758000600000},
    ],
    "mistakes": [
        {"id": 1, "date": 1758000700000, "gameLabel": "Partie vs Noa", "fenBefore": "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
         "playedSan": "Nf6", "bestUci": "g7g6", "cls": "blunder", "attempts": 1, "solved": 0},
        {"id": 2, "date": 1758000800000, "gameLabel": "Partie vs Noa", "fenBefore": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
         "playedSan": "Qh5", "bestUci": "g1f3", "cls": "mistake", "attempts": 0, "solved": 1},
    ],
    "learnSessions": [
        {"id": 1, "date": 1758000900000, "domain": "tactic", "itemId": "00sHx", "success": 1, "ratingAfter": 845},
        {"id": 2, "date": 1758001000000, "domain": "endgame", "itemId": "kq-vs-k", "success": 0, "ratingAfter": None},
    ],
}
SEED_SETTINGS = {"themeId": "purple", "showLegalMoves": False, "playSounds": False, "chesscomUsername": "moi", "reviewDepth": "deep"}


# ---------- IndexedDB natif ----------

OPEN_DB = """
() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {
    const db = r.result
    if (db.objectStoreNames.length !== 6) { db.close(); rej(new Error('schéma absent : ' + db.objectStoreNames.length + ' stores')); return }
    res(db)
  }
  r.onerror = () => rej(r.error)
})
"""


def wait_schema(page, tries=40):
    """L'app (Dexie) crée la base au premier accès : on attend qu'elle ait ses 6 stores avant de
    la toucher nativement (un open() natif sur une base absente en créerait une vide)."""
    for _ in range(tries):
        n = page.evaluate(
            """() => new Promise((res) => {
              indexedDB.databases().then((list) => {
                if (!list.some((d) => d.name === 'chess-local')) return res(0)
                const r = indexedDB.open('chess-local')
                r.onsuccess = () => { const n = r.result.objectStoreNames.length; r.result.close(); res(n) }
                r.onerror = () => res(-1)
              })
            })"""
        )
        if n == 6:
            return True
        page.wait_for_timeout(250)
    return False


def seed_db(page, data):
    page.evaluate(
        "async (data) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const tx = db.transaction(Object.keys(data), 'readwrite')
          for (const [t, rows] of Object.entries(data)) for (const r of rows) tx.objectStore(t).put(r)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); tx.onabort = () => rej(tx.error) })
          db.close()
        }""",
        data,
    )


def snapshot(page):
    """Toutes les lignes de tous les stores, triées par clé primaire (ordre natif de getAll)."""
    return page.evaluate(
        "async () => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const names = [...db.objectStoreNames]
          const tx = db.transaction(names, 'readonly')
          const out = {}
          for (const n of names) out[n] = await new Promise((res, rej) => { const q = tx.objectStore(n).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
          db.close()
          return out
        }"""
    )


def settings_state(page):
    return page.evaluate(f"() => {{ try {{ return JSON.parse(localStorage.getItem('{SETTINGS_KEY}')).state }} catch {{ return null }} }}")


def last_export(page):
    return page.evaluate(f"() => localStorage.getItem('{LAST_EXPORT_KEY}')")


def counts(snap):
    return {t: len(snap.get(t, [])) for t in TABLES}


# ---------- page Stats ----------


def open_stats(page):
    page.goto(f"{BASE}/#/stats")
    ok = ck.appears("[stats] page chargée", page, "main :text('Statistiques')", timeout=15000)
    return ok and check("[stats] base prête (6 stores)", wait_schema(page))


FRESH_MSG = f"{MSG}:not([data-stale])"


def arm(page):
    """Marque le message affiché comme périmé : `message()` n'acceptera qu'un élément rendu
    APRÈS. Deux cas consécutifs qui attendent le même texte ne peuvent donc pas se satisfaire
    l'un l'autre (React ne retire pas un attribut qu'il n'a pas posé)."""
    page.evaluate(f"() => document.querySelectorAll('{MSG}').forEach((el) => el.setAttribute('data-stale', '1'))")


def message(page, timeout=15000):
    """Attend le prochain message de sauvegarde et retourne (texte, genre)."""
    try:
        page.wait_for_function(f"() => (document.querySelector('{FRESH_MSG}')?.textContent || '').trim() !== ''", timeout=timeout)
    except Exception:
        return "", ""
    el = page.locator(FRESH_MSG)
    return el.inner_text().strip(), el.get_attribute("data-kind") or ""


def choose_file(page, path):
    arm(page)
    page.set_input_files(FILE_INPUT, path)


def click_export(page):
    arm(page)
    page.click("[data-testid=export-btn]")


def write_file(tmp, name, content):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content if isinstance(content, str) else json.dumps(content))
    return path


def backup_dict(version=2, settings=None, **tables):
    d = {"_app": "chess-local", "_version": version, "_date": "2026-09-18T10:00:00.000Z"}
    for t in TABLES:
        if t in tables:
            if tables[t] is not None:
                d[t] = tables[t]
        else:
            d[t] = list(SEED[t])
    if settings is not None:
        d["settings"] = settings
    return d


def seeded_context(p, browser, extra_scripts=(), settings_by_app=False, **options):
    """Contexte iPhone standalone avec réglages « purple/deep » et base peuplée par SEED.

    settings_by_app=True : les réglages sont écrits dans localStorage comme l'app le ferait, et le
    script d'init du contexte garde ses valeurs par défaut (vert/rapide). Nécessaire pour prouver
    un effacement : ce script ré-injecte SES réglages à chaque chargement si la clé manque."""
    ctx = mobile_context(p, browser, ck, settings=None if settings_by_app else SEED_SETTINGS, standalone=True, **options)
    ctx.add_init_script(NO_SHARE)
    for s in extra_scripts:
        ctx.add_init_script(s)
    page = ctx.new_page()
    if not open_stats(page):
        return ctx, page
    seed_db(page, SEED)
    if settings_by_app:
        page.evaluate(f"(blob) => localStorage.setItem('{SETTINGS_KEY}', blob)", json.dumps({"state": SEED_SETTINGS, "version": 0}))
    page.reload()
    ck.appears("[seed] Stats rechargée", page, "main :text('Statistiques')", timeout=15000)
    wait_schema(page)
    return ctx, page


# ---------- volets ----------


def part_roundtrip(p, browser, tmp):
    ctx, page = seeded_context(p, browser)
    before = snapshot(page)
    check("[seed] base peuplée", counts(before) == {t: len(SEED[t]) for t in TABLES}, f"({counts(before)})")
    check("[seed] Stats affiche 2 gagnées", page.locator("main :text('2 gagnées')").count() == 1)

    arm(page)
    with page.expect_download() as dl:
        page.click("[data-testid=export-btn]")
    name = dl.value.suggested_filename
    check("[export] nom daté en local", re.fullmatch(r"chesslocal-sauvegarde-\d{4}-\d{2}-\d{2}-\d{4}\.json", name) is not None, f"({name})")
    path = os.path.join(tmp, "export.json")
    dl.value.save_as(path)
    text, kind = message(page)
    check("[export] message de succès avec le nombre de parties", kind == "success" and "Sauvegarde exportée" in text and "4 parties" in text, f"({text!r})")
    le = json.loads(last_export(page) or "null")
    check("[export] date du dernier export mémorisée (clé additive)", isinstance(le, dict) and le.get("games") == 4 and isinstance(le.get("at"), (int, float)), f"({le})")
    check("[export] Stats affiche la date du dernier export", "jamais" not in page.locator("[data-testid=last-export]").inner_text().lower())
    with open(path, encoding="utf-8") as f:
        exported = json.load(f)
    check("[export] format prod : _app, _version 2, 6 tables, settings en chaîne",
          exported.get("_app") == "chess-local" and exported.get("_version") == 2 and all(isinstance(exported.get(t), list) for t in TABLES) and isinstance(exported.get("settings"), str))
    stores = sorted(k for k in exported if not k.startswith("_") and k != "settings")
    check("[export] garde-fou : les tables exportées = les object stores réels", stores == sorted(before.keys()), f"({stores} vs {sorted(before.keys())})")
    check("[export] contenu = base", {t: exported[t] for t in TABLES} == before)
    page.screenshot(path=f"{SHOTS}/backup_stats_after_export.png", full_page=True)
    ctx.close()

    # Profil VIERGE : réglages par défaut (thème vert), base vide.
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(NO_SHARE)
    page = ctx.new_page()
    if not open_stats(page):
        ctx.close()
        return
    empty = snapshot(page)
    check("[vierge] base vide", all(len(v) == 0 for v in empty.values()), f"({counts(empty)})")
    check("[vierge] dernier export : jamais", "jamais" in page.locator("[data-testid=last-export]").inner_text().lower())
    choose_file(page, path)
    if ck.appears("[restore] feuille de confirmation", page, "[data-testid=restore-sheet]"):
        body = page.locator("[data-testid=restore-sheet]").inner_text()
        check("[restore] la feuille résume le fichier (date, parties, classements)",
              "4 parties" in body and "5 classements" in body and re.search(r"faite le \d{2}/\d{2}/\d{4} à \d{2}:\d{2}", body) is not None, f"({body[:160]!r})")
        check("[restore] base vide : pas de bouton « exporter d'abord »", page.locator("[data-testid=restore-export-first]").count() == 0)
        page.screenshot(path=f"{SHOTS}/backup_restore_sheet.png")
        page.click("[data-testid=restore-confirm]")
    text, kind = message(page, timeout=20000)
    check("[restore] succès qui dit ce qui a été restauré", kind == "success" and text.startswith("Sauvegarde restaurée") and "4 parties" in text and "Réglages restaurés" in text, f"({text!r})")
    check("[restore] plus de « Recharge la page »", "recharge" not in text.lower())
    after = snapshot(page)
    check("[restore] base STRICTEMENT identique à l'export (ids compris)", after == before, f"({counts(after)})")
    check("[restore] réglages identiques", settings_state(page) == SEED_SETTINGS, f"({settings_state(page)})")

    # GLOB-2 : interface à jour sans rechargement, puis un réglage touché n'écrase rien.
    check("[glob-2] Stats affiche 2 gagnées sans rechargement", page.locator("main :text('2 gagnées')").count() == 1)
    check("[glob-2] puzzles à jour sans rechargement", page.locator("main :text('3 résolus / 4 tentés')").count() == 1)
    check("[glob-2] thème Améthyste sélectionné sans rechargement", "border-accent" in (page.locator("button[title='Améthyste']").get_attribute("class") or ""))
    page.locator("main button.h-6.w-11").nth(1).click()  # toggle Sons
    page.wait_for_timeout(300)
    st = settings_state(page)
    check("[glob-2] toggle Sons appliqué", st and st["playSounds"] is True, f"({st})")
    check("[glob-2] le thème restauré survit au toggle", st and st["themeId"] == "purple" and st["reviewDepth"] == "deep", f"({st})")
    page.reload()
    ck.appears("[glob-2] Stats rechargée", page, "main :text('Statistiques')", timeout=15000)
    st = settings_state(page)
    check("[glob-2] réglages restaurés toujours là après rechargement", st and st["themeId"] == "purple" and st["reviewDepth"] == "deep" and st["playSounds"] is True, f"({st})")
    check("[glob-2] Profond sélectionné après rechargement", "border-accent" in (page.get_by_role("button", name="Profond", exact=True).get_attribute("class") or ""))
    ctx.close()


def part_refusals(p, browser, tmp):
    ctx, page = seeded_context(p, browser)
    before = snapshot(page)
    cases = [
        ("texte non JSON", "bonjour, je ne suis pas du JSON", "illisible"),
        ("JSON tronqué", '{"_app":"chess-local","_version":2,"games":[{"pgn":"1. e4', "illisible"),
        ("JSON null", "null", "pas une sauvegarde ChessLocal"),
        ("JSON tableau", "[]", "pas une sauvegarde ChessLocal"),
        ("autre app", backup_dict() | {"_app": "autre-app"}, "pas une sauvegarde ChessLocal"),
        ("_version absent", {k: v for k, v in backup_dict().items() if k != "_version"}, "version"),
        ("version future 99", backup_dict(version=99), "version plus récente"),
        ("table non-tableau", backup_dict(games="oops"), "abîmée"),
        ("ligne sans pgn", backup_dict(games=[{"id": 1, "date": 1}]), "forme inattendue"),
        ("ids en double", backup_dict(games=[game(1, "1-0"), game(1, "0-1")]), "identifiant en double"),
        ("ids incohérents (une ligne sans id)", backup_dict(games=[game(1, "1-0"), {"pgn": "1. e4", "date": 5}]), "incohérents"),
        ("id non entier", backup_dict(games=[dict(game(1, "1-0"), id=1.5)]), "identifiant invalide"),
        ("clé __proto__", '{"_app":"chess-local","_version":2,"games":[{"__proto__":{"x":1},"pgn":"1. e4","date":1}],"ratings":[],"puzzleAttempts":[],"rushScores":[],"mistakes":[],"learnSessions":[]}', "clé interdite"),
        ("table requise absente en v2", backup_dict(mistakes=None), "abîmée"),
        ("fichier vide valide", backup_dict(**{t: [] for t in TABLES}), "vide"),
    ]
    for label, content, expected in cases:
        path = write_file(tmp, re.sub(r"\W+", "_", label) + ".json", content)
        choose_file(page, path)
        text, kind = message(page)
        check(f"[refus] {label} : message rouge en français", kind == "error" and expected in text, f"({text!r})")
        check(f"[refus] {label} : aucune feuille de confirmation", page.locator("[data-testid=restore-sheet]").count() == 0)
        check(f"[refus] {label} : base INCHANGÉE", snapshot(page) == before)
        check(f"[refus] {label} : aucun message brut du moteur JS", "Unexpected" not in text and "JSON at position" not in text and "Cannot read" not in text)
    page.screenshot(path=f"{SHOTS}/backup_refus.png", full_page=True)

    # Fichier trop gros : refusé sur la taille, avant même la lecture.
    big = os.path.join(tmp, "trop_gros.json")
    with open(big, "w", encoding="utf-8") as f:
        f.write('{"_app":"chess-local","_version":2,"pad":"')
        for _ in range(51):
            f.write("x" * (1024 * 1024))
        f.write('"}')
    choose_file(page, big)
    text, kind = message(page)
    check("[refus] fichier > 50 Mo : refusé", kind == "error" and "volumineux" in text, f"({text!r})")
    check("[refus] fichier > 50 Mo : base INCHANGÉE", snapshot(page) == before)

    # Le même fichier choisi deux fois de suite doit produire deux messages (input remis à zéro).
    path = write_file(tmp, "deux_fois.json", backup_dict() | {"_app": "autre-app"})
    choose_file(page, path)
    first, _ = message(page)
    choose_file(page, path)
    again, kind = message(page)
    check("[refus] le même fichier rechoisi est relu (nouveau message)", first and again == first and kind == "error", f"({again!r})")

    # Annulation de la confirmation : rien ne change.
    path = write_file(tmp, "valide_autre.json", backup_dict(games=[game(9, "1-0")], settings=None))
    choose_file(page, path)
    if ck.appears("[annuler] feuille ouverte pour un fichier valide", page, "[data-testid=restore-sheet]"):
        body = page.locator("[data-testid=restore-sheet]").inner_text()
        check("[annuler] la feuille dit ce qui sera remplacé", "4 parties" in body and "seront remplacé" in body and "1 partie" in body, f"({body[:200]!r})")
        check("[annuler] bouton « exporter d'abord » présent (base non vide)", page.locator("[data-testid=restore-export-first]").count() == 1)
        # « Exporter d'abord » depuis la feuille : le fichier sort, la feuille reste ouverte et
        # utilisable, la date d'export est mémorisée.
        with page.expect_download() as dl:
            page.click("[data-testid=restore-export-first]")
        check("[annuler] export depuis la feuille : fichier téléchargé", dl.value.suggested_filename.endswith(".json"))
        ck.appears("[annuler] export depuis la feuille : confirmation dans la feuille", page, "[data-testid=restore-sheet] :text('Sauvegarde exportée')", timeout=10000)
        check("[annuler] la feuille reste ouverte après l'export", page.locator("[data-testid=restore-sheet]").count() == 1)
        check("[annuler] boutons de la feuille réactivés", page.locator("[data-testid=restore-confirm]").is_enabled() and page.locator("[data-testid=restore-cancel]").is_enabled())
        le = json.loads(last_export(page) or "null")
        check("[annuler] date d'export mémorisée depuis la feuille", isinstance(le, dict) and le.get("games") == 4, f"({le})")
        page.click("[data-testid=restore-cancel]")
        page.wait_for_timeout(300)
    check("[annuler] feuille fermée", page.locator("[data-testid=restore-sheet]").count() == 0)
    check("[annuler] base INCHANGÉE", snapshot(page) == before)
    check("[annuler] pas de message de succès", "restaurée" not in page.locator(MSG).inner_text() if page.locator(MSG).count() else True)
    check("[annuler] réglages inchangés", settings_state(page) == SEED_SETTINGS)
    ctx.close()


def part_old_v1(p, browser, tmp):
    """Ancienne sauvegarde v1 : sans `mistakes` ni `learnSessions`. Comportement défini : ces
    deux tables sont VIDÉES (jamais d'état mixte), et c'est annoncé avant et après."""
    ctx, page = seeded_context(p, browser)
    before = snapshot(page)
    v1 = backup_dict(version=1, games=[game(7, "0-1")], ratings=[{"key": "rapid", "value": 777, "games": 7}], puzzleAttempts=[], rushScores=[],
                     mistakes=None, learnSessions=None, settings=None)
    path = write_file(tmp, "v1_ancienne.json", v1)
    choose_file(page, path)
    if ck.appears("[v1] feuille ouverte", page, "[data-testid=restore-sheet]"):
        body = page.locator("[data-testid=restore-sheet]").inner_text().lower()
        check("[v1] la feuille annonce les tables vidées", "vidées" in body and "erreurs" in body and "séances" in body, f"({body[:300]!r})")
        check("[v1] la feuille dit que les réglages sont conservés", "réglages" in body and "conservés" in body, f"({body[:300]!r})")
        page.screenshot(path=f"{SHOTS}/backup_restore_v1_sheet.png")
        page.click("[data-testid=restore-confirm]")
    text, kind = message(page, timeout=20000)
    check("[v1] succès annoncé avec les tables vidées", kind == "success" and text.startswith("Sauvegarde restaurée") and "vidées" in text.lower(), f"({text!r})")
    after = snapshot(page)
    check("[v1] mistakes et learnSessions vidées", after["mistakes"] == [] and after["learnSessions"] == [])
    check("[v1] les autres tables = le fichier", after["games"] == v1["games"] and after["ratings"] == v1["ratings"] and after["puzzleAttempts"] == [] and after["rushScores"] == [])
    check("[v1] réglages conservés (fichier sans réglages)", settings_state(page) == SEED_SETTINGS)
    check("[v1] la base a bien changé (le test peut échouer)", after != before)
    ctx.close()


def part_edge_cases(p, browser, tmp):
    """v1 qui CONTIENT `mistakes` (validées comme les autres), sans `_date`, avec des réglages
    illisibles : données restaurées, réglages ignorés ET annoncés, jamais « Invalid Date »."""
    ctx, page = seeded_context(p, browser)
    f = backup_dict(version=1, games=[game(8, "1-0")], ratings=[], puzzleAttempts=[], rushScores=[],
                    mistakes=[dict(SEED["mistakes"][0], id=3)], learnSessions=None, settings="pas du json")
    del f["_date"]
    path = write_file(tmp, "v1_avec_mistakes_sans_date.json", f)
    choose_file(page, path)
    if ck.appears("[cas limites] feuille ouverte", page, "[data-testid=restore-sheet]"):
        body = page.locator("[data-testid=restore-sheet]").inner_text()
        check("[cas limites] sans _date : « sans date », jamais Invalid Date", "sans date" in body and "Invalid" not in body, f"({body[:120]!r})")
        check("[cas limites] réglages illisibles annoncés", "illisibles" in body and "conservés" in body, f"({body[:300]!r})")
        low = body.lower()
        check("[cas limites] seules les séances sont annoncées vidées (mistakes présentes en v1)", "séances" in low and "vidées" in low and "erreurs à revoir et séances" not in low, f"({low[:300]!r})")
        page.click("[data-testid=restore-confirm]")
    text, kind = message(page, timeout=20000)
    check("[cas limites] succès qui annonce les réglages ignorés", kind == "success" and "illisibles" in text and "1 erreur à revoir" in text, f"({text!r})")
    after = snapshot(page)
    check("[cas limites] mistakes du fichier restaurées, séances vidées", after["mistakes"] == f["mistakes"] and after["learnSessions"] == [] and after["games"] == f["games"])
    check("[cas limites] réglages inchangés", settings_state(page) == SEED_SETTINGS, f"({settings_state(page)})")
    ctx.close()


def part_export_paths(p, browser, tmp):
    # Feuille de partage disponible : le fichier passe par navigator.share, avec le bon nom.
    ctx = mobile_context(p, browser, ck, settings=SEED_SETTINGS, standalone=True, timezone_id="Europe/Paris")
    ctx.add_init_script(share_stub())
    page = ctx.new_page()
    page.clock.set_fixed_time("2026-09-17T22:30:00Z")  # 00:30 le 18 à Paris : en UTC ce serait encore le 17
    if open_stats(page):
        seed_db(page, SEED)
        page.reload()
        ck.appears("[partage] Stats rechargée", page, "main :text('Statistiques')", timeout=15000)
        click_export(page)
        text, kind = message(page)
        shared = page.evaluate("() => window.__shared || null")
        check("[partage] navigator.share a reçu le fichier", bool(shared) and shared["type"] == "application/json" and shared["head"].startswith('{"_app":"chess-local"'), f"({shared})")
        check("[partage] nom en date LOCALE (00:30 à Paris, pas la veille en UTC)", bool(shared) and shared["name"] == "chesslocal-sauvegarde-2026-09-18-0030.json", f"({shared and shared['name']})")
        check("[partage] message de succès", kind == "success" and "Sauvegarde exportée" in text and "4 parties" in text, f"({text!r})")
        le = json.loads(last_export(page) or "null")
        check("[partage] dernier export mémorisé", isinstance(le, dict) and le.get("games") == 4, f"({le})")
        shown = page.locator("[data-testid=last-export]").inner_text()
        check("[partage] Stats affiche la date locale du dernier export", "18/09/2026" in shown and "00:30" in shown, f"({shown!r})")
    ctx.close()

    # Partage annulé par l'utilisateur : rien n'est mémorisé, message honnête.
    ctx = mobile_context(p, browser, ck, settings=SEED_SETTINGS, standalone=True)
    ctx.add_init_script(share_stub("abort"))
    page = ctx.new_page()
    if open_stats(page):
        click_export(page)
        text, kind = message(page)
        check("[partage annulé] message « annulé », pas de succès", "annulé" in text.lower() and kind != "success", f"({text!r})")
        check("[partage annulé] aucune date d'export mémorisée", last_export(page) is None)
        check("[partage annulé] Stats affiche toujours « jamais »", "jamais" in page.locator("[data-testid=last-export]").inner_text().lower())
    ctx.close()

    # Partage refusé (activation expirée) : PAS de repli téléchargement (faux succès en PWA iOS),
    # message rouge, rien de mémorisé, puis nouvel essai synchrone qui aboutit.
    ctx = mobile_context(p, browser, ck, settings=SEED_SETTINGS, standalone=True)
    ctx.add_init_script(share_stub("fail_then_ok"))
    page = ctx.new_page()
    downloads = []
    page.on("download", lambda d: downloads.append(d))
    if open_stats(page):
        seed_db(page, SEED)
        page.reload()
        ck.appears("[partage refusé] Stats rechargée", page, "main :text('Statistiques')", timeout=15000)
        click_export(page)
        text, kind = message(page)
        check("[partage refusé] message rouge, pas de succès", kind == "error" and "pas abouti" in text, f"({text!r})")
        check("[partage refusé] aucune date d'export mémorisée", last_export(page) is None)
        page.wait_for_timeout(500)
        check("[partage refusé] aucun téléchargement de repli", not downloads)
        if ck.appears("[partage refusé] bouton « Partager le fichier »", page, "[data-testid=share-retry]", timeout=5000):
            arm(page)
            page.click("[data-testid=share-retry]")
            text, kind = message(page)
            shared = page.evaluate("() => window.__shared || null")
            check("[partage refusé] nouvel essai : fichier partagé", bool(shared) and shared["head"].startswith('{"_app":"chess-local"'), f"({shared})")
            check("[partage refusé] nouvel essai : message de succès", kind == "success" and "4 parties" in text, f"({text!r})")
            le = json.loads(last_export(page) or "null")
            check("[partage refusé] nouvel essai : date mémorisée", isinstance(le, dict) and le.get("games") == 4, f"({le})")
            check("[partage refusé] bouton de nouvel essai retiré", page.locator("[data-testid=share-retry]").count() == 0)
    ctx.close()


def part_storage_status(p, browser):
    for value, word in ((True, "oui"), (False, "non")):
        ctx = mobile_context(p, browser, ck, standalone=True)
        ctx.add_init_script(NO_SHARE)
        ctx.add_init_script(persisted_stub(value))
        page = ctx.new_page()
        if open_stats(page):
            if ck.appears(f"[stockage] état affiché (persisted={value})", page, f"[data-testid=storage-persisted]:has-text('{word}')", timeout=10000):
                block = page.locator("[data-testid=storage-status]").inner_text().lower()
                check("[stockage] phrase claire : cet appareil, icône, exporte", "cet appareil" in block and "icône" in block and "export" in block, f"({block[:200]!r})")
                if value:
                    page.screenshot(path=f"{SHOTS}/backup_storage_status.png", full_page=True)
        ctx.close()


def part_reset(p, browser):
    ctx, page = seeded_context(p, browser, settings_by_app=True)
    before = snapshot(page)
    check("[reset] réglages purple/deep en place avant", settings_state(page) == SEED_SETTINGS, f"({settings_state(page)})")
    page.click("[data-testid=reset-btn]")
    if ck.appears("[reset] première confirmation", page, "[data-testid=reset-sheet]"):
        body = page.locator("[data-testid=reset-sheet]").inner_text()
        check("[reset] la feuille dit ce qui sera effacé", "4 parties" in body and "5 classements" in body, f"({body[:200]!r})")
        page.click("[data-testid=reset-confirm]")
    if ck.appears("[reset] deuxième confirmation", page, "[data-testid=reset-final-sheet]"):
        page.screenshot(path=f"{SHOTS}/backup_reset_final_sheet.png")
        page.click("[data-testid=reset-final-cancel]")
        page.wait_for_timeout(300)
    check("[reset] annulation à la deuxième étape : feuilles fermées", page.locator("[data-testid=reset-final-sheet]").count() == 0 and page.locator("[data-testid=reset-sheet]").count() == 0)
    check("[reset] annulation : base INCHANGÉE", snapshot(page) == before)
    check("[reset] annulation : réglages inchangés", settings_state(page) == SEED_SETTINGS)

    page.click("[data-testid=reset-btn]")
    ck.appears("[reset] première confirmation (2e passage)", page, "[data-testid=reset-sheet]")
    page.click("[data-testid=reset-confirm]")
    ck.appears("[reset] deuxième confirmation (2e passage)", page, "[data-testid=reset-final-sheet]")
    page.click("[data-testid=reset-final-confirm]")
    ck.appears("[reset] l'app redémarre sur l'accueil", page, "main :text('Problèmes')", timeout=20000)
    ok = check("[reset] base recréée vide", wait_schema(page) and all(len(v) == 0 for v in snapshot(page).values()))
    # Après l'effacement, le script d'init du contexte ré-injecte SES défauts (vert/rapide) au
    # rechargement : purple/deep encore là prouverait que localStorage n'a pas été vidé.
    st = settings_state(page)
    check("[reset] réglages purple/deep effacés", st is not None and st["themeId"] == "green" and st["reviewDepth"] == "fast", f"({st})")
    check("[reset] date du dernier export effacée", last_export(page) is None)
    if ok:
        page.goto(f"{BASE}/#/stats")
        ck.appears("[reset] Stats utilisable après réinitialisation", page, "main :text('Statistiques')", timeout=15000)
        check("[reset] Stats affiche 0 gagnées", page.locator("main :text('0 gagnées')").count() == 1)
    ctx.close()


def part_prod_format(p, browser, tmp):
    """Un fichier construit à l'image exacte de l'export du build de prod (_version 2, lignes telles
    que l'app les écrit, réglages en chaîne au format persist) se restaure à 100 %."""
    prod = backup_dict(settings=json.dumps({"state": {"themeId": "blue", "showLegalMoves": True, "playSounds": True, "chesscomUsername": "hikaru", "reviewDepth": "fast"}, "version": 0}))
    prod["_date"] = "2026-07-20T15:15:54.000Z"
    path = write_file(tmp, "export_prod_v2.json", prod)
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(NO_SHARE)
    page = ctx.new_page()
    if open_stats(page):
        choose_file(page, path)
        if ck.appears("[prod v2] feuille ouverte", page, "[data-testid=restore-sheet]"):
            page.click("[data-testid=restore-confirm]")
        text, kind = message(page, timeout=20000)
        check("[prod v2] restaurée", kind == "success" and text.startswith("Sauvegarde restaurée"), f"({text!r})")
        after = snapshot(page)
        check("[prod v2] 6 tables identiques au fichier", {t: after[t] for t in TABLES} == {t: prod[t] for t in TABLES}, f"({counts(after)})")
        st = settings_state(page)
        check("[prod v2] réglages du fichier appliqués", st == {"themeId": "blue", "showLegalMoves": True, "playSounds": True, "chesscomUsername": "hikaru", "reviewDepth": "fast"}, f"({st})")
        check("[prod v2] thème Océan sélectionné sans rechargement", "border-accent" in (page.locator("button[title='Océan']").get_attribute("class") or ""))

        # Réglages hostiles : valeurs hors liste blanche ramenées au défaut, sans refuser les données.
        hostile = backup_dict(games=[game(5, "1-0")], settings=json.dumps({"state": {"themeId": "evil", "reviewDepth": "evil", "playSounds": "oui", "setTheme": "x", "chesscomUsername": "attaquant"}, "version": 0}))
        path = write_file(tmp, "reglages_hostiles.json", hostile)
        choose_file(page, path)
        if ck.appears("[réglages hostiles] feuille ouverte", page, "[data-testid=restore-sheet]"):
            page.click("[data-testid=restore-confirm]")
        text, kind = message(page, timeout=20000)
        st = settings_state(page)
        check("[réglages hostiles] données restaurées", kind == "success" and snapshot(page)["games"] == hostile["games"], f"({text!r})")
        check("[réglages hostiles] valeurs hors liste ramenées au défaut, chaîne légitime gardée",
              st == {"themeId": "green", "showLegalMoves": True, "playSounds": True, "chesscomUsername": "attaquant", "reviewDepth": "balanced"}, f"({st})")
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    with tempfile.TemporaryDirectory(prefix="chesslocal-backup-") as tmp:
        part_roundtrip(p, browser, tmp)
        part_refusals(p, browser, tmp)
        part_old_v1(p, browser, tmp)
        part_edge_cases(p, browser, tmp)
        part_export_paths(p, browser, tmp)
        part_storage_status(p, browser)
        part_reset(p, browser)
        part_prod_format(p, browser, tmp)
    browser.close()


ck.run(suite)
