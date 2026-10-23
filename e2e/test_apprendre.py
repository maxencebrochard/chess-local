"""E2E « Apprendre » en hub guidé (lot 5 du plan UX) : structure, budget de taps, retours et liste
des moments critiques.

- hub, Toutes les leçons, Entraînement, chaque groupe, Réviser mes parties et la liste des moments
  critiques aux trois formats (393x660 PWA avec zones sûres émulées, 393x852, 1440x900) : titre,
  cartes de 44 px au moins, aucun débordement, captures `apprendre_*` ;
- budget : chaque fonction d'Apprendre atteinte en quatre taps au plus depuis l'Accueil, l'onglet
  Apprendre compris (mesuré en tapant le chemin, pas déclaré), et chaque route propriété
  d'Apprendre atteinte par au moins un chemin ;
- retours : chaque page ouverte par son lien direct ramène à son hub (le groupe propriétaire),
  un cours ouvert depuis un groupe ramène au groupe, une séance lancée depuis un groupe y revient ;
- moments critiques : bilans semés dans `reviews`, liste par partie, état issu de
  `critical-moment`, exercice ouvert avec le state du bilan, retour vers la liste (y compris après
  rechargement), état vide explicite et état de chargement.

Usage : npm run test:e2e -- --suite apprendre
"""
import json

from helpers import BASE, SHOTS, Checker, desktop_context, mobile_context, overflow_x, wait_js
from moment_fixtures import FENS_A, FENS_B, FOUND_B, GAME_A, GAME_B, GAME_C, MISS_B, MOMENT_A, NOW, SESSIONS  # noqa: F401

ck = Checker("apprendre")
check = ck.check

SAFE_TOP, SAFE_BOTTOM = 59, 34
STORES = 7

# Un mat en 1 portant tous les thèmes (même méthode que test_learn) : toute séance Tactiques ou
# Stratégie se construit sans charger les 16 Mo de puzzles.
PUZZLES = json.dumps([["L10", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8", 1000,
                       "fork pin skewer mateIn1 mateIn2 backRankMate hangingPiece sacrifice deflection attraction "
                       "promotion intermezzo defensiveMove rookEndgame pawnEndgame zugzwang exposedKing kingsideAttack "
                       "quietMove middlegame advantage crushing endgame opening short long"]])

GROUPS = {
    "tactique": "Tactique et calcul", "attaque-defense": "Attaque et défense", "finales": "Finales",
    "ouvertures": "Ouvertures", "strategie": "Stratégie",
}

OPEN_DB = f"""
() => new Promise((res, rej) => {{
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {{
    const db = r.result
    if (db.objectStoreNames.length !== {STORES}) {{ db.close(); rej(new Error('schéma inattendu')); return }}
    res(db)
  }}
  r.onerror = () => rej(r.error)
}})
"""


def wait_schema(page, tries=60):
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
        if n == STORES:
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


# Une faute non résolue : active la carte Mes erreurs (budget de taps).
MISTAKE = {"date": NOW, "gameLabel": "Partie test", "fenBefore": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
           "playedSan": "f6", "bestUci": "b8c6", "cls": "mistake", "attempts": 0, "solved": 0}


# ---------------------------------------------------------------- outils
def formats(p, browser):
    """(nom, fabrique de contexte) des trois formats de référence."""
    def m660():
        ctx = mobile_context(p, browser, ck, standalone=True, viewport={"width": 393, "height": 660}, service_workers="block")
        return ctx, True

    def m852():
        return mobile_context(p, browser, ck, standalone=True, service_workers="block"), False

    def desk():
        return desktop_context(browser, ck, service_workers="block"), False

    return [("393x660", m660), ("393x852", m852), ("1440x900", desk)]


def new_page(ctx, safe):
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=PUZZLES))
    page = ctx.new_page()
    if safe:
        page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM}})
    return page


def go(page, path):
    page.goto(f"{BASE}/#{path}")


def hash_of(page):
    return page.evaluate("() => location.hash")


def at(page, route, timeout=10000):
    """Vrai dès que l'URL est exactement `#<route>` (sans requête)."""
    return wait_js(page, "(r) => location.hash.split('?')[0] === '#' + r", timeout=timeout, arg=route)


