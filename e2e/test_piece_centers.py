"""Centre des pixels peints, et non seulement de la boîte CSS, au repos."""
import subprocess
import sys

from helpers import BASE, Checker, mobile_context, shot

ck = Checker("piece_centers")

CENTERS = """async () => {
  const result = [];
  for (const el of document.querySelectorAll('[data-square] [data-piece]')) {
    const drawing = el.querySelector('img,svg');
    if (!drawing) continue;
    const square = el.closest('[data-square]');
    const s = square.getBoundingClientRect(), r = drawing.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    let img = drawing;
    if (drawing.tagName.toLowerCase() === 'svg') {
      img = new Image();
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString((() => { const copy = drawing.cloneNode(true); copy.removeAttribute('style'); return copy; })()));
    }
    await img.decode();
    const c = document.createElement('canvas'); c.width = c.height = 512;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0, 512, 512);
    const d = g.getImageData(0, 0, 512, 512).data;
    let x0=512,y0=512,x1=-1,y1=-1;
    for(let y=0;y<512;y++) for(let x=0;x<512;x++) if(d[(y*512+x)*4+3]>127) {
      x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
    }
    result.push({square:square.dataset.square,code:el.dataset.piece,
      dx:(r.x+(x0+x1+1)/1024*r.width-s.x-s.width/2)/s.width,
      dy:(r.y+(y0+y1+1)/1024*r.height-s.y-s.height/2)/s.height,
      boxDx:(box.x+box.width/2-s.x-s.width/2)/s.width,
      boxDy:(box.y+box.height/2-s.y-s.height/2)/s.height,
      painted:x1>=x0, lift:getComputedStyle(el.querySelector('.board-piece')).transform});
  }
  return result;
}"""


def measure(page, label):
    # L'amorce des puzzles peut commencer après 700 ms. Mesurer au repos exige
    # que les pièces ET leurs positions restent stables au-delà de cette amorce.
    page.wait_for_function("""() => {
      const now = performance.now();
      const state = JSON.stringify([...document.querySelectorAll('[data-square] [data-piece]')].map(el => {
        const r = el.getBoundingClientRect();
        return [el.closest('[data-square]').dataset.square, el.dataset.piece, r.x, r.y, r.width, r.height];
      }));
      if (!window.__centerRest || window.__centerRest.state !== state) {
        window.__centerRest = {state, since: now};
        return false;
      }
      return now - window.__centerRest.since >= 1000;
    }""", timeout=15000)
    page.evaluate('delete window.__centerRest')
    values = page.evaluate(CENTERS)
    bad = [v for v in values if not v['painted'] or max(abs(v['dx']), abs(v['dy']), abs(v['boxDx']), abs(v['boxDy'])) > .02]
    if bad:
        shot(page, 'centrage_echec_' + label.replace('/', '_').replace(' ', '_'))
    ck.check(label + ' : pixels centrés à ±2 %', bool(values) and not bad, str(bad))
    return values


