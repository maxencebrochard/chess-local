"""E2E « viewport » : le document ne défile jamais, seule la zone de contenu défile.

Bug iPhone (PWA standalone, intermittent) : un geste vers le haut ou vers le bas décalait
TOUTE l'app (en-tête sous l'heure, nav basse remontée sur une bande vide). Ce n'était pas
`<main>` qui défilait, c'était le document : la fenêtre restait défilable par l'utilisateur,
son rebond n'était pas coupé (`overscroll-behavior` posé sur body, que le viewport ignore) et
`<main>` en butée chaînait le geste vers elle.

Chromium n'a ni rebond élastique ni décalage « coincé » d'iOS : la suite prouve la cause
structurelle, pas le rendu exact du téléphone.
- structure : html/body non défilables, rebond du viewport coupé, `<main>` en
  `overscroll-behavior: contain`, coquille exactement à la taille du viewport, sans débordement
  horizontal, safe areas appliquées (émulées à 59/34 px en standalone via CDP) ;
- le helper `overflow_x` des autres suites reste capable d'échouer avec body fixé : preuve par
  des débordements provoqués dans body, les calques fixes et les scrollers verticaux ;
- gestes TACTILES réels (CDP) dans les deux sens, sur la nav, sur `<main>` en butée haute et
  basse avec poursuite au-delà, et sur une page dont le contenu tient : avec un débordement du
  document provoqué exprès (ce qu'iOS produit quand sa zone visible ne colle pas à la mise en
  page), aucun geste ne doit bouger le document, l'en-tête ou la nav.

Usage : npm run test:e2e -- --suite viewport
"""
from helpers import BASE, FINALES, Checker, desktop_context, mobile_context, overflow_x, shot, touch_drag

ck = Checker("viewport")
check = ck.check

SAFE_TOP, SAFE_BOTTOM = 59, 34
# Pages qui défilent dans `<main>` ou non : la liste couvre les deux (mesuré sur main :
# `/`, `/analyse`, `/puzzles` en 393x852 tiennent sans défiler).
PAGES = ["/", "/mats", "/mats?d=geo-diagonale-ligne", "/apprendre", "/analyse", "/jouer", "/puzzles", "/stats", "/revision"]
# Débordement provoqué : un élément ajouté en fin de `host`, retiré par `remove_injected`. En
# hauteur sur body, c'est le débordement du document (ce qu'iOS produit quand sa zone visible ne
# colle pas à la mise en page) : sans lui, Chromium n'a nulle part où chaîner le geste et tous
# les gestes passeraient aussi sur l'ancien code.
TALL = "height: 400px; width: 1px"
WIDE = "width: 600px; height: 1px"


def inject(page, host, css):
    page.evaluate(
        """([host, css]) => {
          const d = document.createElement('div')
          d.dataset.e2e = 'overflow'
          d.style.cssText = css
          document.querySelector(host).appendChild(d)
        }""",
        [host, css],
    )


def remove_injected(page):
    page.evaluate("() => { for (const d of document.querySelectorAll('[data-e2e=overflow]')) d.remove(); window.scrollTo(0, 0) }")


STATE = """() => {
  const m = document.querySelector('main')
  const nav = [...document.querySelectorAll('nav')].find((n) => n.offsetParent && getComputedStyle(n).display !== 'none' && n.getBoundingClientRect().top > 0)
  const cs = (e) => getComputedStyle(e)
  return {
    inner: innerHeight,
    scrollY: Math.round(scrollY),
    vvTop: Math.round(visualViewport.offsetTop),
    docOverflow: document.scrollingElement.scrollHeight - innerHeight,
    htmlOverflow: cs(document.documentElement).overflowY,
    bodyOverflow: cs(document.body).overflowY,
    viewportOverscroll: cs(document.documentElement).overscrollBehaviorY,
    mainOverscroll: cs(m).overscrollBehaviorY,
    mainTop: Math.round(m.getBoundingClientRect().top),
    mainPadTop: cs(m).paddingTop,
    mainScrollTop: Math.round(m.scrollTop),
    mainMax: m.scrollHeight - m.clientHeight,
    navTop: nav ? Math.round(nav.getBoundingClientRect().top) : null,
    navBottom: nav ? Math.round(nav.getBoundingClientRect().bottom) : null,
    navPadBottom: nav ? cs(nav).paddingBottom : null,
  }
}"""


