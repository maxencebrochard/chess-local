"""E2E « audit UI » : chaque écran de l'app, sur la cible réelle, passé au crible d'un designer.

Trois profils : la PWA installée sur iPhone 14 Pro (393x852, safe areas émulées à 59/34 px via
CDP), un petit écran (393x660, onglet Safari) et le bureau (1440x900). Pour chaque route et chaque
état important (partie en cours, fin de partie, bilan, feuilles, états vides), la suite capture
l'écran dans `e2e/shots/ui_audit/<profil>/` et mesure, sur ce qui est réellement affiché :
- débordement horizontal (helper `overflow_x`) ;
- texte coupé : un bloc dont le contenu dépasse sa boîte sans points de suspension ;
- cibles tactiles : boutons, liens et champs d'au moins 44x44 px (HIG Apple), sur mobile ;
- contraste WCAG AA : 4,5:1, ou 3:1 pour un grand texte, fond composé depuis la pile des calques peints ;
- typographie française : espace avant « : ; ! ? », espaces dans « », pas de guillemets droits ni
  de tiret cadratin ;
- safe areas en standalone : aucun texte ni élément interactif peint sous l'encoche ou la barre home.

Chaque mesure est un check par écran : une régression fait échouer la suite avec l'élément fautif.
Les exceptions sont nommées dans `ALLOW` avec leur raison.

Usage : npm run test:e2e -- --suite ui_audit
"""
import json
import os
import re

from helpers import BASE, SHOTS, Checker, desktop_context, mobile_context, overflow_x

ck = Checker("ui_audit")
check = ck.check

SAFE_TOP, SAFE_BOTTOM = 59, 34
OUT = os.path.join(SHOTS, "ui_audit")
ONLY = os.environ.get("UI_AUDIT_ONLY")  # filtre facultatif sur le nom d'écran (mise au point)
REPORT = os.environ.get("UI_AUDIT_REPORT")  # chemin facultatif : défauts bruts en JSON
# Preuve par mutation : un défaut de la catégorie est injecté dans chaque écran mesuré, et la suite
# doit passer au rouge (ex. `UI_AUDIT_MUTATION=contrast UI_AUDIT_ONLY=accueil`).
MUTATION = os.environ.get("UI_AUDIT_MUTATION")
MUTATIONS = {
    "overflow": "const d = document.createElement('div'); d.style.cssText = 'width: 2000px; height: 1px'; document.querySelector('main').appendChild(d)",
    "truncate": "const d = document.createElement('div'); d.style.cssText = 'width: 60px; overflow: hidden; white-space: nowrap'; d.textContent = 'Texte beaucoup trop long pour sa boîte'; document.querySelector('main').prepend(d)",
    "targets": "const b = document.createElement('button'); b.textContent = 'ok'; b.style.cssText = 'font-size: 12px; padding: 0; width: 43px; height: 44px'; document.querySelector('main').prepend(b)",
    "contrast": "const p = document.createElement('p'); p.textContent = 'Texte peu lisible'; p.style.color = '#4a4744'; document.querySelector('main').prepend(p)",
    "typo": "const p = document.createElement('p'); p.textContent = 'Bravo! Tu as trouvé'; document.querySelector('main').prepend(p)",
    "safe": "const b = document.createElement('button'); b.textContent = 'Sous l\\'encoche'; b.style.cssText = 'position: fixed; top: 4px; left: 120px; z-index: 99; min-height: 44px; min-width: 44px'; document.body.appendChild(b)",
}

PROFILES = {
    "standalone": {"mobile": True, "standalone": True},
    "petit": {"mobile": True, "standalone": False},
    "desktop": {"mobile": False},
}

# ---------------------------------------------------------------- données semées
TABLES = ["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"]
DAY = 86400_000
PGN = (
    '[Event "Partie vs Noa"]\n[Site "chess-local"]\n[White "Moi"]\n[Black "Noa"]\n[Result "1-0"]\n\n'
    "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Bd2 Bxd2+ 8. Nbxd2 d5 "
    "9. exd5 Nxd5 10. Qb3 Nce7 11. O-O O-O 12. Rfe1 c6 13. Ne4 Qb6 14. Qxb6 axb6 15. Nc5 b5 "
    "16. Bxd5 Nxd5 17. Ne5 Re8 18. Rac1 f6 19. Nf3 Rxe1+ 20. Rxe1 Kf7 21. Re8 Kxe8 1-0"
)