def suite(p):
    result = subprocess.run([sys.executable, 'scripts/center-pieces.py', '--check'], capture_output=True, text=True)
    ck.check('Marges générées à jour', result.returncode == 0, result.stdout + result.stderr)
    browser = p.chromium.launch()
    try:
        for name in ['wikimedia', 'atelier', 'celtique', 'chessnut', 'fantasy', 'spatial', 'classique']:
            ctx = mobile_context(p, browser, ck, standalone=True, settings={'pieceSet': name})
            page = ctx.new_page()
            page.goto(f'{BASE}/#/analyse')
            if ck.appears(name + ' : plateau', page, '[data-square=e2] [data-piece]'):
                measure(page, name)
                shot(page, 'centres_' + name)
            for route in ['attaque/att-05ejA', 'defense/def-0DZDW', 'finales/kp-square',
                          'apprendre/finales/mat-deux-tours', 'apprendre/roque/grec-schema',
                          'puzzles', 'mats?d=chrono-krr']:
                page.goto(f'{BASE}/#/{route}')
                if ck.appears(name + ' : ' + route, page, '[data-square] [data-piece]'):
                    measure(page, name + ' / ' + route)
                    if name == 'atelier':
                        shot(page, 'centres_atelier_' + route.replace('/', '_').replace('?', '_'))
            for route, button in [('rush', 'Survie'), ('apprendre', 'Tactiques'),
                                  ('mats?d=chrono-krr', 'Commencer'), ('mats?d=mate-1', 'Commencer')]:
                page.goto(f'{BASE}/#/{route}')
                selector = f'main button:has-text("{button}")'
                if ck.appears(name + ' : lancement ' + route, page, selector):
                    page.locator(selector).first.click()
                    if route == 'apprendre' and ck.appears(name + ' : leçon', page, "button:has-text(\"C'est parti\")"):
                        page.get_by_role('button', name="C'est parti").click()
                    if ck.appears(name + ' : exercice ' + route, page, '[data-square] [data-piece]'):
                        measure(page, name + ' / ' + route)
            page.goto(f'{BASE}/#/jouer')
            if ck.appears(name + ' : configuration Jouer', page, 'text=Adversaire'):
                page.get_by_role('button', name='Illimité', exact=True).click()
                page.get_by_role('button', name='Jouer', exact=True).click()
                if ck.appears(name + ' : Jouer', page, '[data-square] [data-piece]'):
                    measure(page, name + ' / Jouer')
            page.goto(f'{BASE}/#/ouvertures')
            if ck.appears(name + ' : ouvertures', page, "main button:has-text('Partie écossaise')"):
                page.locator('main button', has_text='Partie écossaise').first.click()
                if ck.appears(name + ' : variante', page, '[data-variant]'):
                    page.locator('[data-variant]').first.click()
                    if ck.appears(name + ' : drill', page, '[data-square] [data-piece]'):
                        measure(page, name + ' / ouvertures')
            # Positions des suites diagnostic_attaque et defense, dans le profil isolé du test.
            page.evaluate("""() => new Promise((resolve, reject) => {
              const request = indexedDB.open('chess-local');
              request.onerror = () => reject(request.error);
              request.onsuccess = () => {
                const db = request.result;
                const tx = db.transaction('mistakes', 'readwrite');
                const date = new Date(); date.setDate(date.getDate()-3); date.setHours(12,0,0,0);
                const common = {date:+date, gameLabel:'Centrage', gameKey:'game:centres', cls:'blunder', attempts:0, solved:0};
                tx.objectStore('mistakes').put({...common,id:901,color:'w',
                  fenBefore:'r1bq1rk1/pp2bppp/2n1p3/3pP3/3P4/2NB1N2/PP3PPP/R2QK2R w KQ - 0 10',playedSan:'a3',bestUci:'d3h7'});
                tx.objectStore('mistakes').put({...common,id:902,color:'b',
                  fenBefore:'r1bq1rk1/pp3pp1/2n1p2p/3pP1NQ/3P4/2NB4/PP3PPP/R3K2R b KQ - 0 1',playedSan:'Nb4',bestUci:'d8g5'});
                tx.oncomplete = () => {db.close();resolve()};
                tx.onerror = () => {db.close();reject(tx.error)};
              };
            })""")
            for route in ['attaques-manquees/901', 'defenses-ratees/902', 'revision']:
                page.goto(f'{BASE}/#/{route}')
                if ck.appears(name + ' : ' + route, page, '[data-square] [data-piece]'):
                    measure(page, name + ' / ' + route)
            page.goto(f'{BASE}/#/analyse')
            if ck.appears(name + ' : options analyse', page, "button:has-text('Options')"):
                page.locator("button:visible", has_text='Options').click()
                page.get_by_role('button', name='♟ Jouer contre le moteur depuis ici', exact=True).filter(visible=True).click()
                if ck.appears(name + ' : analyse/jouer', page, '[data-square] [data-piece]'):
                    measure(page, name + ' / analyse/jouer')
            page.goto(f'{BASE}/#/analyse')
            if ck.appears(name + ' : petit écran', page, '[data-square=e2] [data-piece]'):
                page.set_viewport_size({'width': 393, 'height': 660})
                measure(page, name + ' / 393x660')
                if name == 'atelier':
                    shot(page, 'centres_atelier_660')
            ctx.close()
    finally:
        browser.close()

ck.run(suite)
