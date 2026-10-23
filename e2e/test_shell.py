"""E2E « coquille » (App.tsx) : cinq onglets (lot 2 du plan UX) sans empilement d'historique,
onglet allumé sur chaque famille de routes et anciens liens, hub Plus et sous-liste de la nav
latérale, pictogrammes SVG (taille, couleur et aplat actifs mesurés), scroll remis à zéro,
frontière d'erreur, route inconnue, nav accessible aux trois formats.

Usage : npm run test:e2e -- --suite shell
"""
from helpers import BASE, Checker, desktop_context, mobile_context, overflow_x, scroll_state, shot

ck = Checker("shell")
check = ck.check

TABS = [("Jouer", "#/jouer"), ("Puzzles", "#/puzzles"), ("Apprendre", "#/apprendre"),
        ("Plus", "#/plus"), ("Accueil", "#/")]
LABELS = ["Accueil", "Jouer", "Puzzles", "Apprendre", "Plus"]
ACCENT = [129, 182, 76]        # --color-accent, onglet actif de la nav basse
ACCENT_LIGHT = [181, 220, 140]  # --color-accent-light, onglet actif de la nav latérale
SAFE_TOP, SAFE_BOTTOM = 59, 34

# Chaque famille de routes et l'onglet qu'elle allume (« Placement cible de chaque route » du
# lot 0) : "page" sur la racine de l'onglet, "true" sur une route rattachée. Le marqueur prouve
# que l'ancien lien rend toujours sa page (pas de repli vers l'accueil).
DEEP = [
    ("/", "Accueil", "page", "text=Résolvez !"),
    ("/seance", "Accueil", "true", "main h1"),
    ("/jouer", "Jouer", "page", "text=Adversaire"),
    ("/puzzles", "Puzzles", "page", "main >> text=Classement puzzles"),
    ("/rush", "Puzzles", "true", "text=Survie"),
    ("/mats", "Puzzles", "true", "h1:has-text('Mats éclair')"),
    ("/apprendre", "Apprendre", "page", "main h1"),
    ("/apprendre/parcours", "Apprendre", "true", "main h1"),
    ("/ouvertures", "Apprendre", "true", "main h1"),
    ("/repertoire", "Apprendre", "true", "main h1"),
    ("/finales/chrono", "Apprendre", "true", "main h1"),
    ("/revision", "Apprendre", "true", "main h1"),
    ("/attaques-manquees", "Apprendre", "true", "main h1"),
    ("/moment-critique", "Apprendre", "true", "text=Aucun moment critique"),
    ("/apprendre/lecons", "Apprendre", "true", "main h1:text-is('Toutes les leçons')"),
    ("/apprendre/entrainement", "Apprendre", "true", "main h1:text-is('Entraînement')"),
    ("/apprendre/entrainement/finales", "Apprendre", "true", "main h1:text-is('Finales')"),
    ("/apprendre/mes-parties", "Apprendre", "true", "main h1:text-is('Réviser mes parties')"),
    ("/apprendre/moments-critiques", "Apprendre", "true", "main h1:text-is('Moments critiques')"),
    ("/plus", "Plus", "page", "main h1:text-is('Plus')"),
    ("/analyse", "Plus", "true", "[data-board]"),
    ("/analyse/jouer", "Plus", "true", "text=Aucune position"),
    ("/archive", "Plus", "true", "main h1:has-text('Archive')"),
    ("/import", "Plus", "true", "text=Importer depuis"),
    ("/stats", "Plus", "true", "main h1:text-is('Statistiques')"),
    ("/reglages", "Plus", "true", "main h1:text-is('Réglages')"),
    ("/donnees", "Plus", "true", "main h1:has-text('Mes données')"),
    ("/insights", "Plus", "true", "main h1:has-text('Insights')"),
]
# Sous-destination sélectionnée dans la sous-liste de la nav latérale, par route de la famille Plus.
SELECTED = {"/plus": None, "/analyse": "Analyse", "/analyse/jouer": "Analyse", "/archive": "Mes parties",
            "/import": "Importer", "/stats": "Statistiques", "/insights": "Mon bilan",
            "/reglages": "Réglages", "/donnees": "Mes données"}