def game(i, result, tc="5+0", tclass="blitz", mode="bot", color="w"):
    g = {
        "id": i, "date": 1760000000000 - i * DAY, "mode": mode, "playerColor": color, "timeControl": tc,
        "timeClass": tclass, "pgn": PGN.replace("1-0", result), "result": result,
        "termination": "abandon" if result != "1/2-1/2" else "accord", "playerRatingAfter": 1180 + i * 7,
    }
    if mode == "bot":
        g["botId"] = "noa"
    return g


def seed(now_ms):
    return {
        "games": [game(1, "1-0"), game(2, "0-1", "3+2"), game(3, "1/2-1/2", "10+0", "rapid"), game(4, "1-0", "1+0", "bullet"),
                  game(5, "0-1", "illimité", "unlimited", mode="local", color="b")],
        "ratings": [
            {"key": "blitz", "value": 1212, "games": 14}, {"key": "bullet", "value": 1087, "games": 6},
            {"key": "rapid", "value": 1301, "games": 9}, {"key": "puzzle", "value": 1456, "games": 40},
            {"key": "learn-tactic", "value": 1320, "games": 12}, {"key": "learn-endgame", "value": 1105, "games": 5},
        ],
        "puzzleAttempts": [
            {"id": i + 1, "puzzleId": pid, "date": now_ms - (i + 1) * DAY, "success": i % 3 != 0, "puzzleRating": 1400 + i * 10, "ratingAfter": 1400 + i * 5}
            for i, pid in enumerate(["001KR", "004yJ", "005Ep", "007AH", "007mr", "009bn"])
        ],
        "rushScores": [
            {"id": 1, "mode": "3min", "score": 17, "date": now_ms - 2 * DAY},
            {"id": 2, "mode": "5min", "score": 23, "date": now_ms - 3 * DAY},
            {"id": 3, "mode": "survival", "score": 31, "date": now_ms - 4 * DAY},
        ],
        "mistakes": [
            {"id": 1, "date": now_ms - 2 * DAY, "gameLabel": "Partie vs Noa (blitz)", "fenBefore": "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
             "playedSan": "Nf6", "bestUci": "g7g6", "cls": "blunder", "attempts": 1, "solved": 0, "color": "b", "gameKey": "game:2"},
            {"id": 2, "date": now_ms - 3 * DAY, "gameLabel": "Partie vs Noa (rapide)", "fenBefore": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
             "playedSan": "Kf1", "bestUci": "a1a8", "cls": "mistake", "attempts": 0, "solved": 0, "color": "w", "gameKey": "game:3"},
        ],
        "learnSessions": [
            {"id": 1, "date": now_ms - 2 * DAY, "domain": "tactic", "itemId": "001KR", "success": 1, "ratingAfter": 1320},
            {"id": 2, "date": now_ms - 3 * DAY, "domain": "endgame", "itemId": "kp-opposition-1", "success": 0, "ratingAfter": 1105},
            {"id": 3, "date": now_ms - 5 * DAY, "domain": "course", "itemId": "finales:mat-dame", "success": 1, "ratingAfter": None},
        ],
        "reviews": [],
    }


OPEN_DB = """() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => res(r.result)
  r.onerror = () => rej(r.error)
})"""


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
        if n == len(TABLES):
            return True
        page.wait_for_timeout(250)
    return False


