"""Passe visuelle : 393x660 (onglet Safari), paysage 852x393, desktop 1440x900. Géométrie + chaînage de scroll de la feuille."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
from s3_tactics_lib import verdict_text

def geom(page):
    return page.evaluate("""() => {
      const r = (e) => { if(!e) return null; const b=e.getBoundingClientRect(); return {x:Math.round(b.x), y:Math.round(b.y), w:Math.round(b.width), h:Math.round(b.height), bottom:Math.round(b.bottom), right:Math.round(b.right)} }
      const sc = document.querySelector('div.fixed.inset-0.z-40')
      const bar=[...document.querySelectorAll('div.flex.items-center.gap-2.px-3.py-2')][0]
      return { vw: innerWidth, vh: innerHeight, board: r(document.querySelector("[id^='chessboard-']")), header: r(document.querySelector('div.fixed.inset-0.z-40 header')),
        q: r(document.querySelector("header button[title='Voir le cours']")), verdictBar: r(bar), next: bar ? r([...bar.querySelectorAll('button')].pop()) : null,
        cta: r([...document.querySelectorAll('button')].find(b => b.innerText.trim() === "C'est parti")),
        nav: r(document.querySelector('nav')), scroller: sc ? {top: sc.scrollTop, sh: sc.scrollHeight, ch: sc.clientHeight} : null,
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth }
    }""")

def new_ctx(p, kind):
    if kind == 'safari':
        return open_mobile(p, standalone=False)
    if kind == 'landscape':
        browser = p.chromium.launch(headless=True)
        opts = dict(p.devices['iPhone 14 Pro']); opts['viewport'] = {'width': 852, 'height': 393}
        ctx = browser.new_context(**opts); page = ctx.new_page()
        state = {"state": DEFAULT_SETTINGS, "version": 0}
        page.add_init_script("if (!localStorage.getItem('chess-local-settings')) " + f"localStorage.setItem('chess-local-settings', {json.dumps(json.dumps(state))})")
        logs = []; page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {str(e)[:300]}")); page.on("console", lambda m: logs.append(f"CONSOLE.{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
        return browser, ctx, page, logs
    return open_desktop(p)

with sync_playwright() as p:
    for kind in ('safari', 'landscape', 'desktop'):
        browser, ctx, page, logs = new_ctx(p, kind)
        touch = kind != 'desktop'
        act = (lambda loc: loc.tap()) if touch else (lambda loc: loc.click())
        page.add_init_script(RND_INIT)
        page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1300)
        shot(page, f"s8_{kind}_home"); print(f"\n##### {kind} home:", json.dumps(geom(page)))
        # Finale kr-mate
        set_rnd(page, rnd_for('kr-mate', 800))
        act(page.locator("main button", has_text="Finales").first); page.wait_for_selector("text=C'est parti"); page.wait_for_timeout(400)
        shot(page, f"s8_{kind}_lesson"); g = geom(page); print(" leçon:", json.dumps(g)); print("  CTA visible sans scroll:", g['cta'] and g['cta']['bottom'] <= g['vh'])
        act(page.locator("text=Voir le cours complet")); page.wait_for_timeout(600)
        shot(page, f"s8_{kind}_sheet")
        sheet = page.evaluate("() => { const p=document.querySelector('div.fixed.inset-0.z-50').firstElementChild.getBoundingClientRect(); const b=document.querySelector(\"div.fixed.inset-0.z-50 [id^='chessboard-']\").getBoundingClientRect(); return {top:p.top, bottom:p.bottom, h:p.height, w:p.width, boardW:b.width, vh: innerHeight} }")
        print(" feuille:", sheet)
        act(page.locator("div.fixed.inset-0.z-50 header button")); page.wait_for_timeout(300)
        act(page.get_by_role("button", name="C'est parti")); page.wait_for_selector("[id^='chessboard-']"); page.wait_for_timeout(900)
        shot(page, f"s8_{kind}_play"); g = geom(page); print(" jeu:", json.dumps(g))
        print("  board entièrement visible sans scroll:", g['board']['bottom'] <= g['vh'], "| ? chevauche board:", g['q'] and not (g['q']['bottom'] <= g['board']['y'] or g['q']['x'] >= g['board']['right']))
        if touch:
            # chaînage de scroll : feuille ouverte, scrollée à fond, puis drag vers le haut encore
            act(page.locator("header button[title='Voir le cours']")); page.wait_for_timeout(500)
            page.evaluate("() => { const sc = document.querySelector('div.fixed.inset-0.z-50 .overflow-y-auto'); sc.scrollTop = sc.scrollHeight }")
            b0 = session_scroller_top(page)
            vh = g['vh']; vw = g['vw']
            touch_drag(page, vw / 2, vh * 0.8, vw / 2, vh * 0.25, steps=10); page.wait_for_timeout(500)
            touch_drag(page, vw / 2, vh * 0.8, vw / 2, vh * 0.25, steps=10); page.wait_for_timeout(500)
            print("  chaînage scroll (feuille au bout, 2 drags): fond", b0, "->", session_scroller_top(page), "| window", page.evaluate("() => scrollY"))
            act(page.locator("div.fixed.inset-0.z-50 header button")); page.wait_for_timeout(300)
            print("  après fermeture: fond scrollTop =", session_scroller_top(page))
        # verdict : dame... ici tour donnée -> Raté
        board = chess.Board('8/8/8/4k3/8/8/8/R3K3 w - - 0 1')
        mv = chess.Move.from_uci('a1a5')  # Ta5+?? le roi ne peut pas prendre (a5 loin) -> on donne plutôt la tour en e... 
        mv = chess.Move.from_uci('a1a4')
        if touch: play_my_move(page, board, mv, 'tap')
        else:
            page.locator("[data-square='a1']").first.click(); page.wait_for_timeout(150); page.locator("[data-square='a4']").first.click(); board.push(mv)
        wait_bot(page, board)
        mv2 = chess.Move.from_uci('a4e4') if chess.Move.from_uci('a4e4') in board.legal_moves else list(board.legal_moves)[0]
        if touch: play_my_move(page, board, mv2, 'tap')
        else:
            page.locator(f"[data-square='{chess.square_name(mv2.from_square)}']").first.click(); page.wait_for_timeout(150); page.locator(f"[data-square='{chess.square_name(mv2.to_square)}']").first.click(); board.push(mv2)
        for _ in range(80):
            if verdict_text(page): break
            wait_bot(page, board, timeout_s=2)
            if verdict_text(page): break
            mvx = list(board.legal_moves)[0]
            if touch: play_my_move(page, board, mvx, 'tap')
            else:
                page.locator(f"[data-square='{chess.square_name(mvx.from_square)}']").first.click(); page.wait_for_timeout(120); page.locator(f"[data-square='{chess.square_name(mvx.to_square)}']").first.click(); board.push(mvx)
        page.wait_for_timeout(600)
        shot(page, f"s8_{kind}_verdict"); g = geom(page); print(" verdict:", verdict_text(page), json.dumps(g))
        if g['verdictBar']:
            print("  barre verdict visible sans scroll:", g['verdictBar']['bottom'] <= g['vh'], "| Suivant déborde à droite:", g['next']['right'] > g['vw'] - 8, "| hauteur barre:", g['verdictBar']['h'])
        print(" LOGS:", [l[:140] for l in logs][:4])
        browser.close()
