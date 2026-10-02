"""E2E « coquille » (App.tsx) : onglets sans empilement d'historique, scroll remis à zéro,
frontière d'erreur, route inconnue, onglet actif sur /rush et /import, nav basse accessible.

Usage : npm run test:e2e -- --suite shell
"""
from helpers import BASE, Checker, desktop_context, mobile_context, scroll_state, shot

ck = Checker("shell")
check = ck.check

TABS = [("Jouer", "#/jouer"), ("Puzzles", "#/puzzles"), ("Apprendre", "#/apprendre"),
        ("Analyse", "#/analyse"), ("Archive", "#/archive"), ("Stats", "#/stats")]

# Crash de rendu provoqué SANS dépendre d'un bug de page : `useSearchParams` (Analyse)
# construit un `URLSearchParams` à chaque rendu ; quand `window.__E2E_BOOM` est armé, le
# constructeur lève, donc le rendu d'Analyse plante là où une frontière doit l'attraper.
# Le prototype natif est conservé pour les `instanceof` de react-router. Le même script
# espionne `console.error` : la frontière doit laisser l'erreur visible en console.
# Mode 'apres-replace' (armé via sessionStorage, consommé au chargement) : Analyse ne plante
# qu'une fois son `navigate('.', { replace, state: null })` de montage passé (state vidé dans
# l'historique) et tant que l'écran de secours n'est pas affiché, c'est-à-dire au rendu qui
# suit le chargement de la partie, pas à un remontage de la page vide.
BOOM = """
(() => {
  const Native = window.URLSearchParams
  if (location.protocol.startsWith('http')) {
    const mode = sessionStorage.getItem('__E2E_BOOM')
    sessionStorage.removeItem('__E2E_BOOM')
    if (mode) window.__E2E_BOOM = mode
  }
  function Boom(init) {
    const boom = window.__E2E_BOOM
    if (boom === true) throw new Error('E2E_BOOM_URLSEARCHPARAMS')
    if (boom === 'apres-replace' && history.state?.usr == null &&
        !document.body.textContent.includes('Cette page a rencontré un problème')) {
      throw new Error('E2E_BOOM_URLSEARCHPARAMS')
    }
    return new Native(init)
  }
  Boom.prototype = Native.prototype
  window.URLSearchParams = Boom
  window.__errs = []
  const original = console.error.bind(console)
  console.error = (...args) => { window.__errs.push(args.map(String).join(' ')); original(...args) }
})()
"""
FALLBACK = "text=Cette page a rencontré un problème"


def tab(page, label):
    """Onglet visible portant ce libellé (la nav latérale est masquée sur mobile, la basse sur desktop)."""
    return page.locator("nav a", has_text=label).locator("visible=true")


def active_tab(page):
    """Libellés des onglets visibles portant `aria-current` (attendu : exactement un)."""
    return page.locator("nav a[aria-current]").locator("visible=true").all_inner_texts()


def hist(page):
    return scroll_state(page)["historyLength"]


def go(page, path):
    page.goto(f"{BASE}/{path}")
    page.wait_for_timeout(700)


def hash_of(page):
    return page.evaluate("() => location.hash")


def tabs_do_not_stack(page, tag):
    """TOUCH-6 : 6 onglets d'affilée, `history.length` ne bouge pas, l'onglet tapé est le seul actif."""
    go(page, "#/")
    before = hist(page)
    for label, expected in TABS:
        tab(page, label).click()
        page.wait_for_timeout(400)
        check(f"[{tag}] onglet {label} -> {expected}", hash_of(page) == expected, f"({hash_of(page)})")
        check(f"[{tag}] onglet {label} : history.length stable", hist(page) == before, f"({before} -> {hist(page)})")
        actives = active_tab(page)
        check(f"[{tag}] onglet {label} : seul aria-current", len(actives) == 1 and label in actives[0], f"({actives})")