def seed_db(page, data):
    page.evaluate(
        "async (data) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const names = Object.keys(data).filter((t) => data[t].length)
          const tx = db.transaction(names, 'readwrite')
          for (const t of names) for (const r of data[t]) tx.objectStore(t).put(r)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); tx.onabort = () => rej(tx.error) })
          db.close()
        }""",
        data,
    )


# ---------------------------------------------------------------- mesures
# Une seule passe dans la page : tout ce qui est visible à l'écran (dans le viewport, non masqué,
# pas sous un calque modal), avec un sélecteur lisible pour chaque élément fautif.
AUDIT_JS = r"""
({ mobile, safeTop, safeBottom }) => {
  const vw = innerWidth, vh = innerHeight
  const out = { truncated: [], targets: [], contrast: [], typo: [], safe: [] }
  const css = (e) => getComputedStyle(e)
  const desc = (e) => {
    let s = e.tagName.toLowerCase()
    const tid = e.getAttribute('data-testid')
    if (tid) s += `[${tid}]`
    if (e.hasAttribute('data-current')) s += '[data-current]'
    const t = (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 50)
    return t ? `${s} « ${t} »` : s
  }
  // Calque modal : le dernier élément fixe qui couvre tout le viewport (voile d'une feuille, fin de
  // partie, séance plein écran). Seul son contenu compte, la page dessous est inerte.
  const layers = [...document.querySelectorAll('body *')].filter((e) => {
    if (css(e).position !== 'fixed' || !e.getClientRects().length) return false
    const r = e.getBoundingClientRect()
    return r.left <= 0 && r.top <= 0 && r.right >= vw && r.bottom >= vh && e.children.length
  })
  const scope = layers.pop() || document.body
  // Rectangle peint : la boîte découpée par la fenêtre et par chaque ancêtre qui découpe ou défile.
  const clipOf = (e, r = e.getBoundingClientRect()) => {
    let [t, b, l, rt] = [Math.max(r.top, 0), Math.min(r.bottom, vh), Math.max(r.left, 0), Math.min(r.right, vw)]
    for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
      const s = css(a)
      if (/(auto|scroll|hidden|clip)/.test(s.overflowX + s.overflowY)) {
        const ar = a.getBoundingClientRect()
        t = Math.max(t, ar.top); b = Math.min(b, ar.bottom); l = Math.max(l, ar.left); rt = Math.min(rt, ar.right)
      }
    }
    return { t, b, l, r: rt, w: rt - l, h: b - t }
  }
  const visible = (e) => {
    if (!e.getClientRects().length || e.closest('[hidden], [inert], [aria-hidden=true], .sr-only')) return false
    for (let a = e; a; a = a.parentElement) {
      const s = css(a)
      if (s.visibility === 'hidden' || Number(s.opacity) === 0) return false
    }
    const c = clipOf(e)
    return c.w >= 1 && c.h >= 1
  }
  // Point peint de l'élément (centre de sa partie visible) : le test de visée dit s'il est recouvert.
  const paintedAt = (e, x, y) => { const h = document.elementFromPoint(x, y); return !!h && (h === e || e.contains(h)) }
  const inBoard = (e) => !!e.closest('[data-board], [data-square], [data-piece]')

  // --- couleurs : le navigateur résout oklch / color-mix de Tailwind 4 via un canvas.
  const cv = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
  const rgba = (c) => {
    cv.clearRect(0, 0, 1, 1)
    cv.fillStyle = '#000'
    cv.fillStyle = c
    cv.fillRect(0, 0, 1, 1)
    const d = cv.getImageData(0, 0, 1, 1).data
    return [d[0], d[1], d[2], d[3] / 255]
  }
  const over = (top, bot) => {
    const a = top[3]
    return [top[0] * a + bot[0] * (1 - a), top[1] * a + bot[1] * (1 - a), top[2] * a + bot[2] * (1 - a), 1]
  }
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])
  }
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }
  const opacityOf = (e) => { let o = 1; for (let a = e; a; a = a.parentElement) o *= Number(css(a).opacity); return o }
  // Fond réellement peint sous le texte : la pile `elementsFromPoint` à partir de l'élément, vers
  // le bas, fonds composés avec leur opacité jusqu'au premier fond opaque. Un dégradé, une image ou
  // un média sous le texte rendent le fond indéterminé : null, le texte n'est pas jugé.
  const bgAt = (e, x, y) => {
    const stack = document.elementsFromPoint(x, y)
    let i = stack.findIndex((h) => h === e || e.contains(h))
    if (i < 0) i = stack.findIndex((h) => h.contains(e))
    if (i < 0) return null
    const lay = []
    for (const h of stack.slice(i)) {
      if (h !== e && e.contains(h)) continue
      const s = css(h)
      if (/^(img|video|canvas|svg)$/i.test(h.tagName) || (s.backgroundImage && s.backgroundImage !== 'none')) return null
      const c = rgba(s.backgroundColor)
      c[3] *= opacityOf(h)
      if (c[3] > 0) lay.push(c)
      if (c[3] >= 0.999) break
    }
    let bg = rgba(css(document.body).backgroundColor)
    for (let k = lay.length - 1; k >= 0; k--) bg = over(lay[k], bg)
    return bg
  }

  // --- textes : un élément par parent de nœud texte significatif
  const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  const texts = []
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const e = n.parentElement
    if (!n.nodeValue.trim() || !e || seen.has(e)) continue
    seen.add(e)
    if (e.closest('script, style, noscript, svg, input, textarea, select') || inBoard(e) || !visible(e)) continue
    texts.push(e)
  }
  // Pictogrammes seuls (emoji, flèches, symboles de pièces, chevrons) : pas du texte à lire.
  const pictoOnly = /^[\s\p{Extended_Pictographic}\ufe0f\u200d\u{1f3fb}-\u{1f3ff}\u2190-\u21ff\u2300-\u23ff\u25a0-\u27bf\u2654-\u265f\u2b00-\u2bff›‹«»·•…✕✓]*$/u
  const ownText = (e) => [...e.childNodes].filter((c) => c.nodeType === 3).map((c) => c.nodeValue).join('')
  for (const e of texts) {
    const s = css(e)
    const own = ownText(e)
    const range = document.createRange()
    range.selectNodeContents(e)
    const tr = range.getBoundingClientRect()
    const vis = clipOf(e, tr)
    // Contraste (les commandes désactivées en sont exemptées par WCAG 1.4.3).
    if (!pictoOnly.test(own) && !e.closest(':disabled, [aria-disabled=true]') && vis.w > 0 && vis.h > 0) {
      const x = vis.l + vis.w / 2, y = vis.t + vis.h / 2
      const bg = bgAt(e, x, y)
      if (bg) {
        const fg = rgba(s.color)
        fg[3] *= opacityOf(e)
        const r = ratio(over(fg, bg), bg)
        const px = parseFloat(s.fontSize), w = Number(s.fontWeight)
        const need = px >= 24 || (px >= 18.66 && w >= 700) ? 3 : 4.5
        const hex = (c) => '#' + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')
        if (r < need - 0.005) out.contrast.push({ el: desc(e), ratio: Math.round(r * 100) / 100, need, px, fg: hex(over(fg, bg)), bg: hex(bg), weight: w })
      }
    }
    // Typographie française du texte affiché. Le texte propre de l'élément, plus le début du
    // nœud suivant (« <b>Note</b>: »).
    const issues = []
    if (/\u2014/.test(own)) issues.push('tiret cadratin')
    if (/"/.test(own)) issues.push('guillemet droit')
    if (/«(?![\s\u00a0\u202f])/.test(own) || /(?<![\s\u00a0\u202f])»/.test(own)) issues.push('espace manquante dans « »')
    const full = e.textContent
    for (const m of full.matchAll(/([\p{L}\p{N})»%])([:;!?]+)(?=[\s\u00a0\u202f»)]|$)/gu)) {
      const before = full.slice(Math.max(0, m.index - 12), m.index + 1)
      // Coup noté (Cxf7!, e4!?, O-O!) ou annotation de classe : symbole d'échecs, pas ponctuation.
      if (/^[!?]+$/.test(m[2]) && /([KQRBNCDTFR]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBNDTFC])?[+#]?|O-O(-O)?)$/.test(before)) continue
      issues.push(`espace avant « ${m[2]} » (${full.slice(Math.max(0, m.index - 15), m.index + 3).trim()})`)
    }
    if (issues.length && own.trim()) out.typo.push({ el: desc(e), issues: [...new Set(issues)] })
    // Texte coupé : ses lignes sortent d'un ancêtre qui découpe (overflow hidden/clip, pas un
    // scroller), sans points de suspension sur cet ancêtre.
    const lines = [...range.getClientRects()]
    for (let a = e; a && a !== document.body; a = a.parentElement) {
      const as = css(a)
      if (/(auto|scroll)/.test(as.overflowX + as.overflowY)) break
      if (!/(hidden|clip)/.test(as.overflowX + as.overflowY)) continue
      if (as.textOverflow === 'ellipsis' || as.webkitLineClamp !== 'none') break
      const ar = a.getBoundingClientRect()
      const cut = lines.some((l) => l.width > 0 && (l.right > ar.right + 1 || l.left < ar.left - 1 || l.bottom > ar.bottom + 1 || l.top < ar.top - 1))
      if (cut) out.truncated.push({ el: desc(e), coupé_par: desc(a).slice(0, 40) })
      break
    }
    // Texte qui sort de sa propre boîte sans être coupé (mot trop long, nowrap) : il chevauche.
    if (s.display !== 'inline' && !/(hidden|clip|auto|scroll)/.test(s.overflowX)) {
      const er = e.getBoundingClientRect()
      if (lines.some((l) => l.width > 0 && (l.right > er.right + 1.5 || l.left < er.left - 1.5))) out.truncated.push({ el: desc(e), déborde: Math.round(tr.right - er.right) })
    }
  }

  // --- cibles tactiles : dimensions minimales de 44 px et visée au milieu des quatre bords
  // (les coins arrondis restent acceptés). Le padding ou un pseudo-élément peuvent agrandir la
  // zone, un voisin ou du vide non. Seules les commandes
  // entièrement visibles sont jugées (une commande coupée par le bord d'un scroller sera vue
  // entière dans une autre vue de l'écran).
  const controls = [...scope.querySelectorAll('a[href], button, [role=button], [role=switch], input:not([type=hidden]), select, textarea, summary')]
    .filter((e) => visible(e) && !inBoard(e) && css(e).pointerEvents !== 'none' && !e.matches(':disabled'))
  if (mobile) {
    const H = 22 - 0.01
    for (const ctl of controls) {
      // Un champ dans un label : toute l'étiquette est la cible.
      const e = ctl.matches('input') && ctl.closest('label') ? ctl.closest('label') : ctl
      const r = e.getBoundingClientRect()
      const c = clipOf(e)
      // Sous la bande de l'encoche, la commande est en partie masquée : jugée dans une autre vue.
      if (c.w < r.width - 1 || c.h < r.height - 1 || r.top < safeTop) continue
      const x = r.left + r.width / 2, y = r.top + r.height / 2
      const hit = (px, py) => {
        // Chromium peut inclure le voisin à moins d'un pixel du point (130,99 -> bloc à 131).
        // Garder l'ordre peint, mais écarter ce voisin si son rectangle ne contient pas le point.
        // La cible et les pseudo-éléments conservent leur visée native, y compris hors de leur boîte.
        const h = document.elementsFromPoint(px, py).find((node) => {
          if (node === e || e.contains(node)) return true
          const r = node.getBoundingClientRect()
          if (px >= r.left && px < r.right && py >= r.top && py < r.bottom) return true
          return ['::before', '::after'].some((pseudo) => !['none', 'normal'].includes(getComputedStyle(node, pseudo).content))
        })
        return !!h && (h === e || e.contains(h))
      }
      const expanded = ['::before', '::after'].some((pseudo) => {
        const s = getComputedStyle(e, pseudo)
        return !['none', 'normal'].includes(s.content) && ['absolute', 'fixed'].includes(s.position)
      })
      // Une cible ordinaire de 43 px doit échouer même si la visée native arrondit ses bords.
      const sized = (r.width >= 44 && r.height >= 44) || expanded
      const ok = sized && [[x, y - H], [x, y + H], [x - H, y], [x + H, y]].every(([px, py]) => hit(px, py))
      if (!ok) out.targets.push({ el: desc(ctl), w: Math.round(r.width), h: Math.round(r.height), x: r.x, y: r.y })
    }
  }
  // --- safe areas : la partie peinte et non recouverte d'un texte ou d'une commande ne passe ni
  // sous l'encoche ni sous la barre home.
  if (safeTop) {
    for (const e of new Set([...texts, ...controls])) {
      if (e.closest('nav')) continue
      const c = clipOf(e)
      if (c.w < 1 || c.h < 1) continue
      const x = c.l + c.w / 2
      if (c.t < safeTop - 0.5 && paintedAt(e, x, (c.t + Math.min(c.b, safeTop)) / 2)) out.safe.push({ el: desc(e), top: Math.round(c.t), zone: 'encoche' })
      if (c.b > vh - safeBottom + 0.5 && paintedAt(e, x, (Math.max(c.t, vh - safeBottom) + c.b) / 2)) out.safe.push({ el: desc(e), bottom: Math.round(c.b), zone: 'barre home' })
    }
  }
  return out
}
"""

# Exceptions assumées : (catégorie, prédicat sur l'élément fautif, raison). Tout le reste échoue.
# Le blanc sur l'accent opaque n'est plus toléré : le lot 1 de la refonte UX impose `on-accent`.
ALLOW = [
    ("targets", lambda i: "[data-current]" in i["el"],
     "coups des listes de partie (MoveList, MoveStrip) : liste dense comme chess.com, doublée par les "
     "boutons ◀ ▶ de 44 px"),
]


def allowed(cat, item):
    return any(c == cat and pred(item) for c, pred, _why in ALLOW)


def measure(page, profile):
    p = PROFILES[profile]
    standalone = p.get("standalone", False)
    res = page.evaluate(AUDIT_JS, {"mobile": p["mobile"], "safeTop": SAFE_TOP if standalone else 0, "safeBottom": SAFE_BOTTOM if standalone else 0})
    res["overflow"] = overflow_x(page)
    return res


RAW = []


def audit(page, profile, name, scroll=True):
    """Capture l'écran puis, défilé jusqu'en bas par pas d'un écran, mesure chaque vue."""
    if ONLY and not re.search(ONLY, name):
        return
    page.evaluate("() => document.fonts.ready")
    page.mouse.move(1, 1)  # aucun survol : la couleur mesurée est celle au repos
    if MUTATION:
        page.evaluate(f"() => {{ {MUTATIONS[MUTATION]} }}")
    page.wait_for_timeout(350)
    os.makedirs(os.path.join(OUT, profile), exist_ok=True)
    page.screenshot(path=os.path.join(OUT, profile, f"{name}.png"), scale="css")
    views = [measure(page, profile)]
    if scroll:
        h, total = page.evaluate("() => { const m = document.querySelector('main'); return [m.clientHeight, m.scrollHeight] }")
        k = 1
        while k * (h - 80) < total - h + 80 and k < 8:
            page.evaluate(f"() => document.querySelector('main').scrollTo(0, {k * (h - 80)})")
            page.wait_for_timeout(200)
            page.screenshot(path=os.path.join(OUT, profile, f"{name}~{k}.png"), scale="css")
            views.append(measure(page, profile))
            k += 1
        if k > 1:
            page.evaluate("() => document.querySelector('main').scrollTo(0, 0)")
    merged = {c: [] for c in ("truncated", "targets", "contrast", "typo", "safe")}
    for v in views:
        for c in merged:
            for item in v[c]:
                if item not in merged[c]:
                    merged[c].append(item)
    tag = f"[{profile}] {name}"
    RAW.append({"profile": profile, "name": name, **merged, "overflow": max(v["overflow"] for v in views)})
    ov = max(v["overflow"] for v in views)
    check(f"{tag} : aucun débordement horizontal", ov == 0, f"({ov} px)")
    labels = {
        "truncated": "aucun texte coupé ou qui déborde",
        "targets": "cibles tactiles d'au moins 44 px",
        "contrast": "contraste WCAG AA",
        "typo": "typographie française",
        "safe": "rien sous l'encoche ni sous la barre home",
    }
    for cat, label in labels.items():
        if cat == "targets" and not PROFILES[profile]["mobile"]:
            continue
        if cat == "safe" and not PROFILES[profile].get("standalone"):
            continue
        bad = [i for i in merged[cat] if not allowed(cat, i)]
        check(f"{tag} : {label}", not bad, f"({json.dumps(bad[:6], ensure_ascii=False)}{' ...' if len(bad) > 6 else ''})")


