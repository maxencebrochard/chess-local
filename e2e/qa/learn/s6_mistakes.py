"""Mes erreurs (via bilan /analyse), aller-retour Analyser (simple + double), rechargement en séance."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
from s3_tactics_lib import verdict_text
PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"

def state(page):
    s = get_session(page)
    return {'hash': page.evaluate("() => location.hash"), 'header': (page.locator('header h1').first.inner_text().replace('\n', ' ') if page.locator('header h1').count() else None),
            'verdict': verdict_text(page), 'stored': s and {'idx': s['itemIdx'], 'phase': s['phase'], 'results': s['results'], 'scored': s['scoredItems']}}

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.add_init_script(RND_INIT)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    page.locator("main button", has_text="Options").tap(); page.wait_for_timeout(300)
    page.locator("text=Importer PGN ou FEN").tap(); page.wait_for_timeout(200)
    page.fill("textarea", PGN)
    page.locator("button:has-text('Charger')").tap(); page.wait_for_timeout(500)
    page.get_by_role("button", name="★ Bilan").tap()
    page.wait_for_selector("text=Démarrer le bilan", timeout=240000)
    shot(page, "s6_bilan_done")
    ms = db_eval(page, "db.mistakes.toArray()")
    for m in ms: print("  mistake:", m['id'], m['gameLabel'], '|', m['fenBefore'].split(' ')[1], 'joue', m['playedSan'], 'best', m['bestUci'], m['cls'])
    page.locator("header button:has-text('✕')").first.tap(); page.wait_for_timeout(500)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1200)
    shot(page, "s6_home_with_mistakes")
    print("compteur Mes erreurs:", page.locator("button", has_text="Mes erreurs").inner_text().replace('\n', ' '))
    page.locator("button", has_text="Mes erreurs").tap(); page.wait_for_selector("text=C'est parti"); page.wait_for_timeout(300)
    sess = get_session(page)['session']
    print("séance:", [(i['mistake']['id'], i['mistake']['playedSan']) for i in sess['items']], "| ? visible:", page.locator("header button[title='Voir le cours']").count())
    print("leçon:", page.locator('.bg-white').first.inner_text().replace('\n', ' | '))
    shot(page, "s6_mistake_lesson")
    go_play(page)
    print("bandeau:", page.locator("div.rounded.bg-surface-2").first.inner_text().replace('\n', ' '))
    shot(page, "s6_mistake_play")
    m0 = sess['items'][0]['mistake']
    board = chess.Board(m0['fenBefore'])
    # 1) mauvais coup exprès : rejouer le coup fautif d'origine
    bad = board.parse_san(m0['playedSan'])
    play_my_move(page, board, bad, 'tap'); board.pop()
    page.wait_for_timeout(300); print(" pendant vérif:", page.locator("text=Je vérifie").count()); shot(page, "s6_mistake_checking")
    for _ in range(120):
        if verdict_text(page): break
        page.wait_for_timeout(250)
    print(" après coup fautif rejoué:", state(page), "| db:", [(m['id'], m['attempts'], m['solved']) for m in db_eval(page, "db.mistakes.toArray()")])
    shot(page, "s6_mistake_fail")
    # 2) Analyser -> retour (simple)
    page.locator("button", has_text="Analyser").tap(); page.wait_for_timeout(1500)
    print(" sur /analyse:", page.evaluate("() => location.hash"), "| bouton retour:", page.locator("button", has_text="Retour à l'exercice").count()); shot(page, "s6_analyse_1")
    page.locator("button", has_text="Retour à l'exercice").tap(); page.wait_for_timeout(1200)
    print(" retour 1:", state(page)); shot(page, "s6_back_1")
    # 3) double aller-retour
    page.locator("button", has_text="Analyser").tap(); page.wait_for_timeout(1500)
    page.locator("button", has_text="Retour à l'exercice").tap(); page.wait_for_timeout(1200)
    print(" retour 2:", state(page)); shot(page, "s6_back_2")
    # 4) Réessayer après retour, bon coup -> solved ?
    page.locator("button", has_text="Réessayer").tap(); page.wait_for_timeout(500)
    good = chess.Move.from_uci(m0['bestUci'])
    play_my_move(page, board, good, 'drag'); page.wait_for_timeout(1200)
    print(" après bon coup (réessai):", state(page), "| db:", [(m['id'], m['attempts'], m['solved']) for m in db_eval(page, "db.mistakes.toArray()")])
    shot(page, "s6_mistake_retry_ok")
    # 5) item suivant puis RECHARGEMENT en phase play
    page.locator("button", has_text="Suivant").tap(); page.wait_for_timeout(500)
    print(" item 2:", state(page))
    go_play(page)
    page.reload(); page.wait_for_timeout(1500)
    print(" après F5:", state(page), "| accueil visible:", page.get_by_role("button", name="Séance", exact=True).count())
    shot(page, "s6_after_reload")
    # 6) retour navigateur (history.back) depuis /analyse au lieu du bouton
    page.locator("button", has_text="Mes erreurs").tap(); page.wait_for_selector("text=C'est parti"); go_play(page)
    s2 = get_session(page)['session']; mm = s2['items'][0]['mistake']
    b2 = chess.Board(mm['fenBefore']); play_my_move(page, b2, chess.Move.from_uci(mm['bestUci']), 'tap'); page.wait_for_timeout(1000)
    print(" item erreur réussi:", state(page))
    page.locator("button", has_text="Analyser").tap(); page.wait_for_timeout(1200)
    page.go_back(); page.wait_for_timeout(1200)
    print(" après history.back depuis /analyse:", state(page), "| accueil:", page.get_by_role("button", name="Séance", exact=True).count())
    shot(page, "s6_history_back")
    print("sessions:", [(s['domain'], s['itemId'], s['success'], s['ratingAfter']) for s in learn_sessions(page)])
    print("LOGS:", [l[:200] for l in logs])
    browser.close()