LAYOUT = """() => {
  const main = document.querySelector('main')
  const targets = [...main.querySelectorAll('a, button')].filter((e) => e.offsetParent !== null)
  const small = targets.filter((e) => { const r = e.getBoundingClientRect(); return r.height < 44 || r.width < 44 })
    .map((e) => (e.getAttribute('aria-label') || e.textContent).trim().slice(0, 40))
  const clipped = [...main.querySelectorAll('h1, h2, p, span')].filter((e) => e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1
    && getComputedStyle(e).overflow !== 'visible').map((e) => e.textContent.trim().slice(0, 40))
  const h1 = main.querySelector('h1')
  return { small, clipped, h1: h1 ? h1.textContent.trim() : null, cards: targets.length }
}"""


def layout(page, tag, title):
    m = page.evaluate(LAYOUT)
    check(f"[{tag}] titre « {title} »", m["h1"] == title, f"({m['h1']!r})")
    check(f"[{tag}] cibles de 44 px au moins", not m["small"], f"({m['small']})")
    check(f"[{tag}] aucun texte coupé", not m["clipped"], f"({m['clipped']})")
    check(f"[{tag}] aucun débordement horizontal", overflow_x(page) == 0)
    return m


# ---------------------------------------------------------------- structure aux trois formats
def structure(p, browser):
    for fmt, make in formats(p, browser):
        ctx, safe = make()
        page = new_page(ctx, safe)
        go(page, "/apprendre")
        if not ck.appears(f"[{fmt}] hub Apprendre", page, "[data-testid=path-hero]", timeout=20000):
            ctx.close()
            continue
        if not check(f"[{fmt}] base prête", wait_schema(page)):
            ctx.close()
            continue
        seed_db(page, {"reviews": [GAME_A, GAME_B, GAME_C], "learnSessions": SESSIONS, "mistakes": [MISTAKE]})
        go(page, "/apprendre")
        ck.appears(f"[{fmt}] hub relu", page, "[data-testid=path-hero-progress]")
        layout(page, f"{fmt} hub", "Apprendre")
        order = page.evaluate("() => [...document.querySelectorAll('main a, main button')].map((e) => e.dataset.testid || e.dataset.learn || e.textContent.trim())")
        check(f"[{fmt} hub] parcours, leçons, entraînement, révision puis séance rapide",
              order == ["path-hero", "lecons", "entrainement", "mes-parties", "Séance rapide"], f"({order})")
        if safe:
            hero = page.locator("[data-testid=path-hero]").bounding_box()
            check(f"[{fmt} hub] parcours sous la zone sûre et visible sans défiler", hero and hero["y"] >= SAFE_TOP and hero["y"] + hero["height"] <= 660 - SAFE_BOTTOM - 48,
                  f"({hero})")
        page.screenshot(path=f"{SHOTS}/apprendre_hub_{fmt}.png", full_page=True)

        go(page, "/apprendre/lecons")
        if ck.appears(f"[{fmt}] Toutes les leçons", page, "[data-testid=defense-card-progress]", timeout=20000):
            layout(page, f"{fmt} leçons", "Toutes les leçons")
            sections = page.locator("main section h2").all_inner_texts()
            check(f"[{fmt} leçons] cours rangés par sujet", sections == ["Débuter", "Finales", "Attaque et défense", "Stratégie"], f"({sections})")
            courses = page.evaluate("() => [...document.querySelectorAll('main [data-course]')].map((e) => e.dataset.course)")
            check(f"[{fmt} leçons] cinq cours dans l'ordre", courses == ["bases", "finales", "roque", "defense", "structures"], f"({courses})")
            page.screenshot(path=f"{SHOTS}/apprendre_lecons_{fmt}.png", full_page=True)

        go(page, "/apprendre/entrainement")
        if ck.appears(f"[{fmt}] Entraînement", page, "main a[data-group]", timeout=20000):
            layout(page, f"{fmt} entraînement", "Entraînement")
            groups = page.evaluate("() => [...document.querySelectorAll('main a[data-group]')].map((e) => [e.dataset.group, e.querySelector('.ui-card-title').textContent, !!e.querySelector('.ui-card-description')])")
            check(f"[{fmt} entraînement] cinq groupes dans l'ordre, chacun avec son objectif",
                  [g[0] for g in groups] == list(GROUPS) and [g[1] for g in groups] == list(GROUPS.values()) and all(g[2] for g in groups), f"({groups})")
            # Au plus une information de progression par groupe ; profil sans séance : aucune.
            progress = page.evaluate("() => [...document.querySelectorAll('main a[data-group]')].map((e) => e.querySelectorAll('[data-group-progress]').length)")
            check(f"[{fmt} entraînement] aucune progression inventée sur un profil neuf", progress == [0] * 5, f"({progress})")
            check(f"[{fmt} entraînement] section « À partir de mes parties »", page.locator("main h2", has_text="À partir de mes parties").count() == 1
                  and page.locator("main a[data-learn=mes-parties]").count() == 1)
            check(f"[{fmt} entraînement] sous-modes absents du hub", page.locator("main [data-session]").count() == 0
                  and page.locator("main a[href='#/convertir']").count() == 0)
            page.screenshot(path=f"{SHOTS}/apprendre_entrainement_{fmt}.png", full_page=True)

        for slug, title in GROUPS.items():
            go(page, f"/apprendre/entrainement/{slug}")
            if ck.appears(f"[{fmt}] groupe {slug}", page, "main h2:has-text(\"S'entraîner\")", timeout=20000):
                layout(page, f"{fmt} {slug}", title)
                page.screenshot(path=f"{SHOTS}/apprendre_groupe_{slug}_{fmt}.png", full_page=True)

        go(page, "/apprendre/mes-parties")
        if ck.appears(f"[{fmt}] Réviser mes parties", page, "[data-testid=moments-card][data-count='3']", timeout=20000):
            page.wait_for_selector("[data-testid=mistakes-card][data-count='1']", timeout=10000)
            layout(page, f"{fmt} mes-parties", "Réviser mes parties")
            page.screenshot(path=f"{SHOTS}/apprendre_mes_parties_{fmt}.png", full_page=True)

        go(page, "/apprendre/moments-critiques")
        if ck.appears(f"[{fmt}] liste des moments", page, "[data-testid=moment-item]", timeout=20000):
            layout(page, f"{fmt} moments", "Moments critiques")
            page.screenshot(path=f"{SHOTS}/apprendre_moments_{fmt}.png", full_page=True)
        ctx.close()


