"""E2E « Révision espacée » (/revision) : échéances calculées depuis l'historique, carte de
l'accueil, séance mixte (fautes, puzzles, variante) plafonnée à 8 puis « Continuer », décalage
après réussite ou échec, écritures dans les tables d'origine, Réessayer et ✕ sans effet,
aller-retour Analyser, écran vide, item introuvable.

Les données sont semées directement dans IndexedDB (schéma créé par l'app d'abord, comme
test_backup), avec des dates relatives aux jours civils locaux : chaque règle de l'échelle de
Leitner [1, 3, 7, 21] jours a son item, dû ou non. `puzzles.json` est remplacé par une petite
liste qui contient les ids semés (mat en 1 : Ra8#). Le service worker est bloqué : en prod, le
précache servirait le vrai fichier.

Usage : npm run test:e2e -- --suite revision
        npm run test:e2e:dev -- --suite revision      (StrictMode : effets et updaters doublés)
"""
import json
import os
import re
from datetime import datetime

from helpers import BASE, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move

ck = Checker("revision")
check = ck.check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "src", "data", "openings.json"), encoding="utf-8") as f:
    OPENINGS = json.load(f)

DAY = 86_400_000
# Minuit local d'aujourd'hui : les échéances sont des jours civils locaux, et Chromium partage le
# fuseau du système. Les dates semées tombent à midi (J-n) ou juste après minuit (aujourd'hui) :
# aucune règle ne dépend de l'heure de lancement de la suite.
TODAY0 = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def ago(days=0):
    """Midi il y a `days` jours ; `days=0` : aujourd'hui, une minute après minuit."""
    return TODAY0 + 60_000 if days == 0 else TODAY0 - days * DAY + DAY // 2


# Mat en 1 : amorce ...Nc3 (coup adverse), puis Ra8#. Même position sous plusieurs ids.
MATE_FEN = "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1"
FIXTURE_IDS = ("L10", "L11", "L16", "L17", "L18", "L19", "L21")
PUZZLES = [[pid, MATE_FEN, "e4c3 a1a8", 1000, "backRankMate mate mateIn1 short"] for pid in FIXTURE_IDS]

# Faute : Dxd8+ gagne la dame (bestUci d1d8) ; h3 la perd (…Dxd1+) : Stockfish tranche « raté ».
MISTAKE_FEN = "3q2k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1"

GORING = next(o for o in OPENINGS if o["name"] == "Scotch Game: Göring Gambit, Main Line")["uci"]
RELFSSON = next(o for o in OPENINGS if o["name"] == "Scotch Game: Relfsson Gambit")["uci"]


def pa(i, pid, days, ok):
    return {"id": i, "puzzleId": pid, "date": ago(days), "success": ok, "puzzleRating": 1000, "ratingAfter": 900}


def ls(i, domain, item, days, ok):
    return {"id": i, "date": ago(days), "domain": domain, "itemId": item, "success": 1 if ok else 0, "ratingAfter": None}


def mistake(i, days, solved, attempts):
    return {"id": i, "date": ago(days), "gameLabel": f"Partie {i}", "fenBefore": MISTAKE_FEN, "playedSan": "h3",
            "bestUci": "d1d8", "cls": "blunder", "attempts": attempts, "solved": solved}