# ---------------------------------------------------------------- parcours
def goto(page, path, marker="main >> *", timeout=15000):
    page.goto(f"{BASE}/#{path}")
    return ck.appears(f"page {path} affichée", page, marker, timeout=timeout)


def click(page, name, selector, timeout=15000):
    """Clic précédé d'un check : un élément absent fait échouer un check, pas toute la suite."""
    if ck.appears(name, page, selector, timeout=timeout):
        page.locator(selector).first.click()
        return True
    return False


def tour(page, profile):
    """Profil peuplé : toutes les routes et leurs états principaux."""
    a = lambda name, **kw: audit(page, profile, name, **kw)  # noqa: E731
    t = f"[{profile}]"

    goto(page, "/", "main [data-review-ready]")
    a("accueil")

    # Jouer : réglages, partie en cours, feuille d'abandon, fin de partie.
    goto(page, "/jouer", "main :text('Adversaire')")
    a("jouer-reglages")
    page.locator("main button", has_text="Noa").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    if ck.appears(f"{t} partie lancée", page, "[data-square='e2']"):
        page.locator("[data-square='e2']").click()
        page.locator("[data-square='e4']").click()
        ck.appears(f"{t} réponse du bot", page, "main [data-current]:nth-of-type(2)", timeout=20000)
        a("jouer-partie", scroll=False)
        click(page, f"{t} bouton Abandonner", "button:has-text('Abandonner')")
        ck.appears(f"{t} feuille d'abandon", page, "text=Abandonner la partie ?")
        a("jouer-abandon", scroll=False)
        page.get_by_role("button", name="Oui, abandonner", exact=True).click()
        ck.appears(f"{t} fin de partie", page, "div.fixed button:has-text('Nouvelle partie')")
        a("jouer-fin", scroll=False)
        page.locator("div.fixed button", has_text="Nouvelle partie").click()

    goto(page, "/puzzles", "[data-square='e2']", timeout=30000)
    page.wait_for_timeout(1200)
    a("puzzles")

    goto(page, "/rush", "main :text('Record')")
    ck.appears(f"{t} puzzles du rush chargés", page, "main button:has-text('3 minutes'):enabled", timeout=30000)
    a("rush")
    page.locator("main button", has_text="3 minutes").click()
    if ck.appears(f"{t} rush lancé", page, "[data-square='e2']"):
        page.wait_for_timeout(1200)
        a("rush-en-cours", scroll=False)

    goto(page, "/apprendre", "main :text('Séance')")
    a("apprendre")
    page.get_by_role("button", name="Séance", exact=True).click()
    if ck.appears(f"{t} séance d'Apprendre", page, "button:has-text(\"C'est parti\")", timeout=30000):
        a("apprendre-seance-intro", scroll=False)
        page.locator("button:has-text(\"C'est parti\")").click()
        if ck.appears(f"{t} exercice de la séance", page, "[data-board]"):
            page.wait_for_timeout(1000)
            a("apprendre-seance", scroll=False)

    for slug in ("finales", "roque"):
        goto(page, f"/apprendre/{slug}", "[data-testid=course-progress]")
        a(f"cours-{slug}")
        page.locator("main button[data-lesson]").first.click()
        if ck.appears(f"{t} leçon {slug}", page, "[data-testid=lesson-step]"):
            page.wait_for_timeout(600)
            a(f"cours-{slug}-lecon")

    goto(page, "/ouvertures", "main h1")
    a("ouvertures")
    goto(page, "/mats", "main h1")
    a("mats")
    goto(page, "/mats?d=geo-diagonale-ligne", "main h1")
    page.wait_for_timeout(600)
    a("mats-fiche")

    goto(page, "/revision", "main >> *")
    page.wait_for_timeout(2500)
    a("revision")

    goto(page, "/attaques-manquees", "main h1")
    page.wait_for_timeout(800)
    a("attaques-manquees")
    goto(page, "/attaques-manquees/2", "[data-board]")
    a("attaque-manquee-exercice")

    goto(page, "/attaque", "[data-testid=attack-item]")
    a("attaque")
    page.locator("[data-testid=attack-item]").first.click()
    if ck.appears(f"{t} exercice d'attaque", page, "[data-square='e2']"):
        page.wait_for_timeout(1500)
        a("attaque-exercice", scroll=False)

    goto(page, "/finales", "[data-testid=endgame-item]")
    a("finales")
    page.locator("[data-testid=endgame-item]").first.click()
    if ck.appears(f"{t} finale jouée", page, "[data-square='e2']"):
        page.wait_for_timeout(1500)
        a("finales-exercice", scroll=False)
    goto(page, "/finales/chrono", "[data-serie='mix']")
    a("finales-chrono")

    for path, item, name in (("/convertir", "conversion-item", "convertir"), ("/defense", "defense-item", "defense")):
        goto(page, path, f"[data-testid={item}]")
        a(name)
        page.locator(f"[data-testid={item}]").first.click()
        if ck.appears(f"{t} exercice {name}", page, "[data-square='e2']"):
            page.wait_for_timeout(1500)
            a(f"{name}-exercice", scroll=False)

    goto(page, "/seance", "[data-seance-intro]")
    if ck.appears(f"{t} plan de la séance du jour", page, "[data-seance-plan]", timeout=30000):
        a("seance-intro")
        page.locator("[data-seance-intro] button", has_text="Commencer").first.click()
        if ck.appears(f"{t} étape de la séance du jour", page, "[data-seance-step] [data-board]"):
            page.wait_for_timeout(1000)
            a("seance-etape", scroll=False)

    goto(page, "/analyse", "[data-square='e2']")
    page.wait_for_timeout(1500)
    a("analyse-vide")
    if PROFILES[profile]["mobile"]:
        click(page, f"{t} options de l'analyse", "main button:has-text('Options')")
        a("analyse-options", scroll=False)
        if PROFILES[profile].get("standalone"):
            check(f"{t} le voile Options assombrit aussi la zone de l'encoche", page.locator("h2:has-text('Options')").evaluate(
                "(heading) => heading.parentElement.parentElement.contains(document.elementFromPoint(innerWidth / 2, 20))"))
    if click(page, f"{t} jouer depuis l'analyse", "button:has-text('Jouer contre le moteur'):visible"):
        if ck.appears(f"{t} partie depuis une position", page, "[data-testid=position-game]"):
            a("analyse-jouer")
    # Même route : sans détour, le changement de hash ne remonte pas la page et `?game=` est ignoré.
    goto(page, "/archive", "main h1")
    goto(page, "/analyse?game=1", "[data-square='e2']")
    page.wait_for_timeout(1500)
    a("analyse-partie")
    goto(page, "/archive", "main h1")
    goto(page, "/analyse?game=1&review=1", "[data-square='e2']")
    if ck.appears(f"{t} bilan calculé", page, "text=Démarrer le bilan", timeout=120000):
        a("analyse-bilan")
        page.locator("text=Démarrer le bilan").first.click()
        page.wait_for_timeout(1200)
        a("analyse-bilan-coup", scroll=False)

    goto(page, "/archive", "main h1")
    page.wait_for_timeout(600)
    a("archive")
    goto(page, "/stats", "main :text('Statistiques')")
    a("stats")
    click(page, f"{t} bouton de réinitialisation", "[data-testid=reset-btn]")
    page.wait_for_timeout(400)
    a("stats-reinitialiser", scroll=False)
    page.keyboard.press("Escape")

    goto(page, "/insights", "main h1")
    page.wait_for_timeout(800)
    a("insights")
    goto(page, "/import", "main h1")
    a("import")