HUB = [  # (libellé, hash attendu, titre des pages extraites de Stats au lot 3, munies d'un retour vers Plus)
    ("Mes parties", "#/archive", None), ("Importer des parties", "#/import", None),
    ("Analyse", "#/analyse", None), ("Mon bilan", "#/insights", None), ("Statistiques", "#/stats", None),
    ("Réglages", "#/reglages", "main h1:text-is('Réglages')"), ("Mes données", "#/donnees", "main h1:has-text('Mes données')"),
]
# Anciens states de navigation vers les sections de Stats (lot 2 : Plus et nav latérale ; carte de
# migration de l'app native avant le lot 3) : Stats les renvoie vers la page extraite, en replace.
LEGACY = [({"section": "reglages"}, "#/reglages"), ({"section": "donnees"}, "#/donnees"), ({"backup": True}, "#/donnees")]
SUB = ["Mes parties", "Importer", "Analyse", "Mon bilan", "Statistiques", "Réglages", "Mes données"]

# Mesures de la nav visible : onglets, pictogrammes, couleurs résolues par un canvas (Tailwind 4
# écrit les gris en oklch), contraste WCAG contre le fond réel du lien (composé sur la nav).
NAV_METRICS = """() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1
  const g = cv.getContext('2d', { willReadFrequently: true })
  const rgba = (c) => {
    g.clearRect(0, 0, 1, 1); g.fillStyle = '#000'; g.fillStyle = c; g.fillRect(0, 0, 1, 1)
    const d = g.getImageData(0, 0, 1, 1).data
    return [d[0], d[1], d[2], Math.round(d[3] / 255 * 100) / 100]
  }
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])
  }
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05) }
  const over = (top, under) => top[3] >= 1 ? top : [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])).concat(1)
  const shown = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 }
  const nav = [...document.querySelectorAll('nav[aria-label="Navigation principale"]')].find(shown)
  if (!nav) return null
  const navBg = rgba(getComputedStyle(nav).backgroundColor)
  const tabs = [...nav.querySelectorAll('a[data-nav-tab]')].filter(shown).map((a) => {
    const r = a.getBoundingClientRect()
    const svg = a.querySelector('svg')
    const s = svg ? svg.getBoundingClientRect() : null
    const text = [...a.childNodes].find((n) => n.nodeType === 3)
    let lines = 0, labelTop = null
    if (text) {
      const range = document.createRange(); range.selectNodeContents(text)
      const rects = [...range.getClientRects()]
      lines = new Set(rects.map((q) => Math.round(q.top))).size
      labelTop = rects.length ? Math.min(...rects.map((q) => q.top)) : null
    }
    const color = rgba(getComputedStyle(a).color)
    const bg = over(rgba(getComputedStyle(a).backgroundColor), navBg)
    const shapes = svg ? [...svg.querySelectorAll('path, circle, rect, ellipse')] : []
    return {
      label: text ? text.textContent.trim() : '', current: a.getAttribute('aria-current'),
      w: r.width, h: r.height, left: r.left, right: r.right, top: r.top, bottom: r.bottom,
      icon: s && { w: s.width, h: s.height, cx: s.left + s.width / 2, top: s.top, bottom: s.bottom,
        viewBox: svg.getAttribute('viewBox'), strokeWidth: svg.getAttribute('stroke-width'),
        hidden: svg.getAttribute('aria-hidden'), name: svg.dataset.icon },
      lines, labelTop, color, contrast: ratio(color, bg),
      strokesFollowText: shapes.length > 0 && shapes.every((e) => rgba(getComputedStyle(e).stroke).join() === color.join()),
      fills: [...(svg ? svg.querySelectorAll('[data-fill]') : [])].map((e) => {
        const cs = getComputedStyle(e); return { rgba: rgba(cs.fill), opacity: +cs.fillOpacity }
      }),
    }
  })
  const sub = nav.querySelector('[data-nav-sub]')
  return {
    vw: innerWidth, vh: innerHeight, tabs, links: [...nav.querySelectorAll('a')].filter(shown).length,
    currents: [...nav.querySelectorAll('[aria-current]')].filter(shown).length,
    padBottom: getComputedStyle(nav).paddingBottom, navBottom: nav.getBoundingClientRect().bottom,
    sub: sub && shown(sub) ? [...sub.querySelectorAll('a')].map((a) => ({
      label: a.textContent.trim(), selected: a.hasAttribute('data-selected'), current: a.getAttribute('aria-current'),
      h: a.getBoundingClientRect().height, w: a.getBoundingClientRect().width, href: a.getAttribute('href') })) : null,
  }
}"""

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