def state(page):
    return page.evaluate(STATE)


def same_frame(label, before, after):
    """Le geste ne doit bouger ni le document, ni le viewport visuel, ni l'en-tête, ni la nav."""
    keys = ("scrollY", "vvTop", "mainTop", "navTop", "navBottom")
    moved = {k: (before[k], after[k]) for k in keys if before[k] != after[k]}
    check(f"{label} : document, en-tête et nav immobiles", not moved, f"({moved})" if moved else "")


# Point de départ d'un geste : un élément de `<main>` qui laisse défiler (pas l'échiquier en
# `touch-action: none`, qui avalerait le geste et ferait passer le check sans rien prouver).
FREE_POINT = """([x, hint, lo, hi]) => {
  const free = (y) => {
    let el = document.elementFromPoint(x, y)
    if (!el || !el.closest('main') || el.closest('.boardbox')) return false
    for (; el; el = el.parentElement) {
      const t = getComputedStyle(el).touchAction
      if (t !== 'auto' && !t.includes('pan-y') && t !== 'manipulation') return false
    }
    return true
  }
  for (let d = 0; d <= hi - lo; d += 4) {
    for (const y of [hint - d, hint + d]) if (y >= lo && y <= hi && free(y)) return y
  }
  return null
}"""


def settle(page):
    """Attend la fin de l'inertie : document et `<main>` immobiles sur deux lectures."""
    last = None
    for _ in range(12):
        cur = page.evaluate("() => [scrollY, document.querySelector('main').scrollTop]")
        if cur == last:
            return
        last = cur
        page.wait_for_timeout(150)


def stable_layout(page):
    """Attend que la hauteur de `<main>` ne bouge plus (Dexie, puzzles.json chargés après coup)."""
    last = None
    for _ in range(20):
        cur = page.evaluate("() => document.querySelector('main').scrollHeight")
        if cur == last:
            return
        last = cur
        page.wait_for_timeout(250)


def gesture(page, label, x, hint, dy, lo, hi):
    """Geste tactile depuis un point libre de `<main>` proche de `hint`. Faux si aucun point."""
    y = page.evaluate(FREE_POINT, [x, hint, lo, hi])
    if not check(f"{label} : point de départ hors échiquier", y is not None, f"(x {x}, autour de {hint})"):
        return False
    touch_drag(page, x, y, x, y + dy, steps=20)
    settle(page)
    return True