def tour_empty(page, profile):
    """Profil vierge : états vides, et erreur de chargement des puzzles."""
    a = lambda name, **kw: audit(page, profile, name, **kw)  # noqa: E731
    goto(page, "/", "main [data-review-ready]")
    a("vide-accueil")
    for path, name in (("/archive", "vide-archive"), ("/stats", "vide-stats"), ("/revision", "vide-revision"),
                       ("/attaques-manquees", "vide-attaques-manquees"), ("/insights", "vide-insights")):
        goto(page, path, "main h1")
        page.wait_for_timeout(1200)
        a(name)
    page.route("**/puzzles.json", lambda route: route.abort())
    goto(page, "/rush", "main :text('Réessayer')")
    a("erreur-rush")
    goto(page, "/puzzles", "main >> *")
    page.wait_for_timeout(1500)
    a("erreur-puzzles")
    page.unroute("**/puzzles.json")
    goto(page, "/route-inconnue-audit", "main [data-review-ready]")
    check(f"[{profile}] route inconnue redirigée vers l'accueil", page.evaluate("location.hash") == "#/")
    a("route-inconnue")


# Transitions et animations coupées : une couleur lue en plein fondu (nav, feuilles, squelettes de
# chargement) donnerait un contraste faux et instable.
FREEZE = """document.addEventListener('DOMContentLoaded', () => {
  const st = document.createElement('style')
  st.textContent = '*, *::before, *::after { transition: none !important; animation: none !important }'
  document.head.appendChild(st)
})"""