# Dus aujourd'hui (10) : puzzles L10 (raté J-5), L11 (boîte 1 réussi J-4, échéance J-1), L16 (raté
# dans Apprendre Tactiques J-6), L17 (boîte 3, dernière réussite J-29, échéance J-8), L18 (raté dans
# Apprendre Stratégie J-7), L19 (réussi J-10 puis raté J-2 : seul le dernier échec compte), L21
# (boîte 1 réussi J-3 : échéance aujourd'hui pile) ; fautes 1 (créée J-10) et 4 (classée dans
# Apprendre sans ligne de réussite : les événements font foi) ; variante Göring (ratée J-3).
# Exclus : L12 (raté aujourd'hui : demain), L13 (boîte 1 réussi J-2 : J+1), L14 (quatre
# réussites : acquis), L15 (jamais raté), L22 (raté J-45 : en retard de plus d'un mois, oublié),
# faute 2 (réussie hier : J+2), faute 3 (acquise), Relfsson (boîte 1 réussie hier), suite Göring
# (une suite n'est pas une variante), variante orpheline, variante jamais ratée.
SEED = {
    "puzzleAttempts": [
        pa(1, "L10", 5, False),
        pa(2, "L11", 30, False), pa(3, "L11", 4, True),
        pa(4, "L12", 0, False),
        pa(5, "L13", 30, False), pa(6, "L13", 2, True),
        pa(7, "L14", 60, False), pa(8, "L14", 50, True), pa(9, "L14", 40, True), pa(10, "L14", 30, True), pa(11, "L14", 20, True),
        pa(12, "L15", 3, True),
        pa(13, "L17", 40, False), pa(14, "L17", 39, True), pa(15, "L17", 36, True), pa(16, "L17", 29, True),
        pa(17, "L19", 10, True), pa(18, "L19", 2, False),
        pa(19, "L21", 30, False), pa(20, "L21", 3, True),
        pa(21, "L22", 45, False),
    ],
    "mistakes": [
        mistake(1, 10, 0, 0),
        mistake(2, 20, 1, 1),
        mistake(3, 40, 1, 4),
        mistake(4, 7, 1, 1),
    ],
    "learnSessions": [
        ls(1, "tactic", "L16", 6, False),
        ls(2, "mistakes", "2", 1, True),
        ls(3, "mistakes", "3", 39, True), ls(4, "mistakes", "3", 36, True), ls(5, "mistakes", "3", 29, True), ls(6, "mistakes", "3", 8, True),
        ls(7, "opening-drill", f"full:w:{GORING}", 3, False),
        ls(8, "opening-drill", f"full:w:{RELFSSON}", 5, False), ls(9, "opening-drill", f"full:w:{RELFSSON}", 1, True),
        ls(10, "opening-drill", f"suite:w:{GORING}", 10, False),
        ls(11, "opening-drill", "full:w:e2e4 a7a5 h2h4", 10, False),
        ls(12, "opening-drill", "full:b:e2e4 c7c5", 2, True),
        ls(13, "strategy", "carte:L18", 7, False),
    ],
}
EXPECTED_DUE = 10
EXPECTED_DETAIL = "7 puzzles · 2 erreurs · 1 variante"
# Séance 1 (8 items) : types entrelacés, chaque type du plus en retard au moins en retard, le type
# le plus en retard en tête (faute J-9, puzzle J-8, variante J-2). Séance 2 : les 2 restants.
EXPECTED_KINDS_1 = ["mistake", "puzzle", "variant", "mistake", "puzzle", "puzzle", "puzzle", "puzzle"]
EXPECTED_NEXT = {
    "L17": "Acquis : ne reviendra plus",        # boîte 3 -> acquis
    "L18": "Revient dans 3 jours", "L16": "Revient dans 3 jours", "L10": "Revient dans 3 jours", "L19": "Revient dans 3 jours",
    "L11": "Revient dans une semaine", "L21": "Revient dans une semaine",  # boîte 1 -> 2
    "Partie 1": "Revient demain",              # ratée
    "Partie 4": "Revient dans 3 jours",        # réussie
}
# Dus demain, après les deux séances : faute 1 (ratée aujourd'hui), L12 (raté aujourd'hui), L13
# (boîte 1 réussie J-2). Soit 3.

# Item introuvable : un puzzle raté dont l'id n'est plus dans puzzles.json, plus un puzzle dû demain
# (sans lui, « pas de fausse prochaine révision » ne pourrait pas échouer).
ORPHAN_SEED = {"puzzleAttempts": [pa(1, "L20", 5, False), pa(2, "L10", 0, False)]}


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
    """L'app (Dexie) crée la base au premier accès : attendre ses 6 stores avant d'y écrire
    nativement (un open() natif sur une base absente en créerait une vide)."""
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


def db_rows(page, table):
    return page.evaluate(
        "async (t) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const rows = await new Promise((res, rej) => { const q = db.transaction(t).objectStore(t).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
          db.close()
          return rows
        }""",
        table,
    )


def sessions(page, domain):
    """[(itemId, success)] des lignes learnSessions d'un domaine, par ordre de date."""
    rows = sorted(db_rows(page, "learnSessions"), key=lambda r: r["date"])
    return [(r["itemId"], r["success"]) for r in rows if r["domain"] == domain]


