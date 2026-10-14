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


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        scenario(p, browser, 10, 'rapid', list(range(3019, 3009, -1)), list(reversed(MONTHS[1:])))
        scenario(p, browser, 25, 'rapid', list(range(3019, 3009, -1)) + [3000], list(reversed(MONTHS)))
        scenario(p, browser, 10, 'bullet', [], list(reversed(MONTHS)))
    finally:
        browser.close()


ck.run(suite)
