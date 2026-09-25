"""Gestes tactiles instrumentés : état avant / pendant / après + journal d'événements navigateur."""
import json
from touch_env import *  # noqa: F401,F403

# Journal posé AVANT le code de l'app : pointercancel = le navigateur a repris le geste (scroll/pan).
PROBE_INIT = """
window.__ev = [];
for (const t of ['pointerdown', 'pointercancel', 'touchcancel', 'touchstart', 'touchend', 'contextmenu', 'selectstart']) {
  document.addEventListener(t, (e) => {
    const el = e.target; const d = el && el.tagName ? el.tagName.toLowerCase() + (el.closest && el.closest('[data-piece]') ? '(piece)' : '') : '?';
    window.__ev.push(t + ':' + d + (e.defaultPrevented ? ':prevented' : ''));
  }, { capture: true, passive: true });
}
document.addEventListener('scroll', (e) => { const el = e.target; window.__ev.push('scroll:' + (el === document ? 'document' : el.tagName.toLowerCase() + '.' + String(el.className).slice(0, 70))) }, { capture: true, passive: true });
window.addEventListener('popstate', () => window.__ev.push('popstate'));
window.addEventListener('hashchange', () => window.__ev.push('hashchange'));
"""

SNAP = """() => {
  const scrollers = [];
  for (const el of document.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1)
      scrollers.push({ el: el.tagName.toLowerCase() + '.' + String(el.className).slice(0, 40), top: Math.round(el.scrollTop), max: el.scrollHeight - el.clientHeight });
  }
  const pos = {};
  for (const p of document.querySelectorAll('[data-square] [data-piece]')) pos[p.closest('[data-square]').getAttribute('data-square')] = p.getAttribute('data-piece');
  const b = document.querySelector('[id$="-board"]');
  // clone de drag = pièce rendue hors des cases (DragOverlay, position fixed)
  const clone = [...document.querySelectorAll('[data-piece]')].some((p) => !p.closest('[data-square]'));
  const sel = [...document.querySelectorAll('[data-square]')].filter((q) => { const i = q.lastElementChild; return i && /255, 255, 51, 0\\.5/.test(i.style.backgroundColor + i.style.background) }).map((q) => q.getAttribute('data-square'));
  return { windowScrollY: Math.round(scrollY), scrollers, hash: location.hash, historyLength: history.length,
           boardTop: b ? Math.round(b.getBoundingClientRect().top) : null, pos, dragClone: clone, selected: sel,
           promo: !!document.querySelector('.z-20 button'), textSelection: String(getSelection()).length };
}"""


HIT = """([x, y]) => {
  const e = document.elementFromPoint(x, y); if (!e) return 'RIEN';
  const inBoard = !!e.closest('[id$="-board"]');
  if (!inBoard) return 'HORS-BOARD:' + e.tagName.toLowerCase() + '.' + String(e.className.baseVal ?? e.className).slice(0, 28);
  if (e.closest('[data-piece]')) return 'piece:' + e.closest('[data-piece]').getAttribute('data-piece');
  if (e.tagName === 'SPAN') return 'coordonnee:' + e.textContent;
  return 'case-vide';
}"""


def install(page):
    page.add_init_script(PROBE_INIT)


def snap(page):
    return page.evaluate(SNAP)


def events(page, reset=True):
    ev = page.evaluate("() => { const e = window.__ev || []; return e.slice() }")
    if reset:
        page.evaluate("() => { window.__ev = [] }")
    return ev