# ---------------------------------------------------------------- budget de taps
def tap(page, selector):
    loc = page.locator(selector).locator("visible=true").first
    loc.wait_for(state="visible", timeout=15000)
    loc.click()


ROUTES_OWNED = [
    "/apprendre/parcours", "/apprendre/lecons", "/apprendre/bases", "/apprendre/finales", "/apprendre/roque",
    "/apprendre/defense", "/apprendre/structures", "/apprendre/entrainement", "/visualisation", "/mats",
    "/attaque", "/defense", "/convertir", "/finales", "/finales/chrono", "/ouvertures", "/repertoire", "/structures",
    "/apprendre/mes-parties", "/revision", "/attaques-manquees", "/defenses-ratees", "/apprendre/moments-critiques",
    "/moment-critique",
]
SESSION = "button[aria-label='Quitter la séance']"


def budget_table():
    """(fonction, sélecteurs tapés après l'onglet Apprendre, route attendue, marqueur ou None)."""
    learn, train, mine = "main a[data-learn=lecons]", "main a[data-learn=entrainement]", "main a[data-learn=mes-parties]"
    rows = [
        ("Parcours", ["[data-testid=path-hero]"], "/apprendre/parcours", None),
        ("Toutes les leçons", [learn], "/apprendre/lecons", None),
        ("Séance rapide", ["main button:has-text('Séance rapide')"], "/apprendre", SESSION),
        ("Entraînement", [train], "/apprendre/entrainement", None),
        ("Réviser mes parties", [mine], "/apprendre/mes-parties", None),
        ("Révision espacée", [mine, "main a[href='#/revision']"], "/revision", None),
        ("Mes erreurs", [mine, "[data-testid=mistakes-card]"], "/apprendre", SESSION),
        ("Mes attaques manquées", [mine, "[data-testid=missed-attacks-card]"], "/attaques-manquees", None),
        ("Mes défenses ratées", [mine, "[data-testid=missed-defenses-card]"], "/defenses-ratees", None),
        ("Moments critiques", [mine, "[data-testid=moments-card]"], "/apprendre/moments-critiques", None),
        ("Moment critique (exercice)", [mine, "[data-testid=moments-card]", "[data-testid=moment-item]"], "/moment-critique", "[data-testid=position-game]"),
    ]
    for slug in ("bases", "finales", "roque", "defense", "structures"):
        rows.append((f"Cours {slug}", [learn, f"main [data-course={slug}]"], f"/apprendre/{slug}", None))
    hrefs = {
        "tactique": [("session", "tactic"), "/visualisation", "/mats"],
        "attaque-defense": ["/attaque", "/defense", "/convertir", "/apprendre/roque", "/apprendre/defense"],
        "finales": [("session", "endgame"), "/finales", "/finales/chrono", "/apprendre/finales"],
        "ouvertures": [("session", "opening"), "/ouvertures", "/repertoire"],
        "strategie": [("session", "strategy"), "/structures", "/apprendre/structures"],
    }
    for slug, items in hrefs.items():
        group = f"main a[data-group={slug}]"
        rows.append((GROUPS[slug], [train, group], f"/apprendre/entrainement/{slug}", None))
        for it in items:
            if isinstance(it, tuple):
                rows.append((f"{GROUPS[slug]} : séance", [train, group, f"main [data-session={it[1]}]"], "/apprendre", SESSION))
            else:
                rows.append((f"{GROUPS[slug]} : {it}", [train, group, f"main a[href='#{it}']"], it, None))
    return rows