def new_ctx(p, browser, profile):
    spec = PROFILES[profile]
    opts = {"service_workers": "block", "reduced_motion": "reduce"}
    if spec["mobile"]:
        ctx = mobile_context(p, browser, ck, standalone=spec.get("standalone", False), **opts)
    else:
        ctx = desktop_context(browser, ck, **opts)
    ctx.add_init_script(FREEZE)
    page = ctx.new_page()
    if spec.get("standalone"):
        cdp = ctx.new_cdp_session(page)
        cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM}})
    return ctx, page


def run_profile(p, browser, profile):
    ctx, page = new_ctx(p, browser, profile)
    tour_empty(page, profile)
    ctx.close()
    ctx, page = new_ctx(p, browser, profile)
    goto(page, "/stats", "main :text('Statistiques')")
    if check(f"[{profile}] base prête", wait_schema(page)):
        now = page.evaluate("() => Date.now()")
        seed_db(page, seed(now))
    tour(page, profile)
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    for profile in PROFILES:
        if not os.environ.get("UI_AUDIT_PROFILE") or profile == os.environ["UI_AUDIT_PROFILE"]:
            run_profile(p, browser, profile)
    browser.close()
    if REPORT:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(RAW, f, ensure_ascii=False, indent=1)


ck.run(suite)
