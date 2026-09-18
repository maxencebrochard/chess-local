"""Enveloppe : chaque route x chaque viewport. Titre, overflow_x, onglet actif, erreurs, capture pleine page."""
import json
import os
import sys

QA = "e2e/qa"
os.environ.setdefault("SHOTS", f"{QA}/global/shots")
sys.path.insert(0, QA)
from qa_helpers import *  # noqa

ROUTES = ["/", "/jouer", "/puzzles", "/rush", "/apprendre", "/analyse", "/archive", "/stats", "/import", "/nimporte"]
VIEWPORTS = [
    ("m393x852", 393, 852, True),
    ("m393x660", 393, 660, True),
    ("m320x568", 320, 568, True),
    ("m430x932", 430, 932, True),
    ("land852x393", 852, 393, True),
    ("tab820x1180", 820, 1180, True),
    ("desk1440x900", 1440, 900, False),
]
only = sys.argv[1:] or None
STATE = {"state": DEFAULT_SETTINGS, "version": 0}
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, w, h, mobile in VIEWPORTS:
        if only and name not in only:
            continue
        if mobile:
            opts = dict(p.devices["iPhone 14 Pro"])
            opts["viewport"] = {"width": w, "height": h}
            if w >= 800 and h >= 1000:
                opts["user_agent"] = p.devices["iPad (gen 7)"]["user_agent"]
                opts["device_scale_factor"] = 2
        else:
            opts = {"viewport": {"width": w, "height": h}}
        ctx = browser.new_context(**opts)
        page = ctx.new_page()
        page.add_init_script(
            "if (!localStorage.getItem('chess-local-settings')) "
            f"localStorage.setItem('chess-local-settings', {json.dumps(json.dumps(STATE))})"
        )
        logs = []
        page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {str(e)[:200]}"))
        page.on("console", lambda m: logs.append(f"CONSOLE.{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
        page.on("requestfailed", lambda r: logs.append(f"REQFAILED: {r.url[:120]} {r.failure}"))
        page.on("response", lambda r: logs.append(f"HTTP{r.status}: {r.url[:120]}") if r.status >= 400 else None)
        for route in ROUTES:
            logs.clear()
            page.goto(f"{BASE}/#{route}")
            page.wait_for_timeout(1600)
            info = page.evaluate(
                """() => {
                  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 }
                  const navs = [...document.querySelectorAll('nav')].filter(vis)
                  const active = navs.flatMap(n => [...n.querySelectorAll('a[aria-current="page"]')]).map(a => a.textContent.trim())
                  const main = document.querySelector('main')
                  const board = document.querySelector("[id^='chessboard-']") || document.querySelector('[data-square]')?.closest('div[style]')
                  const sq = document.querySelector("[data-square='a1']")
                  const sqb = sq ? sq.getBoundingClientRect() : null
                  // éléments qui dépassent du viewport à droite
                  const vw = document.documentElement.clientWidth
                  const over = [...document.querySelectorAll('main *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > vw + 1 }).slice(0, 5)
                     .map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 60) + ' right=' + Math.round(e.getBoundingClientRect().right))
                  return {
                    title: document.title,
                    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    mainOverflowX: main ? main.scrollWidth - main.clientWidth : null,
                    active,
                    mainTextLen: main ? main.innerText.trim().length : null,
                    mainScrollable: main ? main.scrollHeight - main.clientHeight : null,
                    squarePx: sqb ? Math.round(sqb.width) : null,
                    boardTop: sqb ? Math.round(document.querySelector("[data-square='a8'], [data-square='h1']").getBoundingClientRect().top) : null,
                    over,
                  }
                }"""
            )
            slug = route.strip("/") or "home"
            # capture pleine page : le scroll est dans <main>, on agrandit donc temporairement le viewport
            page.screenshot(path=os.path.join(SHOTS, f"env_{name}_{slug}.png"))
            if info["mainScrollable"] and info["mainScrollable"] > 4:
                extra = info["mainScrollable"]
                page.set_viewport_size({"width": w, "height": h + extra})
                page.wait_for_timeout(250)
                page.screenshot(path=os.path.join(SHOTS, f"env_{name}_{slug}_full.png"))
                page.set_viewport_size({"width": w, "height": h})
                page.wait_for_timeout(150)
            rec = {"vp": name, "route": route, **info, "logs": list(logs)}
            results.append(rec)
            print(json.dumps(rec, ensure_ascii=False))
        ctx.close()
    browser.close()

out = f"{QA}/global/envelope_results{'_' + '_'.join(only) if only else ''}.json"
with open(out, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