def page_suite(page, label, path, standalone, slug):
    page.goto(f"{BASE}/#{path}")
    ck.appears(f"{label} : page affichée", page, "main >> *")
    stable_layout(page)
    # `/mats` -> `/mats?d=...` garde le chemin : `<main>` n'est pas remis en haut par la coquille.
    page.evaluate("() => document.querySelector('main').scrollTo(0, 0)")
    s = state(page)
    h = s["inner"]

    # Structure.
    check(f"{label} : html ne défile pas", s["htmlOverflow"] == "hidden", f"(overflow-y {s['htmlOverflow']})")
    check(f"{label} : body ne défile pas", s["bodyOverflow"] == "hidden", f"(overflow-y {s['bodyOverflow']})")
    check(f"{label} : rebond du viewport coupé (overscroll-behavior sur html)",
          s["viewportOverscroll"] == "none", f"({s['viewportOverscroll']})")
    check(f"{label} : <main> ne chaîne pas son défilement", s["mainOverscroll"] == "contain", f"({s['mainOverscroll']})")
    check(f"{label} : document sans débordement", s["docOverflow"] == 0, f"({s['docOverflow']} px)")
    check(f"{label} : en-tête collé en haut", s["mainTop"] == 0, f"(top {s['mainTop']})")
    check(f"{label} : nav collée en bas", s["navBottom"] == h, f"(bottom {s['navBottom']}, viewport {h})")
    check(f"{label} : pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    if standalone:
        check(f"{label} : safe area haute appliquée", s["mainPadTop"] == f"{SAFE_TOP + 12}px", f"({s['mainPadTop']})")
        check(f"{label} : safe area basse appliquée", s["navPadBottom"] == f"{SAFE_BOTTOM}px", f"({s['navPadBottom']})")

    shot(page, f"viewport_{slug}")

    # Débordement provoqué : sur l'ancien code, le document devient défilable et les gestes
    # en butée de `<main>` s'y chaînent.
    inject(page, "body", TALL)
    page.evaluate("() => window.scrollTo(0, 150)")
    try:
        page.wait_for_timeout(100)
        base = state(page)
        check(f"{label} : document immobile même s'il déborde (scrollTo sans effet)", base["scrollY"] == 0,
              f"(scrollY {base['scrollY']})")
        nav_y = (base["navTop"] + base["navBottom"]) / 2
        lo, hi = base["mainTop"] + 80, base["navTop"] - 10  # zone de `<main>` visible
        x = 30

        # Nav basse (hors zone défilante), vers le haut puis vers le bas.
        b = state(page)
        touch_drag(page, 200, nav_y, 200, nav_y - 300)
        settle(page)
        same_frame(f"{label} : geste vers le haut sur la nav", b, state(page))
        b = state(page)
        touch_drag(page, 200, nav_y - 300, 200, nav_y)
        settle(page)
        same_frame(f"{label} : geste vers le bas sur la nav", b, state(page))

        # `<main>` en haut, geste vers le bas (doigt qui descend) poursuivi au-delà.
        page.evaluate("() => document.querySelector('main').scrollTo(0, 0)")
        b = state(page)
        if gesture(page, f"{label} : <main> en haut", x, lo + 40, 400, lo, hi):
            a = state(page)
            same_frame(f"{label} : <main> en haut, geste vers le bas au-delà", b, a)
            check(f"{label} : <main> reste en haut", a["mainScrollTop"] == 0, f"(scrollTop {a['mainScrollTop']})")

        # `<main>` en bas, geste vers le haut (doigt qui monte) poursuivi au-delà.
        page.evaluate("() => document.querySelector('main').scrollTo(0, 1e6)")
        b = state(page)
        if gesture(page, f"{label} : <main> en bas", x, hi - 40, -400, lo, hi):
            a = state(page)
            same_frame(f"{label} : <main> en bas, geste vers le haut au-delà", b, a)
            check(f"{label} : <main> reste en bas", a["mainScrollTop"] == a["mainMax"],
                  f"(scrollTop {a['mainScrollTop']} / {a['mainMax']})")

        if base["mainMax"] > 0:
            # Geste qui commence par défiler `<main>` puis continue au-delà de la butée.
            page.evaluate("() => { const m = document.querySelector('main'); m.scrollTo(0, m.scrollHeight - m.clientHeight - 60) }")
            b = state(page)
            if gesture(page, f"{label} : fin de <main>", x, hi - 20, -450, lo, hi):
                same_frame(f"{label} : geste qui finit <main> puis continue", b, state(page))
            # Témoin positif : le pipeline tactile vit et `<main>` défile toujours.
            page.evaluate("() => document.querySelector('main').scrollTo(0, 0)")
            if gesture(page, f"{label} : témoin", x, hi - 20, -250, lo, hi):
                after = state(page)
                check(f"{label} : <main> défile toujours au doigt", after["mainScrollTop"] > 0,
                      f"(scrollTop {after['mainScrollTop']})")
    finally:
        remove_injected(page)


def overflow_x_suite(page, label):
    """Chaque branche détecte un débordement provoqué, puis revient à zéro."""
    page.goto(f"{BASE}/#/")
    ck.appears(f"{label} : page affichée", page, "main >> *")
    try:
        inject(page, "main", WIDE)
        check(f"{label} : un élément trop large dans <main> est détecté", overflow_x(page) > 0, f"({overflow_x(page)} px)")
        remove_injected(page)
        check(f"{label} : <main> sans débordement après retrait", overflow_x(page) == 0)
        inject(page, "#root", f"{WIDE}; position: absolute; left: 0; top: 0")
        check(f"{label} : un élément qui s'échappe de la coquille est détecté", overflow_x(page) > 0, f"({overflow_x(page)} px)")
    finally:
        remove_injected(page)
    check(f"{label} : plus rien une fois retiré", overflow_x(page) == 0, f"({overflow_x(page)} px)")

    page.evaluate("""() => {
      const strip = document.createElement('div')
      strip.dataset.e2e = 'overflow'
      strip.className = 'overflow-x-auto'
      strip.innerHTML = '<div style="width:600px;height:1px"></div>'
      document.querySelector('main').appendChild(strip)
    }""")
    try:
        check(f"{label} : bande réellement défilable", page.locator("[data-e2e=overflow]").evaluate("e => e.scrollWidth > e.clientWidth"))
        check(f"{label} : bande horizontale volontaire exclue", overflow_x(page) == 0)
    finally:
        remove_injected(page)

    page.goto(f"{BASE}/#/apprendre/finales/mat-deux-tours")
    if not ck.appears(f"{label} : calque de leçon ouvert", page, "button[aria-label='Fermer la leçon']"):
        return
    for host, name in (("main > .fixed", "calque fixe"), ("main > .fixed .overflow-y-auto", "scroller interne")):
        check(f"{label} : {name} sans débordement initial", overflow_x(page) == 0)
        try:
            inject(page, host, WIDE)
            check(f"{label} : débordement du {name} détecté", overflow_x(page) > 0)
        finally:
            remove_injected(page)
        check(f"{label} : {name} sans débordement après retrait", overflow_x(page) == 0)


def badge_suite(page, label):
    for orientation in ("w", "b"):
        page.goto(f"{BASE}/#/analyse")
        if not ck.appears(f"{label} : analyse ouverte", page, "[id^=chessboard-]"):
            continue
        page.evaluate("""(color) => history.replaceState({ ...history.state, usr: {
          pgn: '1. h3 a6 2. g3 b6 *', color, review: true
        } }, '', location.href)""", orientation)
        page.reload()
        if not ck.appears(f"{label} {orientation} : bilan calculé", page, "text=Démarrer le bilan", timeout=240000):
            continue
        page.click("text=Démarrer le bilan")
        for san, square, edge in (("h3", "h3", orientation == "w"), ("a6", "a6", orientation == "b"),
                                  ("g3", "g3", False), ("b6", "b6", False)):
            page.locator(".fixed button[data-current]", has_text=san).first.click()
            badge = page.locator(".boardbox .pointer-events-none.absolute.z-10")
            box = badge.bounding_box()
            cell = page.locator(f".boardbox [data-square='{square}']").first.bounding_box()
            check(f"{label} {orientation} {san} : pastille visible", box is not None and cell is not None)
            if box and cell:
                right = box["x"] + box["width"]
                expected = cell["x"] + cell["width"] + (0 if edge else box["width"] * 0.4)
                check(f"{label} {orientation} {san} : placement de la pastille", abs(right - expected) < 1)
                check(f"{label} {orientation} {san} : pastille dans le viewport", box["x"] >= 0 and right <= page.viewport_size["width"])
            check(f"{label} {orientation} {san} : aucun débordement", overflow_x(page) == 0)


SHEET = "div.fixed .overflow-y-auto"


def sheet_suite(page, label):
    """Feuille modale (cours d'Apprendre) : elle défile, et en butée le geste ne se chaîne pas
    vers le document. C'est la seule chose à lire derrière elle : le calque de la feuille est
    `fixed`, son bloc conteneur est le viewport, et Chromium chaîne le défilement le long des
    blocs conteneurs, donc vers le document et jamais vers `<main>` ni vers la racine de séance
    qui l'entourent dans le DOM. Sonde : sans `contain`, la racine de séance pré-défilée reste à
    40 px avec l'ancien CSS comme avec le nouveau, alors que le document bouge avec l'ancien
    (de 150 à 0 px, puis à 285 px)."""
    page.goto(f"{BASE}/#/apprendre")
    ck.appears(f"{label} : accueil Apprendre", page, "main button:has-text('Finales')")
    page.locator("main button", has_text=FINALES).click()
    if not ck.appears(f"{label} : leçon affichée", page, "text=Voir le cours complet"):
        return
    page.click("text=Voir le cours complet")
    if not ck.appears(f"{label} : feuille ouverte", page, SHEET):
        return
    page.wait_for_timeout(400)
    ob = page.evaluate(f"() => getComputedStyle(document.querySelector('{SHEET}')).overscrollBehaviorY")
    check(f"{label} : la feuille ne chaîne pas son défilement", ob == "contain", f"({ob})")
    inject(page, "body", TALL)
    try:
        page.evaluate("() => window.scrollTo(0, 150)")
        box = page.locator(SHEET).bounding_box()
        x = box["x"] + 12
        read = f"() => [Math.round(scrollY), Math.round(document.querySelector('{SHEET}').scrollTop)]"
        b = page.evaluate(read)
        # Feuille en haut, geste vers le bas au-delà.
        touch_drag(page, x, box["y"] + 20, x, box["y"] + 20 + 300, steps=20)
        settle(page)
        a = page.evaluate(read)
        check(f"{label} : feuille en haut, geste vers le bas : le document ne bouge pas", a[0] == b[0], f"({b} -> {a})")
        # Feuille en bas, geste vers le haut au-delà.
        page.evaluate(f"() => document.querySelector('{SHEET}').scrollTo(0, 1e6)")
        b = page.evaluate(read)
        y0 = box["y"] + box["height"] - 20
        touch_drag(page, x, y0, x, y0 - 300, steps=20)
        settle(page)
        a = page.evaluate(read)
        check(f"{label} : feuille en bas, geste vers le haut : le document ne bouge pas", a[0] == b[0], f"({b} -> {a})")
        # Témoin positif : la feuille défile au doigt.
        page.evaluate(f"() => document.querySelector('{SHEET}').scrollTo(0, 0)")
        touch_drag(page, x, y0, x, y0 - 200, steps=14)
        settle(page)
        top = page.evaluate(f"() => document.querySelector('{SHEET}').scrollTop")
        check(f"{label} : la feuille défile toujours au doigt", top > 0, f"(scrollTop {top})")
    finally:
        remove_injected(page)


def desktop_suite(p, browser):
    """1440x900 : nav latérale, même règle (document fixe, `<main>` à la hauteur du viewport)."""
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    for path in ("/", "/stats", "/analyse"):
        label = f"[1440x900] {path}"
        page.goto(f"{BASE}/#{path}")
        ck.appears(f"{label} : page affichée", page, "main >> *")
        stable_layout(page)
        d = page.evaluate("""() => {
          const m = document.querySelector('main').getBoundingClientRect()
          const side = [...document.querySelectorAll('nav')].find((n) => getComputedStyle(n).display !== 'none')
          return { over: document.scrollingElement.scrollHeight - innerHeight, top: m.top, bottom: m.bottom,
                   inner: innerHeight, side: side ? Math.round(side.getBoundingClientRect().height) : null }
        }""")
        check(f"{label} : document sans débordement", d["over"] == 0, f"({d['over']} px)")
        check(f"{label} : pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        check(f"{label} : <main> à la hauteur du viewport", d["top"] == 0 and d["bottom"] == d["inner"], f"({d})")
        check(f"{label} : nav latérale sur toute la hauteur", d["side"] == d["inner"], f"({d['side']})")
    shot(page, "viewport_1440x900_analyse")
    ctx.close()


def suite(p):
    browser = p.chromium.launch()
    try:
        for standalone in (True, False):
            size = "393x852" if standalone else "393x660"
            ctx = mobile_context(p, browser, ck, standalone=standalone)
            page = ctx.new_page()
            if standalone:
                # PWA installée sur iPhone 14 Pro : Dynamic Island en haut, barre d'accueil en bas.
                cdp = ctx.new_cdp_session(page)
                cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM}})
            for path in PAGES:
                label = f"[{size}] {path}"
                slug = path.strip("/").replace("?", "_").replace("=", "-").replace("/", "_") or "accueil"
                page_suite(page, label, path, standalone, f"{size}_{slug}")
            overflow_x_suite(page, f"[{size}] helper overflow_x")
            badge_suite(page, f"[{size}] pastille")
            sheet_suite(page, f"[{size}] feuille de cours")
            ctx.close()
        desktop_suite(p, browser)
    finally:
        browser.close()


ck.run(suite)