# Écrit (ou efface, avec None) une ligne de la table Dexie `ratings`, directement dans IndexedDB.
RATING_ROW = """(row) => new Promise((resolve, reject) => {
  const req = indexedDB.open('chess-local')
  req.onerror = () => reject(req.error)
  req.onsuccess = () => {
    const db = req.result
    const tx = db.transaction('ratings', 'readwrite')
    if (row) tx.objectStore('ratings').put(row)
    else tx.objectStore('ratings').delete('rapid')
    tx.oncomplete = () => { db.close(); resolve(true) }
    tx.onerror = () => { db.close(); reject(tx.error) }
  }
})"""


def tab(page, label):
    """Onglet visible portant ce libellé (la nav latérale est masquée sur mobile, la basse sur desktop)."""
    return page.locator("nav a[data-nav-tab]", has_text=label).locator("visible=true")


def active_tab(page):
    """Libellés de TOUS les liens visibles de la nav portant `aria-current` (attendu : exactement
    un, l'onglet : la sous-liste de Plus n'en porte jamais)."""
    return page.locator("nav a[aria-current]").locator("visible=true").all_inner_texts()


def hub_link(page, label):
    """Carte du hub Plus (dans `<main>`), par son titre exact."""
    return page.locator("main a[data-plus]").filter(has=page.locator(".ui-card-title", has_text=label)).first


def hist(page):
    return scroll_state(page)["historyLength"]


def go(page, path):
    page.goto(f"{BASE}/{path}")
    page.wait_for_timeout(700)


def scroll_main_down(page):
    """Fait défiler <main> en bas une fois la page paresseuse montée : sous charge, 700 ms ne
    suffisent pas toujours et un scrollTop posé sur un <main> encore court reste à 0. Si la page
    ne devient jamais défilable, la précondition qui suit échoue proprement."""
    try:
        page.wait_for_function("() => { const m = document.querySelector('main'); return m && m.scrollHeight > m.clientHeight + 100 }", timeout=15000)
    except Exception:
        return
    page.evaluate("() => { document.querySelector('main').scrollTop = 9999 }")


def hash_of(page):
    return page.evaluate("() => location.hash")


