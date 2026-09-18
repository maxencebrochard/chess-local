"""B. Feuille de cours depuis chaque domaine : bon cours, contenu, diagramme, scroll, fermeture."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from lh import *

def sheet_info(page):
    return page.evaluate("""() => {
      const sheet = document.querySelector('div.fixed.inset-0.z-50')
      if (!sheet) return null
      const panel = sheet.firstElementChild
      const sc = panel.querySelector('.overflow-y-auto')
      const board = sheet.querySelector("[id^='chessboard-']")
      const svgArrows = board ? board.parentElement.querySelectorAll('svg line, svg path, svg polygon, svg marker').length : 0
      const r = panel.getBoundingClientRect()
      return {
        title: sheet.querySelector('h2')?.innerText,
        intro: sc.querySelector('p')?.innerText?.length,
        sections: [...sheet.querySelectorAll('h3')].map(h => h.innerText),
        keyPoints: sheet.querySelectorAll('ul li').length,
        hasBoard: !!board,
        boardBox: board ? board.getBoundingClientRect().toJSON() : null,
        pieces: board ? board.querySelectorAll('[data-piece]').length : 0,
        svgArrows,
        panel: {top: r.top, bottom: r.bottom, h: r.height},
        scroll: {top: sc.scrollTop, h: sc.scrollHeight, client: sc.clientHeight},
        vh: innerHeight,
      }
    }""")

def sheet_open(page):
    return page.locator('div.fixed.inset-0.z-50').count() > 0

results = []
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.add_init_script(RND_INIT)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1500)
    for label, rnd in [("Finales", 0.5), ("Tactiques", 0.18), ("Stratégie", 0.3), ("Ouvertures", 0.1)]:
        page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(800)
        set_rnd(page, rnd)
        start_domain(page, label)
        sess = get_session(page)
        item = sess['session']['items'][0]
        cid = expected_course_id(item)
        exp = COURSES.get(cid)
        print(f"\n=== {label} item={item['kind']} key={item.get('endgame',{}).get('id') or item.get('theme') or item.get('card',{}).get('id') or item.get('line',{}).get('name')} -> cours attendu {cid} = {exp and exp['title']}")
        shot(page, f"s1_{label}_lesson")
        # 1) depuis la leçon
        page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(600)
        info = sheet_info(page)
        print(" feuille(leçon):", json.dumps(info, ensure_ascii=False))
        ok_title = info and exp and info['title'].replace('📚','').strip() == exp['title']
        print("  titre OK:", ok_title, "| sections attendues:", [s['heading'] for s in exp['sections']], "| kp attendus:", len(exp['keyPoints']))
        shot(page, f"s1_{label}_sheet_top")
        # scroll interne par drag tactile
        bg_before = session_scroller_top(page)
        touch_drag(page, 196, 700, 196, 250, steps=12)
        page.wait_for_timeout(400)
        info2 = sheet_info(page)
        print("  après drag: scrollTop feuille", info['scroll']['top'], '->', info2['scroll']['top'], "| fond", bg_before, '->', session_scroller_top(page))
        # scroller tout en bas
        page.evaluate("() => { const sc = document.querySelector('div.fixed.inset-0.z-50 .overflow-y-auto'); sc.scrollTop = sc.scrollHeight }")
        page.wait_for_timeout(300)
        shot(page, f"s1_{label}_sheet_bottom")
        # fermeture bouton bas
        page.locator("div.fixed.inset-0.z-50 button", has_text="Retour à l'exercice").tap(); page.wait_for_timeout(300)
        print("  fermeture 'Retour à l'exercice':", not sheet_open(page), "| leçon visible:", page.get_by_role('button', name="C'est parti").is_visible())
        # réouverture + ✕
        page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(400)
        page.locator("div.fixed.inset-0.z-50 header button").tap(); page.wait_for_timeout(300)
        print("  fermeture ✕:", not sheet_open(page))
        # réouverture + tap fond
        page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(400)
        inf = sheet_info(page)
        print("  panel top:", inf['panel']['top'])
        if inf['panel']['top'] > 12:
            page.touchscreen.tap(196, max(4, inf['panel']['top'] / 2)); page.wait_for_timeout(300)
            print("  fermeture tap fond:", not sheet_open(page))
        else:
            print("  PAS de fond tapable (panel top <= 12px)")
            page.locator("div.fixed.inset-0.z-50 header button").tap(); page.wait_for_timeout(300)
        # 2) depuis l'exercice via ?
        go_play(page)
        page.wait_for_timeout(1500)
        before = board_fen_pieces(page)
        q = page.locator("header button[title='Voir le cours']")
        qb = q.bounding_box(); xb = page.locator("header button", has_text="✕").first.bounding_box()
        print("  bouton ? box:", qb, "| ✕ box:", xb)
        q.tap(); page.wait_for_timeout(500)
        info3 = sheet_info(page)
        print("  feuille(jeu) titre:", info3 and info3['title'])
        shot(page, f"s1_{label}_sheet_play")
        page.locator("div.fixed.inset-0.z-50 header button").tap(); page.wait_for_timeout(300)
        after = board_fen_pieces(page)
        print("  fermeture ✕ (jeu):", not sheet_open(page), "| board identique:", before == after, "| nb pièces", len(after))
        shot(page, f"s1_{label}_play_after_close")
        results.append((label, cid, ok_title))
        page.locator("header button", has_text="✕").first.tap(); page.wait_for_timeout(400)
    print("\nLOGS:", logs)
    browser.close()