def mistake_row(page, i):
    return next(m for m in db_rows(page, "mistakes") if m["id"] == i)


# ---------- contexte semé ----------

def seeded(p, browser, seed=SEED, standalone=True, desktop=False):
    """Contexte surveillé, base semée (après création du schéma par l'app), puzzles.json réduit."""
    if desktop:
        ctx = desktop_context(browser, ck, service_workers="block")
    else:
        ctx = mobile_context(p, browser, ck, standalone=standalone, service_workers="block")
    body = json.dumps(PUZZLES)
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    ck.appears("[seed] Stats chargée", page, "main :text('Statistiques')", timeout=15000)
    if check("[seed] schéma à 6 stores créé par l'app", wait_schema(page)):
        seed_db(page, seed)
    return ctx, page


# ---------- lecture de la séance ----------

def item_kind(page, timeout=8000):
    """Type de l'item affiché : 'variant' (drill plein écran), 'mistake' ou 'puzzle' (attribut
    data-review-item du cadre), None si rien n'apparaît."""
    try:
        page.wait_for_selector("[data-drill], [data-review-item]", timeout=timeout)
    except Exception:
        return None
    if page.locator("[data-drill]").count():
        return "variant"
    return page.locator("[data-review-item]").first.get_attribute("data-review-item")


def drill_uci(page):
    v = page.get_attribute("[data-drill]", "data-uci")
    return v.split(" ") if v else []


def wait_plies(page, n, timeout=15000):
    try:
        page.wait_for_function(
            """(n) => { const d = document.querySelector('[data-drill]');
                        const u = d && d.getAttribute('data-uci'); return (u ? u.split(' ').length : 0) >= n }""",
            arg=n, timeout=timeout,
        )
        return True
    except Exception:
        return False


def play_line(page, line, color):
    """Joue les coups du joueur de `line` en attendant les réponses (copie de test_openings)."""
    me = 0 if color == "w" else 1
    for i in range(len(line)):
        if i % 2 != me:
            continue
        if not wait_plies(page, i):
            return check(f"[variante] réponse adverse avant le demi-coup {i}", False)
        tap_move(page, line[i][0:2], line[i][2:4])
        if not wait_plies(page, i + 1, 5000):
            return check(f"[variante] coup {line[i]} accepté", False, f"(position {drill_uci(page)})")
    return True


def next_label(page):
    el = page.locator("[data-review-next], [data-result-note]")
    return el.first.inner_text().strip() if el.count() else ""


def header_text(page):
    return page.locator("header h1").first.inner_text() if page.locator("header h1").count() else ""


def click_next(page):
    if ck.appears("[séance] bouton Suivant", page, "button:text-is('Suivant')", timeout=5000):
        page.get_by_role("button", name="Suivant", exact=True).click()
        page.wait_for_timeout(500)