def budget(p, browser):
    ctx = mobile_context(p, browser, ck, service_workers="block")
    page = new_page(ctx, False)
    go(page, "/")
    if not check("[budget] base prête", wait_schema(page)):
        ctx.close()
        return
    seed_db(page, {"reviews": [GAME_A, GAME_B], "mistakes": [MISTAKE]})
    reached = set()
    worst = 0
    for name, steps, route, marker in budget_table():
        go(page, "/")
        page.wait_for_selector("nav a[data-nav-tab=apprendre] >> visible=true", timeout=15000)
        try:
            tap(page, "nav a[data-nav-tab=apprendre]")
            for s in steps:
                tap(page, s)
            ok = True
        except Exception as e:  # sélecteur absent : le chemin n'existe pas
            ok = check(f"[budget] {name} : chemin tapé", False, f"({type(e).__name__}: {str(e)[:120]})")
        if not ok:
            continue
        taps = 1 + len(steps)
        worst = max(worst, taps)
        arrived = at(page, route, 15000)
        if marker:
            ck.appears(f"[budget] {name} : écran affiché", page, marker, timeout=20000)
        got = hash_of(page).split("?")[0][1:]
        if check(f"[budget] {name} en {taps} taps (≤ 4) → {route}", arrived and got == route and taps <= 4, f"({got}, {taps} taps)"):
            reached.add(route)
        if marker == SESSION and page.locator(SESSION).count():
            page.locator(SESSION).click()
    missing = [r for r in ROUTES_OWNED if r not in reached]
    check("[budget] chaque route d'Apprendre atteinte par un chemin mesuré", not missing, f"(manquantes : {missing})")
    print(f"[mesure] budget : {len(budget_table())} fonctions, pire chemin {worst} taps depuis l'Accueil", flush=True)
    ctx.close()


# ---------------------------------------------------------------- retours
BACKS = [
    ("/apprendre/lecons", "Apprendre", "/apprendre"),
    ("/apprendre/entrainement", "Apprendre", "/apprendre"),
    ("/apprendre/mes-parties", "Apprendre", "/apprendre"),
    ("/apprendre/entrainement/finales", "Entraînement", "/apprendre/entrainement"),
    ("/apprendre/moments-critiques", "Réviser mes parties", "/apprendre/mes-parties"),
    ("/attaque", "Attaque et défense", "/apprendre/entrainement/attaque-defense"),
    ("/defense", "Attaque et défense", "/apprendre/entrainement/attaque-defense"),
    ("/convertir", "Attaque et défense", "/apprendre/entrainement/attaque-defense"),
    ("/finales", "Finales", "/apprendre/entrainement/finales"),
    ("/finales/chrono", "Finales", "/apprendre/entrainement/finales"),
    ("/ouvertures", "Ouvertures", "/apprendre/entrainement/ouvertures"),
    ("/repertoire", "Ouvertures", "/apprendre/entrainement/ouvertures"),
    ("/visualisation", "Tactique et calcul", "/apprendre/entrainement/tactique"),
    ("/structures", "Stratégie", "/apprendre/entrainement/strategie"),
    ("/attaques-manquees", "Réviser mes parties", "/apprendre/mes-parties"),
    ("/defenses-ratees", "Réviser mes parties", "/apprendre/mes-parties"),
    ("/apprendre/finales", "Toutes les leçons", "/apprendre/lecons"),
    ("/apprendre/structures", "Toutes les leçons", "/apprendre/lecons"),
]


