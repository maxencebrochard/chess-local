import json
from pathlib import Path
import sys

from helpers import BASE, LIVE, Checker, mobile_context

if LIVE:
    sys.exit(0)

ck = Checker('insights_archives')
USER = 'insights_archives_qa'
API = f'https://api.chess.com/pub/player/{USER}/games/'
MONTHS = ['2025/07', '2025/08'] + [f'2025/{m:02}' for m in range(9, 13)] + [f'2026/{m:02}' for m in range(1, 10)]


def scenario(p, browser, count, cadence, expected_ids, months):
    tag = f'{cadence}/{count}'
    ctx = mobile_context(p, browser, ck, settings={'chesscomUsername': USER}, standalone=True, service_workers='block')
    calls = []
    ctx.on('request', lambda req: calls.append(req.url) if req.url.startswith(API) else None)
    page = ctx.new_page()
    page.goto(f'{BASE}/#/insights')
    if not ck.appears(f'{tag} configuration', page, '[data-testid=insights-config]'):
        ctx.close()
        return
    page.click(f'[data-testid=tc-{cadence}]')
    page.click(f'[data-testid=count-{count}]')
    page.click('[data-testid=src-local]')
    page.click('[data-testid=insights-run]')
    if ck.appears(f'{tag} résultat', page, '[data-testid=insights-report], [role=alert]', timeout=90000):
        ck.check(f'{tag} archives décroissantes, arrêt sans requête superflue', calls == [API + 'archives'] + [API + m for m in months], str(calls))
        keys = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-insights-v1'))?.lastRun?.keys ?? []")
        ck.check(f'{tag} dernières parties de la cadence, même anciennes', keys == [f'chesscom:{i}' for i in expected_ids], str(keys))
        text = page.locator('main').inner_text().replace('\xa0', ' ')
        if len(expected_ids) < count:
            label = 'rapide' if cadence == 'rapid' else 'bullet'
            ck.check(f'{tag} épuisement explicite', f'{len(expected_ids)} parties de {label} trouvées sur tout ton historique' in text, text[:700])
        else:
            ck.check(f'{tag} aucun faux épuisement', 'sur tout ton historique' not in text)
    ctx.close()


def departure(p, browser):
    ctx = mobile_context(p, browser, ck, settings={'chesscomUsername': USER}, standalone=True, service_workers='block')
    calls, failed, held = [], [], []
    ctx.on('request', lambda req: calls.append(req.url) if req.url.startswith(API) else None)
    ctx.on('requestfailed', lambda req: failed.append(req.url) if req.url.startswith(API) else None)
    first_archive = API + MONTHS[-1]
    ctx.route(first_archive, lambda route: held.append(route))
    fixture = json.loads((Path(__file__).parent / 'fixtures/chesscom.json').read_text())['routes']
    page = ctx.new_page()
    page.goto(f'{BASE}/#/insights')
    if not ck.appears('départ : configuration', page, '[data-testid=insights-config]'):
        ctx.close()
        return
    page.click('[data-testid=tc-rapid]')
    page.click('[data-testid=count-10]')
    page.click('[data-testid=src-local]')
    with page.expect_request(first_archive):
        page.click('[data-testid=insights-run]')
    page.wait_for_timeout(100)
    page.locator("nav a[data-nav-tab]", has_text="Plus").locator('visible=true').click()
    page.locator("main a[data-plus='statistiques']").click()
    if not ck.appears('départ : Stats affiché', page, "main :text('Statistiques')"):
        ctx.close()
        return
    before = list(calls)
    page.wait_for_timeout(300)
    ck.check('départ : requête en cours annulée et aucune nouvelle requête', failed == [first_archive] and calls == before, str((failed, calls)))
    page.goto(f'{BASE}/#/insights')
    if not ck.appears('retour : configuration', page, '[data-testid=insights-config]'):
        ctx.close()
        return
    page.click('[data-testid=tc-rapid]')
    page.click('[data-testid=count-10]')
    page.click('[data-testid=src-local]')
    with page.expect_request(first_archive):
        page.click('[data-testid=insights-run]')
    page.wait_for_timeout(100)
    if ck.check('retour : deux requêtes interceptées', len(held) == 2, str(len(held))):
        before = list(calls)
        held[0].fulfill(status=200, content_type='application/json', body=json.dumps(fixture[first_archive]['body']))
        page.wait_for_timeout(500)
        ck.check('retour : ancienne collecte arrêtée malgré la réponse tardive', calls == before, str(calls))
        held[1].fulfill(status=200, content_type='application/json', body=json.dumps(fixture[first_archive]['body']))
        if ck.appears('retour : nouveau rapport', page, '[data-testid=insights-report]', timeout=90000):
            expected = [API + 'archives', first_archive, API + 'archives'] + [API + m for m in reversed(MONTHS[1:])]
            ck.check('retour : une seule collecte complète, sans doublons', calls == expected, str(calls))
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        departure(p, browser)
        scenario(p, browser, 10, 'rapid', list(range(3019, 3009, -1)), list(reversed(MONTHS[1:])))
        scenario(p, browser, 25, 'rapid', list(range(3019, 3009, -1)) + [3000], list(reversed(MONTHS)))
        scenario(p, browser, 10, 'bullet', [], list(reversed(MONTHS)))
    finally:
        browser.close()


ck.run(suite)