def play_item(page, kind, n, log):
    """Joue l'item courant selon son type, note son libellé et son échéance dans `log`."""
    if kind == "mistake":
        m = re.search(r"Partie \d", page.locator("[data-review-item]").inner_text())
        if not check(f"[séance] item {n + 1} : libellé de la faute lisible", m is not None):
            return
        label = m.group(0)
        if label == "Partie 1":
            if n == 0:
                shot(page, "revision_mistake_852")
            tap_move(page, "h2", "h3")
            ck.appears("[faute 1] vérification Stockfish puis verdict « Raté »", page, "text=✗ Raté", timeout=60000)
            shot(page, "revision_verdict_852")
            log[label] = next_label(page)
            # Réessayer : le bon coup réussit à l'écran, sans réécrire le résultat enregistré.
            if ck.appears("[faute 1] bouton Réessayer", page, "button:has-text('Réessayer')", timeout=3000):
                page.get_by_role("button", name="Réessayer").click()
                page.wait_for_timeout(400)
                tap_move(page, "d1", "d8")
                ck.appears("[faute 1] réessai : « Réussi » à l'écran", page, "text=✓ Réussi", timeout=10000)
                check("[faute 1] l'échéance affichée reste celle de la première tentative", next_label(page) == "Revient demain", f"({next_label(page)!r})")
        else:
            tap_move(page, "d1", "d8")
            ck.appears(f"[{label}] meilleur coup : verdict « Réussi » sans moteur", page, "text=✓ Réussi", timeout=5000)
            log[label] = next_label(page)
    elif kind == "puzzle":
        banners = page.locator("[data-review-item] p", has_text="Puzzle")
        banner = banners.first.inner_text() if banners.count() else ""
        m = re.search(r"Puzzle (L\d+)", banner)
        if not check(f"[séance] item {n + 1} : bandeau « Puzzle L.. » lisible", m is not None, f"({banner!r})"):
            return
        pid = m.group(1)
        check(f"[{pid}] le bandeau ne livre pas le thème avant le verdict", "Mat" not in banner, f"({banner!r})")
        if not log.get("_puzzle_shot"):
            shot(page, "revision_puzzle_852")
            log["_puzzle_shot"] = True
        page.wait_for_timeout(1200)  # amorce ...Nc3
        tap_move(page, "a1", "a8")
        ck.appears(f"[{pid}] verdict « Réussi »", page, "text=✓ Réussi", timeout=8000)
        log[pid] = next_label(page)
        after = banners.first.inner_text() if banners.count() else ""
        check(f"[{pid}] thèmes affichés après le verdict", "Mat en 1" in after, f"({after!r})")
        if not log.get("_analysed"):
            log["_analysed"] = True
            # Analyser puis retour : la séance reprend au même item, verdict conservé.
            header = header_text(page)
            if ck.appears("[analyse] bouton Analyser", page, "button:has-text('Analyser')", timeout=3000):
                page.locator("button", has_text="Analyser").click()
            if ck.appears("[analyse] « Retour à la révision »", page, "button:has-text('Retour à la révision')", timeout=10000):
                page.locator("button", has_text="Retour à la révision").click()
                page.wait_for_timeout(800)
                check("[analyse] retour sur #/revision", page.evaluate("() => location.hash") == "#/revision")
                check("[analyse] même item après le retour", header_text(page) == header, f"({header_text(page)!r} vs {header!r})")
                check("[analyse] verdict conservé après le retour", page.locator("text=✓ Réussi").count() > 0 and next_label(page) == log[pid], f"({next_label(page)!r})")
    else:
        check("[variante] en-tête de séance sur le drill (« Révision n/8 »)", "Révision" in header_text(page) and "/8" in header_text(page), f"({header_text(page)!r})")
        check("[variante] ligne d'état « Raté il y a 3 jours »", page.locator("[data-drill] >> text=Raté il y a 3 jours").count() > 0)
        ok = play_line(page, GORING.split(" "), "w")
        if ck.appears("[variante] « Variante maîtrisée »", page, "[data-result] >> text=Variante maîtrisée", timeout=5000):
            btn = page.locator("[data-result] button", has_text="Suivant")
            check("[variante] bouton « Suivant » (pas « Variante suivante »)", btn.count() > 0 and btn.first.inner_text().strip() == "Suivant")
        log["Göring"] = next_label(page) if ok else ""
        shot(page, "revision_variant_852")


def play_session(page, expected_n, log):
    """Enchaîne les items jusqu'à l'écran de fin. Retourne la liste des types rencontrés."""
    kinds = []
    for n in range(expected_n):
        kind = item_kind(page)
        if kind is None:
            check(f"[séance] item {n + 1} affiché", False)
            break
        kinds.append(kind)
        if kind != "variant":
            check(f"[séance] en-tête « {n + 1}/{expected_n} »", f"{n + 1}/{expected_n}" in header_text(page), f"({header_text(page)!r})")
        play_item(page, kind, n, log)
        click_next(page)
    return kinds


# ---------- volets ----------