def tabs_do_not_stack(page, tag):
    """TOUCH-6 : les 5 onglets d'affilée, `history.length` ne bouge pas, l'onglet tapé est le seul actif."""
    go(page, "#/")
    before = hist(page)
    for label, expected in TABS:
        tab(page, label).click()
        # La navigation est une transition : l'ancien onglet reste allumé tant que la chunk de la
        # page n'est pas chargée. Sous charge, 400 ms ne suffisent pas ; borne à 10 s.
        try:
            page.wait_for_function(
                """([hash, label]) => location.hash === hash && [...document.querySelectorAll('nav a[aria-current]')]
                  .some((a) => a.offsetParent !== null && a.innerText.includes(label))""",
                arg=[expected, label], timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(100)
        check(f"[{tag}] onglet {label} -> {expected}", hash_of(page) == expected, f"({hash_of(page)})")
        check(f"[{tag}] onglet {label} : history.length stable", hist(page) == before, f"({before} -> {hist(page)})")
        actives = active_tab(page)
        check(f"[{tag}] onglet {label} : seul aria-current", len(actives) == 1 and label in actives[0], f"({actives})")


def nav_format(page, tag, desktop=False, safe=False):
    """Cinq onglets exactement, pictogrammes SVG, couleurs actif/inactif mesurées, cibles et
    géométrie, puis l'onglet allumé sur chaque famille de routes (anciens liens compris)."""
    go(page, "#/jouer")
    m = page.evaluate(NAV_METRICS)
    if not check(f"[{tag}] nav visible mesurée", m is not None):
        return
    tabs = m["tabs"]
    check(f"[{tag}] cinq onglets exactement, dans l'ordre", [t["label"] for t in tabs] == LABELS, f"({[t['label'] for t in tabs]})")
    check(f"[{tag}] aucun autre lien dans la nav hors famille Plus", m["links"] == 5, f"({m['links']})")
    check(f"[{tag}] cibles >= 44x44", all(t["w"] >= 44 and t["h"] >= 44 for t in tabs),
          f"({[(round(t['w']), round(t['h'])) for t in tabs]})")
    size = 20 if desktop else 24
    icons = [t["icon"] for t in tabs]
    check(f"[{tag}] un pictogramme SVG par onglet", all(icons), f"({icons})")
    if not all(icons):
        return
    check(f"[{tag}] pictogrammes {size}x{size} px", all(abs(i["w"] - size) < 0.5 and abs(i["h"] - size) < 0.5 for i in icons),
          f"({[(i['w'], i['h']) for i in icons]})")
    check(f"[{tag}] grille 24 et trait 1,75 communs", all(i["viewBox"] == "0 0 24 24" and i["strokeWidth"] == "1.75" for i in icons),
          f"({[(i['viewBox'], i['strokeWidth']) for i in icons]})")
    check(f"[{tag}] pictogrammes masqués aux lecteurs d'écran", all(i["hidden"] == "true" for i in icons))
    check(f"[{tag}] pictogrammes distincts", len({i["name"] for i in icons}) == 5, f"({[i['name'] for i in icons]})")
    check(f"[{tag}] trait du pictogramme = couleur du libellé (currentColor)", all(t["strokesFollowText"] for t in tabs))
    check(f"[{tag}] libellés sur une ligne", all(t["lines"] == 1 for t in tabs), f"({[t['lines'] for t in tabs]})")
    active = [t for t in tabs if t["current"]]
    idle = [t for t in tabs if not t["current"]]
    if check(f"[{tag}] /jouer : un seul onglet actif, Jouer", [t["label"] for t in active] == ["Jouer"], f"({[t['label'] for t in active]})"):
        a = active[0]
        want = ACCENT_LIGHT if desktop else ACCENT
        check(f"[{tag}] couleur active = {'accent-light' if desktop else 'accent'}", a["color"][:3] == want, f"({a['color']})")
        check(f"[{tag}] couleur inactive commune et distincte de l'active",
              len({tuple(t["color"]) for t in idle}) == 1 and idle[0]["color"] != a["color"], f"({[t['color'] for t in idle]})")
        check(f"[{tag}] contraste des libellés et pictogrammes >= 4,5:1", all(t["contrast"] >= 4.5 for t in tabs),
              f"({[round(t['contrast'], 2) for t in tabs]})")
        check(f"[{tag}] aplat actif : formes remplies de la couleur à 22 %",
              a["fills"] and all(f["rgba"][:3] == a["color"][:3] and f["rgba"][3] > 0 and abs(f["opacity"] - 0.22) < 0.01 for f in a["fills"]),
              f"({a['fills']})")
        check(f"[{tag}] onglets inactifs : contour seul", all(f["rgba"][3] == 0 for t in idle for f in t["fills"]),
              f"({[t['fills'] for t in idle]})")
    if not desktop:
        widths = [t["w"] for t in tabs]
        check(f"[{tag}] cinq colonnes égales sur toute la largeur", max(widths) - min(widths) < 1 and abs(sum(widths) - m["vw"]) < 1,
              f"({[round(w, 1) for w in widths]}, vw {m['vw']})")
        check(f"[{tag}] pictogramme centré au-dessus du libellé",
              all(abs(t["icon"]["cx"] - (t["left"] + t["right"]) / 2) <= 1 and t["icon"]["bottom"] <= t["labelTop"] + 1 for t in tabs),
              f"({[(round(t['icon']['cx'] - (t['left'] + t['right']) / 2, 1), round(t['labelTop'] - t['icon']['bottom'], 1)) for t in tabs]})")
        check(f"[{tag}] nav basse collée en bas", abs(m["navBottom"] - m["vh"]) < 1, f"({m['navBottom']} / {m['vh']})")
        if safe:
            check(f"[{tag}] zone sûre basse appliquée", m["padBottom"] == f"{SAFE_BOTTOM}px", f"({m['padBottom']})")
            check(f"[{tag}] onglets au-dessus de l'indicateur d'accueil", all(t["bottom"] <= m["vh"] - SAFE_BOTTOM + 0.5 for t in tabs),
                  f"({[round(t['bottom']) for t in tabs]})")
    check(f"[{tag}] aucun débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    shot(page, f"shell_nav_{tag.replace(' ', '_')}")

    # Familles de routes : un seul `aria-current` dans la nav, sur le bon onglet, avec la bonne valeur.
    for path, label, value, marker in DEEP:
        page.goto(f"{BASE}/#{path}")
        ck.appears(f"[{tag}] {path} : page rendue par l'ancien lien", page, marker, timeout=15000)
        check(f"[{tag}] {path} : URL conservée", hash_of(page) == f"#{path}", f"({hash_of(page)})")
        m = page.evaluate(NAV_METRICS)
        cur = [(t["label"], t["current"]) for t in m["tabs"] if t["current"]]
        check(f"[{tag}] {path} allume {label} ({value})", cur == [(label, value)] and m["currents"] == 1, f"({cur}, {m['currents']} aria-current)")
        if desktop:
            if label == "Plus":
                sub = m["sub"] or []
                check(f"[{tag}] {path} : sous-liste de Plus dépliée", [x["label"] for x in sub] == SUB, f"({[x['label'] for x in sub]})")
                sel = [x["label"] for x in sub if x["selected"]]
                want = SELECTED[path]
                check(f"[{tag}] {path} : sous-destination sélectionnée {want}", sel == ([want] if want else []), f"({sel})")
                check(f"[{tag}] {path} : sous-liste sans aria-current, cibles >= 44 px",
                      all(x["current"] is None and x["h"] >= 44 for x in sub), f"({[(x['current'], round(x['h'])) for x in sub]})")
            else:
                check(f"[{tag}] {path} : sous-liste de Plus repliée", m["sub"] is None)
    if desktop:
        shot(page, f"shell_sidebar_plus_{tag}")


def hub_plus(page, tag):
    """Hub /plus : titre, trois groupes, sept destinations en push ; Réglages et Mes données
    ouvrent leurs pages, dont le retour mène au hub."""
    go(page, "#/plus")
    check(f"[{tag}] hub : titre Plus", page.locator("main h1").inner_text().strip() == "Plus")
    groups = page.locator("main section h2").all_inner_texts()
    check(f"[{tag}] hub : trois groupes", groups == ["Parties", "Outils et progression", "Réglages et données"], f"({groups})")
    titles = page.locator("main a[data-plus] .ui-card-title").all_inner_texts()
    check(f"[{tag}] hub : sept destinations dans l'ordre", titles == [h[0] for h in HUB], f"({titles})")
    descs = page.locator("main a[data-plus] .ui-card-description").all_inner_texts()
    check(f"[{tag}] hub : chaque destination a sa description", len(descs) == 7 and all(d.strip() for d in descs), f"({len(descs)})")
    cards = page.locator("main a[data-plus]")
    boxes = [cards.nth(i).bounding_box() for i in range(cards.count())]
    check(f"[{tag}] hub : cartes >= 44 px de haut", all(b and b["height"] >= 44 for b in boxes))
    check(f"[{tag}] hub : un pictogramme SVG masqué par carte",
          page.locator("main a[data-plus] svg[aria-hidden='true']").count() == 7)
    check(f"[{tag}] hub : aucun débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    shot(page, f"shell_hub_{tag}", full_page=True)
    for label, expected, section in HUB:
        go(page, "#/plus")
        before = hist(page)
        hub_link(page, label).click()
        page.wait_for_timeout(600)
        check(f"[{tag}] hub {label} -> {expected}, descente empilée", hash_of(page) == expected and hist(page) == before + 1,
              f"({hash_of(page)}, {before} -> {hist(page)})")
        actives = active_tab(page)
        check(f"[{tag}] hub {label} : Plus reste allumé", len(actives) == 1 and "Plus" in actives[0], f"({actives})")
        if section:
            ck.appears(f"[{tag}] hub {label} : page rendue", page, section)
            check(f"[{tag}] hub {label} : aucun state de navigation", page.evaluate("() => history.state?.usr == null"))
            back = page.get_by_role("button", name="Retour à Plus", exact=True)
            check(f"[{tag}] hub {label} : retour « Plus » de 44 px", back.count() == 1 and (back.bounding_box() or {}).get("height", 0) >= 44)
            back.click()
            page.wait_for_timeout(500)
            check(f"[{tag}] hub {label} : le retour de la page mène au hub", hash_of(page) == "#/plus", f"({hash_of(page)})")
            page.go_back()
            page.wait_for_timeout(500)
        page.go_back()
        page.wait_for_timeout(500)
        check(f"[{tag}] hub {label} : retour arrière -> hub", hash_of(page) == "#/plus", f"({hash_of(page)})")


def sidebar_plus(page):
    """Nav latérale : sous-liste de Plus en replace, Réglages et Mes données sur leurs pages."""
    go(page, "#/plus")
    before = hist(page)
    sub = page.locator("nav [data-nav-sub] a")
    sub.filter(has_text="Statistiques").click()
    page.wait_for_timeout(600)
    check("[desktop] sous-liste Statistiques -> #/stats en replace", hash_of(page) == "#/stats" and hist(page) == before,
          f"({hash_of(page)}, {before} -> {hist(page)})")
    for label, expected in (("Réglages", "#/reglages"), ("Mes données", "#/donnees")):
        sub.filter(has_text=label).click()
        page.wait_for_timeout(600)
        check(f"[desktop] sous-liste {label} -> {expected}", hash_of(page) == expected, f"({hash_of(page)})")
        check(f"[desktop] sous-liste {label} : history.length stable", hist(page) == before, f"({before} -> {hist(page)})")
        check(f"[desktop] sous-liste {label} sélectionné",
              page.locator("nav [data-nav-sub] a[data-selected]").all_inner_texts() == [label])
    sub.filter(has_text="Mes parties").click()
    page.wait_for_timeout(600)
    check("[desktop] sous-liste Mes parties -> #/archive", hash_of(page) == "#/archive")
    check("[desktop] sélection déplacée sur Mes parties",
          page.locator("nav [data-nav-sub] a[data-selected]").all_inner_texts() == ["Mes parties"])
    shot(page, "shell_sidebar_archive")
    tab(page, "Jouer").click()
    page.wait_for_timeout(400)
    check("[desktop] sous-liste repliée hors de Plus", page.locator("nav [data-nav-sub]").count() == 0)


def legacy_states(page, tag):
    """Un ancien state `section`/`backup` sur /stats (entrée d'historique restaurée, ancienne carte
    de migration) aboutit à la page extraite, en replace, et le state ne survit pas."""
    for state, expected in LEGACY:
        go(page, "#/plus")
        page.evaluate("(usr) => history.replaceState({ usr, key: 'legacy', idx: history.state?.idx ?? 0 }, '', '#/stats')", state)
        before = hist(page)
        page.reload()
        page.wait_for_timeout(1200)
        check(f"[{tag}] ancien state {state} sur /stats -> {expected}", hash_of(page) == expected, f"({hash_of(page)})")
        check(f"[{tag}] ancien state {state} : replace, state effacé",
              hist(page) == before and page.evaluate("() => history.state?.usr == null"), f"({before} -> {hist(page)})")
        actives = active_tab(page)
        check(f"[{tag}] ancien state {state} : Plus allumé", len(actives) == 1 and "Plus" in actives[0], f"({actives})")
    go(page, "#/stats")
    page.wait_for_timeout(600)
    check(f"[{tag}] /stats sans state reste Statistiques", hash_of(page) == "#/stats" and page.locator("main h1").inner_text().strip() == "Statistiques")


def suite(p):
    browser = p.chromium.launch(headless=True)

    # ---------- Trois formats : nav, pictogrammes, familles de routes ----------
    ctx = mobile_context(p, browser, ck, standalone=True, viewport={"width": 393, "height": 660})
    page = ctx.new_page()
    page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM}})
    nav_format(page, "393x660 standalone", safe=True)
    ctx.close()
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    nav_format(page, "393x852")
    hub_plus(page, "393x852")
    legacy_states(page, "393x852")
    ctx.close()
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    nav_format(page, "1440x900", desktop=True)
    hub_plus(page, "1440x900")
    sidebar_plus(page)
    ctx.close()

    # ---------- iPhone, PWA installée ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(BOOM)
    page = ctx.new_page()
    tabs_do_not_stack(page, "touch-6 mobile")

    # Accueil : une tuile vers une racine d'onglet est une navigation d'onglet, en replace (le
    # swipe-back iOS ne ramène pas à l'accueil en pleine partie) ; Puzzle Rush et chess.com
    # (/rush, /import) sont des descentes, empilées. Les tuiles Stats, Analyse et Archive gardent
    # leur replace d'anciennes racines d'onglet : l'accueil est refondu au lot 4.
    for name, loc, expected in (
        ("CTA Jouer", page.get_by_role("button", name="Jouer", exact=True), "#/jouer"),
        ("carte Problèmes", page.locator("main a", has_text="Résolvez"), "#/puzzles"),
        ("carte Rapide", page.locator("main a", has_text="Rapide"), "#/stats"),
        ("tuile Analyse", page.locator("main a", has_text="Stockfish 18"), "#/analyse"),
        ("tuile Archive", page.locator("main a", has_text="Archive"), "#/archive"),
    ):
        go(page, "#/")
        before = hist(page)
        loc.first.click()
        page.wait_for_timeout(600)
        check(f"[accueil] {name} -> {expected}", hash_of(page) == expected, f"({hash_of(page)})")
        check(f"[accueil] {name} : replace, history.length stable", hist(page) == before, f"({before} -> {hist(page)})")
    go(page, "#/")
    before = hist(page)
    page.locator("main a", has_text="Importer tes parties").click()
    page.wait_for_timeout(600)
    check("[push] tuile chess.com -> #/import, empile une entrée", hash_of(page) == "#/import" and hist(page) == before + 1,
          f"({hash_of(page)}, {before} -> {hist(page)})")

    # Descente empilée : la tuile Puzzle Rush reste un push (le swipe-back a une cible),
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

    # GLOB-9 minimal : 5 cibles de 44 px, nav nommée, icônes masquées aux lecteurs d'écran.
    links = page.locator("nav a").locator("visible=true")
    check("[glob-9] 5 onglets visibles", links.count() == 5, f"({links.count()})")
    boxes = [links.nth(i).bounding_box() for i in range(links.count())]
    check("[glob-9] cibles >= 44x44", all(b and b["height"] >= 44 and b["width"] >= 44 for b in boxes),
          f"({[(round(b['width']), round(b['height'])) for b in boxes if b]})")
    check("[glob-9] nav basse nommée", page.locator("nav[aria-label]").locator("visible=true").count() == 1)
    check("[glob-9] icônes aria-hidden", page.locator("nav a svg[aria-hidden='true']").locator("visible=true").count() == 5)
    shot(page, "shell_nav_mobile")

    # Frontière d'erreur : crash de rendu d'Analyse (atteinte par le hub Plus, comme un
    # utilisateur) -> écran de secours, nav utilisable, reset au changement de route,
    # « Revenir à l'accueil », « Recharger ».
    def to_analyse():
        tab(page, "Plus").click()
        page.wait_for_timeout(300)
        hub_link(page, "Analyse").click()

    go(page, "#/")
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        to_analyse()
        ck.appears("[boundary] écran de secours affiché", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    check("[boundary] nav toujours utilisable (5 onglets)", page.locator("nav a").locator("visible=true").count() == 5)
    errs = page.evaluate("() => window.__errs")
    check("[boundary] erreur conservée en console.error", any("E2E_BOOM" in e for e in errs), f"({len(errs)} messages)")
    shot(page, "shell_boundary")
    tab(page, "Plus").click()
    page.wait_for_timeout(500)
    check("[boundary] changement de route : page suivante rendue", page.locator("h1", has_text="Plus").is_visible())
    check("[boundary] changement de route : secours disparu", page.locator(FALLBACK).count() == 0)
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        to_analyse()
        ck.appears("[boundary] second crash -> secours", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    to_analyse()
    ck.appears("[boundary] Plus puis Analyse relance la page", page, "[id^='chessboard-']", timeout=5000)
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        to_analyse()
        ck.appears("[boundary] troisième crash -> secours", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    page.get_by_role("button", name="Revenir à l'accueil").click()
    page.wait_for_timeout(500)
    check("[boundary] Revenir à l'accueil -> #/", hash_of(page) == "#/", f"({hash_of(page)})")
    check("[boundary] accueil rendu après secours", page.locator("text=Résolvez !").is_visible())
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        to_analyse()
        ck.appears("[boundary] crash avant Recharger", page, FALLBACK, timeout=5000)
        page.wait_for_timeout(200)
    page.get_by_role("button", name="Recharger").click()
    page.wait_for_timeout(1500)
    check("[boundary] Recharger : le drapeau ne survit pas", page.evaluate("() => window.__E2E_BOOM") is None)
    ck.appears("[boundary] Recharger rend Analyse", page, "[id^='chessboard-']", timeout=5000)

    # Crash sur l'accueil lui-même : « Revenir à l'accueil » ne change pas de chemin, il doit
    # quand même réarmer la frontière. Crash provoqué par un classement illisible en base (un objet
    # rendu comme texte), réparé avant le tap.
    go(page, "#/stats")
    page.evaluate(RATING_ROW, {"key": "rapid", "value": {"e2e": "boom"}})
    # Message de React 19 en dev, et son code minifié en prod (erreur n° 31).
    with ck.expect_pageerror(("Objects are not valid as a React child", "react.dev/errors/31")):
        tab(page, "Accueil").click()
        ck.appears("[boundary] crash sur l'accueil -> secours", page, FALLBACK, timeout=5000)
        page.wait_for_timeout(200)
        check("[boundary] secours sans bloc technique en anglais", page.locator("main", has_text="Détail technique").count() == 0)
    page.evaluate(RATING_ROW, None)
    # Re-tap de l'onglet courant (Accueil sur l'accueil) : seul geste qui réarme la frontière sans
    # changer de chemin. L'ancien re-tap d'Analyse n'a plus d'onglet depuis le lot 2.
    tab(page, "Accueil").click()
    page.wait_for_timeout(800)
    check("[boundary] re-tap de l'onglet courant relance la page",
          hash_of(page) == "#/" and page.locator("text=Résolvez !").is_visible() and page.locator(FALLBACK).count() == 0,
          f"({hash_of(page)})")
    go(page, "#/stats")
    page.evaluate(RATING_ROW, {"key": "rapid", "value": {"e2e": "boom"}})
    with ck.expect_pageerror(("Objects are not valid as a React child", "react.dev/errors/31")):
        tab(page, "Accueil").click()
        ck.appears("[boundary] second crash sur l'accueil -> secours", page, FALLBACK, timeout=5000)
        page.wait_for_timeout(200)
    page.evaluate(RATING_ROW, None)
    page.get_by_role("button", name="Revenir à l'accueil").click()
    page.wait_for_timeout(800)
    check("[boundary] crash sur l'accueil : Revenir à l'accueil rend l'accueil",
          hash_of(page) == "#/" and page.locator("text=Résolvez !").is_visible() and page.locator(FALLBACK).count() == 0,
          f"({hash_of(page)})")

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
    to_analyse()
    ck.appears("[boundary] Plus puis Analyse après crash au chargement relance Analyse", page, "[id^='chessboard-']", timeout=5000)

    # Le check précédent passe aussi avec `resetKey={location.key}` (rendu rejoué avec la
    # transition). Celui-ci échoue avec : navigation de même chemin en replace APRÈS l'affichage
    # du secours (nouvelle `location.key`, `pathname` inchangé), le secours doit rester.
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        to_analyse()
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
    scroll_main_down(page)
    page.wait_for_timeout(200)
    st = scroll_state(page)
    check("[touch-4] précondition : Stats défile et est défilée", st["mainScrollable"] and st["mainScrollTop"] > 0, f"({st})")
    tab(page, "Jouer").click()
    page.wait_for_timeout(500)
    st = scroll_state(page)
    check("[touch-4] scroll remis à zéro sur la nouvelle route", st["hash"] == "#/jouer" and st["mainScrollTop"] == 0, f"({st})")
    # Même chemin, requête seule changée (fiche de Mats éclair depuis le hub) : un écran nouveau,
    # remis en haut aussi. Par le hash, comme un lien ou un retour arrière.
    go(page, "#/mats")
    scroll_main_down(page)
    page.wait_for_timeout(200)
    st = scroll_state(page)
    check("[touch-4] précondition : /mats défile et est défilé", st["mainScrollable"] and st["mainScrollTop"] > 0, f"({st})")
    page.evaluate("() => { location.hash = '#/mats?d=chrono-kq' }")
    ck.appears("[touch-4] fiche ouverte par la requête", page, "[data-sheet='chrono-kq'] [data-square='a1']", timeout=5000)
    page.wait_for_timeout(300)
    st = scroll_state(page)
    check("[touch-4] scroll remis à zéro quand seule la requête change", st["hash"] == "#/mats?d=chrono-kq" and st["mainScrollable"] and st["mainScrollTop"] == 0, f"({st})")
    ctx.close()

    # ---------- Desktop : nav latérale, mêmes règles ----------
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.add_init_script(BOOM)
    tabs_do_not_stack(page, "touch-6 desktop")
    check("[glob-9] nav latérale nommée", page.locator("nav[aria-label]").locator("visible=true").count() == 1)
    side = page.locator("nav a").locator("visible=true")
    heights = [round(side.nth(i).bounding_box()["height"]) for i in range(side.count())]
    check("[glob-9] nav latérale : 5 cibles de 44 px de haut au moins", len(heights) == 5 and min(heights) >= 44, f"({heights})")
    # Re-tap d'une sous-destination courante (Analyse sur /analyse) : comme un onglet, il réarme
    # la frontière sans changer de chemin.
    go(page, "#/plus")
    with ck.expect_pageerror("E2E_BOOM_URLSEARCHPARAMS"):
        page.evaluate("() => { window.__E2E_BOOM = true }")
        page.locator("nav [data-nav-sub] a", has_text="Analyse").click()
        ck.appears("[boundary desktop] crash d'Analyse -> secours", page, FALLBACK, timeout=5000)
        page.evaluate("() => { window.__E2E_BOOM = false }")
        page.wait_for_timeout(200)
    page.locator("nav [data-nav-sub] a", has_text="Analyse").click()
    ck.appears("[boundary desktop] re-tap de la sous-destination courante relance Analyse", page, "[id^='chessboard-']", timeout=5000)
    ctx.close()
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