def suite(p):
    browser = p.chromium.launch(headless=True)

    # ---------- iPhone, PWA installée ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(BOOM)
    page = ctx.new_page()
    tabs_do_not_stack(page, "touch-6 mobile")

    # Descente empilée : une tuile de l'accueil reste un push (le swipe-back a une cible),
    # et /rush allume l'onglet Puzzles (GLOB-6).
    go(page, "#/")
    before = hist(page)
    page.locator("main a", has_text="Puzzle Rush").click()
    page.wait_for_timeout(600)
    check("[push] tuile Puzzle Rush -> #/rush", hash_of(page) == "#/rush")
    check("[push] tuile Puzzle Rush empile une entrée", hist(page) == before + 1, f"({before} -> {hist(page)})")
    actives = active_tab(page)
    check("[glob-6] /rush allume Puzzles", len(actives) == 1 and "Puzzles" in actives[0], f"({actives})")
    check("[glob-6] /rush : aria-current='true' (route rattachée)",
          tab(page, "Puzzles").get_attribute("aria-current") == "true")
    page.go_back()
    page.wait_for_timeout(500)
    check("[push] retour arrière -> accueil", hash_of(page) == "#/")
    go(page, "#/import")
    actives = active_tab(page)
    check("[glob-6] /import allume Analyse", len(actives) == 1 and "Analyse" in actives[0], f"({actives})")
    go(page, "#/apprendre/")
    actives = active_tab(page)
    check("[glob-6] barre finale : #/apprendre/ allume Apprendre", len(actives) == 1 and "Apprendre" in actives[0], f"({actives})")

    # GLOB-7 : route inconnue -> accueil, en replace (pas d'entrée fantôme au retour arrière).
    go(page, "#/stats")
    before = hist(page)
    go(page, "#/nimporte")
    check("[glob-7] route inconnue -> #/", hash_of(page) == "#/", f"({hash_of(page)})")
    check("[glob-7] accueil rendu", page.locator("text=Résolvez !").is_visible())
    check("[glob-7] redirection en replace", hist(page) == before + 1, f"({before} -> {hist(page)})")
    page.go_back()
    page.wait_for_timeout(500)
    check("[glob-7] retour arrière ne rebondit pas sur la route inconnue", hash_of(page) == "#/stats", f"({hash_of(page)})")

    # GLOB-9 minimal : 7 cibles de 44 px, nav nommée, icônes masquées aux lecteurs d'écran.
    links = page.locator("nav a").locator("visible=true")
    check("[glob-9] 7 onglets visibles", links.count() == 7, f"({links.count()})")
    boxes = [links.nth(i).bounding_box() for i in range(links.count())]
    check("[glob-9] cibles >= 44x44", all(b and b["height"] >= 44 and b["width"] >= 44 for b in boxes),
          f"({[(round(b['width']), round(b['height'])) for b in boxes if b]})")
    check("[glob-9] nav basse nommée", page.locator("nav[aria-label]").locator("visible=true").count() == 1)
    check("[glob-9] icônes aria-hidden", page.locator("nav a [aria-hidden='true']").locator("visible=true").count() == 7)
    shot(page, "shell_nav_mobile")

    # Frontière d'erreur : crash de rendu d'Analyse -> écran de secours, nav utilisable,
    # reset au changement de route, « Revenir à l'accueil », « Recharger ».
    go(page, "#/")
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        tab(page, "Analyse").click()
        ck.appears("[boundary] écran de secours affiché", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    check("[boundary] nav toujours utilisable (7 onglets)", page.locator("nav a").locator("visible=true").count() == 7)
    errs = page.evaluate("() => window.__errs")
    check("[boundary] erreur conservée en console.error", any("E2E_BOOM" in e for e in errs), f"({len(errs)} messages)")
    shot(page, "shell_boundary")
    tab(page, "Stats").click()
    page.wait_for_timeout(500)
    check("[boundary] changement de route : page suivante rendue", page.locator("h1", has_text="Statistiques").is_visible())
    check("[boundary] changement de route : secours disparu", page.locator(FALLBACK).count() == 0)
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        tab(page, "Analyse").click()
        ck.appears("[boundary] second crash -> secours", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    tab(page, "Analyse").click()
    ck.appears("[boundary] re-tap de l'onglet courant relance la page", page, "[id^='chessboard-']", timeout=5000)
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        tab(page, "Stats").click()
        page.wait_for_timeout(300)
        tab(page, "Analyse").click()
        ck.appears("[boundary] troisième crash -> secours", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    page.get_by_role("button", name="Revenir à l'accueil").click()
    page.wait_for_timeout(500)
    check("[boundary] Revenir à l'accueil -> #/", hash_of(page) == "#/", f"({hash_of(page)})")
    check("[boundary] accueil rendu après secours", page.locator("text=Résolvez !").is_visible())
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        tab(page, "Analyse").click()
        ck.appears("[boundary] crash avant Recharger", page, FALLBACK, timeout=5000)
        page.wait_for_timeout(200)
    page.get_by_role("button", name="Recharger").click()
    page.wait_for_timeout(1500)
    check("[boundary] Recharger : le drapeau ne survit pas", page.evaluate("() => window.__E2E_BOOM") is None)
    ck.appears("[boundary] Recharger rend Analyse", page, "[id^='chessboard-']", timeout=5000)

    # Crash au rendu qui suit le chargement d'une partie par state de navigation : le
    # `navigate('.', { replace, state: null })` de montage d'Analyse change `location.key`
    # sans changer de chemin, il ne doit pas réarmer la frontière (sinon Analyse est remontée
    # vide et la partie envoyée disparaît sans message). Avec React 19, le rendu planté est
    # rejoué de façon synchrone avec toutes les mises à jour en attente, transition du routeur
    # comprise : ce check fige le contrat plus qu'il ne reproduit un échec observé.
    go(page, "#/")
    page.evaluate("""() => {
      sessionStorage.setItem('__E2E_BOOM', 'apres-replace')
      history.replaceState({ usr: { pgn: '1. e4 e5 2. Nf3 Nc6', label: 'E2E' }, key: 'e2e', idx: 0 }, '', '#/analyse')
    }""")
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.reload()
        ck.appears("[boundary] crash après le chargement par state -> secours", page, FALLBACK, timeout=5000)
        page.wait_for_timeout(1000)
        check("[boundary] navigate('.', replace) de la page : secours maintenu", page.locator(FALLBACK).is_visible())
        check("[boundary] navigate('.', replace) de la page : state consommé, chemin inchangé",
              hash_of(page) == "#/analyse" and page.evaluate("() => history.state?.usr == null"), f"({hash_of(page)})")
        page.evaluate("() => { window.__E2E_BOOM = false }")
    tab(page, "Analyse").click()
    ck.appears("[boundary] re-tap après crash au chargement relance Analyse", page, "[id^='chessboard-']", timeout=5000)

    # Le check précédent passe aussi avec `resetKey={location.key}` (rendu rejoué avec la
    # transition). Celui-ci échoue avec : navigation de même chemin en replace APRÈS l'affichage
    # du secours (nouvelle `location.key`, `pathname` inchangé), le secours doit rester.
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        tab(page, "Stats").click()
        page.wait_for_timeout(300)
        tab(page, "Analyse").click()
        ck.appears("[boundary] crash avant navigation de même chemin", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    page.evaluate("() => location.replace(location.href.split('#')[0] + '#/analyse?e2e=1')")
    page.wait_for_timeout(1000)
    check("[boundary] navigation de même chemin (replace) : secours maintenu",
          hash_of(page) == "#/analyse?e2e=1" and page.locator(FALLBACK).is_visible(), f"({hash_of(page)})")
    ctx.close()

    # ---------- iPhone dans Safari (393x660) : TOUCH-4 ----------
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    go(page, "#/stats")
    page.evaluate("() => { document.querySelector('main').scrollTop = 9999 }")
    page.wait_for_timeout(200)
    st = scroll_state(page)
    check("[touch-4] précondition : Stats défile et est défilée", st["mainScrollable"] and st["mainScrollTop"] > 0, f"({st})")
    tab(page, "Jouer").click()
    page.wait_for_timeout(500)
    st = scroll_state(page)
    check("[touch-4] scroll remis à zéro sur la nouvelle route", st["hash"] == "#/jouer" and st["mainScrollTop"] == 0, f"({st})")
    ctx.close()

    # ---------- Desktop : nav latérale, mêmes règles ----------
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    tabs_do_not_stack(page, "touch-6 desktop")
    check("[glob-9] nav latérale nommée", page.locator("nav[aria-label]").locator("visible=true").count() == 1)
    ctx.close()
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