def part_home_and_session(p, browser):
    ctx, page = seeded(p, browser)

    # --- Apprendre : ligne Révision avec le compte ---
    page.goto(f"{BASE}/#/apprendre")
    if ck.appears("[apprendre] ligne « Révision espacée » (items dus)", page, "main a:has-text('Révision espacée')", timeout=10000):
        row = page.locator("main a", has_text="Révision espacée")
        badge = row.locator("[data-review-count]")
        check(f"[apprendre] pastille {EXPECTED_DUE} et détail par type", badge.count() == 1 and badge.inner_text().strip() == str(EXPECTED_DUE)
              and EXPECTED_DETAIL in row.inner_text(), f"({row.inner_text()!r})")
        row.scroll_into_view_if_needed()
        shot(page, "revision_learn_due_852")

    # --- Accueil : carte avec le compte exact des items dus ---
    page.goto(f"{BASE}/#/")
    if ck.appears("[accueil] carte « À réviser aujourd'hui »", page, "main a:has-text(\"À réviser aujourd'hui\")", timeout=10000):
        badge = page.locator("[data-review-count]").first.inner_text().strip() if page.locator("[data-review-count]").count() else ""
        check(f"[échéances] compteur = {EXPECTED_DUE} (dus : échecs J-5/J-6/J-7, boîte 1 réussie J-4 et J-3, boîte 3, réussi puis raté, "
              "faute J-10, faute classée sans ligne, variante J-3 ; exclus : aujourd'hui, boîte 1 à J-2, acquis, jamais raté, "
              "J-45 oublié, faute réussie hier, suite, orpheline)", badge == str(EXPECTED_DUE), f"({badge!r})")
        sub = page.locator("main a:has-text(\"À réviser aujourd'hui\")").inner_text()
        check(f"[accueil] détail par type « {EXPECTED_DETAIL} »", EXPECTED_DETAIL in sub, f"({sub!r})")
        check("[accueil] aucun débordement horizontal (393x852)", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        shot(page, "revision_home_852")
        hist_before = page.evaluate("() => history.length")
        page.locator("main a", has_text="À réviser aujourd'hui").click()
        page.wait_for_timeout(600)
        check("[accueil] la carte mène à #/revision (descente empilée)", page.evaluate("() => location.hash") == "#/revision"
              and page.evaluate("() => history.length") == hist_before + 1, f"({page.evaluate('() => location.hash')})")
    else:
        page.goto(f"{BASE}/#/revision")
        page.wait_for_timeout(800)
    actives = page.locator("nav a[aria-current]").locator("visible=true").all_inner_texts()
    check("[nav] onglet Apprendre allumé sur /revision", len(actives) == 1 and "Apprendre" in actives[0], f"({actives})")

    # --- ✕ pendant le premier item : rien n'est écrit ---
    kind = item_kind(page)
    check("[séance] premier item = la faute 1 (la plus en retard, J-10)", kind == "mistake" and "Partie 1" in page.locator("[data-review-item]").first.inner_text(), f"({kind})")
    check("[séance] en-tête « 1/8 » (séance plafonnée à 8)", "1/8" in header_text(page), f"({header_text(page)!r})")
    check("[séance] ligne d'état « Raté il y a 10 jours · étape 1/4 »", page.locator("text=Raté il y a 10 jours · étape 1/4").count() > 0)
    if ck.appears("[séance] bouton ✕", page, "header button:has-text('✕')", timeout=3000):
        page.locator("header button", has_text="✕").click()
        page.wait_for_timeout(500)
    m1 = mistake_row(page, 1)
    check("[✕] quitter sans jouer n'écrit rien (faute intacte, aucune ligne learnSessions)",
          m1["attempts"] == 0 and m1["solved"] == 0 and not any(k == "1" for k, _ in sessions(page, "mistakes")), f"({m1['attempts']}, {sessions(page, 'mistakes')})")
    check("[✕] retour à l'accueil (returnTo par défaut)", page.evaluate("() => location.hash") == "#/")

    # --- Séance 1 : 8 items entrelacés, puis Continuer ---
    page.goto(f"{BASE}/#/revision")
    log = {}
    kinds = play_session(page, 8, log)
    check("[séance 1] ordre des types : faute, puzzle, variante, faute, puis puzzles", kinds == EXPECTED_KINDS_1, f"({kinds})")
    if ck.appears("[fin 1] écran de fin", page, "[data-review-end]", timeout=5000):
        end = page.locator("[data-review-end]").inner_text()
        check("[fin 1] « 7/8 réussis »", "7/8 réussis" in end, f"({end[:60]!r})")
        row = page.locator("[data-review-end] li", has_text="Partie 1")
        check("[fin 1] récapitulatif : la faute ratée « Revient demain »", row.count() == 1 and "✗" in row.inner_text() and "Revient demain" in row.inner_text(), f"({row.inner_text() if row.count() else ''!r})")
        row = page.locator("[data-review-end] li", has_text="L17")
        check("[fin 1] récapitulatif : L17 « Acquis »", row.count() == 1 and "Acquis" in row.inner_text(), f"({row.inner_text() if row.count() else ''!r})")
        check("[fin 1] aucun débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        shot(page, "revision_end_852")
        if ck.appears("[fin 1] « Continuer (2 restants) »", page, "button:has-text('Continuer (2 restants)')", timeout=3000):
            page.locator("button", has_text="Continuer").click()
            page.wait_for_timeout(800)

    # --- Séance 2 : les 2 restants ---
    kinds2 = play_session(page, 2, log)
    check("[séance 2] deux puzzles", kinds2 == ["puzzle", "puzzle"], f"({kinds2})")
    if ck.appears("[fin 2] écran de fin", page, "[data-review-end]", timeout=5000):
        end = page.locator("[data-review-end]").inner_text()
        check("[fin 2] « 2/2 réussis », plus de Continuer", "2/2 réussis" in end and page.locator("button", has_text="Continuer").count() == 0, f"({end[:60]!r})")
        if ck.appears("[fin 2] bouton Terminer", page, "button:has-text('Terminer')", timeout=3000):
            page.get_by_role("button", name="Terminer").click()
            page.wait_for_timeout(600)
        check("[fin 2] Terminer ramène à l'accueil", page.evaluate("() => location.hash") == "#/", f"({page.evaluate('() => location.hash')})")

    got = {k: v for k, v in log.items() if not k.startswith("_")}
    check("[échéances] après chaque item : boîte 0 → 3 jours, boîte 1 → une semaine, boîte 3 → acquis, échec → demain, variante → 3 jours",
          got == {**EXPECTED_NEXT, "Göring": "Revient dans 3 jours"}, f"({got})")

    # --- Écritures : là où l'écran d'origine écrit, sans Elo ---
    m1, m4 = mistake_row(page, 1), mistake_row(page, 4)
    check("[données] faute 1 : attempts 1, solved 0 (le réessai n'a rien réécrit)", m1["attempts"] == 1 and m1["solved"] == 0, f"({m1['attempts']}, {m1['solved']})")
    check("[données] faute 4 : attempts 2, solved 1", m4["attempts"] == 2 and m4["solved"] == 1, f"({m4['attempts']}, {m4['solved']})")
    ms = sessions(page, "mistakes")
    check("[données] fautes : une ligne learnSessions chacune (1 → 0, 4 → 1)", ms.count(("1", 0)) == 1 and ms.count(("1", 1)) == 0 and ms.count(("4", 1)) == 1, f"({ms})")
    rev = sorted(sessions(page, "revision"))
    check("[données] puzzles : sept lignes domaine revision, success 1", rev == sorted((f"puzzle:{i}", 1) for i in FIXTURE_IDS), f"({rev})")
    drill = [s for k, s in sessions(page, "opening-drill") if k == f"full:w:{GORING}"]
    check("[données] variante : recordDrill (échec semé puis réussite)", drill == [0, 1], f"({drill})")
    check("[données] puzzleAttempts intact (aucune ligne ajoutée, Elo puzzle inchangé)", len(db_rows(page, "puzzleAttempts")) == len(SEED["puzzleAttempts"])
          and all(r["key"] != "puzzle" for r in db_rows(page, "ratings")))

    # --- Après les séances : plus rien de dû aujourd'hui ---
    page.goto(f"{BASE}/#/")
    if ck.appears("[accueil] compte connu", page, "[data-review-ready]", timeout=10000):
        check("[accueil] carte masquée quand rien n'est dû", page.locator("main a", has_text="À réviser aujourd'hui").count() == 0)
    page.goto(f"{BASE}/#/apprendre")
    if ck.appears("[apprendre] ligne « Révision espacée »", page, "main a:has-text('Révision espacée')", timeout=10000):
        row = page.locator("main a", has_text="Révision espacée")
        check("[apprendre] « Rien à réviser aujourd'hui », prochaine demain", "Rien à réviser aujourd'hui" in row.inner_text() and "demain" in row.inner_text(), f"({row.inner_text()!r})")
        row.scroll_into_view_if_needed()
        shot(page, "revision_learn_row_852")
        row.click()
        page.wait_for_timeout(600)
    else:
        page.goto(f"{BASE}/#/revision")
        page.wait_for_timeout(600)
    if ck.appears("[vide] écran « Rien à réviser aujourd'hui »", page, "text=Rien à réviser aujourd'hui", timeout=5000):
        nxt = page.locator("[data-review-next-due]").first.inner_text() if page.locator("[data-review-next-due]").count() else ""
        check("[vide] prochaine échéance : demain, 3 éléments (faute ratée aujourd'hui, L12, L13)", "demain" in nxt and "3 " in nxt, f"({nxt!r})")
        check("[vide] aucun débordement horizontal", overflow_x(page) == 0)
        shot(page, "revision_empty_852")
        if ck.appears("[vide] lien « Retour à Apprendre » (returnTo d'Apprendre)", page, "main a:has-text('Retour à Apprendre')", timeout=3000):
            page.locator("main a", has_text="Retour à Apprendre").click()
            page.wait_for_timeout(500)
            check("[vide] retour sur #/apprendre", page.evaluate("() => location.hash") == "#/apprendre")
    ctx.close()


def part_orphan(p, browser):
    """Un puzzle dû dont l'id n'est plus dans puzzles.json : compté sur l'accueil (IndexedDB seul),
    écarté de la séance avec un message honnête, jamais supprimé."""
    ctx, page = seeded(p, browser, seed=ORPHAN_SEED)
    page.goto(f"{BASE}/#/")
    if ck.appears("[orphelin] carte sur l'accueil (compte sans puzzles.json)", page, "main a:has-text(\"À réviser aujourd'hui\")", timeout=10000):
        badge = page.locator("[data-review-count]")
        check("[orphelin] compteur 1 (le puzzle dû demain n'y est pas)", badge.count() == 1 and badge.first.inner_text().strip() == "1")
        page.locator("main a", has_text="À réviser aujourd'hui").click()
        if ck.appears("[orphelin] message « introuvable » à la place de la séance", page, "[data-review-missing]", timeout=10000):
            txt = page.locator("[data-review-missing]").inner_text()
            check("[orphelin] « 1 élément à réviser est introuvable », ignoré", "1 élément à réviser est introuvable" in txt and "ignoré" in txt, f"({txt!r})")
            check("[orphelin] pas de fausse « prochaine révision » (un puzzle est pourtant dû demain)", page.locator("[data-review-next-due]").count() == 0)
        check("[orphelin] les lignes restent en base (jamais supprimées)", len(db_rows(page, "puzzleAttempts")) == 2)
    ctx.close()


def part_layouts(p, browser):
    """Carte de l'accueil et premier item à 393x660 et 1440x900 : rien ne déborde, rien ne défile."""
    for tag, kw in (("660", {"standalone": False}), ("desktop", {"desktop": True})):
        ctx, page = seeded(p, browser, **kw)
        page.goto(f"{BASE}/#/")
        if ck.appears(f"[{tag}] carte sur l'accueil", page, "main a:has-text(\"À réviser aujourd'hui\")", timeout=10000):
            check(f"[{tag}] accueil sans débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
            # L'accueil tient sans défiler, CTA Jouer compris : la carte ne pousse rien sous le pli.
            sc = page.evaluate("() => { const m = document.querySelector('main'); return m.scrollHeight - m.clientHeight }")
            check(f"[{tag}] accueil sans défilement vertical (Jouer visible en entier)", sc <= 0, f"({sc} px de trop)")
            card = page.locator("main a", has_text="À réviser aujourd'hui").bounding_box()
            check(f"[{tag}] carte entièrement visible", card is not None and card["y"] >= 0 and card["y"] + card["height"] <= page.viewport_size["height"], f"({card})")
            shot(page, f"revision_home_{tag}")
            page.locator("main a", has_text="À réviser aujourd'hui").click()
            kind = item_kind(page)
            check(f"[{tag}] séance ouverte", kind is not None, f"({kind})")
            check(f"[{tag}] séance sans débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
            board = page.locator("[id^='chessboard-']").first
            bb = board.bounding_box() if board.count() else None
            check(f"[{tag}] échiquier visible en entier", bb is not None and bb["y"] >= 0 and bb["y"] + bb["height"] <= page.viewport_size["height"], f"({bb})")
            shot(page, f"revision_session_{tag}")
        ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    part_home_and_session(p, browser)
    part_orphan(p, browser)
    part_layouts(p, browser)
    browser.close()


ck.run(suite)