def gesture(page, x1, y1, x2, y2, steps=14, step_ms=16, hold_ms=60, extra_touch=None):
    """Drag tactile CDP avec relevé à mi-course. extra_touch=(x,y) : second doigt posé à mi-course."""
    events(page)
    before = snap(page)
    start_hit = page.evaluate(HIT, [x1, y1])
    cdp = page.context.new_cdp_session(page)
    P = lambda x, y, i=1: {"x": round(x, 1), "y": round(y, 1), "id": i, "radiusX": 8, "radiusY": 8, "force": 1}
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [P(x1, y1)]})
    page.wait_for_timeout(hold_ms)
    mid = None
    for i in range(1, steps + 1):
        x = x1 + (x2 - x1) * i / steps
        y = y1 + (y2 - y1) * i / steps
        pts = [P(x, y)]
        if extra_touch and i > steps // 2:
            pts.append(P(extra_touch[0], extra_touch[1], 2))
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pts})
        page.wait_for_timeout(step_ms)
        if i == max(1, steps // 2):
            mid = snap(page)
    page.wait_for_timeout(hold_ms)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    page.wait_for_timeout(350)
    after = snap(page)
    return {"before": before, "mid": mid, "after": after, "events": events(page), "startHit": start_hit}


def verdict(r):
    """Résumé une ligne : scroll ? navigation ? coup joué ? drag activé ? geste volé par le navigateur ?"""
    b, m, a = r["before"], r["mid"], r["after"]
    sc = lambda s: {x["el"]: x["top"] for x in s["scrollers"]}
    # un scroller qui APPARAIT (contenu allongé) n'est pas un scroll : on compare les positions, absent = 0
    scrolled = {k: (sc(b).get(k, 0), v) for k, v in sc(a).items() if sc(b).get(k, 0) != v or (m and sc(m).get(k, 0) != sc(b).get(k, 0))}
    ev = r["events"]
    return {
        "scrolled": scrolled or None,
        "windowScrollY": (b["windowScrollY"], a["windowScrollY"]),
        "boardTop": (b["boardTop"], (m or a)["boardTop"], a["boardTop"]),
        "nav": None if (b["hash"], b["historyLength"]) == (a["hash"], a["historyLength"]) else (b["hash"], b["historyLength"], a["hash"], a["historyLength"]),
        "moved": b["pos"] != a["pos"],
        "dragCloneMid": bool(m and m["dragClone"]),
        "pointercancel": sum(1 for e in ev if e.startswith("pointercancel")),
        # le recentrage programmé de la bande de coups (MoveStrip.tsx:26, overflow-x-auto) n'est pas un scroll de page
        "scrollEvents": sum(1 for e in ev if e.startswith("scroll") and "overflow-x-auto" not in e),
        "stripScroll": sum(1 for e in ev if e.startswith("scroll") and "overflow-x-auto" in e),
        "selectedAfter": a["selected"], "promo": a["promo"],
    }


def line(label, r, expect=None):
    """expect : préfixe attendu de startHit ('piece:w', 'piece:b', 'case-vide', 'coordonnee', 'HORS-BOARD')."""
    v = verdict(r)
    flag = "SCROLL" if v["scrolled"] or v["scrollEvents"] else "ok    "
    if expect and not str(r.get("startHit", "")).startswith(expect):
        flag = "INVALI"  # le test n'a pas touché la cible prévue : résultat à ignorer
    v["valid"] = flag != "INVALI"
    print(f"[{flag}] {label:58s} hit={r.get('startHit', '?'):16s} moved={str(v['moved']):5s} clone={str(v['dragCloneMid']):5s} pcancel={v['pointercancel']} scrollEv={v['scrollEvents']:3d} boardTop={v['boardTop']} scrolled={json.dumps(v['scrolled'])} nav={v['nav']} sel={v['selectedAfter']}")
    if v["scrollEvents"] and not v["scrolled"]:
        # scroll sans déplacement vertical d'un scroller suivi : afficher QUI a défilé (ex : bande de coups horizontale)
        print("      cibles des scroll:", sorted(set(e for e in r["events"] if e.startswith("scroll") and "overflow-x-auto" not in e)))
    return v


def sq_rect(page, sq):
    return page.locator(f"[data-square='{sq}']").first.bounding_box()


def squares_with(page, prefix):
    """Cases portant une pièce dont le code commence par prefix ('w' ou 'b')."""
    return page.evaluate("(p) => [...document.querySelectorAll('[data-square] [data-piece]')].filter(e => e.getAttribute('data-piece').startsWith(p)).map(e => e.closest('[data-square]').getAttribute('data-square'))", prefix)


def empty_squares(page):
    return page.evaluate("() => [...document.querySelectorAll('[data-square]')].filter(e => !e.querySelector('[data-piece]')).map(e => e.getAttribute('data-square'))")