def backs(p, browser):
    ctx = mobile_context(p, browser, ck, service_workers="block")
    page = new_page(ctx, False)
    for path, label, target in BACKS:
        go(page, path)
        btn = page.get_by_role("button", name=f"Retour à {label}", exact=True)
        if not ck.appears(f"[retour] {path} : « Retour à {label} »", page, f"main button[aria-label=\"Retour à {label}\"]", timeout=20000):
            continue
        btn.first.click()
        ok = at(page, target)
        check(f"[retour] {path} → {target}", ok and hash_of(page) == f"#{target}", f"({hash_of(page)})")

    # Groupe inconnu : retour déterministe au hub, sans page vide.
    go(page, "/apprendre/entrainement/inconnu")
    ok = at(page, "/apprendre/entrainement")
    check("[retour] groupe inconnu → Entraînement (replace)", ok)

    # Cours ouvert depuis un groupe : son retour ramène au groupe, même après une leçon.
    go(page, "/apprendre/entrainement/finales")
    tap(page, "main a[href='#/apprendre/finales']")
    if ck.appears("[retour] cours depuis Finales : « Retour à Finales »", page, "main button[aria-label='Retour à Finales']", timeout=20000):
        tap(page, "main [data-lesson]")
        ck.appears("[retour] leçon ouverte", page, "[data-testid=lesson-step]", timeout=20000)
        page.locator("button[aria-label='Fermer la leçon']").click()  # ✕ de la leçon : retour au sommaire
        ck.appears("[retour] sommaire après la leçon : retour toujours vers Finales", page, "main button[aria-label='Retour à Finales']", timeout=20000)
        page.locator("main button[aria-label='Retour à Finales']").click()
        ok = at(page, "/apprendre/entrainement/finales")
        check("[retour] cours → groupe Finales", ok, f"({hash_of(page)})")

    # Mats éclair ouvert depuis Tactique et calcul : retour nommé vers le groupe.
    go(page, "/apprendre/entrainement/tactique")
    tap(page, "main a[href='#/mats']")
    if ck.appears("[retour] Mats éclair depuis le groupe : « Retour à Tactique et calcul »", page, "main button[aria-label='Retour à Tactique et calcul']", timeout=20000):
        page.locator("main button[aria-label='Retour à Tactique et calcul']").click()
        ok = at(page, "/apprendre/entrainement/tactique")
        check("[retour] Mats éclair → groupe Tactique et calcul", ok, f"({hash_of(page)})")

    # Révision ouverte depuis Réviser mes parties : son lien de sortie y ramène.
    go(page, "/apprendre/mes-parties")
    tap(page, "main a[href='#/revision']")
    if ck.appears("[retour] révision vide : « Retour à Réviser mes parties »", page, "main a:has-text('Retour à Réviser mes parties')", timeout=20000):
        page.locator("main a", has_text="Retour à Réviser mes parties").click()
        ok = at(page, "/apprendre/mes-parties")
        check("[retour] révision → Réviser mes parties", ok, f"({hash_of(page)})")

    # Séance lancée depuis un groupe : ✕ ramène au groupe, sans entrée d'historique en double.
    go(page, "/apprendre/entrainement")
    tap(page, "main a[data-group=finales]")
    page.wait_for_selector("main [data-session=endgame]", timeout=15000)
    before = page.evaluate("() => history.length")
    tap(page, "main [data-session=endgame]")
    if ck.appears("[séance] séance Finales ouverte depuis le groupe", page, SESSION, timeout=20000):
        check("[séance] URL #/apprendre pendant la séance", hash_of(page) == "#/apprendre", f"({hash_of(page)})")
        check("[séance] titre du domaine", "Finales" in page.locator("header h1").first.inner_text())
        page.locator(SESSION).click()
        ok = at(page, "/apprendre/entrainement/finales")
        check("[séance] ✕ ramène au groupe Finales", ok, f"({hash_of(page)})")
        check("[séance] historique inchangé (replace à l'aller et au retour)", page.evaluate("() => history.length") == before,
              f"({before} → {page.evaluate('() => history.length')})")
        page.go_back()
        ok = at(page, "/apprendre/entrainement")
        check("[séance] retour arrière depuis le groupe : Entraînement", ok, f"({hash_of(page)})")
    ctx.close()


