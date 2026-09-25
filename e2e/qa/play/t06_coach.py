"""Mode Entraîneur : bulle, latence, saut de layout, cohérence des commentaires, indication, annuler."""
import time
from common import *

SAMPLER = """() => {
  window.__s = []; window.__t0 = performance.now()
  window.__timer = setInterval(() => {
    const bb = document.querySelector('.boardbox'); const bub = document.querySelector('.bg-white.rounded-2xl')
    const evalLabel = document.querySelector('main .bg-neutral-800 span')
    const ply = document.querySelectorAll('main [data-current]').length
    window.__s.push([Math.round(performance.now() - window.__t0), bb ? Math.round(bb.getBoundingClientRect().top * 10) / 10 : null,
      bub ? Math.round(bub.getBoundingClientRect().height) : null, bub ? bub.innerText : null, ply, evalLabel ? evalLabel.textContent : null])
  }, 50)
}"""


def dump_transitions(page, label):
    s = page.evaluate("() => window.__s")
    last = None
    print(f"--- {label} : transitions (t ms, boardTop, hBulle, ply, eval, texte)")
    for t, top, h, txt, ply, ev in s:
        key = (top, h, txt, ply)
        if key != last:
            print(f"    {t:6} top={top} h={h} ply={ply} eval={ev} | {txt!r}")
            last = key
    tops = sorted({x[1] for x in s if x[1] is not None})
    print(f"    positions verticales distinctes du board: {tops}")
    return s


with sync_playwright() as p:
    for standalone in (True, False):
        tag = "852" if standalone else "660"
        browser, ctx, page, logs = open_mobile(p, standalone=standalone)
        goto_play(page)
        setup(page, mode="coach", bot="Noa", color="Blancs")
        page.evaluate(SAMPLER)
        shot(page, f"coach_{tag}_greeting")
        st = scroll_state(page)
        inner = page.evaluate("""() => { const e = document.querySelector('main .overflow-y-auto'); return e ? {sh: e.scrollHeight, ch: e.clientHeight} : null }""")
        print(f"[{tag}] zone scrollable interne:", inner, "| main:", st["mainScrollHeight"], st["mainClientHeight"])
        bar = page.evaluate("""() => Array.from(document.querySelectorAll('main .border-t button')).map(b => {const r=b.getBoundingClientRect(); return [b.innerText.replace(/\\n/g,' '), Math.round(r.width), Math.round(r.height)]})""")
        print(f"[{tag}] barre d'actions:", bar)
        page.wait_for_timeout(800)
        # 1. e4
        t0 = page.evaluate("() => Math.round(performance.now() - window.__t0)")
        drag_piece(page, "e2", "e4")
        print(f"[{tag}] e4 joué à t={t0} ms")
        wait_ply(page, 2); page.wait_for_timeout(3500)
        shot(page, f"coach_{tag}_after_e4")
        b = chess.Board(); b.push_san("e4"); bm = sync_bot_move(page, b)
        print(f"[{tag}] réponse du bot: {bm}")
        if standalone:
            # 2. un coup raisonnable puis une gaffe franche : dame donnée
            t1 = page.evaluate("() => Math.round(performance.now() - window.__t0)")
            tap_move(page, "d1", "h5") if b.is_legal(chess.Move.from_uci("d1h5")) else tap_move(page, "g1", "f3")
            mv = chess.Move.from_uci("d1h5") if b.is_legal(chess.Move.from_uci("d1h5")) else chess.Move.from_uci("g1f3")
            b.push(mv)
            print(f"[{tag}] {mv} joué à t={t1}")
            wait_ply(page, 4); page.wait_for_timeout(3500)
            bm = sync_bot_move(page, b); print(f"[{tag}] réponse du bot: {bm}")
            # gaffe : la dame prend un pion défendu si possible
            blunder = None
            for cand in ["h5f7", "h5h7", "h5e5", "f3e5"]:
                m = chess.Move.from_uci(cand)
                if b.is_legal(m):
                    blunder = m; break
            if blunder:
                t2 = page.evaluate("() => Math.round(performance.now() - window.__t0)")
                tap_move(page, chess.square_name(blunder.from_square), chess.square_name(blunder.to_square))
                san = b.san(blunder); b.push(blunder)
                print(f"[{tag}] gaffe tentée {san} à t={t2}")
                page.wait_for_timeout(700)
                shot(page, f"coach_{tag}_blunder_early")
                wait_ply(page, 6); page.wait_for_timeout(4000)
                shot(page, f"coach_{tag}_after_blunder")
                bm = sync_bot_move(page, b); print(f"[{tag}] réponse du bot: {bm}")
            # Indication
            t3 = time.time()
            page.locator("button", has_text="Indication").click()
            page.wait_for_function("() => document.querySelectorAll('main svg line, main svg path[marker-end], main svg polygon').length > 0 || document.querySelector('main [class*=arrow]')", timeout=15000)
            print(f"[{tag}] flèche d'indication après {time.time()-t3:.2f}s")
            page.wait_for_timeout(300)
            shot(page, f"coach_{tag}_hint")
            # Annuler
            n0 = ply_count(page)
            page.locator("button", has_text="Annuler").click(); page.wait_for_timeout(2500)
            print(f"[{tag}] Annuler: {n0} -> {ply_count(page)} demi-coups ; bulle: {page.locator('.bg-white.rounded-2xl').inner_text()!r}")
            shot(page, f"coach_{tag}_takeback")
        dump_transitions(page, f"coach {tag}")
        # Abandon : modale
        page.locator("button", has_text="Abandonner").click(); page.wait_for_selector("div.fixed"); page.wait_for_timeout(500)
        shot(page, f"coach_{tag}_resign_modal")
        print(f"[{tag}] modale:", page.locator("div.fixed").inner_text().replace("\n", " | "))
        page.touchscreen.tap(196, 20); page.wait_for_timeout(400)
        shot(page, f"coach_{tag}_after_modal")
        print(f"[{tag}] LOGS:", logs)
        browser.close()

    # 1.Nf3 : texte « le grand classique »
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    goto_play(page)
    setup(page, mode="coach", bot="Noa", color="Blancs")
    tap_move(page, "g1", "f3")
    for _ in range(30):
        txt = page.locator(".bg-white.rounded-2xl").inner_text()
        if "f3" in txt:
            break
        page.wait_for_timeout(100)
    print("1.Cf3 ->", repr(txt))
    browser.close()
