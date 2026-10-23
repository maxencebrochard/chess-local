"""Coordonnées de l'échiquier : chaque lettre et chaque chiffre reste dans son coin, sans toucher l'encre d'une pièce.

L'encre du glyphe vient de `measureText` (boîte réellement peinte, pas la boîte de ligne).
L'encre des pièces vient des pixels opaques du dessin rendu, rastérisé comme dans `test_piece_centers.py`.
Chaque coordonnée est confrontée à la pièce posée sur sa case et aux douze pièces du jeu à la même place :
une case vide aujourd'hui peut porter n'importe quelle pièce demain.
Tous les jeux doivent laisser les coins libres : ceux qui dessinent jusqu'au bord de la case sont réduits au rendu
(`scale` de `src/lib/pieces.ts`).
En cas de contact malgré tout, la pièce doit être peinte au-dessus de la coordonnée, jamais l'inverse.
"""
from helpers import BASE, Checker, desktop_context, mobile_context, shot

ck = Checker("coordinates")

SETS = ['atelier', 'wikimedia', 'celtique', 'chessnut', 'fantasy', 'spatial', 'classique']

# Une marge d'un pixel CSS : un glyphe collé à l'encre se lit comme un chevauchement.
MEASURE = """async () => {
  const MARGIN = 1, N = 256;
  const masks = {};
  const raster = async (drawing) => {
    let img = drawing;
    if (drawing.tagName.toLowerCase() === 'svg') {
      img = new Image();
      const copy = drawing.cloneNode(true); copy.removeAttribute('style');
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(copy));
    }
    await img.decode();
    const c = document.createElement('canvas'); c.width = c.height = N;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0, N, N);
    const d = g.getImageData(0, 0, N, N).data;
    const on = [];
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (d[(y * N + x) * 4 + 3] > 64) on.push([x, y]);
    return on;
  };
  // Dessin de chaque pièce, en fractions de sa case (tous les dessins d'un jeu ont la même boîte).
  const pieces = {};
  for (const el of document.querySelectorAll('[data-square] [data-piece]')) {
    const drawing = el.querySelector('img,svg');
    if (!drawing) continue;
    const s = el.closest('[data-square]').getBoundingClientRect(), r = drawing.getBoundingClientRect();
    const code = el.dataset.piece;
    masks[code] ??= await raster(drawing);
    pieces[el.closest('[data-square]').dataset.square] = code;
    masks[code].box ??= {x: (r.x - s.x) / s.width, y: (r.y - s.y) / s.height, w: r.width / s.width, h: r.height / s.height};
  }
  const glyphs = [];
  for (const span of document.querySelectorAll('[data-square] > span > span')) {
    const text = span.textContent;
    if (!/^[a-h1-8]$/.test(text)) continue;
    const square = span.closest('[data-square]'), s = square.getBoundingClientRect();
    const range = document.createRange(); range.selectNodeContents(span);
    const line = range.getBoundingClientRect();
    const cs = getComputedStyle(span);
    const g = document.createElement('canvas').getContext('2d');
    g.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const m = g.measureText(text);
    const base = line.top + m.fontBoundingBoxAscent;
    const ink = {left: line.left - m.actualBoundingBoxLeft - MARGIN, right: line.left + m.actualBoundingBoxRight + MARGIN,
                 top: base - m.actualBoundingBoxAscent - MARGIN, bottom: base + m.actualBoundingBoxDescent + MARGIN};
    const hits = {};
    for (const [code, on] of Object.entries(masks)) {
      const b = on.box;
      let n = 0;
      for (const [x, y] of on) {
        const px = s.x + (b.x + (x + .5) / N * b.w) * s.width, py = s.y + (b.y + (y + .5) / N * b.h) * s.height;
        if (px >= ink.left && px <= ink.right && py >= ink.top && py <= ink.bottom) n++;
      }
      if (n) hits[code] = n;
    }
    // Ordre de peinture aux pixels communs : la pièce doit recouvrir la coordonnée.
    let above = 0;
    const code = pieces[square.dataset.square], piece = code && masks[code];
    if (piece) {
      const b = piece.box;
      span.parentElement.style.pointerEvents = 'auto';
      for (const [x, y] of piece) {
        const px = s.x + (b.x + (x + .5) / N * b.w) * s.width, py = s.y + (b.y + (y + .5) / N * b.h) * s.height;
        if (px < ink.left + MARGIN || px > ink.right - MARGIN || py < ink.top + MARGIN || py > ink.bottom - MARGIN) continue;
        if (!document.elementFromPoint(px, py)?.closest('[data-piece]')) above++;
      }
      span.parentElement.style.pointerEvents = 'none';
    }
    const inside = ink.left + MARGIN >= s.left && ink.right - MARGIN <= s.right && ink.top + MARGIN >= s.top && ink.bottom - MARGIN <= s.bottom;
    glyphs.push({square: square.dataset.square, text, above, piece: pieces[square.dataset.square] ?? null, hits, inside,
                 size: parseFloat(cs.fontSize), squarePx: Math.round(s.width),
                 ink: [ink.left - s.x, ink.top - s.y, ink.right - s.x, ink.bottom - s.y].map((v) => Math.round(v * 10) / 10)});
  }
  return {glyphs, codes: Object.keys(masks).sort()};
}"""