# ---------------------------------------------------------------- liste des moments critiques
SEEN_LOADING = """
(() => {
  window.__momentsLoading = false
  new MutationObserver(() => {
    if (document.querySelector('[data-testid=moments-loading]')) window.__momentsLoading = true
  }).observe(document, { childList: true, subtree: true })
})()
"""


def moments(p, browser):
    # --- État vide, avec l'état de chargement observé avant lui ---
    ctx = mobile_context(p, browser, ck, service_workers="block")
    ctx.add_init_script(SEEN_LOADING)
    page = new_page(ctx, False)
    go(page, "/apprendre/moments-critiques")
    if ck.appears("[moments vide] état vide explicite", page, "[data-testid=moments-empty]", timeout=20000):
        empty = page.locator("[data-testid=moments-empty]")
        check("[moments vide] titre « Analyse une partie pour voir ses moments critiques »",
              empty.locator("h2").inner_text() == "Analyse une partie pour voir ses moments critiques")
        link = empty.locator("a")
        check("[moments vide] lien d'action vers Mon bilan", link.count() == 1 and link.get_attribute("href") == "#/insights" and link.inner_text() == "Ouvrir Mon bilan",
              f"({link.get_attribute('href') if link.count() else None})")
        check("[moments vide] état de chargement affiché d'abord", page.evaluate("() => window.__momentsLoading") is True)
        check("[moments vide] plus de chargement une fois lu", page.locator("[data-testid=moments-loading]").count() == 0)
        check("[moments vide] aucune entrée", page.locator("[data-testid=moment-item]").count() == 0)
        page.screenshot(path=f"{SHOTS}/apprendre_moments_vide.png", full_page=True)
    # Lien direct vers l'exercice sans moment : renvoi vers la liste (écart 12 du lot 0).
    go(page, "/moment-critique")
    if ck.appears("[moments vide] /moment-critique sans moment : lien vers la liste", page, "main a:has-text('Voir mes moments critiques')", timeout=20000):
        check("[moments vide] le lien vise la liste", page.locator("main a", has_text="Voir mes moments critiques").get_attribute("href") == "#/apprendre/moments-critiques")
    ctx.close()

    # --- Bilans semés ---
    ctx = mobile_context(p, browser, ck, service_workers="block")
    page = new_page(ctx, False)
    go(page, "/apprendre/mes-parties")
    if not check("[moments] base prête", wait_schema(page)):
        ctx.close()
        return
    seed_db(page, {"reviews": [GAME_A, GAME_B, GAME_C], "learnSessions": SESSIONS})
    go(page, "/apprendre/mes-parties")
    tap(page, "[data-testid=moments-card]")
    if not ck.appears("[moments] liste affichée", page, "[data-testid=moment-item]", timeout=20000):
        ctx.close()
        return
    games = page.evaluate("() => [...document.querySelectorAll('[data-testid=moments-game]')].map((g) => [g.dataset.key, [...g.querySelectorAll('[data-testid=moment-item]')].map((m) => [m.dataset.fen, m.dataset.best, m.dataset.status])])")
    check("[moments] deux parties, la plus récente d'abord, sans la partie sans bascule",
          [g[0] for g in games] == ["chesscom:555", "local:7"], f"({[g[0] for g in games]})")
    if len(games) == 2:
        check("[moments] chess.com : coup unique trouvé puis bascule, positions exactes",
              [m[:2] for m in games[0][1]] == [[FOUND_B, "b8c6"], [MISS_B, "g8f6"]], f"({games[0][1]})")
        check("[moments] partie de l'app : la bascule 4. Fxf7+, meilleur coup d3", [m[:2] for m in games[1][1]] == [[MOMENT_A, "d2d3"]], f"({games[1][1]})")
        check("[moments] état issu de critical-moment : retrouvé, à faire, manqué",
              [m[2] for m in games[0][1]] + [m[2] for m in games[1][1]] == ["found", "", "missed"], f"({games})")
    text = page.locator("main").inner_text()
    check("[moments] en-tête de partie : adversaire et résultat", "Contre Rival (1200)" in text and "Victoire · chess.com" in text and "Défaite · ChessLocal" in text, f"({text[:300]!r})")
    check("[moments] libellés « ✓ Retrouvé » et « ✗ Manqué »", "✓ Retrouvé" in text and "✗ Manqué" in text)
    check("[moments] résumé « 3 moments dans 2 parties »", page.locator("[data-testid=moments-summary]").inner_text().startswith("3 moments dans 2 parties"))
    check("[moments] aucune écriture en base à la lecture", page.evaluate(
        "async () => { const db = await (" + OPEN_DB + ")(); const n = await new Promise((r) => { const q = db.transaction('learnSessions').objectStore('learnSessions').count(); q.onsuccess = () => r(q.result) }); db.close(); return n }") == len(SESSIONS))

    # --- Exercice ouvert depuis la liste, avec le state du bilan ---
    before = page.evaluate("() => history.length")
    page.locator(f"[data-testid=moment-item][data-fen='{MOMENT_A}']").click()
    if ck.appears("[moments] exercice ouvert", page, "[data-testid=position-game]", timeout=20000):
        check("[moments] URL #/moment-critique", hash_of(page) == "#/moment-critique", f"({hash_of(page)})")
        check("[moments] titre du moment (coup 4)", page.locator("[data-testid=position-game] h1").inner_text() == "Moment critique · coup 4",
              f"({page.locator('[data-testid=position-game] h1').inner_text()!r})")
        stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-position-game-v1') || 'null')")
        back = (stored or {}).get("back") or {}
        analysis = back.get("analysis") or {}
        check("[moments] partie persistée : position du moment et origine « liste »",
              stored and stored.get("startFen") == MOMENT_A and back.get("from") == "liste", f"({stored and stored.get('startFen')}, {back.get('from')})")
        check("[moments] state du bilan : clé de partie game:7, camp, retour vers la liste",
              analysis.get("bilan", {}).get("gameKey") == "game:7" and analysis.get("color") == "w"
              and analysis.get("returnTo") == "/apprendre/moments-critiques" and analysis.get("returnLabel") == "Retour aux moments critiques",
              f"({analysis.get('bilan', {}).get('gameKey')}, {analysis.get('color')}, {analysis.get('returnTo')})")
        check("[moments] state du bilan : PGN rejouable coup pour coup", "Bxf7+" in analysis.get("pgn", "") and "[White \"qa_user\"]" in analysis.get("pgn", ""),
              f"({analysis.get('pgn', '')[:120]!r})")
        check("[moments] descente en replace (historique inchangé)", page.evaluate("() => history.length") == before)
        # Rechargement : la partie persistée garde son origine, la sortie ramène toujours à la liste.
        page.reload()
        ck.appears("[moments] exercice repris après rechargement", page, "[data-testid=position-game]", timeout=20000)
        page.locator("[data-testid=position-game] header button[aria-label=Retour]").click()
        ok = at(page, "/apprendre/moments-critiques")
        check("[moments] retour de l'exercice vers la liste", ok, f"({hash_of(page)})")
        ck.appears("[moments] liste réaffichée", page, "[data-testid=moment-item]", timeout=20000)
        # Aucun coup joué : pas de partie « en cours » (inProgressKey), l'état reste celui de la base.
        check("[moments] état du moment inchangé sans coup joué", page.locator(f"[data-testid=moment-item][data-fen='{MOMENT_A}'][data-status=missed]").count() == 1)
        # Seconde ouverture sans rechargement : même sortie.
        page.locator(f"[data-testid=moment-item][data-fen='{MISS_B}']").click()
        if ck.appears("[moments] second exercice ouvert", page, "[data-testid=position-game]", timeout=20000):
            check("[moments] second exercice : camp noir en bas", page.locator("[data-testid=position-game] h1").inner_text() == "Moment critique · coup 3...")
            page.locator("[data-testid=position-game] header button[aria-label=Retour]").click()
            ok = at(page, "/apprendre/moments-critiques")
            check("[moments] retour direct vers la liste", ok, f"({hash_of(page)})")
    page.screenshot(path=f"{SHOTS}/apprendre_moments_retour.png", full_page=True)
    # Retour de la liste : Réviser mes parties.
    if ck.appears("[moments] retour d'en-tête de la liste", page, "main button[aria-label='Retour à Réviser mes parties']", timeout=10000):
        page.locator("main button[aria-label='Retour à Réviser mes parties']").click()
        ok = at(page, "/apprendre/mes-parties")
        check("[moments] liste → Réviser mes parties", ok, f"({hash_of(page)})")
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    moments(p, browser)
    backs(p, browser)
    budget(p, browser)
    structure(p, browser)
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
