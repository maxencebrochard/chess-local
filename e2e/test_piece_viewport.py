"""Le début d'une partie doit montrer le plateau entier après une configuration défilée."""
from helpers import BASE, Checker, mobile_context, shot

ck = Checker('piece_viewport')


def suite(p):
    browser = p.chromium.launch()
    try:
        for standalone in (False, True):
            ctx = mobile_context(p, browser, ck, standalone=standalone)
            page = ctx.new_page()
            page.goto(f'{BASE}/#/jouer')
            if ck.appears('Configuration', page, 'text=Adversaire'):
                page.get_by_role('button', name='Illimité', exact=True).click()
                page.get_by_role('button', name='Jouer', exact=True).click()
                if ck.appears('Partie lancée', page, '[data-board]'):
                    bounds = page.locator('[data-board]').bounding_box()
                    nav = page.locator('nav[aria-label="Navigation principale"]:visible').bounding_box()
                    ck.check(f'Plateau entier au départ, standalone={standalone}',
                             bounds is not None and nav is not None and bounds['y'] >= 0
                             and bounds['y'] + bounds['height'] <= nav['y'], str(bounds))
                    shot(page, f'plateau_depart_{"852" if standalone else "660"}')
            ctx.close()
    finally:
        browser.close()


ck.run(suite)