def rest(page):
    # Mesurer au repos : animation de mise en place terminée, dessins stables pendant 500 ms.
    page.wait_for_function("""() => {
      const now = performance.now();
      const state = JSON.stringify([...document.querySelectorAll('[data-square] [data-piece], [data-square] > span > span')].map(el => {
        const r = el.getBoundingClientRect();
        return [el.textContent, el.dataset?.piece, r.x, r.y, r.width, r.height];
      }));
      if (!window.__coordRest || window.__coordRest.state !== state) {
        window.__coordRest = {state, since: now};
        return false;
      }
      return now - window.__coordRest.since >= 500;
    }""", timeout=15000)
    page.evaluate('delete window.__coordRest')


def measure(page, label, bottom, left, full_set):
    rest(page)
    result = page.evaluate(MEASURE)
    glyphs = result['glyphs']
    seen = {g['text'] for g in glyphs}
    ck.check(f'{label} : seize coordonnées, lettres en bas ({bottom}) et chiffres à gauche ({left})',
             seen == set('abcdefgh12345678') and len(glyphs) == 16
             and all(g['square'][1] == bottom for g in glyphs if g['text'].isalpha())
             and all(g['square'][0] == left for g in glyphs if g['text'].isdigit()),
             str([(g['text'], g['square']) for g in glyphs]))
    if full_set:
        ck.check(f'{label} : les douze pièces du jeu mesurées', len(result['codes']) == 12, str(result['codes']))
    outside = [g for g in glyphs if not g['inside']]
    ck.check(f'{label} : chaque coordonnée tient dans sa case', not outside, str(outside))
    # 13 px fixes couvraient 28 % d'une case d'iPhone : la taille suit la case, bornée à 9 et 15 px.
    bad_size = [(g['text'], g['size'], g['squarePx']) for g in glyphs
                if not (abs(g['size'] - min(15, max(9, g['squarePx'] * .19))) <= .6)]
    ck.check(f'{label} : taille des coordonnées à 19 % de la case (9 à 15 px)', not bad_size, str(bad_size[:4]))
    above = [(g['text'], g['square'], g['piece'], g['above']) for g in glyphs if g['above']]
    ck.check(f'{label} : la pièce est peinte au-dessus de la coordonnée', not above, str(above))
    on_piece = [g for g in glyphs if g['piece'] and g['piece'] in g['hits']]
    any_piece = [g for g in glyphs if g['hits']]
    if any_piece:
        shot(page, 'coordonnees_' + label.replace(' / ', '_').replace(' ', '_').replace('/', '_'))
    ck.check(f'{label} : aucune coordonnée sur la pièce de sa case', not on_piece,
             str([(g['text'], g['square'], g['piece'], g['hits'][g['piece']], g['size'], g['squarePx'], g['ink']) for g in on_piece]))
    ck.check(f'{label} : aucune coordonnée sur l\'une des douze pièces à sa place', not any_piece,
             str([(g['text'], g['square'], g['hits'], g['size'], g['squarePx'], g['ink']) for g in any_piece][:6]))


def positions(page, label):
    """Départ côté blanc (les douze pièces), même position retournée, puis la défense signalée (élève noir)."""
    page.goto(f'{BASE}/#/analyse')
    if ck.appears(f'{label} : analyse', page, '[data-square=e2] [data-piece]'):
        measure(page, f'{label} / blancs en bas', '1', 'a', True)
        page.locator("button[title=\"Retourner l'échiquier\"]:visible, button:visible:has-text('Options')").first.click()
        sheet = page.get_by_role('button', name="⇅ Retourner l'échiquier").filter(visible=True)
        if sheet.count():
            sheet.click()
        if ck.appears(f'{label} : échiquier retourné', page, '[data-square=h8] > span > span:text-is("8")', timeout=5000):
            measure(page, f'{label} / noirs en bas', '8', 'h', True)
    page.goto(f'{BASE}/#/defense/def-0DZDW')
    if ck.appears(f'{label} : défense côté noir', page, '[data-square=h8] [data-piece]'):
        measure(page, f'{label} / défense def-0DZDW', '8', 'h', False)


def suite(p):
    browser = p.chromium.launch()
    try:
        for name in SETS:
            ctx = mobile_context(p, browser, ck, settings={'pieceSet': name})
            page = ctx.new_page()
            positions(page, f'{name} 393x660')
            page.set_viewport_size({'width': 393, 'height': 852})
            positions(page, f'{name} 393x852')
            ctx.close()
            ctx = desktop_context(browser, ck, settings={'pieceSet': name})
            positions(ctx.new_page(), f'{name} 1440x900')
            ctx.close()
    finally:
        browser.close()


ck.run(suite)
